"""Inbound SMTP listener: the mail server forwards branch / ISP mail straight to the agent.

Driven with a real SMTP client (`smtplib`) and raw sockets against a listener on 127.0.0.1.
"""

from __future__ import annotations

import asyncio
import email.policy
import smtplib
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Generator
from email.message import EmailMessage
from ipaddress import ip_network
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.agent import scheduler
from app.auth.service import ensure_initial_admin
from app.common.config import Settings, get_settings
from app.common.database import Base
from app.directory.seeder import seed_branches_from_excel
from app.email_engine import imap_poller, smtp_listener
from app.email_engine.smtp_listener import InboundSmtpListener
from app.ticketing.models import Ticket, TicketEmail
from app.ticketing.service import ensure_system_settings

AGENT = "itsupport-agent@kazyon.com"
StartListener = Callable[..., Awaitable[InboundSmtpListener]]


@pytest.fixture()
def dropbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the shared inbound dropbox at a temp dir (listener writes, poller reads)."""
    monkeypatch.setattr(imap_poller, "_IMPORTS_DIR", tmp_path / "imports")
    return tmp_path / "imports" / "inbox"


@pytest_asyncio.fixture()
async def start_listener(dropbox: Path) -> AsyncIterator[StartListener]:
    started: list[InboundSmtpListener] = []

    async def _start(
        *,
        allowed: str = "127.0.0.1/32",
        recipients: set[str] | None = None,
        max_bytes: int = 1024 * 1024,
        on_stored: Callable[[], None] | None = None,
    ) -> InboundSmtpListener:
        async def _resolve() -> set[str]:
            return recipients if recipients is not None else {AGENT}

        listener = InboundSmtpListener(
            host="127.0.0.1",
            port=0,
            allowed_networks=[ip_network(a.strip()) for a in allowed.split(",")],
            resolve_recipients=_resolve,
            max_message_bytes=max_bytes,
            hostname="agent.test",
            on_message_stored=on_stored,
        )
        await listener.start()
        started.append(listener)
        return listener

    yield _start
    for listener in started:
        await listener.stop()


def _message(subject: str = "Store 2009 down", body: str = "Store 2009 is offline.") -> bytes:
    msg = EmailMessage()
    msg["From"] = "GITSupport@kazyon.com"
    msg["To"] = AGENT
    msg["Subject"] = subject
    msg["Message-ID"] = f"<{uuid4().hex}@kazyon.com>"
    msg.set_content(body)
    return msg.as_bytes(policy=email.policy.SMTP)  # CRLF, as a real MTA sends


def _send(port: int, raw: bytes, *, rcpt: str = AGENT) -> dict[str, tuple[int, bytes]]:
    with smtplib.SMTP("127.0.0.1", port, timeout=5) as client:
        return client.sendmail("relay@kazyon.com", [rcpt], raw)


def _raw_session(port: int, payload: bytes) -> str:
    """Send raw bytes in one go and return everything the server answers until it closes."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(payload)
        chunks = []
        while True:
            try:
                data = sock.recv(65536)
            except TimeoutError:
                break
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode()


def _stored(dropbox: Path) -> list[bytes]:
    return [p.read_bytes() for p in sorted(dropbox.glob("*.eml"))] if dropbox.exists() else []


# ==============================================================================
# Accepting and rejecting mail
# ==============================================================================


@pytest.mark.asyncio
async def test_accepted_message_is_written_to_dropbox_and_wakes_poller(
    start_listener: StartListener, dropbox: Path
) -> None:
    woken: list[bool] = []
    listener = await start_listener(on_stored=lambda: woken.append(True))
    raw = _message(body="line one\n.leading dot line\nline three")

    refused = await asyncio.to_thread(_send, listener.bound_port, raw)

    assert refused == {}
    files = _stored(dropbox)
    assert len(files) == 1
    stored = files[0]
    assert stored.startswith(b"Received: from ")
    assert b"X-Kz-Envelope-From: <relay@kazyon.com>" in stored
    assert f"X-Kz-Envelope-To: <{AGENT}>".encode() in stored
    assert b"Subject: Store 2009 down" in stored
    assert b"\r\n.leading dot line\r\n" in stored  # dot-stuffing undone
    assert list(dropbox.glob("*.tmp")) == []
    assert woken == [True]
    assert listener.stats.messages_accepted == 1


