"""Tests for the 3-Hour Proactive Fleet Diagnostic Scan, per-diagnosis flow initiation, safety guards, and Settings stop/start controls."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.agent.scheduler import is_within_store_window, run_scheduled_fleet_scan_if_due
from app.auth.service import ensure_initial_admin
from app.common.config import get_settings
from app.common.contracts import (
    ConnectionFailureType,
    EscalationReason,
    TicketStatus,
    TicketTriggerSource,
)
from app.common.database import Base, get_db
from app.directory.models import Branch
from app.main import app
from app.ticketing.models import FleetScanRun, Ticket, TicketEmail


@pytest.fixture()
def client_and_db(tmp_path: Path) -> Generator[tuple[TestClient, Session], None, None]:
    db_file = tmp_path / f"test_fleet_scan_{uuid4().hex}.db"
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


def test_settings_fleet_scan_configuration_and_stop_toggle(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """GET and PUT /api/v1/settings persist fleet_scan_enabled, 180m interval, Cairo window, and mass outage guard."""
    client, _ = client_and_db
    headers = _admin_headers(client)

    res_get = client.get("/api/v1/settings", headers=headers)
    assert res_get.status_code == 200
    body = res_get.json()
    assert body["fleet_scan_enabled"] is False
    assert body["fleet_scan_interval_minutes"] == 180
    assert body["fleet_scan_window_start"] == "08:00"
    assert body["fleet_scan_window_end"] == "23:00"
    assert body["fleet_scan_mass_outage_pct"] == 5

    # Enable 3-hour proactive fleet scan
    res_enable = client.put(
        "/api/v1/settings",
        headers=headers,
        json={
            "fleet_scan_enabled": True,
            "fleet_scan_interval_minutes": 180,
            "fleet_scan_window_start": "08:00",
            "fleet_scan_window_end": "23:00",
            "fleet_scan_mass_outage_pct": 5,
        },
    )
    assert res_enable.status_code == 200
    assert res_enable.json()["fleet_scan_enabled"] is True

    # Stop proactive fleet scan from Settings
    res_stop = client.put(
        "/api/v1/settings",
        headers=headers,
        json={"fleet_scan_enabled": False},
    )
    assert res_stop.status_code == 200
    assert res_stop.json()["fleet_scan_enabled"] is False


def test_proactive_fleet_scan_starts_flows_by_diagnosis_and_deduplicates(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """Running the Proactive Fleet Scan opens PROACTIVE_SCAN tickets and routes FULL_OUTAGE, LOCAL_LOOP_DOWN_ON_4G, and INTERNAL_LAN_SWITCH appropriately, while skipping open duplicates on a second scan."""
    client, db = client_and_db
    headers = _admin_headers(client)

    # Run a full proactive scan in AUTO mode (6 simulated failing stores out of 1,150 = 0.52% < 5% guard)
    res_scan = client.post(
        "/api/v1/settings/fleet-scans/run-now",
        headers=headers,
        json={"dry_run": False, "simulate_scenario": "AUTO", "limit": 2000},
    )
    assert res_scan.status_code == 200
    scan_data = res_scan.json()
    assert scan_data["status"] == "COMPLETED"
    assert scan_data["total_branches"] >= 1000
    assert scan_data["confirmed_down"] == 6
    assert scan_data["duplicates_skipped"] == 0
    assert len(scan_data["created_ticket_numbers"]) == 6

    db.expire_all()

    # 1. FULL_OUTAGE branch (e.g. 2009) -> AWAITING_REGIONAL_IT + email to Regional IT
    b_full = db.execute(select(Branch).where(Branch.branch_code == "2009")).scalar_one()
    t_full = db.execute(
        select(Ticket).where(Ticket.branch_id == b_full.id).order_by(Ticket.id.desc())
    ).scalar_one()
    assert t_full.trigger_source == TicketTriggerSource.PROACTIVE_SCAN.value
    assert t_full.connection_failure_type == ConnectionFailureType.FULL_OUTAGE.value
    assert t_full.status == TicketStatus.AWAITING_REGIONAL_IT.value
    em_full = (
        db.execute(
            select(TicketEmail).where(
                TicketEmail.ticket_id == t_full.id,
                TicketEmail.thread_type == "BRANCH",
            )
        )
        .scalars()
        .all()
    )
    assert len(em_full) == 1
    assert em_full[0].classification_label == "REGIONAL_IT_NOTIFY"

    # 2. LOCAL_LOOP_DOWN_ON_4G branch (e.g. 1173) -> ESCALATED_TO_ISP + ISP escalation + Branch phone request
    b_4g = db.execute(select(Branch).where(Branch.branch_code == "1173")).scalar_one()
    t_4g = db.execute(
        select(Ticket).where(Ticket.branch_id == b_4g.id).order_by(Ticket.id.desc())
    ).scalar_one()
    assert t_4g.trigger_source == TicketTriggerSource.PROACTIVE_SCAN.value
    assert t_4g.connection_failure_type == ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value
    assert t_4g.status == TicketStatus.ESCALATED_TO_ISP.value
    em_4g_isp = (
        db.execute(
            select(TicketEmail).where(
                TicketEmail.ticket_id == t_4g.id,
                TicketEmail.thread_type == "ISP",
            )
        )
        .scalars()
        .all()
    )
    assert len(em_4g_isp) == 1
    assert em_4g_isp[0].classification_label == "ESCALATION"

    # 3. INTERNAL_LAN_SWITCH branch (e.g. 1201) -> INTERNAL_LAN_ISSUE + Regional IT alert (no ISP email)
    b_lan = db.execute(select(Branch).where(Branch.branch_code == "1201")).scalar_one()
    t_lan = db.execute(
        select(Ticket).where(Ticket.branch_id == b_lan.id).order_by(Ticket.id.desc())
    ).scalar_one()
    assert t_lan.trigger_source == TicketTriggerSource.PROACTIVE_SCAN.value
    assert t_lan.connection_failure_type == ConnectionFailureType.INTERNAL_LAN_SWITCH.value
    assert t_lan.status == TicketStatus.INTERNAL_LAN_ISSUE.value
    em_lan_isp = (
        db.execute(
            select(TicketEmail).where(
                TicketEmail.ticket_id == t_lan.id,
                TicketEmail.thread_type == "ISP",
            )
        )
        .scalars()
        .all()
    )
    assert len(em_lan_isp) == 0

    # 4. Second scan skips all 6 open tickets (no duplicates)
    res_scan2 = client.post(
        "/api/v1/settings/fleet-scans/run-now",
        headers=headers,
        json={"dry_run": False, "simulate_scenario": "AUTO", "limit": 2000},
    )
    assert res_scan2.status_code == 200
    scan2_data = res_scan2.json()
    assert scan2_data["confirmed_down"] == 6
    assert scan2_data["duplicates_skipped"] == 6
    assert scan2_data["created_ticket_numbers"] == []


def test_proactive_fleet_scan_mass_outage_circuit_breaker(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """When failing branches exceed fleet_scan_mass_outage_pct (e.g. FULL_OUTAGE across fleet), MASS_OUTAGE_GUARD trips and zero store tickets are created."""
    client, db = client_and_db
    headers = _admin_headers(client)

    res_scan = client.post(
        "/api/v1/settings/fleet-scans/run-now",
        headers=headers,
        json={"dry_run": False, "simulate_scenario": "FULL_OUTAGE", "limit": 50},
    )
    assert res_scan.status_code == 200
    data = res_scan.json()
    assert data["status"] == "MASS_OUTAGE_GUARD"
    assert data["confirmed_down"] == 50
    assert data["created_ticket_numbers"] == []

    db.expire_all()
    proactive_tickets = (
        db.execute(
            select(Ticket).where(Ticket.trigger_source == TicketTriggerSource.PROACTIVE_SCAN.value)
        )
        .scalars()
        .all()
    )
    assert len(proactive_tickets) == 0

    # Verify MASS_OUTAGE_SUSPECTED alert email was recorded
    alert_emails = (
        db.execute(
            select(TicketEmail).where(
                TicketEmail.classification_label == EscalationReason.MASS_OUTAGE_SUSPECTED.value
            )
        )
        .scalars()
        .all()
    )
    assert len(alert_emails) == 1


def test_proactive_fleet_scan_two_strike_retest_recovery(
    client_and_db: tuple[TestClient, Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A branch that fails the initial 1-ping sweep due to transient packet loss but passes on the 4-ping confirmation re-test is counted in recovered_on_retest and opens no ticket."""
    import app.agent.workflow as wf_mod

    client, _ = client_and_db
    headers = _admin_headers(client)

    orig_exec = wf_mod.execute_dual_ping_and_traceroute

    async def _retest_always_passes(**kwargs: Any) -> dict[str, Any]:
        kwargs["simulate_scenario"] = "PASS"
        return await orig_exec(**kwargs)

    monkeypatch.setattr(wf_mod, "execute_dual_ping_and_traceroute", _retest_always_passes)

    res_scan = client.post(
        "/api/v1/settings/fleet-scans/run-now",
        headers=headers,
        json={"dry_run": False, "simulate_scenario": "AUTO", "limit": 2000},
    )
    assert res_scan.status_code == 200
    data = res_scan.json()
    assert data["status"] == "COMPLETED"
    assert data["failing_initial"] == 6
    assert data["recovered_on_retest"] == 6
    assert data["confirmed_down"] == 0
    assert data["created_ticket_numbers"] == []


