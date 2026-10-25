"""Page 12 (AI Agent, Mailbox & SLA Settings): real connection tests, and the agent using the saved values.

- `POST /api/v1/settings/test-smtp` opens a real SMTP session (connect, EHLO, STARTTLS, login) and
  reports the step that failed. Exercised against an in-process SMTP server, so no network is needed.
- `POST /api/v1/settings/test-vllm` calls `GET /v1/models` and checks the configured model is served.
- Outbound mail, vLLM calls, diagnostics and the loop guard read the saved settings, not `.env`.
"""

from __future__ import annotations

import base64
import json
import socket
import socketserver
import threading
from collections.abc import Generator, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.agent import vllm_client
from app.agent.vllm_client import VllmCallOptions, guided_json, set_vllm_override
from app.agent.workflow import ingest_and_triage_eml
from app.auth.service import ensure_initial_admin
from app.common.config import get_settings
from app.common.contracts import IspResponseAnalysis
from app.common.database import Base, get_db
from app.diagnostics import service as diag_service
from app.diagnostics.base import DualPingTracerouteRequest
from app.directory.seeder import seed_branches_from_excel
from app.email_engine import smtp_sender
from app.email_engine.parser import build_synthetic_eml_bytes
from app.email_engine.smtp_sender import dispatch_outbound_email
from app.main import app
from app.ticketing.schemas import SystemSettingsUpdateRequest
from app.ticketing.service import ensure_system_settings

# ==============================================================================
# In-process SMTP server
# ==============================================================================


@dataclass
class FakeSmtpServer:
    host: str
    port: int
    require_auth: bool
    credentials: tuple[str, str] | None
    messages: list[dict[str, Any]] = field(default_factory=list)


def _make_handler(state: FakeSmtpServer) -> type[socketserver.StreamRequestHandler]:
    class _Handler(socketserver.StreamRequestHandler):
        def _send(self, line: str) -> None:
            self.wfile.write(f"{line}\r\n".encode())

        def handle(self) -> None:
            self._send("220 fake.kazyon.test ESMTP ready")
            mail_from = ""
            rcpts: list[str] = []
            authed = False
            while True:
                raw = self.rfile.readline()
                if not raw:
                    return
                line = raw.decode().rstrip("\r\n")
                verb = line.split(" ", 1)[0].upper()
                if verb in {"EHLO", "HELO"}:
                    self._send("250-fake.kazyon.test greets you")
                    if state.credentials is not None:
                        self._send("250-AUTH PLAIN")
                    self._send("250 SIZE 10240000")
                elif verb == "AUTH":
                    parts = line.split(" ")
                    decoded = base64.b64decode(parts[2]).decode() if len(parts) > 2 else ""
                    _, user, password = (decoded.split("\x00") + ["", "", ""])[:3]
                    if state.credentials == (user, password):
                        authed = True
                        self._send("235 2.7.0 Authentication successful")
                    else:
                        self._send("535 5.7.8 Authentication credentials invalid")
                elif verb == "MAIL":
                    if state.require_auth and not authed:
                        self._send("530 5.7.0 Authentication required")
                        continue
                    mail_from = line.split(":", 1)[1].split()[0].strip("<>")
                    rcpts = []
                    self._send("250 OK")
                elif verb == "RCPT":
                    rcpts.append(line.split(":", 1)[1].split()[0].strip("<>"))
                    self._send("250 OK")
                elif verb == "DATA":
                    self._send("354 End data with <CR><LF>.<CR><LF>")
                    body_lines: list[str] = []
                    while True:
                        data_line = self.rfile.readline().decode().rstrip("\r\n")
                        if data_line == ".":
                            break
                        body_lines.append(data_line)
                    state.messages.append(
                        {"from": mail_from, "rcpts": rcpts, "data": "\n".join(body_lines)}
                    )
                    self._send("250 OK queued")
                elif verb in {"NOOP", "RSET"}:
                    self._send("250 OK")
                elif verb == "QUIT":
                    self._send("221 Bye")
                    return
                else:
                    self._send("502 Command not implemented")

    return _Handler


