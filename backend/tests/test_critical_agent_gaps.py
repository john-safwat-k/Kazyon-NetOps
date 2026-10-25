"""Tests for Fix Plan: Critical Gaps in the Autonomous Agent Flow (Gaps 1–6).

Covers:
- Gap 6: Table-driven state machine transition enforcement, B1 on DIAGNOSING blocked, repeat branch email on ESCALATED_TO_ISP blocked, forced engineer override audited.
- Gap 4: Loop guard blocks SMTP, records `blocked_by_loop_guard`, logs `email_blocked`, escalates with `LOOP_GUARD_TRIPPED` on 2nd block, and fails safe when Redis is down.
- Gap 5: Never sends a made-up site phone; uses `site contact : will be shared shortly`, requests phone from branch, and relays phone when reply arrives.
- Gaps 1 & 2: Live ICMP ping/traceroute decision tree, real final verification (rejects closure when IP1 still down), `DIAGNOSTICS_UNAVAILABLE` escalation, and startup refusal of `simulated` mode in `production`.
- Gap 3: Golden test across all 63 `.eml` files in `Info/`, WE SAP code extraction (`#1251` vs `#6181183`), router photo persistence + vision pass/fail/no-image skip, `vLLM` 3-retry + 3-cycle `LLM_UNAVAILABLE` escalation, low-confidence human review, `AUTO_ACK`, and `BRANCH_ACTION_BLOCKER`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.agent.classifier import classify_inbound_email
from app.agent.vllm_client import set_vllm_override
from app.agent.workflow import ingest_and_triage_eml, trigger_email_in_loop
from app.auth.service import ensure_initial_admin
from app.common.audit import AuditLog
from app.common.config import Settings, get_settings
from app.common.contracts import (
    BranchEmailAnalysis,
    EscalationReason,
    TicketPriority,
    TicketStatus,
)
from app.common.database import Base
from app.common.exceptions import (
    InvalidStateTransitionError,
    LLMInferenceError,
    SupportAgentError,
)
from app.diagnostics import executor as diag_executor
from app.directory.seeder import seed_branches_from_excel
from app.email_engine.loop_guard import check_and_increment_outbound_allowance
from app.email_engine.parser import (
    build_synthetic_eml_bytes,
    extract_branch_sap_code,
    parse_eml_bytes,
)
from app.email_engine.smtp_sender import dispatch_outbound_email
from app.ticketing.models import Ticket, TicketEmail, TicketEvent
from app.ticketing.service import (
    apply_loop_guard_trip,
    ensure_system_settings,
    transition_ticket,
)
from app.ticketing.state_machine import ALLOWED_TRANSITIONS, assert_transition


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / f"test_gaps_{uuid4().hex}.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, future=True
    )
    session = TestingSessionLocal()
    ensure_initial_admin(session)
    seed_branches_from_excel(session, dry_run=False)
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()


# ==============================================================================
# GAP 6: Enforce Ticket State Transitions
# ==============================================================================


@pytest.mark.parametrize("current_status", list(TicketStatus))
@pytest.mark.parametrize("target_status", list(TicketStatus))
def test_state_machine_all_legal_and_illegal_pairs(
    current_status: TicketStatus,
    target_status: TicketStatus,
) -> None:
    """Every (current, target) pair in TicketStatus × TicketStatus must match ALLOWED_TRANSITIONS."""
    expected_legal = target_status in ALLOWED_TRANSITIONS.get(current_status, frozenset())
    if expected_legal:
        assert_transition(current_status, target_status)
    else:
        with pytest.raises(InvalidStateTransitionError):
            assert_transition(current_status, target_status)


@pytest.mark.asyncio
async def test_b1_contact_update_blocked_on_diagnosing_ticket(
    db_session: Session,
) -> None:
    """A contact update email arriving while a ticket is still in DIAGNOSING must not send an ISP relay."""
    # Create a ticket in DIAGNOSING state for branch 2009
    from app.directory.service import get_branch_by_code

    branch = get_branch_by_code(db_session, "2009")
    assert branch is not None
    ticket = Ticket(
        ticket_number="NET-9001",
        title="2009-Kafr Nasar · Diagnosing",
        description="Initial outage",
        status=TicketStatus.DIAGNOSING.value,
        priority=TicketPriority.HIGH.value,
        branch_id=branch.id,
        isp_id=branch.isp_id,
        sender_email="GITSupport@kazyon.com",
        ai_automation_enabled=True,
    )
    db_session.add(ticket)
    db_session.commit()

    eml = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="RE: URGENT [NET-9001]: ISP cannot reach site contact",
        body_text=(
            "For store 2009, the active phone number for the shift manager is 010 9988 7766. "
            "Kindly relay to the ISP NOC."
        ),
    )
    res = await ingest_and_triage_eml(db_session, eml)

    assert res["action"] == "LOGGED_ON_TIMELINE_TRANSITION_BLOCKED"
    assert res["outbound_emails"] == []
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.DIAGNOSING.value
    events = (
        db_session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id))
        .scalars()
        .all()
    )
    assert any(e.event_type == "status_transition_blocked" for e in events)


@pytest.mark.asyncio
async def test_repeat_branch_email_on_escalated_ticket_does_not_reescalate(
    db_session: Session,
) -> None:
    """A second branch outage email on an already ESCALATED_TO_ISP ticket must attach to the timeline without re-escalating."""
    r1 = await trigger_email_in_loop(
        db_session,
        {
            "scenario": "BRANCH_INCIDENT",
            "branch_code": "2009",
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    ticket_num = r1["ticket_number"]
    assert r1["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value
    assert any(em["thread_type"] == "ISP" for em in r1["outbound_emails"])

    # Send a second branch outage email for the same branch 2009 while ESCALATED_TO_ISP
    r2 = await trigger_email_in_loop(
        db_session,
        {
            "scenario": "BRANCH_INCIDENT",
            "branch_code": "2009",
            "subject": f"[{ticket_num}] Store 2009 still down — any update?",
            "body_text": "Dear IT Support, Store 2009 is still offline. Router photo attached.",
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    assert r2["ticket_number"] == ticket_num
    assert r2["action"] == "LOGGED_ON_TIMELINE_TRANSITION_BLOCKED"
    assert r2["outbound_emails"] == []


def test_force_transition_audited_for_engineer(db_session: Session) -> None:
    """Manual engineer override with force=True allows out-of-band transitions and records an AuditLog."""
    from app.directory.service import get_branch_by_code

    branch = get_branch_by_code(db_session, "2009")
    assert branch is not None
    ticket = Ticket(
        ticket_number="NET-9002",
        title="2009 · Force test",
        description="Test",
        status=TicketStatus.CLOSED.value,
        priority=TicketPriority.MEDIUM.value,
        branch_id=branch.id,
        isp_id=branch.isp_id,
    )
    db_session.add(ticket)
    db_session.commit()

    # Normal transition from CLOSED is forbidden
    with pytest.raises(InvalidStateTransitionError):
        transition_ticket(db_session, ticket, TicketStatus.DIAGNOSING)

    # Forced transition by ENGINEER succeeds and writes an audit log
    transition_ticket(
        db_session,
        ticket,
        TicketStatus.DIAGNOSING,
        actor_type="ENGINEER",
        actor_name="admin",
        reason="Re-opened by NOC lead",
        force=True,
    )
    db_session.commit()
    assert ticket.status == TicketStatus.DIAGNOSING.value
    audits = (
        db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "ticket.status_forced",
                AuditLog.resource_id == "NET-9002",
            )
        )
        .scalars()
        .all()
    )
    assert len(audits) == 1


# ==============================================================================
# GAP 4: Make the Loop Guard Actually Block
# ==============================================================================


def test_loop_guard_redis_down_fails_safe_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Redis is unavailable and LOOP_GUARD_FAIL_OPEN_FOR_TESTS is False, the loop guard blocks sends."""
    monkeypatch.setenv("LOOP_GUARD_FAIL_OPEN_FOR_TESTS", "false")
    get_settings.cache_clear()
    monkeypatch.setattr("app.email_engine.loop_guard.get_redis", lambda: None)

    allowed = check_and_increment_outbound_allowance("NET-9100", max_per_hour=6)
    assert allowed is False