@pytest.mark.anyio
async def test_scheduler_respects_enabled_flag_store_window_and_3h_interval(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """run_scheduled_fleet_scan_if_due skips when disabled, outside Cairo store window, or before 180 minutes have elapsed."""
    _, db = client_and_db

    # 1. Cairo window check: 10:00 UTC is 12:00/13:00 Cairo (inside 08:00-23:00); 01:00 UTC is 03:00/04:00 Cairo (outside)
    day_utc = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)
    night_utc = datetime(2026, 10, 27, 1, 0, tzinfo=timezone.utc)
    assert is_within_store_window(day_utc, "08:00", "23:00") is True
    assert is_within_store_window(night_utc, "08:00", "23:00") is False

    # 2. Disabled by default -> skipped
    res_disabled = await run_scheduled_fleet_scan_if_due(db, now_utc=day_utc)
    assert res_disabled["skipped"] is True
    assert res_disabled["reason"] == "fleet_scan_disabled"

    # 3. Enable fleet_scan_enabled, but test outside store window -> skipped
    from app.ticketing.service import ensure_system_settings

    settings_row = ensure_system_settings(db)
    settings_row.fleet_scan_enabled = True
    settings_row.fleet_scan_interval_minutes = 180
    db.commit()

    res_outside = await run_scheduled_fleet_scan_if_due(db, now_utc=night_utc)
    assert res_outside["skipped"] is True
    assert res_outside["reason"] == "outside_store_hours_window"

    # 4. Insert a recent FleetScanRun 60 minutes ago (< 180m interval) -> skipped
    recent_run = FleetScanRun(
        suite_id="SUITE-TEST",
        triggered_by="SCHEDULER",
        status="COMPLETED",
        total_branches=1150,
        failing_initial=0,
        recovered_on_retest=0,
        confirmed_down=0,
        duplicates_skipped=0,
        created_ticket_numbers=[],
        summary="Test run",
        details_json={},
        started_at=datetime(2026, 10, 27, 9, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 10, 27, 9, 1, tzinfo=timezone.utc),
    )
    db.add(recent_run)
    db.commit()

    res_not_elapsed = await run_scheduled_fleet_scan_if_due(db, now_utc=day_utc)
    assert res_not_elapsed["skipped"] is True
    assert res_not_elapsed["reason"] == "interval_not_elapsed"
    assert res_not_elapsed["minutes_until_next"] == 120.0
