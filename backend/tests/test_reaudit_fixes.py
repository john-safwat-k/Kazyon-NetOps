"""Tests for the five bugs found in the re-audit of the critical-gaps work.

1. Emails deferred because vLLM was down are queued and re-ingested until they succeed or
   escalate (IMAP has already marked them Seen).
2. A vLLM failure during the router-photo check no longer loses the email; an unexpected
   ingest crash is recorded and reported instead of being rolled back silently.
3. An ISP closure while the ticket waits on a site contact runs final verification.
4. Final verification of ORANGE/WE branches traceroute IP1 even when both pings pass.
5. Ticketless sends get their own loop-guard bucket, and a tripped guard escalates through
   `transition_ticket` (never from `smtp_sender`).
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.agent import scheduler
from app.agent.vllm_client import set_vllm_override
from app.agent.workflow import ingest_and_triage_eml, trigger_email_in_loop
from app.auth.service import ensure_initial_admin
from app.common.config import get_settings
from app.common.contracts import (
    EscalationReason,
    RouterPhotoVisionAnalysis,
    TicketPriority,
    TicketStatus,
)
from app.common.database import Base
from app.common.exceptions import LLMInferenceError
from app.diagnostics import executor as diag_executor
from app.directory.models import Branch
from app.directory.seeder import seed_branches_from_excel
from app.directory.service import get_branch_by_code
from app.email_engine import imap_poller
from app.email_engine.parser import build_synthetic_eml_bytes
from app.email_engine.smtp_sender import dispatch_outbound_email
from app.ticketing.models import Ticket, TicketEmail, TicketEvent
from app.ticketing.service import apply_loop_guard_trip, list_human_escalations
from tests.conftest import default_fake_vllm_responder


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / f"test_reaudit_{uuid4().hex}.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=test_engine)
    session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)()
    ensure_initial_admin(session)
    seed_branches_from_excel(session, dry_run=False)
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()


@pytest.fixture()
def retry_queue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the vLLM retry queue at a temp dir with no backoff, and silence the local dropbox."""
    queue_dir = tmp_path / "llm_retry"
    monkeypatch.setenv("LLM_RETRY_QUEUE_DIR", str(queue_dir))
    monkeypatch.setenv("LLM_RETRY_BACKOFF_SEC", "0")
    get_settings.cache_clear()
    monkeypatch.setattr(imap_poller, "_consume_local_dropbox_eml_files_sync", lambda: [])
    return queue_dir


def _failing_vllm(
    messages: list[dict[str, Any]],
    schema: type[BaseModel],
    images: list[bytes] | None = None,
) -> BaseModel:
    raise LLMInferenceError("Simulated vLLM connection timeout")


def _branch_incident_eml(message_id: str, *, attachments: list[str] | None = None) -> bytes:
    return build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Store 2009 (Kafr Nasar) network down",
        body_text="Store 2009 is offline and POS is not syncing.\nSite contact: 010 1111 2222",
        message_id=message_id,
        attachment_filenames=attachments or [],
    )


def _escalated_ticket(db: Session, number: str, *, status: TicketStatus) -> Ticket:
    branch = get_branch_by_code(db, "2009")
    assert branch is not None
    ticket = Ticket(
        ticket_number=number,
        title="2009 · test",
        description="test",
        status=status.value,
        priority=TicketPriority.HIGH.value,
        branch_id=branch.id,
        isp_id=branch.isp_id,
        ai_automation_enabled=True,
    )
    db.add(ticket)
    db.commit()
    return ticket


# ==============================================================================
# Bug 1: deferred emails are re-ingested from the retry queue
# ==============================================================================


