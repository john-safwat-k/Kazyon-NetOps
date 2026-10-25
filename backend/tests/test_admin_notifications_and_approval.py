"""Tests for Admin Action Email Notifications on every agent action and Ask-Before-Acting Approval Mode."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.auth.service import ensure_initial_admin
from app.common.config import get_settings
from app.common.database import Base, get_db
from app.main import app
from app.ticketing.models import Ticket, TicketEmail, TicketEvent


@pytest.fixture()
def client_and_db(tmp_path: Path) -> Generator[tuple[TestClient, Session], None, None]:
    db_file = tmp_path / f"test_admin_approval_{uuid4().hex}.db"
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

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client, session
    app.dependency_overrides.clear()
    session.close()
    test_engine.dispose()


def _admin_headers(client: TestClient) -> dict[str, str]:
    settings = get_settings()
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_settings_admin_notification_and_execution_mode_roundtrip(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """GET and PUT /api/v1/settings persist admin_notification_email, notify_admin_on_every_action, and require_admin_approval_before_action."""
    client, _ = client_and_db
    headers = _admin_headers(client)

    res_get = client.get("/api/v1/settings", headers=headers)
    assert res_get.status_code == 200
    body = res_get.json()
    assert body["admin_notification_email"]
    assert body["notify_admin_on_every_action"] is True
    assert body["require_admin_approval_before_action"] is False

    res_put = client.put(
        "/api/v1/settings",
        headers=headers,
        json={
            "admin_notification_email": "chief-admin@kazyon.com",
            "notify_admin_on_every_action": True,
            "require_admin_approval_before_action": True,
        },
    )
    assert res_put.status_code == 200
    updated = res_put.json()
    assert updated["admin_notification_email"] == "chief-admin@kazyon.com"
    assert updated["notify_admin_on_every_action"] is True
    assert updated["require_admin_approval_before_action"] is True


def test_autonomous_mode_sends_admin_email_on_every_agent_action(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """In Proceed Without Asking mode, every agent action emails an [AGENT ACTION REPORT] to the configured admin email."""
    client, db_session = client_and_db
    headers = _admin_headers(client)

    client.put(
        "/api/v1/settings",
        headers=headers,
        json={
            "admin_notification_email": "ops-admin@kazyon.com",
            "notify_admin_on_every_action": True,
            "require_admin_approval_before_action": False,
        },
    )

    # 1. Trigger a Branch Outage (Full Outage -> Escalate to ISP)
    res_inc = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "BRANCH_INCIDENT",
            "branch_code": "2009",
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    assert res_inc.status_code == 200
    inc_data = res_inc.json()
    ticket_number = inc_data["ticket_number"]
    assert inc_data["ticket_status"] == "ESCALATED_TO_ISP"
    assert len(inc_data["outbound_emails"]) == 2
    assert inc_data["admin_notification"] is not None
    assert inc_data["admin_notification"]["to"] == "ops-admin@kazyon.com"
    assert inc_data["admin_notification"]["classification_label"] == "ADMIN_ACTION_NOTIFICATION"
    assert "[AGENT ACTION REPORT]" in inc_data["admin_notification"]["subject"]

    # 2. Trigger ISP Welcome reply -> also sends Admin Action Report
    res_wel = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "ISP_WELCOME",
            "ticket_number": ticket_number,
            "branch_code": "2009",
        },
    )
    assert res_wel.status_code == 200
    wel_data = res_wel.json()
    assert wel_data["action"] == "ISP_WELCOME_RECORDED_4_6H_LOOP_STARTED"
    assert wel_data["admin_notification"] is not None
    assert wel_data["admin_notification"]["to"] == "ops-admin@kazyon.com"
    assert "ISP_WELCOME_RECORDED_4_6H_LOOP_STARTED" in wel_data["admin_notification"]["subject"]

    # 3. Trigger ISP Resolved -> Final verification PASS -> Closes ticket & sends Admin Action Report
    res_res = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "ISP_RESOLVED",
            "ticket_number": ticket_number,
            "branch_code": "2009",
            "diagnostic_scenario": "PASS",
        },
    )
    assert res_res.status_code == 200
    res_data = res_res.json()
    assert res_data["ticket_status"] == "CLOSED"
    assert res_data["admin_notification"] is not None
    assert "VERIFIED_AND_CLOSED" in res_data["admin_notification"]["subject"]

    # Verify all 3 ADMIN_NOTIFICATION emails were persisted in DB for this ticket
    db_session.expire_all()
    ticket = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == ticket_number)
    ).scalar_one()
    admin_emails = (
        db_session.execute(
            select(TicketEmail).where(
                TicketEmail.ticket_id == ticket.id,
                TicketEmail.thread_type == "ADMIN_NOTIFICATION",
            )
        )
        .scalars()
        .all()
    )
    assert len(admin_emails) == 3


def test_ask_before_acting_mode_approve_and_reject_workflows(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """When require_admin_approval_before_action=True, agent runs diagnostics first, pauses for approval, and executes only on approveAction (or aborts on rejectAction)."""
    client, db_session = client_and_db
    headers = _admin_headers(client)

    client.put(
        "/api/v1/settings",
        headers=headers,
        json={
            "admin_notification_email": "approver-admin@kazyon.com",
            "notify_admin_on_every_action": True,
            "require_admin_approval_before_action": True,
        },
    )

    # Part A: Test Approve & Execute workflow on branch 1173
    res_inc = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "BRANCH_INCIDENT",
            "branch_code": "1173",
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    assert res_inc.status_code == 200
    inc_data = res_inc.json()
    ticket_number = inc_data["ticket_number"]

    # Verify agent paused before sending ISP/Branch outbound emails
    assert inc_data["action"] == "AWAITING_ADMIN_APPROVAL"
    assert inc_data["ticket_status"] == "NEEDS_HUMAN_REVIEW"
    assert inc_data["outbound_emails"] == []
    assert inc_data["admin_notification"] is not None
    assert inc_data["admin_notification"]["to"] == "approver-admin@kazyon.com"
    assert inc_data["admin_notification"]["classification_label"] == "ADMIN_APPROVAL_REQUEST"
    assert "[ADMIN APPROVAL REQUIRED]" in inc_data["admin_notification"]["subject"]

    # Check Ticket 360 Detail exposes pending_admin_action and draft emails
    detail_res = client.get(f"/api/v1/tickets/{ticket_number}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["escalation_reason"] == "ADMIN_APPROVAL_REQUIRED"
    assert detail["pending_admin_action"] is not None
    assert detail["pending_admin_action"]["target_status"] == "ESCALATED_TO_ISP"
    assert len(detail["pending_admin_action"]["proposed_emails"]) == 2
    assert len(detail["isp_emails"]) == 0

    # Check Human Review Queue lists the ticket with primary_action="Approve & Execute"
    esc_res = client.get("/api/v1/escalations", headers=headers)
    assert esc_res.status_code == 200
    esc_items = [e for e in esc_res.json() if e["ticket_number"] == ticket_number]
    assert len(esc_items) == 1
    assert esc_items[0]["reason"] == "ADMIN_APPROVAL_REQUIRED"
    assert esc_items[0]["primary_action"] == "Approve & Execute"
    assert esc_items[0]["pending_admin_action"] is not None

    # Approve the pending action via POST /api/v1/tickets/{ticket_number}/approve-action
    approve_res = client.post(
        f"/api/v1/tickets/{ticket_number}/approve-action",
        headers=headers,
    )
    assert approve_res.status_code == 200
    approved_detail = approve_res.json()
    assert approved_detail["status"] == "ESCALATED_TO_ISP"
    assert approved_detail["ai_automation_enabled"] is True
    assert approved_detail["pending_admin_action"] is None
    assert approved_detail["escalation_reason"] is None
    assert len(approved_detail["isp_emails"]) == 1
    assert any(e["outbound"] for e in approved_detail["branch_emails"])

    # Part B: Test Reject Action workflow on branch 2060
    res_inc2 = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "BRANCH_INCIDENT",
            "branch_code": "2060",
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    assert res_inc2.status_code == 200
    inc2_data = res_inc2.json()
    ticket2_number = inc2_data["ticket_number"]
    assert inc2_data["action"] == "AWAITING_ADMIN_APPROVAL"
    assert inc2_data["ticket_status"] == "NEEDS_HUMAN_REVIEW"
    assert inc2_data["outbound_emails"] == []

    # Reject the pending action via POST /api/v1/tickets/{ticket_number}/reject-action
    reject_res = client.post(
        f"/api/v1/tickets/{ticket2_number}/reject-action",
        headers=headers,
    )
    assert reject_res.status_code == 200
    rejected_detail = reject_res.json()
    assert rejected_detail["status"] == "DIAGNOSING"
    assert rejected_detail["ai_automation_enabled"] is False
    assert rejected_detail["pending_admin_action"] is None
    # No ISP emails were sent!
    assert len(rejected_detail["isp_emails"]) == 0
    # Timeline recorded admin_action_rejected
    db_session.expire_all()
    ticket2 = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == ticket2_number)
    ).scalar_one()
    events2 = (
        db_session.execute(select(TicketEvent).where(TicketEvent.ticket_id == ticket2.id))
        .scalars()
        .all()
    )
    assert any(ev.event_type == "admin_action_rejected" for ev in events2)