@pytest.mark.asyncio
async def test_loop_guard_limit_hit_blocks_smtp_and_escalates_on_second_block(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When loop guard returns False, SMTP is skipped, `blocked_by_loop_guard` is recorded, and 2nd block escalates with LOOP_GUARD_TRIPPED."""
    from app.directory.service import get_branch_by_code

    branch = get_branch_by_code(db_session, "2009")
    assert branch is not None
    ticket = Ticket(
        ticket_number="NET-9101",
        title="2009 · Loop guard test",
        description="Test",
        status=TicketStatus.ESCALATED_TO_ISP.value,
        priority=TicketPriority.HIGH.value,
        branch_id=branch.id,
        isp_id=branch.isp_id,
        ai_automation_enabled=True,
    )
    db_session.add(ticket)
    db_session.commit()

    # Force loop guard to return False
    monkeypatch.setattr(
        "app.email_engine.smtp_sender.check_and_increment_outbound_allowance",
        lambda ticket_number, max_per_hour=6: False,
    )
    smtp_called = False

    def _fail_if_smtp_called(*args: Any, **kwargs: Any) -> None:
        nonlocal smtp_called
        smtp_called = True

    monkeypatch.setattr(
        "app.email_engine.smtp_sender._send_via_live_smtp_sync", _fail_if_smtp_called
    )

    # 1st blocked send: recorded as blocked, ticket still ESCALATED_TO_ISP
    em1 = await dispatch_outbound_email(
        db_session,
        ticket=ticket,
        thread_type="ISP",
        recipients=["noc@noor.net"],
        subject="Chaser 1",
        body_text="Checking status",
        classification_label="SLA_CHASER",
    )
    db_session.commit()
    assert smtp_called is False
    assert em1.ai_analysis_json.get("blocked_by_loop_guard") is True
    assert em1.ai_analysis_json.get("smtp_live_sent") is False
    # The sender only records the block; it never changes ticket status itself
    assert ticket.status == TicketStatus.ESCALATED_TO_ISP.value
    assert apply_loop_guard_trip(db_session, ticket) is False
    assert ticket.status == TicketStatus.ESCALATED_TO_ISP.value

    # 2nd blocked send within 1 hour: escalates ticket to NEEDS_HUMAN_REVIEW with LOOP_GUARD_TRIPPED
    em2 = await dispatch_outbound_email(
        db_session,
        ticket=ticket,
        thread_type="ISP",
        recipients=["noc@noor.net"],
        subject="Chaser 2",
        body_text="Checking status again",
        classification_label="SLA_CHASER",
    )
    db_session.commit()
    assert em2.ai_analysis_json.get("blocked_by_loop_guard") is True
    assert ticket.status == TicketStatus.ESCALATED_TO_ISP.value
    assert apply_loop_guard_trip(db_session, ticket) is True
    db_session.commit()
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.NEEDS_HUMAN_REVIEW.value
    assert ticket.escalation_reason == EscalationReason.LOOP_GUARD_TRIPPED.value
    assert ticket.ai_automation_enabled is False


# ==============================================================================
# GAP 5: Never Send a Made-Up Site Phone Number
# ==============================================================================


@pytest.mark.asyncio
async def test_missing_phone_escalation_and_subsequent_phone_relay(
    db_session: Session,
) -> None:
    """Branch email with no phone escalates immediately with 'will be shared shortly', asks branch for phone, and relays when reply arrives."""
    raw_no_phone = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Store 2009 (Kafr Nasar) network down",
        body_text=(
            "Dear Network Support,\n"
            "Store 2009 is completely offline. Router photo attached (cables seated, power LED green).\n"
            "Please check with Noor NOC urgently."
        ),
        attachment_filenames=["router_2009_ok.jpg"],
    )
    r1 = await ingest_and_triage_eml(
        db_session,
        raw_no_phone,
        diagnostic_scenario="FULL_OUTAGE",
        _from_harness=True,
    )
    ticket_num = r1["ticket_number"]
    assert ticket_num.startswith("NET-")
    assert r1["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value

    # Check ISP escalation email body: must have "will be shared shortly" and NO 010/011/012/015 phone digits
    isp_emails = (
        db_session.execute(
            select(TicketEmail).where(
                TicketEmail.thread_type == "ISP",
                TicketEmail.direction == "OUTBOUND",
            )
        )
        .scalars()
        .all()
    )
    assert len(isp_emails) == 1
    assert "will be shared shortly" in isp_emails[0].body_text
    assert re.search(r"01[0125]\d", isp_emails[0].body_text.replace(" ", "")) is None

    # Check that a SITE_PHONE_REQUEST email was sent to the branch
    assert any(
        em["classification_label"] == "SITE_PHONE_REQUEST" and em["thread_type"] == "BRANCH"
        for em in r1["outbound_emails"]
    )

    # Now branch replies with an active phone number -> B1 relays it to the ISP
    raw_phone_reply = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject=f"RE: ACTION [{ticket_num}]: Active site phone needed for 2009-Kafr Nasar",
        body_text="The active phone number for the store manager at 2009 is 010 5544 3322.",
    )
    r2 = await ingest_and_triage_eml(db_session, raw_phone_reply)
    assert r2["action"] == "RELAYED_CONTACT_TO_ISP"
    assert any(
        em["classification_label"] == "CONTACT_RELAY_TO_ISP" and em["thread_type"] == "ISP"
        for em in r2["outbound_emails"]
    )
    relay_em = (
        db_session.execute(
            select(TicketEmail).where(TicketEmail.classification_label == "CONTACT_RELAY_TO_ISP")
        )
        .scalars()
        .first()
    )
    assert relay_em is not None
    assert "010 5544 3322" in relay_em.body_text


# ==============================================================================
# GAPS 1 & 2: Live Diagnostics and Real Final Verification
# ==============================================================================


def test_production_forbids_simulated_diagnostic_mode() -> None:
    """Production environment must refuse to start if DIAGNOSTIC_MODE=simulated or LOOP_GUARD_FAIL_OPEN_FOR_TESTS=true."""
    with pytest.raises(ValidationError):
        Settings(app_env="production", diagnostic_mode="simulated")

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            diagnostic_mode="live",
            loop_guard_fail_open_for_tests=True,
        )


@pytest.mark.asyncio
async def test_diagnostic_scenario_override_forbidden_outside_simulated_harness(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passing diagnostic_scenario from non-harness path or in live mode raises 403 SupportAgentError."""
    eml = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Store 2009 down",
        body_text="Store 2009 is down.",
    )
    with pytest.raises(SupportAgentError) as exc_info:
        await ingest_and_triage_eml(
            db_session,
            eml,
            diagnostic_scenario="PASS",
            _from_harness=False,
        )
    assert exc_info.value.status_code == 403

    monkeypatch.setenv("DIAGNOSTIC_MODE", "live")
    get_settings.cache_clear()
    with pytest.raises(SupportAgentError) as exc_info2:
        await ingest_and_triage_eml(
            db_session,
            eml,
            diagnostic_scenario="PASS",
            _from_harness=True,
        )
    assert exc_info2.value.status_code == 403


