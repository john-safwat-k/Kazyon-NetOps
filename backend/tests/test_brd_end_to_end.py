"""End-to-End Integration Tests for BRD v5.0:
- 1,150-Store Excel Directory Seeder & IP Derivation (`10.<AB>.<CD>.1` / `.2`)
- Dual-Ping (`IP1`/`IP2`) + `ORANGE`/`WE` 4G Hub Traceroute Decision Tree
- Replication Dashboard HTML Parser & Regional IT Notification
- `.eml` Ingestion & Triage (`NOOR`, `ORANGE`, `WE` formats, Blockers, Closures)
- Jira-Style Kanban Board, 360° Ticket Detail, Escalations, and System Settings APIs
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.auth.service import ensure_initial_admin
from app.common.config import get_settings
from app.common.database import Base, get_db
from app.directory.seeder import derive_branch_ips, seed_branches_from_excel
from app.main import app


@pytest.fixture()
def client_and_db(tmp_path: Path) -> Generator[tuple[TestClient, Session], None, None]:
    db_file = tmp_path / f"test_brd_{uuid4().hex}.db"
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
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_excel_1150_store_seeder_and_ip_derivation(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, db = client_and_db
    headers = _admin_headers(client)

    ip1, ip2 = derive_branch_ips("2009")
    assert ip1 == "10.20.9.1"
    assert ip2 == "10.20.9.2"

    # Seed from Info/Copy of All store ISP (2).xlsx
    summary = seed_branches_from_excel(db, dry_run=False)
    assert summary.total_rows_parsed == 1150
    assert summary.by_isp["NOOR"] == 906
    assert summary.by_isp["ORANGE"] == 181
    assert summary.by_isp["WE"] == 63

    # Verify API returns 1,150 branches and 3 ISPs
    branches_resp = client.get("/api/v1/branches?limit=20", headers=headers)
    assert branches_resp.status_code == 200
    data = branches_resp.json()
    assert data["total"] == 1150
    assert len(data["items"]) == 20

    isps_resp = client.get("/api/v1/isps", headers=headers)
    assert isps_resp.status_code == 200
    isps = {i["name"]: i for i in isps_resp.json()}
    assert {"NOOR", "ORANGE", "WE"}.issubset(isps.keys())
    assert isps["NOOR"]["store_count"] == 906
    assert isps["ORANGE"]["four_g_hub_ip"] == "10.247.8.1"

    # Run full diagnostic test suite across all 1,150 seeded branches (including zero-padded IPs like 10.10.01.1)
    suite_1150 = client.post(
        "/api/v1/diagnostics/run-suite",
        headers=headers,
        json={"simulate_scenario": "AUTO"},
    )
    assert suite_1150.status_code == 200
    suite_body = suite_1150.json()
    assert suite_body["total_branches"] == 1150
    assert len(suite_body["items"]) == 1150


def test_dual_ping_and_4g_hub_traceroute_decision_tree(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_db
    headers = _admin_headers(client)

    # 1. ORANGE branch 1173 -> IP1 UP, IP2 DOWN, Traceroute hits 10.247.8.1 -> LOCAL_LOOP_DOWN_ON_4G
    r_4g = client.post(
        "/api/v1/diagnostics/run",
        headers=headers,
        json={"branch_code": "1173", "isp_name": "ORANGE", "simulate_scenario": "AUTO"},
    )
    assert r_4g.status_code == 200
    d_4g = r_4g.json()
    assert d_4g["diagnosis_code"] == "LOCAL_LOOP_DOWN_ON_4G"
    assert d_4g["ip_1_up"] is True
    assert d_4g["ip_2_up"] is False
    assert d_4g["four_g_hub_detected"] is True
    assert d_4g["detected_hub_ip"] == "10.247.8.1"

    # 2. NOOR branch 2009 -> IP1 DOWN, IP2 SKIPPED -> FULL_OUTAGE
    r_down = client.post(
        "/api/v1/diagnostics/run",
        headers=headers,
        json={"branch_code": "2009", "isp_name": "NOOR", "simulate_scenario": "AUTO"},
    )
    assert r_down.status_code == 200
    d_down = r_down.json()
    assert d_down["diagnosis_code"] == "FULL_OUTAGE"
    assert d_down["ip_1_up"] is False
    assert d_down["ip_2_up"] is None

    # 3. NOOR branch 1201 -> IP1 UP, IP2 DOWN -> INTERNAL_LAN_SWITCH
    r_lan = client.post(
        "/api/v1/diagnostics/run",
        headers=headers,
        json={"branch_code": "1201", "isp_name": "NOOR", "simulate_scenario": "AUTO"},
    )
    assert r_lan.status_code == 200
    d_lan = r_lan.json()
    assert d_lan["diagnosis_code"] == "INTERNAL_LAN_SWITCH"
    assert d_lan["ip_1_up"] is True
    assert d_lan["ip_2_up"] is False

    # 4. Healthy branch 1366 -> IP1 UP, IP2 UP -> PASS
    r_pass = client.post(
        "/api/v1/diagnostics/run",
        headers=headers,
        json={"branch_code": "1366", "isp_name": "NOOR", "simulate_scenario": "AUTO"},
    )
    assert r_pass.status_code == 200
    assert r_pass.json()["diagnosis_code"] == "PASS"


def test_tickets_360_detail_replication_eml_and_settings_endpoints(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, db = client_and_db
    headers = _admin_headers(client)
    seed_branches_from_excel(db, dry_run=False)

    # Dashboard summary starts clean with 0 demo tickets (Page 2)
    dash = client.get("/api/v1/dashboard/summary?range=7d", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["kpis"]["open"] == 0
    assert len(dash.json()["by_isp"]) == 3

    # Kanban & Tickets List starts with 0 demo tickets (Pages 3 & 4)
    tickets = client.get("/api/v1/tickets", headers=headers)
    assert tickets.status_code == 200
    assert tickets.json() == []

    # Create a real ticket for branch 1173 (ORANGE)
    created_resp = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "branch_code": "1173",
            "priority": "HIGH",
            "site_contact_phone": "010 2345 8817",
            "trigger_source": "DIRECT_EMAIL",
            "description": "Store 1173 local loop down.",
            "run_diagnostics": True,
        },
    )
    assert created_resp.status_code == 201
    ticket_num = created_resp.json()["id"]

    # Ticket 360° Detail (Page 5)
    detail = client.get(f"/api/v1/tickets/{ticket_num}", headers=headers)
    assert detail.status_code == 200
    d_body = detail.json()
    assert d_body["ticket_number"] == ticket_num
    assert d_body["branch"]["code"] == "1173"
    assert d_body["isp"]["name"] == "ORANGE"
    assert len(d_body["events"]) >= 1

    # Add internal note on the created ticket
    note_resp = client.post(
        f"/api/v1/tickets/{ticket_num}/notes",
        headers=headers,
        json={"note": "Checked with Cairo Regional IT; awaiting Orange field team."},
    )
    assert note_resp.status_code == 200
    assert any("Checked with Cairo" in ev["title"] for ev in note_resp.json()["events"])

    # Replication Dashboard HTML parser (Page 6)
    rep_parse = client.post(
        "/api/v1/replication/parse",
        headers=headers,
        json={
            "subject": "Replication Dashboard - 22/10/2026",
            "html_content": "<table><tr><td>1450</td><td>Soliman Metwaly</td><td>Assyut</td><td>21/10 21:14</td><td>21/10/2026</td><td>Not Updated</td></tr></table>",
            "dry_run": True,
        },
    )
    assert rep_parse.status_code == 200
    assert rep_parse.json()["not_updated_count"] == 1

    # Simulate real .eml file from Info/ (Page 8)
    samples_resp = client.get("/api/v1/emails/info-samples", headers=headers)
    assert samples_resp.status_code == 200
    samples = samples_resp.json()
    assert len(samples) >= 50

    sim_resp = client.post(
        f"/api/v1/emails/simulate-eml?sample_filename={samples[0]}",
        headers=headers,
    )
    assert sim_resp.status_code == 200
    assert "classification_label" in sim_resp.json()

    # Settings & Kill-Switch (Page 12)
    settings_get = client.get("/api/v1/settings", headers=headers)
    assert settings_get.status_code == 200
    assert settings_get.json()["global_ai_kill_switch"] is False

    settings_put = client.put(
        "/api/v1/settings",
        headers=headers,
        json={"global_ai_kill_switch": True, "confidence_threshold": 85},
    )
    assert settings_put.status_code == 200
    assert settings_put.json()["global_ai_kill_switch"] is True
    assert settings_put.json()["confidence_threshold"] == 85


def test_bulk_csv_and_excel_upload_template_export_delete_and_cross_screen_availability(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_db
    headers = _admin_headers(client)

    # 1. Download CSV and Excel templates
    tpl_csv = client.get("/api/v1/branches/template?format=csv", headers=headers)
    assert tpl_csv.status_code == 200
    assert "SAP Code" in tpl_csv.text

    tpl_xlsx = client.get("/api/v1/branches/template?format=xlsx", headers=headers)
    assert tpl_xlsx.status_code == 200
    assert len(tpl_xlsx.content) > 100

    # 2. Upload custom CSV with header mapping (dry-run preview first, then commit with replace_existing=True)
    csv_payload = (
        "SAP Code,Branch Name,ISP,L.L Circuit ID,3G / Backup ID,IP 1 (Router),IP 2 (Switch),Region,Regional IT Email\n"
        "3991,Tanta El Bahr,ORANGE,FTTH-3991,4G-3991,10.39.91.1,10.39.91.2,Delta,delta.it@kazyon.com\n"
        "4502,Ismailia Sultan,NOOR,1084502,3G-4502,,,Canal,canal.it@kazyon.com\n"
        "5100,Port Said Fouad,WE,066-5100,WE-4G-5100,10.51.0.1,10.51.0.2,Canal,canal.it@kazyon.com\n"
    ).encode("utf-8")

    dry_resp = client.post(
        "/api/v1/branches/seed-excel?dry_run=true&replace_existing=true",
        headers=headers,
        files={"file": ("custom_branches.csv", csv_payload, "text/csv")},
    )
    assert dry_resp.status_code == 200
    dry_data = dry_resp.json()
    assert dry_data["dry_run"] is True
    assert dry_data["total_rows_parsed"] == 3
    assert dry_data["created_count"] == 3
    assert len(dry_data["preview_rows"]) == 3
    # Verify auto-derived IPs for 4502
    row_4502 = next(r for r in dry_data["preview_rows"] if r["branch_code"] == "4502")
    assert row_4502["ip_1"] == "10.45.2.1"
    assert row_4502["ip_2"] == "10.45.2.2"

    # Commit CSV import
    commit_resp = client.post(
        "/api/v1/branches/seed-excel?dry_run=false&replace_existing=true",
        headers=headers,
        files={"file": ("custom_branches.csv", csv_payload, "text/csv")},
    )
    assert commit_resp.status_code == 200
    commit_data = commit_resp.json()
    assert commit_data["dry_run"] is False
    assert commit_data["created_count"] == 3
    assert commit_data["by_isp"] == {"ORANGE": 1, "NOOR": 1, "WE": 1}

    # 3. Verify uploaded branches appear in Directory & ISP counts
    list_resp = client.get("/api/v1/branches?limit=50", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert list_resp.json()["total"] == 3
    assert {b["branch_code"] for b in items} == {"3991", "4502", "5100"}

    # 4. Verify uploaded branches appear in Diagnostics Sandbox catalog & individual check modes work
    cat_resp = client.get("/api/v1/diagnostics/sandbox-catalog", headers=headers)
    assert cat_resp.status_code == 200
    cat_branches = {b["code"]: b for b in cat_resp.json()["branches"]}
    assert {"3991", "4502", "5100"}.issubset(cat_branches.keys())
    assert cat_branches["3991"]["region"] == "Delta"

    ping1_resp = client.post(
        "/api/v1/diagnostics/run",
        headers=headers,
        json={
            "branch_code": "3991",
            "isp_name": "ORANGE",
            "mode": "ping_ip1",
            "simulate_scenario": "LOCAL_LOOP_DOWN_ON_4G",
        },
    )
    assert ping1_resp.status_code == 200
    assert ping1_resp.json()["metrics_json"]["check_mode"] == "PING_IP1"
    assert ping1_resp.json()["ip_1_up"] is True
    assert ping1_resp.json()["ip_2_up"] is None
    assert len(ping1_resp.json()["steps"]) == 1
    assert ping1_resp.json()["diagnosis_title"] != ""

    # 4b. Run Full Fleet Diagnostic Test Suite across all uploaded branches
    suite_resp = client.post(
        "/api/v1/diagnostics/run-suite",
        headers=headers,
        json={"simulate_scenario": "AUTO"},
    )
    assert suite_resp.status_code == 200
    suite_data = suite_resp.json()
    assert suite_data["total_branches"] == 3
    assert len(suite_data["items"]) == 3
    assert len(suite_data["by_isp"]) == 3
    assert len(suite_data["by_region"]) == 2
    assert all(len(it["steps"]) == 3 for it in suite_data["items"])
    assert all(it["root_cause"] != "" for it in suite_data["items"])

    # 5. Verify manual ticket creation on uploaded branch 3991 with scenario override
    tk_resp = client.post(
        "/api/v1/tickets",
        headers=headers,
        json={
            "branch_code": "3991",
            "priority": "HIGH",
            "trigger_source": "DIRECT_EMAIL",
            "description": "Uploaded branch 3991 test outage",
            "run_diagnostics": True,
            "simulate_scenario": "LOCAL_LOOP_DOWN_ON_4G",
        },
    )
    assert tk_resp.status_code == 201
    assert "3991" in tk_resp.json()["branch"]
    assert tk_resp.json()["failure_code"] == "LOCAL_LOOP_DOWN_ON_4G"

    # 6. Verify Dashboard summary reflects total_branches and custom regions
    dash_resp = client.get("/api/v1/dashboard/summary?range=7d", headers=headers)
    assert dash_resp.status_code == 200
    assert dash_resp.json()["total_branches"] == 3
    assert "Delta" in dash_resp.json()["regions_list"]
    assert "Canal" in dash_resp.json()["regions_list"]

    # 7. Verify Replication Monitor parser matches uploaded branch 4502 and returns frontend fields
    rep_resp = client.post(
        "/api/v1/replication/parse",
        headers=headers,
        json={
            "subject": "Replication Dashboard - 22/10/2026",
            "html_content": (
                "<table><tr><td>4502</td><td>Ismailia Sultan</td><td>Canal</td>"
                "<td>21/10 21:14</td><td>21/10/2026</td><td>Not Updated</td></tr></table>"
            ),
            "dry_run": False,
        },
    )
    assert rep_resp.status_code == 200
    rep_json = rep_resp.json()
    assert rep_json["total_rows_parsed"] == 1
    assert rep_json["tickets_created"] == 1
    assert rep_json["emails_sent"] == 1

    # 8. Export CSV and Excel
    exp_csv = client.get("/api/v1/branches/export?format=csv", headers=headers)
    assert exp_csv.status_code == 200
    assert "Tanta El Bahr" in exp_csv.text

    exp_xlsx = client.get("/api/v1/branches/export?format=xlsx", headers=headers)
    assert exp_xlsx.status_code == 200
    assert len(exp_xlsx.content) > 100

    # 9. Delete branch 5100
    branch_5100_id = next(b["id"] for b in items if b["branch_code"] == "5100")
    del_resp = client.delete(f"/api/v1/branches/{branch_5100_id}", headers=headers)
    assert del_resp.status_code == 204
    after_del = client.get("/api/v1/branches?limit=50", headers=headers)
    assert after_del.json()["total"] == 2


def test_multi_turn_email_loop_harness_end_to_end(
    client_and_db: tuple[TestClient, Session],
) -> None:
    """Verify full multi-turn email loop across Branch & ISP threads with header/tag/case-ref correlation."""
    client, db = client_and_db
    headers = _admin_headers(client)
    seed_branches_from_excel(db, dry_run=False)

    # 1. Check loop status & poll-now endpoints
    st_resp = client.get("/api/v1/emails/loop-status", headers=headers)
    assert st_resp.status_code == 200
    assert "poll_interval_sec" in st_resp.json()

    poll_resp = client.post("/api/v1/emails/poll-now", headers=headers)
    assert poll_resp.status_code == 200
    assert "sla_chaser" in poll_resp.json()

    # 2. Turn 1A: Regional IT sends unplugged cable photo for branch 1188
    t1a = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={"scenario": "CABLE_UNPLUGGED_PHOTO", "branch_code": "1188"},
    )
    assert t1a.status_code == 200
    d1a = t1a.json()
    ticket_num = d1a["ticket_number"]
    assert ticket_num.startswith("NET-")
    assert d1a["ticket_status"] == "AWAITING_BRANCH"
    assert d1a["action"] == "REQUESTED_CABLE_RESEAT"
    assert len(d1a["outbound_emails"]) == 1
    cable_fix_mid = d1a["outbound_emails"][0]["message_id"]

    # 3. Turn 1B: Regional IT replies in-thread (In-Reply-To) after reseating cables -> Vision PASS -> Escalates to NOOR
    t1b = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "REGIONAL_IT_CABLE_FIXED",
            "branch_code": "1188",
            "in_reply_to": cable_fix_mid,
            "diagnostic_scenario": "FULL_OUTAGE",
        },
    )
    assert t1b.status_code == 200
    d1b = t1b.json()
    assert d1b["ticket_number"] == ticket_num
    assert d1b["correlation_method"] == "HEADER_IN_REPLY_TO"
    assert d1b["ticket_status"] == "ESCALATED_TO_ISP"
    assert len(d1b["outbound_emails"]) == 2  # ISP ESCALATION + BRANCH_ACK_ESCALATED

    # 4. Turn 2: ISP Welcome Mail with Case Ref -> Starts 4-6h loop
    t2 = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "ISP_WELCOME",
            "ticket_number": ticket_num,
            "branch_code": "1188",
        },
    )
    assert t2.status_code == 200
    d2 = t2.json()
    assert d2["ticket_number"] == ticket_num
    assert d2["isp_reference_number"] in {"244010", "1-1312322942540", "8407532"}
    assert d2["action"] == "ISP_WELCOME_RECORDED_4_6H_LOOP_STARTED"

    # 5. Turn 3A: ISP reports site contact phone is unreachable -> AWAITING_BRANCH_CONTACT
    t3a = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "ISP_CONTACT_UNREACHABLE",
            "ticket_number": ticket_num,
            "branch_code": "1188",
        },
    )
    assert t3a.status_code == 200
    d3a = t3a.json()
    assert d3a["ticket_status"] == "AWAITING_BRANCH_CONTACT"
    assert d3a["action"] == "MEDIATED_CONTACT_BLOCKER_WITH_BRANCH"
    assert any(
        em["classification_label"] == "CONTACT_BLOCKER_MEDIATION" for em in d3a["outbound_emails"]
    )

    # 6. Turn 3B: Regional IT replies with active phone 010 9988 7766 -> Relayed to ISP on ISP thread!
    t3b = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "REGIONAL_IT_NEW_PHONE",
            "ticket_number": ticket_num,
            "branch_code": "1188",
        },
    )
    assert t3b.status_code == 200
    d3b = t3b.json()
    assert d3b["ticket_status"] == "ESCALATED_TO_ISP"
    assert d3b["action"] == "RELAYED_CONTACT_TO_ISP"
    assert any(
        em["classification_label"] == "CONTACT_RELAY_TO_ISP" and em["thread_type"] == "ISP"
        for em in d3b["outbound_emails"]
    )

    # 7. Turn 4A: ISP claims closure prematurely while link is still DOWN -> Agent rejects closure!
    t4a = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "ISP_RESOLVED_STILL_DOWN",
            "ticket_number": ticket_num,
            "branch_code": "1188",
        },
    )
    assert t4a.status_code == 200
    d4a = t4a.json()
    assert d4a["ticket_status"] == "ESCALATED_TO_ISP"
    assert d4a["action"] == "REJECTED_PREMATURE_ISP_CLOSURE"
    assert any(
        em["classification_label"] == "ISP_REOPEN_FAILED_VERIFY" for em in d4a["outbound_emails"]
    )

    # 8. Turn 4B: ISP restores link and sends Ticket Closure -> Final verification PASS -> Closed!
    t4b = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={
            "scenario": "ISP_RESOLVED",
            "ticket_number": ticket_num,
            "branch_code": "1188",
        },
    )
    assert t4b.status_code == 200
    d4b = t4b.json()
    assert d4b["ticket_status"] == "CLOSED"
    assert d4b["action"] == "VERIFIED_AND_CLOSED"
    assert (
        len(d4b["outbound_emails"]) == 2
    )  # RESOLUTION_CONFIRMATION (BRANCH) + ISP_CLOSURE_ACK (ISP)

    # 9. Re-classify endpoint works on any ingested email
    recls = client.post(f"/api/v1/emails/{d4b['email_id']}/reclassify", headers=headers)
    assert recls.status_code == 200
    assert recls.json()["classification_label"] == "ISP_CLOSURE"

    # 10. Unrecognized email dispatches HUMAN_ESCALATION report and can be converted to a ticket on Page 7
    unrec = client.post(
        "/api/v1/emails/trigger",
        headers=headers,
        json={"scenario": "UNRECOGNIZED"},
    )
    assert unrec.status_code == 200
    dunrec = unrec.json()
    assert dunrec["action"] == "ROUTED_TO_HUMAN_REVIEW_QUEUE"
    assert any(
        em["classification_label"] == "HUMAN_ESCALATION" and em["thread_type"] == "HUMAN_ESCALATION"
        for em in dunrec["outbound_emails"]
    )
    conv = client.post(
        f"/api/v1/escalations/convert-email/{dunrec['email_id']}",
        headers=headers,
    )
    assert conv.status_code == 200
    assert conv.json()["ticket_number"].startswith("NET-")
    assert conv.json()["status"] == "NEEDS_HUMAN_REVIEW"
