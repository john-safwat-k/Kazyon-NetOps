"""Tests for full email thread reply parsing/reading and automatic Branch Regional IT CC on all branch emails."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.agent.vllm_client import set_vllm_override
from app.agent.workflow import ingest_and_triage_eml, process_replication_dashboard_report
from app.auth.models import User
from app.auth.service import ensure_initial_admin
from app.common.database import Base
from app.directory.models import Branch
from app.directory.seeder import seed_branches_from_excel
from app.directory.service import get_branch_by_code
from app.email_engine import imap_poller
from app.email_engine.parser import (
    build_synthetic_eml_bytes,
    parse_eml_bytes,
    split_email_thread_replies,
)
from app.email_engine.smtp_sender import (
    dispatch_outbound_email,
    resolve_branch_regional_it_cc,
)
from app.ticketing.models import Ticket, TicketEmail
from app.ticketing.schemas import TicketEmailReplyRequest
from app.ticketing.service import (
    ensure_system_settings,
    get_ticket_360_detail,
    list_mailbox_triage_logs,
    send_ticket_manual_reply,
)
from tests.conftest import default_fake_vllm_responder


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_file = tmp_path / f"thread_and_cc_{uuid4().hex}.db"
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
    ensure_system_settings(session)
    try:
        yield session
    finally:
        session.close()
        test_engine.dispose()


def test_split_email_thread_replies_parses_all_separators_and_real_info_eml() -> None:
    """Verify `split_email_thread_replies` splits Outlook headers, `On ... wrote:`, and dividers into individual replies."""
    thread_body = (
        "Dear Network Support,\n"
        "We restarted the router and plugged in the WAN cable as requested.\n\n"
        "On 25/10/2026 10:15 AM, Kazyon NetOps Agent <itsupport-agent@kazyon.com> wrote:\n"
        "> Kindly check router power and reply with update.\n\n"
        "From: GITSupport@kazyon.com\n"
        "Sent: Sunday, October 25, 2026 9:40 AM\n"
        "To: itsupport-agent@kazyon.com\n"
        "Subject: Store 2009 offline\n\n"
        "Store 2009 is offline since 9 AM.\n"
        "Site contact: 010 5566 7788\n"
        "-----Original Message-----\n"
        "From: store2009@kazyon.com\n"
        "Sent: Sunday, October 25, 2026 9:15 AM\n"
        "Subject: POS offline\n\n"
        "POS machines are not syncing at store 2009."
    )
    replies = split_email_thread_replies(thread_body)
    assert len(replies) == 4
    assert replies[0]["is_latest"] is True
    assert "restarted the router" in replies[0]["body"]
    assert "Kindly check router power" in replies[1]["body"]
    assert "010 5566 7788" in replies[2]["body"]
    assert "POS machines are not syncing" in replies[3]["body"]

    # Also verify real multi-reply .eml in Info/
    info_dir = Path(__file__).resolve().parent.parent.parent / "Info"
    multi_eml = info_dir / "Re_ [Request ID _##RE-8407532##] _ Kazyon #E33209 #6181183 #6203901 #1251.eml"
    if multi_eml.exists():
        env = parse_eml_bytes(multi_eml.read_bytes())
        real_replies = split_email_thread_replies(env.body_text)
        assert len(real_replies) >= 15
        assert real_replies[0]["is_latest"] is True
        assert all(bool(r["body"]) for r in real_replies)


@pytest.mark.asyncio
async def test_agent_reads_full_email_thread_and_every_reply_for_context(
    db_session: Session,
) -> None:
    """Verify the classifier and workflow read every reply in the email thread AND prior DB emails on the ticket."""
    captured_prompts: list[str] = []

    def inspecting_vllm_responder(
        messages: list[dict[str, Any]],
        schema: type[Any],
        images: list[bytes] | None = None,
    ) -> Any:
        user_msg = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") != "system")
        captured_prompts.append(user_msg)
        return default_fake_vllm_responder(messages, schema, images)

    set_vllm_override(inspecting_vllm_responder)

    # Build an email thread where the top reply only says "Still down, router photo attached"
    # while the store code (2009) and site contact phone (010 8877 6655) are in Reply #2 and Reply #3 of the thread!
    multi_reply_body = (
        "Dear IT Support,\n"
        "The link is still down after checking the router. Router photo is attached.\n\n"
        "On 25/10/2026 11:00 AM, Regional IT <GITSupport@kazyon.com> wrote:\n"
        "> Active shift manager site contact phone is 010 8877 6655.\n\n"
        "From: store2009@kazyon.com\n"
        "Sent: Sunday, October 25, 2026 10:30 AM\n"
        "To: GITSupport@kazyon.com\n"
        "Subject: Network issue\n\n"
        "Dear Regional IT, store 2009 network is completely down."
    )
    raw_eml = build_synthetic_eml_bytes(
        sender="GITSupport@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="FW: Network issue",
        body_text=multi_reply_body,
        attachment_filenames=["router_seated.jpg"],
    )

    res = await ingest_and_triage_eml(
        db_session,
        raw_eml,
        filename="thread_multi_reply.eml",
        diagnostic_scenario="FULL_OUTAGE",
        _from_harness=True,
    )

    assert res["branch_code"] == "2009"
    assert res["ticket_number"].startswith("NET-")
    assert res["triage"]["site_contact_phone"] == "010 8877 6655"
    assert res["triage"]["raw_analysis"]["thread_reply_count"] == 3
    assert len(res["triage"]["raw_analysis"]["thread_replies"]) == 3

    # Verify the LLM prompt included both Fresh Body and Thread Replies / Full Thread Body
    assert any("Thread Replies (3 in email" in p and "Full Thread Body:" in p for p in captured_prompts)

    # Verify the ISP escalation email used the phone number extracted from Reply #2 of the thread
    ticket = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == res["ticket_number"])
    ).scalar_one()
    assert ticket.site_contact_phone == "010 8877 6655"
    isp_outbound = db_session.execute(
        select(TicketEmail).where(
            TicketEmail.ticket_id == ticket.id,
            TicketEmail.thread_type == "ISP",
            TicketEmail.direction == "OUTBOUND",
        )
    ).scalar_one()
    assert "010 8877 6655" in isp_outbound.body_text


def test_imap_poller_does_not_skip_replies_matching_in_reply_to(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify `_fetch_unseen_imap_messages_sync` only deduplicates on the message's own `Message-ID`,
    never skipping a thread reply whose `In-Reply-To` or `References` contains an already-ingested `Message-ID`."""
    parent_mid = "<parent-msg-001@kazyon.com>"
    reply_mid = "<reply-msg-002@kazyon.com>"

    # Simulate parent_mid already ingested
    monkeypatch.setattr(imap_poller, "_ingested_imap_mids", {parent_mid.lower()})

    reply_eml_bytes = build_synthetic_eml_bytes(
        sender="user@gmail.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Re: Follow up",
        body_text="We restarted the router and active phone is 010 1234 5678.",
        message_id=reply_mid,
        in_reply_to=parent_mid,
        references=[parent_mid],
    )
    raw_header_peek = (
        f"Message-ID: {reply_mid}\r\n"
        f"In-Reply-To: {parent_mid}\r\n"
        f"References: {parent_mid}\r\n"
        "From: user@gmail.com\r\n"
        "Subject: Re: Follow up\r\n\r\n"
    ).encode("utf-8")

    class FakeImapConn:
        def __init__(self, host: str, port: int) -> None:
            self.host = host
            self.port = port

        def login(self, username: str, password: str) -> tuple[str, list[bytes]]:
            return "OK", [b"Logged in"]

        def select(self, folder: str) -> tuple[str, list[bytes]]:
            return "OK", [b"1"]

        def search(self, charset: Any, criterion: str) -> tuple[str, list[bytes]]:
            return "OK", [b"1"]

        def fetch(self, num: str, query: str) -> tuple[str, list[ Any]]:
            if "HEADER.FIELDS" in query:
                return "OK", [(b"1 (BODY[HEADER.FIELDS] {180}", raw_header_peek), b")"]
            return "OK", [(b"1 (BODY[] {500}", reply_eml_bytes), b")"]

        def logout(self) -> tuple[str, list[bytes]]:
            return "BYE", [b"Logging out"]

    monkeypatch.setattr(imap_poller.imaplib, "IMAP4_SSL", FakeImapConn)

    fetched = imap_poller._fetch_unseen_imap_messages_sync(
        host="imap.gmail.com",
        port=993,
        username="itsupport-agent@kazyon.com",
        password="secret",
        use_ssl=True,
        folder="INBOX",
    )
    assert len(fetched) == 1
    fname, fetched_bytes = fetched[0]
    parsed = parse_eml_bytes(fetched_bytes)
    assert parsed.message_id == reply_mid
    assert parsed.in_reply_to == parent_mid