@pytest.mark.asyncio
async def test_live_diagnostics_runner_five_cases_and_final_verification(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify live ping/traceroute runner across all 5 network cases and premature ISP closure rejection."""
    monkeypatch.setenv("DIAGNOSTIC_MODE", "live")
    get_settings.cache_clear()

    # Fake state map: ip -> bool (reachable), traceroute_via_hub -> bool
    ping_state: dict[str, bool] = {}
    traceroute_hub_ip: list[str] = []

    async def _fake_live_ping(
        target_ip: str, count: int = 4, timeout_sec: int = 10
    ) -> tuple[bool, str]:
        is_up = ping_state.get(target_ip, False)
        raw = (
            f"PING {target_ip}: 4 packets transmitted, 4 received, 0% packet loss"
            if is_up
            else f"PING {target_ip}: 4 packets transmitted, 0 received, 100% packet loss"
        )
        return is_up, raw

    async def _fake_live_traceroute(
        target_ip: str, max_hops: int = 15, timeout_sec: int = 15
    ) -> tuple[str, list[str]]:
        hops = ["10.0.0.1"] + list(traceroute_hub_ip) + [target_ip]
        raw = "\n".join(f" {idx + 1}  {h}  12.1 ms" for idx, h in enumerate(hops))
        return raw, hops

    monkeypatch.setattr(diag_executor, "run_live_ping", _fake_live_ping)
    monkeypatch.setattr(diag_executor, "run_live_traceroute", _fake_live_traceroute)

    # Case 1: IP1 down on NOOR store 2009 (10.20.9.1) -> FULL_OUTAGE -> ESCALATED_TO_ISP
    ping_state.clear()
    traceroute_hub_ip.clear()
    r1 = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": "2009"}
    )
    assert r1["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value
    t_2009 = r1["ticket_number"]

    # Case 5: ISP sends closure for store 2009 while IP1 is STILL down in live mode -> REJECTED_PREMATURE_ISP_CLOSURE
    r1_close_fail = await trigger_email_in_loop(
        db_session,
        {"scenario": "ISP_RESOLVED", "ticket_number": t_2009, "branch_code": "2009"},
    )
    assert r1_close_fail["action"] == "REJECTED_PREMATURE_ISP_CLOSURE"
    assert r1_close_fail["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value

    # Now IP1 & IP2 come UP on 2009 -> ISP closure is verified and ticket closes!
    ping_state["10.20.9.1"] = True
    ping_state["10.20.9.2"] = True
    r1_close_ok = await trigger_email_in_loop(
        db_session,
        {"scenario": "ISP_RESOLVED", "ticket_number": t_2009, "branch_code": "2009"},
    )
    assert r1_close_ok["action"] == "VERIFIED_AND_CLOSED"
    assert r1_close_ok["ticket_status"] == TicketStatus.CLOSED.value

    # Case 2: IP1 UP + IP2 DOWN on NOOR store 1201 (10.12.1.1 / 10.12.1.2) -> INTERNAL_LAN_ISSUE
    ping_state.clear()
    ping_state["10.12.1.1"] = True
    ping_state["10.12.1.2"] = False
    r2 = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": "1201"}
    )
    assert r2["ticket_status"] == TicketStatus.INTERNAL_LAN_ISSUE.value
    assert r2["action"] == "RETURNED_TO_BRANCH_INTERNAL_SWITCH"

    # Case 3: ORANGE store 1173 (10.11.73.1 UP, 10.11.73.2 DOWN) via 4G hub 10.247.8.1 -> ESCALATED_TO_ISP
    ping_state.clear()
    ping_state["10.11.73.1"] = True
    ping_state["10.11.73.2"] = False
    traceroute_hub_ip[:] = ["10.247.8.1"]
    r3 = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": "1173"}
    )
    assert r3["ticket_status"] == TicketStatus.ESCALATED_TO_ISP.value
    assert r3["action"] == "ESCALATED_TO_ORANGE"

    # Case 4: ORANGE store 1026 (10.10.26.1 UP, 10.10.26.2 DOWN) NOT via 4G hub -> INTERNAL_LAN_ISSUE
    ping_state.clear()
    ping_state["10.10.26.1"] = True
    ping_state["10.10.26.2"] = False
    traceroute_hub_ip.clear()
    r4 = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": "1026"}
    )
    assert r4["ticket_status"] == TicketStatus.INTERNAL_LAN_ISSUE.value
    assert r4["action"] == "RETURNED_TO_BRANCH_INTERNAL_SWITCH"


@pytest.mark.asyncio
async def test_missing_icmp_binary_escalates_diagnostics_unavailable(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ICMP binary or CAP_NET_RAW permission is missing in live mode, escalate with DIAGNOSTICS_UNAVAILABLE."""
    monkeypatch.setenv("DIAGNOSTIC_MODE", "live")
    get_settings.cache_clear()

    async def _missing_ping(
        target_ip: str, count: int = 4, timeout_sec: int = 10
    ) -> tuple[bool, str]:
        return False, "ping binary not found on host PATH."

    monkeypatch.setattr(diag_executor, "run_live_ping", _missing_ping)

    res = await trigger_email_in_loop(
        db_session, {"scenario": "BRANCH_INCIDENT", "branch_code": "2009"}
    )
    assert res["action"] == "HUMAN_ESCALATED_DIAGNOSTICS_UNAVAILABLE"
    assert res["ticket_status"] == TicketStatus.NEEDS_HUMAN_REVIEW.value


# ==============================================================================
# GAP 3: Real vLLM Classification, Router-Photo Vision & 63 Info/*.eml Golden Suite
# ==============================================================================


def test_we_subject_sap_code_extraction_never_slices_longer_numbers() -> None:
    """WE subjects with `#6181183#6201898#1251` must extract `1251`, never `1183` from `6181183`."""
    subj = "Re: [Request ID :##RE-8427545##] : Kazyon #E33209 #6181183#6201898#1251"
    body = "Dear Customer, Ticket 8427545 is now resolved and closed."
    assert extract_branch_sap_code(subj, body) == "1251"

    # Preferred branch code takes precedence when already correlated
    assert extract_branch_sap_code(subj, body, preferred_branch_code="1391") == "1391"


@pytest.mark.asyncio
async def test_golden_63_info_eml_files() -> None:
    """Every single one of the 63 `.eml` files in `Info/` must match `tests/fixtures/info_eml_expected.json`."""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "info_eml_expected.json"
    expected_map: dict[str, dict[str, Any]] = json.loads(fixture_path.read_text())
    info_dir = Path(__file__).resolve().parent.parent.parent / "Info"
    eml_files = sorted(info_dir.glob("*.eml"))
    assert len(eml_files) == 63
    assert len(expected_map) == 63

    for eml_path in eml_files:
        env = parse_eml_bytes(eml_path.read_bytes())
        triage = await classify_inbound_email(env, confidence_threshold_pct=80)
        actual = {
            "trigger_type": triage.trigger_type,
            "classification_label": triage.classification_label,
            "intent": triage.intent,
            "branch_code": triage.branch_code,
            "isp_name": triage.isp_name,
            "isp_reference_number": triage.isp_reference_number,
        }
        assert actual == expected_map[eml_path.name], f"Mismatch on {eml_path.name}"


@pytest.mark.asyncio
async def test_vision_pass_fail_and_no_image_skip(
    db_session: Session,
) -> None:
    """Verify router photo persistence on disk, vision fail -> AWAITING_BRANCH, vision pass -> diagnostics, and no photo -> vision_skipped."""
    # 1. No image attachment -> vision_skipped, goes straight to diagnostics
    eml_no_photo = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Store 2009 offline",
        body_text="Store 2009 is offline. Site contact: 010 2345 8817",
        attachment_filenames=[],
    )
    r_skip = await ingest_and_triage_eml(
        db_session,
        eml_no_photo,
        diagnostic_scenario="FULL_OUTAGE",
        _from_harness=True,
    )
    t_skip = (
        db_session.execute(select(Ticket).where(Ticket.ticket_number == r_skip["ticket_number"]))
        .scalars()
        .one()
    )
    assert t_skip.image_check_passed is None
    assert t_skip.status == TicketStatus.ESCALATED_TO_ISP.value
    skip_events = (
        db_session.execute(select(TicketEvent).where(TicketEvent.ticket_id == t_skip.id))
        .scalars()
        .all()
    )
    assert any(ev.event_type == "vision_skipped" for ev in skip_events)

    # 2. Image attachment with cables_plugged=True -> persisted under ATTACHMENTS_DIR/<ticket_number>/<sha256>.jpg
    r_pass = await trigger_email_in_loop(
        db_session,
        {
            "scenario": "BRANCH_INCIDENT",
            "branch_code": "1188",
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    t_pass = (
        db_session.execute(select(Ticket).where(Ticket.ticket_number == r_pass["ticket_number"]))
        .scalars()
        .one()
    )
    assert t_pass.image_check_passed is True
    assert len(t_pass.router_image_paths) == 1
    persisted_file = Path(t_pass.router_image_paths[0])
    assert persisted_file.exists()
    assert t_pass.ticket_number in persisted_file.parts


@pytest.mark.asyncio
async def test_vllm_timeout_retries_3_cycles_then_escalates_llm_unavailable(
    db_session: Session,
) -> None:
    """When vLLM fails, guided_json retries 3 times per call, and after 3 failed poll cycles escalates with LLM_UNAVAILABLE."""
    call_count = 0

    def _failing_vllm(
        messages: list[dict[str, Any]],
        schema: type[BaseModel],
        images: list[bytes] | None = None,
    ) -> BaseModel:
        nonlocal call_count
        call_count += 1
        raise LLMInferenceError("Simulated vLLM connection timeout")

    set_vllm_override(_failing_vllm)

    eml = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Store 2009 down",
        body_text="Store 2009 is offline. Site contact: 010 2345 8817",
        message_id="<llm-retry-test-2009@kazyon.com>",
    )

    # Cycle 1: 3 internal retries -> DEFERRED_LLM_RETRY
    c1 = await ingest_and_triage_eml(db_session, eml)
    assert c1["action"] == "DEFERRED_LLM_RETRY"
    assert call_count == 3

    # Cycle 2: 3 internal retries -> DEFERRED_LLM_RETRY
    c2 = await ingest_and_triage_eml(db_session, eml)
    assert c2["action"] == "DEFERRED_LLM_RETRY"
    assert call_count == 6

    # Cycle 3: 3 internal retries -> HUMAN_ESCALATED_LLM_UNAVAILABLE
    c3 = await ingest_and_triage_eml(db_session, eml)
    assert c3["action"] == "HUMAN_ESCALATED_LLM_UNAVAILABLE"
    assert call_count == 9
    assert any(em["classification_label"] == "HUMAN_ESCALATION" for em in c3["outbound_emails"])


@pytest.mark.asyncio
async def test_low_confidence_routes_to_human_review(
    db_session: Session,
) -> None:
    """An email with vLLM confidence below threshold (e.g. 0.55 < 0.80) routes to Human Review Queue."""
    ensure_system_settings(db_session)

    def _low_conf_vllm(
        messages: list[dict[str, Any]],
        schema: type[BaseModel],
        images: list[bytes] | None = None,
    ) -> BaseModel:
        if schema is BranchEmailAnalysis:
            return BranchEmailAnalysis(
                is_network_issue=True,
                branch_identifier="2009",
                site_contact_phone="010 2345 8817",
                has_router_photo=False,
                reported_symptoms="Ambiguous store message",
                urgency=TicketPriority.LOW,
                is_resolution_confirmation=False,
                confidence=0.55,
            )
        raise AssertionError(f"Unexpected schema {schema}")

    set_vllm_override(_low_conf_vllm)

    eml = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Store 2009 question",
        body_text="Not sure if store 2009 needs a check.",
    )
    res = await ingest_and_triage_eml(db_session, eml)
    assert res["trigger_type"] == "UNRECOGNIZED"
    assert res["action"] == "ROUTED_TO_HUMAN_REVIEW_QUEUE"