@pytest.mark.asyncio
async def test_llm_deferred_email_is_requeued_until_human_escalation(
    db_session: Session,
    retry_queue: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_vllm_override(_failing_vllm)
    message_id = f"<retry-{uuid4().hex}@kazyon.com>"
    eml = _branch_incident_eml(message_id)

    first = await ingest_and_triage_eml(db_session, eml, deduplicate_strict=True)
    assert first["action"] == "DEFERRED_LLM_RETRY"
    assert len(list(retry_queue.glob("*.eml"))) == 1

    # The backoff is respected: nothing is handed back before it elapses
    monkeypatch.setenv("LLM_RETRY_BACKOFF_SEC", "3600")
    get_settings.cache_clear()
    assert await imap_poller.poll_inbound_mailbox_raw() == []
    monkeypatch.setenv("LLM_RETRY_BACKOFF_SEC", "0")
    get_settings.cache_clear()

    actions = []
    for _ in range(2):
        polled = await imap_poller.poll_inbound_mailbox_raw()
        assert [raw for _, raw in polled] == [eml]
        assert list(retry_queue.glob("*.eml")) == []
        res = await ingest_and_triage_eml(db_session, polled[0][1], deduplicate_strict=True)
        actions.append(res["action"])

    assert actions == ["DEFERRED_LLM_RETRY", "HUMAN_ESCALATED_LLM_UNAVAILABLE"]
    assert list(retry_queue.glob("*.eml")) == []
    rows = (
        db_session.execute(select(TicketEmail).where(TicketEmail.message_id == message_id))
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].thread_type == "HUMAN_ESCALATION"
    reasons = {item.reason for item in list_human_escalations(db_session)}
    assert EscalationReason.LLM_UNAVAILABLE.value in reasons


@pytest.mark.asyncio
async def test_llm_deferred_email_is_processed_when_vllm_recovers(
    db_session: Session,
    retry_queue: Path,
) -> None:
    set_vllm_override(_failing_vllm)
    message_id = f"<recover-{uuid4().hex}@kazyon.com>"
    first = await ingest_and_triage_eml(
        db_session, _branch_incident_eml(message_id), deduplicate_strict=True
    )
    assert first["action"] == "DEFERRED_LLM_RETRY"

    set_vllm_override(default_fake_vllm_responder)
    cycle = await scheduler.run_email_loop_cycle_once(db_session)

    assert cycle["messages_ingested"] == 1
    result = cycle["ingested"][0]
    assert result["action"] != "DEFERRED_LLM_RETRY"
    assert result["ticket_number"].startswith("NET-")
    labels = (
        db_session.execute(
            select(TicketEmail.classification_label).where(TicketEmail.message_id == message_id)
        )
        .scalars()
        .all()
    )
    assert labels == ["INCIDENT_REPORT"]
    assert list(retry_queue.glob("*.eml")) == []


# ==============================================================================
# Bug 2: vision failure and unexpected ingest crashes never lose the email
# ==============================================================================


@pytest.mark.asyncio
async def test_vision_failure_proceeds_to_diagnostics(db_session: Session) -> None:
    def _vision_down(
        messages: list[dict[str, Any]],
        schema: type[BaseModel],
        images: list[bytes] | None = None,
    ) -> BaseModel:
        if schema is RouterPhotoVisionAnalysis:
            raise LLMInferenceError("Simulated multimodal timeout")
        return default_fake_vllm_responder(messages, schema, images)

    set_vllm_override(_vision_down)
    res = await ingest_and_triage_eml(
        db_session,
        _branch_incident_eml(f"<vision-{uuid4().hex}@kazyon.com>", attachments=["router.jpg"]),
    )

    # Simulated fixture: store 2009 is a full outage, so diagnostics escalate to the ISP
    assert res["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value
    ticket = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == res["ticket_number"])
    ).scalar_one()
    assert ticket.image_check_passed is None
    events = {
        e.event_type
        for e in db_session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id))
        .scalars()
        .all()
    }
    assert "vision_unavailable" in events
    assert "vision_skipped" not in events