@pytest.mark.asyncio
async def test_every_outbound_email_to_branch_ccs_regional_it_email(
    db_session: Session,
) -> None:
    """Verify that every email sent to a branch (`thread_type == 'BRANCH'`) across all workflows and manual replies
    CCs the branch's Regional IT email (`branch.regional_it_email`)."""
    branch_2009: Branch | None = get_branch_by_code(db_session, "2009")
    assert branch_2009 is not None
    expected_reg_it = branch_2009.regional_it_email
    assert expected_reg_it  # e.g. GITSupport@kazyon.com
    assert resolve_branch_regional_it_cc(branch_2009, db=db_session) == [expected_reg_it]

    # 1. Replication Dashboard notification (store 1173 -> CITSupport@kazyon.com)
    branch_1173 = get_branch_by_code(db_session, "1173")
    assert branch_1173 is not None
    rep_html = (
        "<table>"
        "<tr><th>ID</th><th>Store Name</th><th>Region</th><th>Last Trans.</th><th>Buss. Date</th><th>Status</th></tr>"
        f"<tr><td>1173</td><td>{branch_1173.name}</td><td>{branch_1173.region}</td>"
        "<td>21:15</td><td>Today</td><td>Not Updated</td></tr>"
        "</table>"
    )
    rep_res = await process_replication_dashboard_report(
        db_session,
        subject="Replication Dashboard - 25/10/2026",
        html_content=rep_html,
        dry_run=False,
    )
    rep_ticket_num = rep_res["created_ticket_numbers"][0]
    rep_ticket = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == rep_ticket_num)
    ).scalar_one()
    rep_branch_email = db_session.execute(
        select(TicketEmail).where(
            TicketEmail.ticket_id == rep_ticket.id,
            TicketEmail.thread_type == "BRANCH",
            TicketEmail.direction == "OUTBOUND",
        )
    ).scalar_one()
    assert branch_1173.regional_it_email in (rep_branch_email.cc or [])
    assert branch_1173.regional_it_email in (rep_branch_email.raw_headers or {}).get("Cc", "")

    # 2. Store sender (`store2009@kazyon.com`) sends an unplugged cable photo -> CABLE_FIX_REQUEST CCs GITSupport@kazyon.com
    unplugged_eml = build_synthetic_eml_bytes(
        sender="store2009@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject="Store 2009 network down",
        body_text=(
            "Dear Network Support,\n"
            "Store 2009 is offline. Router photo attached (WAN cable loose/unplugged).\n"
            "Site contact: 010 2345 8817"
        ),
        attachment_filenames=["router_2009_unplugged.jpg"],
    )
    res_unplugged = await ingest_and_triage_eml(
        db_session,
        unplugged_eml,
        filename="store2009_unplugged.eml",
        diagnostic_scenario="FULL_OUTAGE",
        _from_harness=True,
    )
    assert res_unplugged["action"] == "REQUESTED_CABLE_RESEAT"
    cable_out = res_unplugged["outbound_emails"][0]
    assert cable_out["thread_type"] == "BRANCH"
    assert cable_out["to"] == "store2009@kazyon.com"
    assert expected_reg_it in cable_out["cc"]

    # 3. Store replies with seated router photo -> escalates to ISP and sends BRANCH_ACK_ESCALATED to store2009@kazyon.com with CC to GITSupport@kazyon.com
    ticket_num = res_unplugged["ticket_number"]
    seated_eml = build_synthetic_eml_bytes(
        sender="store2009@kazyon.com",
        recipients=["itsupport-agent@kazyon.com"],
        subject=f"RE: [{ticket_num}] Store 2009 network down",
        body_text=(
            "Dear Network Support,\n"
            "We reseated all router cables and power LED is green. Fresh photo attached.\n"
            "Site contact: 010 2345 8817"
        ),
        in_reply_to=cable_out["message_id"],
        attachment_filenames=["router_2009_seated.jpg"],
    )
    res_seated = await ingest_and_triage_eml(
        db_session,
        seated_eml,
        filename="store2009_seated.eml",
        diagnostic_scenario="FULL_OUTAGE",
        _from_harness=True,
    )
    branch_acks = [o for o in res_seated["outbound_emails"] if o["thread_type"] == "BRANCH"]
    assert len(branch_acks) == 1
    assert branch_acks[0]["to"] == "store2009@kazyon.com"
    assert expected_reg_it in branch_acks[0]["cc"]

    # 4. ISP reports site contact unreachable -> CONTACT_BLOCKER_MEDIATION email to branch CCs GITSupport@kazyon.com
    isp_unreachable_eml = build_synthetic_eml_bytes(
        sender="noc@noor.net",
        recipients=["itsupport-agent@kazyon.com"],
        subject="NOOR NOC - Case No: 244010 - KAZYON - 2009 - Ticket Update",
        body_text=(
            "Dear Kazyon Team,\n"
            "Regarding store 2009 (Case #244010), we tried to call the site contact but the phone is switched off / unreachable."
        ),
    )
    res_unreach = await ingest_and_triage_eml(
        db_session,
        isp_unreachable_eml,
        filename="isp_unreach.eml",
        _from_harness=True,
    )
    assert res_unreach["action"] == "MEDIATED_CONTACT_BLOCKER_WITH_BRANCH"
    med_out = res_unreach["outbound_emails"][0]
    assert med_out["thread_type"] == "BRANCH"
    assert expected_reg_it in med_out["cc"]

    # 5. ISP reports resolution -> Final verification passes -> RESOLUTION_CONFIRMATION email to branch CCs GITSupport@kazyon.com
    isp_resolved_eml = build_synthetic_eml_bytes(
        sender="noc@noor.net",
        recipients=["itsupport-agent@kazyon.com"],
        subject="NOOR NOC - Case No: 244010 - KAZYON - 2009 - Ticket Closure",
        body_text=(
            "Dear Kazyon Team,\n"
            "Regarding store 2009 (Case #244010), the link has been restored with 0% packet loss. Confirming ticket closure."
        ),
    )
    res_closed = await ingest_and_triage_eml(
        db_session,
        isp_resolved_eml,
        filename="isp_closed.eml",
        diagnostic_scenario="PASS",
        _from_harness=True,
    )
    assert res_closed["action"] == "VERIFIED_AND_CLOSED"
    close_branch_outs = [o for o in res_closed["outbound_emails"] if o["thread_type"] == "BRANCH"]
    assert len(close_branch_outs) == 1
    assert expected_reg_it in close_branch_outs[0]["cc"]

    # 6. Manual reply on BRANCH thread via `send_ticket_manual_reply` CCs GITSupport@kazyon.com
    actor = db_session.execute(select(User).limit(1)).scalar_one()
    detail_after_manual = await send_ticket_manual_reply(
        db_session,
        ticket_num,
        TicketEmailReplyRequest(
            thread_type="BRANCH",
            body_text="Manual check-in with store 2009 team.",
        ),
        actor=actor,
    )
    assert all(expected_reg_it in (m.cc_addr or "") for m in detail_after_manual.branch_emails if m.outbound)

    # 7. Direct `dispatch_outbound_email` on BRANCH thread without explicit `cc` still auto-CCs branch.regional_it_email
    ticket_obj = db_session.execute(
        select(Ticket).where(Ticket.ticket_number == ticket_num)
    ).scalar_one()
    direct_em = await dispatch_outbound_email(
        db_session,
        ticket=ticket_obj,
        thread_type="BRANCH",
        recipients=["store2009@kazyon.com"],
        subject=f"[{ticket_num}] Follow-up with store 2009",
        body_text="Checking store status.",
        classification_label="BRANCH_FOLLOWUP",
    )
    assert expected_reg_it in (direct_em.cc or [])
    assert expected_reg_it in (direct_em.raw_headers or {}).get("Cc", "")

    # Verify Ticket 360° Detail and Mailbox Triage Logs expose CC and parsed thread_replies
    detail_360 = get_ticket_360_detail(db_session, ticket_num)
    assert any(len(m.thread_replies) >= 1 for m in detail_360.branch_emails)
    triage_logs = list_mailbox_triage_logs(db_session)
    branch_out_logs = [
        row for row in triage_logs if row["ticket"] == ticket_num and row["dir"] == "OUT" and row["thread_type"] == "BRANCH"
    ]
    assert branch_out_logs
    assert all(expected_reg_it in row["cc"] for row in branch_out_logs)