@pytest.mark.asyncio
async def test_client_outside_allowed_list_is_refused(
    start_listener: StartListener, dropbox: Path
) -> None:
    listener = await start_listener(allowed="10.0.0.0/8")
    with pytest.raises(smtplib.SMTPConnectError) as exc:
        await asyncio.to_thread(_send, listener.bound_port, _message())
    assert exc.value.smtp_code == 554
    assert _stored(dropbox) == []
    assert listener.stats.connections_refused == 1


@pytest.mark.asyncio
async def test_recipient_outside_allowed_list_is_refused(
    start_listener: StartListener, dropbox: Path
) -> None:
    listener = await start_listener()
    with pytest.raises(smtplib.SMTPRecipientsRefused) as exc:
        await asyncio.to_thread(_send, listener.bound_port, _message(), rcpt="ceo@kazyon.com")
    assert exc.value.recipients["ceo@kazyon.com"][0] == 550
    assert _stored(dropbox) == []


@pytest.mark.asyncio
async def test_recipient_check_ignores_case(start_listener: StartListener, dropbox: Path) -> None:
    listener = await start_listener()
    await asyncio.to_thread(_send, listener.bound_port, _message(), rcpt=AGENT.upper())
    assert len(_stored(dropbox)) == 1


@pytest.mark.asyncio
async def test_oversize_message_is_refused(start_listener: StartListener, dropbox: Path) -> None:
    listener = await start_listener(max_bytes=2048)
    with pytest.raises(smtplib.SMTPException) as exc:
        await asyncio.to_thread(_send, listener.bound_port, _message(body="x" * 5000))
    assert "552" in str(exc.value)
    assert _stored(dropbox) == []


@pytest.mark.asyncio
async def test_commands_out_of_order_are_rejected(start_listener: StartListener) -> None:
    listener = await start_listener()
    answer = await asyncio.to_thread(
        _raw_session,
        listener.bound_port,
        b"MAIL FROM:<a@x>\r\nEHLO relay\r\nRCPT TO:<" + AGENT.encode() + b">\r\nDATA\r\n"
        b"STARTTLS\r\nAUTH PLAIN abc\r\nQUIT\r\n",
    )
    codes = [line[:3] for line in answer.splitlines() if line[:3].isdigit() and line[3] == " "]
    # banner, MAIL before EHLO, EHLO, RCPT before MAIL, DATA before MAIL, STARTTLS, AUTH, QUIT
    assert codes == ["220", "503", "250", "503", "503", "502", "502", "221"]


@pytest.mark.asyncio
async def test_smtp_smuggling_bare_lf_is_rejected_and_not_split(
    start_listener: StartListener, dropbox: Path
) -> None:
    """ "\\n.\\r\\n" must not end DATA; otherwise the text after it runs as a forged transaction."""
    listener = await start_listener()
    smuggled = (
        b"EHLO relay\r\n"
        b"MAIL FROM:<relay@kazyon.com>\r\n"
        b"RCPT TO:<" + AGENT.encode() + b">\r\n"
        b"DATA\r\n"
        b"Subject: real\r\n\r\nhello\n.\r\n"
        b"MAIL FROM:<ceo@kazyon.com>\r\n"
        b"RCPT TO:<" + AGENT.encode() + b">\r\n"
        b"DATA\r\n"
        b"Subject: forged\r\n\r\nforged body\r\n"
        b".\r\n"
        b"QUIT\r\n"
    )
    answer = await asyncio.to_thread(_raw_session, listener.bound_port, smuggled)

    assert _stored(dropbox) == []
    assert "550 5.6.0" in answer
    assert "Message accepted" not in answer
    assert listener.stats.messages_rejected == 1


# ==============================================================================
# End to end: listener -> dropbox -> poller -> ticket
# ==============================================================================


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / f'listener_{uuid4().hex}.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)()
    ensure_initial_admin(session)
    seed_branches_from_excel(session, dry_run=False)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.mark.asyncio
async def test_forwarded_branch_email_becomes_a_ticket(
    start_listener: StartListener, dropbox: Path, db_session: Session
) -> None:
    listener = await start_listener()
    raw = _message(
        subject="Store 2009 (Kafr Nasar) network down",
        body="Store 2009 is offline and POS is not syncing.\nSite contact: 010 1111 2222",
    )
    await asyncio.to_thread(_send, listener.bound_port, raw)

    cycle = await scheduler.run_email_loop_cycle_once(db_session)

    assert cycle["messages_ingested"] == 1
    result = cycle["ingested"][0]
    assert result["ticket_number"].startswith("NET-")
    ticket = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == result["ticket_number"])
    ).scalar_one()
    assert ticket.sender_email == "GITSupport@kazyon.com"
    inbound = (
        db_session.execute(select(TicketEmail).where(TicketEmail.ticket_id == ticket.id))
        .scalars()
        .first()
    )
    assert inbound is not None and inbound.direction == "INBOUND"
    assert _stored(dropbox) == []  # moved to processed/