@pytest.mark.asyncio
async def test_scheduler_records_failed_ingest_instead_of_dropping(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message_id = f"<crash-{uuid4().hex}@kazyon.com>"
    eml = _branch_incident_eml(message_id)

    async def _poll(**_: Any) -> list[tuple[str, bytes]]:
        return [("imap_1.eml", eml)]

    async def _crash(*_: Any, **__: Any) -> dict[str, Any]:
        raise RuntimeError("unexpected bug")

    monkeypatch.setattr(scheduler, "poll_inbound_mailbox_raw", _poll)
    monkeypatch.setattr(scheduler, "ingest_and_triage_eml", _crash)

    cycle = await scheduler.run_email_loop_cycle_once(db_session)
    assert cycle["messages_ingested"] == 0

    failed = db_session.execute(
        select(TicketEmail).where(TicketEmail.message_id == message_id)
    ).scalar_one()
    assert failed.classification_label == EscalationReason.INGEST_FAILED.value
    assert "unexpected bug" in failed.ai_analysis_json["error"]
    report = db_session.execute(
        select(TicketEmail).where(
            TicketEmail.direction == "OUTBOUND",
            TicketEmail.in_reply_to == message_id,
        )
    ).scalar_one()
    assert report.thread_type == "HUMAN_ESCALATION"
    reasons = {item.reason for item in list_human_escalations(db_session)}
    assert EscalationReason.INGEST_FAILED.value in reasons


# ==============================================================================
# Bug 3: ISP closure while awaiting a site contact
# ==============================================================================


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("closure_scenario", "expected_action", "expected_status"),
    [
        ("ISP_RESOLVED", "VERIFIED_AND_CLOSED", TicketStatus.CLOSED),
        (
            "ISP_RESOLVED_STILL_DOWN",
            "REJECTED_PREMATURE_ISP_CLOSURE",
            TicketStatus.ESCALATED_TO_ISP,
        ),
    ],
)
async def test_isp_closure_while_awaiting_branch_contact_runs_verification(
    db_session: Session,
    closure_scenario: str,
    expected_action: str,
    expected_status: TicketStatus,
) -> None:
    opened = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": "2009"}
    )
    assert opened["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value
    ticket_number = opened["ticket_number"]

    blocked = await trigger_email_in_loop(
        db_session,
        {"scenario": "ISP_CONTACT_UNREACHABLE", "ticket_number": ticket_number},
    )
    assert blocked["ticket_status"] == TicketStatus.AWAITING_BRANCH_CONTACT.value

    closed = await trigger_email_in_loop(
        db_session, {"scenario": closure_scenario, "ticket_number": ticket_number}
    )
    assert closed["action"] == expected_action
    assert closed["ticket_status"] == expected_status.value


# ==============================================================================
# Bug 4: ORANGE/WE final verification checks the 4G hub even when both IPs are up
# ==============================================================================


@pytest.mark.asyncio
async def test_final_verification_rejects_closure_while_still_on_4g_backup(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DIAGNOSTIC_MODE", "live")
    get_settings.cache_clear()

    ping_state: dict[str, bool] = {}
    hub_in_path: list[str] = []
    traceroute_calls: list[str] = []

    async def _fake_ping(target_ip: str, count: int = 4, timeout_sec: int = 10) -> tuple[bool, str]:
        up = ping_state.get(target_ip, False)
        return up, f"PING {target_ip}: {'0' if up else '100'}% packet loss"

    async def _fake_traceroute(
        target_ip: str, max_hops: int = 15, timeout_sec: int = 15
    ) -> tuple[str, list[str]]:
        traceroute_calls.append(target_ip)
        hops = ["10.0.0.1", *hub_in_path, target_ip]
        return "\n".join(hops), hops

    monkeypatch.setattr(diag_executor, "run_live_ping", _fake_ping)
    monkeypatch.setattr(diag_executor, "run_live_traceroute", _fake_traceroute)

    # ORANGE store 1173: IP1 up, IP2 down, path via 4G hub -> escalated
    ping_state.update({"10.11.73.1": True, "10.11.73.2": False})
    hub_in_path[:] = ["10.247.8.1"]
    opened = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": "1173"}
    )
    assert opened["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value
    ticket_number = opened["ticket_number"]

    # Both IPs answer, but traffic still rides the 4G hub -> closure rejected
    ping_state["10.11.73.2"] = True
    traceroute_calls.clear()
    still_4g = await trigger_email_in_loop(
        db_session, {"scenario": "ISP_RESOLVED", "ticket_number": ticket_number}
    )
    assert traceroute_calls == ["10.11.73.1"]
    assert still_4g["action"] == "REJECTED_PREMATURE_ISP_CLOSURE"
    ticket = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == ticket_number)
    ).scalar_one()
    assert ticket.connection_failure_type == "LOCAL_LOOP_DOWN_ON_4G"

    # Local loop back: no hub in the path -> verified and closed
    hub_in_path.clear()
    restored = await trigger_email_in_loop(
        db_session, {"scenario": "ISP_RESOLVED", "ticket_number": ticket_number}
    )
    assert restored["action"] == "VERIFIED_AND_CLOSED"

    # Initial triage keeps the BRD matrix: both IPs up closes without a traceroute
    we_branch = db_session.execute(
        select(Branch).where(Branch.isp_name == "WE").order_by(Branch.branch_code).limit(1)
    ).scalar_one()
    ping_state.update({we_branch.ip_1: True, we_branch.ip_2: True})
    hub_in_path[:] = ["172.16.70.33"]
    traceroute_calls.clear()
    initial = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": we_branch.branch_code}
    )
    assert initial["action"] == "CLOSED_DIAGNOSTICS_PASSED"
    assert traceroute_calls == []