@pytest.fixture()
def smtp_server_factory() -> Iterator[Any]:
    servers: list[socketserver.ThreadingTCPServer] = []

    def _start(
        *, credentials: tuple[str, str] | None = None, require_auth: bool = False
    ) -> FakeSmtpServer:
        state = FakeSmtpServer("127.0.0.1", 0, require_auth, credentials)
        server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _make_handler(state))
        server.daemon_threads = True
        state.port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return state

    yield _start
    for server in servers:
        server.shutdown()
        server.server_close()


def _closed_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ==============================================================================
# App fixtures
# ==============================================================================


@pytest.fixture()
def session_factory(tmp_path: Path) -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / f'settings_{uuid4().hex}.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    with factory() as session:
        ensure_initial_admin(session)
    yield factory
    engine.dispose()


@pytest.fixture()
def db_session(session_factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        settings = get_settings()
        token = test_client.post(
            "/api/v1/auth/login",
            json={
                "username_or_email": settings.admin_username,
                "password": settings.admin_password,
            },
        ).json()["access_token"]
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()


def _save(db: Session, **values: Any) -> None:
    row = ensure_system_settings(db)
    for key, value in values.items():
        setattr(row, key, value)
    db.commit()


@pytest.fixture()
def smtp_login(monkeypatch: pytest.MonkeyPatch) -> tuple[str, str]:
    monkeypatch.setenv("SMTP_USERNAME", "agent@kazyon.com")
    monkeypatch.setenv("SMTP_PASSWORD", "relay-secret")
    get_settings.cache_clear()
    return ("agent@kazyon.com", "relay-secret")


# ==============================================================================
# SMTP connection test
# ==============================================================================


def test_smtp_test_succeeds_against_unauthenticated_relay(
    client: TestClient, smtp_server_factory: Any
) -> None:
    server = smtp_server_factory()
    resp = client.post(
        "/api/v1/settings/test-smtp",
        json={"smtp_host": server.host, "smtp_port": server.port, "smtp_security": "none"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["stage"] == "done"
    assert body["authenticated"] is False
    assert body["credentials_configured"] is False
    assert "fake.kazyon.test" in body["server_banner"]
    assert server.messages == []  # a test never sends mail


def test_smtp_test_authenticates_with_env_login(
    client: TestClient, smtp_server_factory: Any, smtp_login: tuple[str, str]
) -> None:
    server = smtp_server_factory(credentials=smtp_login, require_auth=True)
    body = client.post(
        "/api/v1/settings/test-smtp",
        json={"smtp_host": server.host, "smtp_port": server.port, "smtp_security": "none"},
    ).json()
    assert body["ok"] is True
    assert body["authenticated"] is True


def test_smtp_test_reports_rejected_login(
    client: TestClient, smtp_server_factory: Any, smtp_login: tuple[str, str]
) -> None:
    server = smtp_server_factory(credentials=("agent@kazyon.com", "other-password"))
    body = client.post(
        "/api/v1/settings/test-smtp",
        json={"smtp_host": server.host, "smtp_port": server.port, "smtp_security": "none"},
    ).json()
    assert body["ok"] is False
    assert body["stage"] == "auth"
    assert "535" in body["error"]
    assert "relay-secret" not in json.dumps(body)


@pytest.mark.parametrize(
    ("payload", "stage"),
    [
        (
            {"smtp_host": "127.0.0.1", "smtp_port": _closed_port(), "smtp_security": "none"},
            "connect",
        ),
        ({"smtp_host": "", "smtp_port": 25, "smtp_security": "none"}, "config"),
    ],
)
def test_smtp_test_reports_connection_failures(
    client: TestClient, payload: dict[str, Any], stage: str
) -> None:
    body = client.post("/api/v1/settings/test-smtp", json=payload).json()
    assert body["ok"] is False
    assert body["stage"] == stage
    assert body["error"]


def test_smtp_test_fails_when_server_needs_login_but_none_configured(
    client: TestClient, smtp_server_factory: Any
) -> None:
    # Like Office 365: connecting works, but MAIL FROM is refused until the client logs in
    server = smtp_server_factory(require_auth=True)
    body = client.post(
        "/api/v1/settings/test-smtp",
        json={"smtp_host": server.host, "smtp_port": server.port, "smtp_security": "none"},
    ).json()
    assert body["ok"] is False
    assert body["stage"] == "sender"
    assert "530" in body["error"]
    assert server.messages == []


def test_smtp_test_reports_missing_starttls(client: TestClient, smtp_server_factory: Any) -> None:
    server = smtp_server_factory()
    body = client.post(
        "/api/v1/settings/test-smtp",
        json={"smtp_host": server.host, "smtp_port": server.port, "smtp_security": "starttls"},
    ).json()
    assert body["ok"] is False
    assert body["stage"] == "tls"


def test_smtp_test_uses_saved_settings_when_form_values_omitted(
    client: TestClient, db_session: Session, smtp_server_factory: Any
) -> None:
    server = smtp_server_factory()
    _save(db_session, smtp_host=server.host, smtp_port=server.port, smtp_security="none")
    body = client.post("/api/v1/settings/test-smtp", json={}).json()
    assert body["ok"] is True
    assert (body["host"], body["port"]) == (server.host, server.port)


def test_settings_endpoints_require_login(client: TestClient) -> None:
    del client.headers["Authorization"]
    assert client.post("/api/v1/settings/test-smtp", json={}).status_code == 401
    assert client.post("/api/v1/settings/test-vllm", json={}).status_code == 401


# ==============================================================================
# Outbound mail uses the saved SMTP settings
# ==============================================================================


@pytest.mark.asyncio
async def test_outbound_mail_goes_through_saved_relay_with_saved_sender(
    db_session: Session, smtp_server_factory: Any
) -> None:
    server = smtp_server_factory()
    _save(
        db_session,
        smtp_host=server.host,
        smtp_port=server.port,
        smtp_security="none",
        smtp_enabled=True,
        mailbox_account="netops-agent@kazyon.com",
    )

    row = await dispatch_outbound_email(
        db_session,
        ticket=None,
        thread_type="HUMAN_ESCALATION",
        recipients=["noc-oncall@kazyon.com"],
        subject="relay check",
        body_text="hello",
        in_reply_to="<relay-check@x>",
    )

    assert row.ai_analysis_json["smtp_live_sent"] is True
    assert row.sender == "netops-agent@kazyon.com"
    assert len(server.messages) == 1
    assert server.messages[0]["from"] == "netops-agent@kazyon.com"
    assert server.messages[0]["rcpts"] == ["noc-oncall@kazyon.com"]


@pytest.mark.asyncio
async def test_outbound_mail_not_sent_while_delivery_disabled(
    db_session: Session, smtp_server_factory: Any
) -> None:
    server = smtp_server_factory()
    _save(db_session, smtp_host=server.host, smtp_port=server.port, smtp_security="none")

    row = await dispatch_outbound_email(
        db_session,
        ticket=None,
        thread_type="HUMAN_ESCALATION",
        recipients=["noc-oncall@kazyon.com"],
        subject="disabled",
        body_text="hello",
        in_reply_to="<disabled@x>",
    )

    assert row.ai_analysis_json["smtp_live_sent"] is False
    assert row.ai_analysis_json["smtp_delivery_disabled"] is True
    assert server.messages == []


@pytest.mark.asyncio
async def test_loop_guard_uses_saved_per_hour_limit(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int | None] = []

    def _record(key: str, max_per_hour: int | None = None) -> bool:
        seen.append(max_per_hour)
        return True

    monkeypatch.setattr(smtp_sender, "check_and_increment_outbound_allowance", _record)
    _save(db_session, max_outbound_emails_per_ticket_hour=11)
    await dispatch_outbound_email(
        db_session,
        ticket=None,
        thread_type="HUMAN_ESCALATION",
        recipients=["noc-oncall@kazyon.com"],
        subject="limit",
        body_text="limit",
        in_reply_to="<limit@x>",
    )
    assert seen == [11]


# ==============================================================================
# vLLM connection test and saved endpoint
# ==============================================================================


@pytest.fixture()
def mock_vllm() -> Iterator[Any]:
    """Register a mocked vLLM server for a base URL; records every request it receives."""
    requests: list[httpx.Request] = []

    def _install(base_url: str, handler: Any) -> list[httpx.Request]:
        def _recording(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            response: httpx.Response = handler(request)
            return response

        key = vllm_client.normalize_vllm_base_url(base_url)
        vllm_client._http_clients[key] = httpx.AsyncClient(
            base_url=key, transport=httpx.MockTransport(_recording)
        )
        return requests

    yield _install
    vllm_client._http_clients.clear()


def _models_response(*model_ids: str) -> httpx.Response:
    return httpx.Response(200, json={"data": [{"id": m} for m in model_ids]})


def test_vllm_test_ok_when_configured_model_is_served(client: TestClient, mock_vllm: Any) -> None:
    model = get_settings().default_worker_model
    requests = mock_vllm("http://vllm-a.test:8002", lambda r: _models_response(model))
    body = client.post(
        "/api/v1/settings/test-vllm", json={"vllm_endpoint": "http://vllm-a.test:8002/v1"}
    ).json()
    assert body["ok"] is True
    assert body["model_available"] is True
    assert body["endpoint"] == "http://vllm-a.test:8002"
    assert str(requests[0].url) == "http://vllm-a.test:8002/v1/models"


def test_vllm_test_fails_when_model_missing(client: TestClient, mock_vllm: Any) -> None:
    mock_vllm("http://vllm-b.test:8002", lambda r: _models_response("some/other-model"))
    body = client.post(
        "/api/v1/settings/test-vllm", json={"vllm_endpoint": "http://vllm-b.test:8002/v1"}
    ).json()
    assert body["ok"] is False
    assert body["available_models"] == ["some/other-model"]
    assert "does not serve" in body["error"]


def test_vllm_test_reports_http_error(client: TestClient, mock_vllm: Any) -> None:
    mock_vllm("http://vllm-c.test:8002", lambda r: httpx.Response(503, text="loading"))
    body = client.post(
        "/api/v1/settings/test-vllm", json={"vllm_endpoint": "http://vllm-c.test:8002"}
    ).json()
    assert body["ok"] is False
    assert "HTTP 503" in body["error"]


def test_vllm_test_reports_unreachable_server(client: TestClient) -> None:
    body = client.post(
        "/api/v1/settings/test-vllm",
        json={"vllm_endpoint": f"http://127.0.0.1:{_closed_port()}/v1"},
    ).json()
    assert body["ok"] is False
    assert body["error"]


def test_vllm_test_rejects_malformed_endpoint(client: TestClient) -> None:
    resp = client.post("/api/v1/settings/test-vllm", json={"vllm_endpoint": "10.100.109.9:8002"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_guided_json_sends_saved_endpoint_temperature_and_tokens(mock_vllm: Any) -> None:
    set_vllm_override(None)
    answer = {
        "intent": "ISP_WELCOME",
        "isp_ticket_number": "244010",
        "summary": "Ticket opened",
        "confidence": 0.95,
    }
    requests = mock_vllm(
        "http://vllm-d.test:8002",
        lambda r: httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(answer)}}]}
        ),
    )

    result = await guided_json(
        [{"role": "user", "content": "hi"}],
        IspResponseAnalysis,
        options=VllmCallOptions(
            base_url="http://vllm-d.test:8002/v1", temperature=0.05, max_tokens=777
        ),
    )

    assert result.intent == "ISP_WELCOME"
    assert str(requests[0].url) == "http://vllm-d.test:8002/v1/chat/completions"
    sent = json.loads(requests[0].content)
    assert (sent["temperature"], sent["max_tokens"]) == (0.05, 777)


@pytest.mark.asyncio
async def test_agent_classifies_through_saved_vllm_endpoint(
    db_session: Session, mock_vllm: Any
) -> None:
    seed_branches_from_excel(db_session, dry_run=False)
    _save(
        db_session,
        vllm_endpoint="http://vllm-e.test:8002/v1",
        vllm_temperature=0.3,
        vllm_max_tokens=512,
    )
    set_vllm_override(None)
    requests = mock_vllm(
        "http://vllm-e.test:8002", lambda r: httpx.Response(503, text="down for test")
    )

    result = await ingest_and_triage_eml(
        db_session,
        build_synthetic_eml_bytes(
            sender="GITSupport@kazyon.com",
            recipients=["itsupport-agent@kazyon.com"],
            subject="Store 2009 down",
            body_text="Store 2009 is offline. Site contact: 010 1111 2222",
            message_id=f"<saved-endpoint-{uuid4().hex}@kazyon.com>",
        ),
    )

    assert result["action"] == "DEFERRED_LLM_RETRY"
    assert requests, "the agent never called the saved vLLM endpoint"
    assert {r.url.host for r in requests} == {"vllm-e.test"}
    sent = json.loads(requests[0].content)
    assert (sent["temperature"], sent["max_tokens"]) == (0.3, 512)


# ==============================================================================
# Diagnostics use the saved timeout / ping count / max hops
# ==============================================================================


@pytest.mark.asyncio
async def test_diagnostics_use_saved_ping_count_hops_and_timeout(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_branches_from_excel(db_session, dry_run=False)
    _save(db_session, ping_count=2, traceroute_max_hops=9, diagnostic_timeout_sec=7)
    captured: dict[str, Any] = {}
    real = diag_service.execute_dual_ping_and_traceroute

    async def _capture(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        result: dict[str, Any] = await real(**kwargs)
        return result

    monkeypatch.setattr(diag_service, "execute_dual_ping_and_traceroute", _capture)
    await diag_service.run_and_persist_diagnostics(
        db_session, DualPingTracerouteRequest(branch_code="2009", simulate_scenario="PASS")
    )
    assert (captured["ping_count"], captured["traceroute_max_hops"], captured["timeout_sec"]) == (
        2,
        9,
        7,
    )

    await diag_service.run_and_persist_diagnostics(
        db_session,
        DualPingTracerouteRequest(branch_code="2009", simulate_scenario="PASS", ping_count=5),
    )
    assert captured["ping_count"] == 5  # an explicit request value still wins


# ==============================================================================
# Settings validation
# ==============================================================================


@pytest.mark.parametrize(
    "bad",
    [
        {"smtp_security": "tls"},
        {"smtp_port": 70000},
        {"vllm_endpoint": "ftp://x"},
        {"diagnostic_timeout_sec": 0},
        {"vllm_temperature": 5},
    ],
)
def test_settings_update_rejects_invalid_values(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SystemSettingsUpdateRequest(**bad)


def test_settings_update_saves_and_reports_credentials_flag(
    client: TestClient, smtp_login: tuple[str, str]
) -> None:
    resp = client.put(
        "/api/v1/settings",
        json={
            "smtp_host": " relay.kazyon.local ",
            "smtp_port": 25,
            "smtp_security": "none",
            "smtp_enabled": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert (body["smtp_host"], body["smtp_port"], body["smtp_security"]) == (
        "relay.kazyon.local",
        25,
        "none",
    )
    assert body["smtp_enabled"] is True
    assert body["smtp_credentials_configured"] is True
    assert "relay-secret" not in resp.text

    assert client.put("/api/v1/settings", json={"smtp_security": "tls"}).status_code == 422


def test_encrypted_smtp_credentials_saved_and_never_leaked(
    client: TestClient, db_session: Session
) -> None:
    from app.common.crypto import decrypt_secret

    secret_pw = "smtp-test-secret-pw-1234"
    resp = client.put(
        "/api/v1/settings",
        json={
            "mailbox_account": "noc@kazyon.com",
            "smtp_host": "mail.kazyon.com",
            "smtp_port": 587,
            "smtp_security": "starttls",
            "smtp_enabled": True,
            "smtp_username": "noc@kazyon.com",
            "smtp_password": secret_pw,
            "test_redirect_email": "sandbox@kazyon.com",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mailbox_account"] == "noc@kazyon.com"
    assert body["smtp_host"] == "mail.kazyon.com"
    assert body["smtp_port"] == 587
    assert body["smtp_security"] == "starttls"
    assert body["smtp_username"] == "noc@kazyon.com"
    assert body["smtp_credentials_configured"] is True
    assert body["test_redirect_email"] == "sandbox@kazyon.com"
    assert secret_pw not in resp.text

    db_session.expire_all()
    row = ensure_system_settings(db_session)
    assert row.smtp_password_encrypted != secret_pw
    assert row.smtp_password_encrypted.startswith("gAAAAA")
    assert decrypt_secret(row.smtp_password_encrypted) == secret_pw


@pytest.mark.asyncio
async def test_outbound_mail_safe_redirect_routes_isp_escalation_to_test_redirect_email(
    db_session: Session, smtp_server_factory: Any
) -> None:
    server = smtp_server_factory()
    _save(
        db_session,
        smtp_host=server.host,
        smtp_port=server.port,
        smtp_security="none",
        smtp_enabled=True,
        mailbox_account="noc@kazyon.com",
        test_redirect_email="sandbox@kazyon.com",
    )

    row = await dispatch_outbound_email(
        db_session,
        ticket=None,
        thread_type="ISP",
        recipients=["noc@noor.net"],
        cc=["ITInfrastructure@kazyon.com"],
        subject="store 1084",
        body_text="Dear NOC\nKindly check connection store 1084",
        in_reply_to="<isp-redirect-test@x>",
        classification_label="NOOR_ESCALATION",
    )

    assert row.recipients == ["noc@noor.net"]
    assert row.ai_analysis_json["smtp_live_sent"] is True
    assert row.ai_analysis_json["test_redirected_to"] == "sandbox@kazyon.com"
    assert len(server.messages) == 1
    assert server.messages[0]["rcpts"] == ["sandbox@kazyon.com"]
    assert "X-Kz-Original-To: noc@noor.net" in server.messages[0]["data"]
    assert "[KAZYON SANDBOX REDIRECT — Thread: ISP" in server.messages[0]["data"]


def test_role_play_isp_reply_and_sandbox_stage_trace(
    client: TestClient, db_session: Session
) -> None:
    seed_branches_from_excel(db_session, dry_run=False)

    # Step 1: Trigger initial branch incident in the sandbox
    step1 = client.post(
        "/api/v1/emails/trigger",
        json={"scenario": "BRANCH_INCIDENT", "branch_code": "2009"},
    )
    assert step1.status_code == 200
    s1 = step1.json()
    assert s1["ticket_number"].startswith("NET-")
    assert len(s1["stage_trace"]) == 6
    assert s1["stage_trace"][0]["name"] == "MIME & Thread Correlation"
    assert any(nxt["scenario"] == "ISP_WELCOME" for nxt in s1["suggested_next_steps"])

    isp_outbound = next(o for o in s1["outbound_emails"] if o["thread_type"] == "ISP")

    # Step 2: Operator replies from their personal @gmail.com address to the redirected ISP email
    step2 = client.post(
        "/api/v1/emails/trigger",
        json={
            "scenario": "CUSTOM",
            "ticket_number": s1["ticket_number"],
            "branch_code": "2009",
            "sender": "my-sandbox@gmail.com",
            "in_reply_to": isp_outbound["message_id"],
            "subject": "Re: store 2009",
            "body_text": "Dear Kazyon Team, we opened trouble ticket #244010 for store 2009 and are investigating.",
        },
    )
    assert step2.status_code == 200
    s2 = step2.json()
    assert s2["trigger_type"] == "ISP_REPLY"
    assert s2["classification_label"] == "ISP_WELCOME"
    assert s2["isp_reference_number"] == "244010"