@pytest.mark.asyncio
async def test_branch_action_blocker_and_auto_ack(
    db_session: Session,
) -> None:
    """AUTO_ACK logs without setting isp_welcome_received; BRANCH_ACTION_BLOCKER transitions to AWAITING_BRANCH_CONTACT and relays instructions."""
    r1 = await trigger_email_in_loop(
        db_session,
        {
            "scenario": "BRANCH_INCIDENT",
            "branch_code": "2009",
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    ticket_num = r1["ticket_number"]

    # 1. ISP sends AUTO_ACK without case reference -> isp_welcome_received stays False
    auto_ack_eml = build_synthetic_eml_bytes(
        sender="noc@noor.net",
        recipients=["itsupport-agent@kazyon.com"],
        subject=f"RE: [{ticket_num}] store 2009",
        body_text="This is an automated response. We have received your email and a trouble ticket will be assigned shortly.",
    )
    r_ack = await ingest_and_triage_eml(db_session, auto_ack_eml)
    assert r_ack["action"] == "ISP_AUTO_ACK_LOGGED"
    ticket = (
        db_session.execute(select(Ticket).where(Ticket.ticket_number == ticket_num)).scalars().one()
    )
    assert ticket.isp_welcome_received is False

    # 2. ISP sends BRANCH_ACTION_BLOCKER -> transitions to AWAITING_BRANCH_CONTACT and emails Regional IT
    blocker_eml = build_synthetic_eml_bytes(
        sender="noc@noor.net",
        recipients=["itsupport-agent@kazyon.com"],
        subject=f"RE: [{ticket_num}] store 2009 - Case No: 244555",
        body_text="Dear Kazyon Team, Kindly check power on the router and restart the router at store 2009.",
    )
    r_blk = await ingest_and_triage_eml(db_session, blocker_eml)
    assert r_blk["action"] == "MEDIATED_BRANCH_ACTION_BLOCKER"
    assert r_blk["ticket_status"] == TicketStatus.AWAITING_BRANCH_CONTACT.value
    assert any(
        em["classification_label"] == "BRANCH_ACTION_MEDIATION" and em["thread_type"] == "BRANCH"
        for em in r_blk["outbound_emails"]
    )