# ==============================================================================
# Bug 5: loop guard key for ticketless mail, and trip escalation via transition_ticket
# ==============================================================================


@pytest.mark.asyncio
async def test_ticketless_sends_use_per_message_loop_guard_key(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keys: list[str] = []

    def _record(key: str, max_per_hour: int | None = None) -> bool:
        keys.append(key)
        return True

    monkeypatch.setattr(
        "app.email_engine.smtp_sender.check_and_increment_outbound_allowance", _record
    )
    ticket = _escalated_ticket(db_session, "NET-9201", status=TicketStatus.ESCALATED_TO_ISP)

    for reply_to in ("<a@x>", "<b@x>"):
        await dispatch_outbound_email(
            db_session,
            ticket=None,
            thread_type="HUMAN_ESCALATION",
            recipients=["noc-oncall@kazyon.com"],
            subject="report",
            body_text="report",
            in_reply_to=reply_to,
        )
    await dispatch_outbound_email(
        db_session,
        ticket=ticket,
        thread_type="ISP",
        recipients=["noc@noor.net"],
        subject="chaser",
        body_text="chaser",
    )

    assert keys == ["NO-TICKET:<a@x>", "NO-TICKET:<b@x>", "NET-9201"]


def test_loop_guard_trip_never_reopens_closed_ticket(db_session: Session) -> None:
    ticket = _escalated_ticket(db_session, "NET-9202", status=TicketStatus.CLOSED)
    for _ in range(2):
        db_session.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_type="AI_AGENT",
                actor_name="AI_AGENT",
                event_type="email_blocked",
                summary="blocked",
                details_json={},
            )
        )
    db_session.commit()

    assert apply_loop_guard_trip(db_session, ticket) is False
    assert ticket.status == TicketStatus.CLOSED.value


@pytest.mark.asyncio
async def test_chaser_cycle_escalates_after_second_blocked_chaser(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.email_engine.smtp_sender.check_and_increment_outbound_allowance",
        lambda key, max_per_hour=None: False,
    )
    ticket = _escalated_ticket(db_session, "NET-9203", status=TicketStatus.ESCALATED_TO_ISP)
    ticket.next_followup_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    first = await scheduler.run_sla_chaser_cycle(db_session)
    assert first["chased_count"] == 0
    assert first["escalated_to_human_count"] == 0
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.ESCALATED_TO_ISP.value

    second = await scheduler.run_sla_chaser_cycle(db_session)
    assert second["escalated_to_human_count"] == 1
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.NEEDS_HUMAN_REVIEW.value
    assert ticket.escalation_reason == EscalationReason.LOOP_GUARD_TRIPPED.value
    assert ticket.ai_automation_enabled is False
    status_events = (
        db_session.execute(
            select(TicketEvent).where(
                TicketEvent.ticket_id == ticket.id,
                TicketEvent.event_type == "status_changed",
            )
        )
        .scalars()
        .all()
    )
    assert any("LOOP_GUARD_TRIPPED" in (e.summary or "") for e in status_events)