# ==============================================================================
# Startup, status and configuration
# ==============================================================================


@pytest.mark.asyncio
async def test_listener_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_LISTENER_ENABLED", raising=False)
    get_settings.cache_clear()
    assert await smtp_listener.start_inbound_smtp_listener() is None
    assert smtp_listener.get_listener_status() == {"enabled": False, "running": False}


@pytest.mark.asyncio
async def test_port_in_use_is_reported_without_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        monkeypatch.setenv("SMTP_LISTENER_ENABLED", "true")
        monkeypatch.setenv("SMTP_LISTENER_HOST", "127.0.0.1")
        monkeypatch.setenv("SMTP_LISTENER_PORT", str(port))
        get_settings.cache_clear()
        try:
            listener = await smtp_listener.start_inbound_smtp_listener()
            status = smtp_listener.get_listener_status()
        finally:
            await smtp_listener.stop_inbound_smtp_listener()
    assert listener is not None
    assert status["enabled"] is True
    assert status["running"] is False
    assert f"port {port}" in status["last_error"]


@pytest.mark.asyncio
async def test_status_reports_running_listener(
    start_listener: StartListener, dropbox: Path
) -> None:
    listener = await start_listener()
    smtp_listener.set_active_listener(listener)
    try:
        await asyncio.to_thread(_send, listener.bound_port, _message())
        status = smtp_listener.get_listener_status()
    finally:
        smtp_listener.set_active_listener(None)
    assert status["running"] is True
    assert status["port"] == listener.bound_port
    assert status["allowed_clients"] == ["127.0.0.1/32"]
    assert status["messages_accepted"] == 1
    assert status["last_received_at"]


@pytest.mark.asyncio
async def test_recipients_default_to_saved_sender_address(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = ensure_system_settings(db_session)
    row.mailbox_account = "NetOps-Agent@kazyon.com"
    db_session.commit()
    monkeypatch.setattr(smtp_listener, "SessionLocal", lambda: Session(bind=db_session.get_bind()))
    monkeypatch.delenv("SMTP_LISTENER_ALLOWED_RECIPIENTS", raising=False)
    get_settings.cache_clear()
    assert await smtp_listener._configured_recipients() == {"netops-agent@kazyon.com"}

    monkeypatch.setenv("SMTP_LISTENER_ALLOWED_RECIPIENTS", "A@kazyon.com, b@kazyon.com")
    get_settings.cache_clear()
    assert await smtp_listener._configured_recipients() == {"a@kazyon.com", "b@kazyon.com"}


def test_production_refuses_listener_open_to_everyone() -> None:
    with pytest.raises(ValueError, match="SMTP_LISTENER_ALLOWED_CLIENTS"):
        Settings(
            app_env="production",
            diagnostic_mode="live",
            loop_guard_fail_open_for_tests=False,
            smtp_listener_enabled=True,
            smtp_listener_allowed_clients="10.1.2.3, 0.0.0.0/0",
        )
    allowed = Settings(
        app_env="production",
        diagnostic_mode="live",
        loop_guard_fail_open_for_tests=False,
        smtp_listener_enabled=True,
        smtp_listener_allowed_clients="10.1.2.3",
    )
    assert [str(n) for n in allowed.smtp_listener_networks()] == ["10.1.2.3/32"]


def test_loop_status_includes_listener(db_session: Session) -> None:
    status: dict[str, Any] = scheduler.get_email_loop_status(db_session)
    assert status["smtp_listener"] == {"enabled": False, "running": False}


@pytest.mark.parametrize("clients", ["REPLACE_WITH_MAIL_SERVER_IP", "", "10.0.0.300"])
def test_enabled_listener_needs_valid_allowed_clients(clients: str) -> None:
    with pytest.raises(ValueError, match="SMTP_LISTENER_ALLOWED_CLIENTS"):
        Settings(smtp_listener_enabled=True, smtp_listener_allowed_clients=clients)
    # Disabled listener: the placeholder in the templates is harmless
    Settings(smtp_listener_enabled=False, smtp_listener_allowed_clients=clients)
