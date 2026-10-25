"""End-to-End Autonomous AI Support Agent Workflow Coordinator & Multi-Turn Email Loop Harness (BRD §4.1 & §4.2)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, cast
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.agent.classifier import classify_inbound_email, inspect_router_photo
from app.agent.vllm_client import VllmCallOptions
from app.common.cache import get_redis
from app.common.config import get_settings
from app.common.contracts import (
    ConnectionFailureType,
    EmailEnvelope,
    EscalationReason,
    TicketPriority,
    TicketStatus,
    TicketTriggerSource,
    UniversalEmailTriageResult,
)
from app.common.exceptions import (
    DiagnosticExecutionError,
    InvalidStateTransitionError,
    LLMInferenceError,
    SupportAgentError,
)
from app.diagnostics.base import DualPingTracerouteRequest
from app.diagnostics.service import run_and_persist_diagnostics
from app.directory.models import Branch
from app.directory.service import ensure_directory_seeded, find_branch_by_hint, get_branch_by_code
from app.email_engine.imap_poller import enqueue_llm_retry_eml
from app.email_engine.loop_guard import is_auto_submitted_email
from app.email_engine.parser import (
    build_synthetic_eml_bytes,
    extract_branch_sap_code,
    extract_circuit_id_hint,
    extract_isp_reference_number,
    extract_site_phone,
    extract_ticket_number_tag,
    parse_eml_bytes,
    parse_replication_dashboard_html,
    read_attachment_image_bytes,
    relocate_attachments_to_ticket,
)
from app.email_engine.smtp_sender import (
    dispatch_outbound_email,
    format_isp_escalation_email,
    resolve_branch_regional_it_cc,
    resolve_isp_recipients,
)
from app.ticketing.models import (
    ReplicationReport,
    ReplicationReportRow,
    SystemSettings,
    Ticket,
    TicketEmail,
    TicketEvent,
)
from app.ticketing.service import (
    apply_loop_guard_trip,
    ensure_operational_seed_data,
    ensure_system_settings,
    transition_ticket,
)

logger = logging.getLogger("it_net.agent.workflow")

_fallback_llm_retry_counts: dict[str, int] = {}


def _increment_llm_retry_count(message_id: str) -> int:
    key = f"it_net:llm_retry:{message_id}"
    client = get_redis()
    if client is not None:
        try:
            val = client.incr(key)
            if int(val) == 1:
                client.expire(key, 86400)
            return int(val)
        except Exception:
            pass
    count = _fallback_llm_retry_counts.get(key, 0) + 1
    _fallback_llm_retry_counts[key] = count
    return count


def vllm_call_options(settings_row: SystemSettings) -> VllmCallOptions:
    """vLLM endpoint, temperature and max tokens as saved on Page 12."""
    return VllmCallOptions(
        base_url=settings_row.vllm_endpoint,
        temperature=settings_row.vllm_temperature,
        max_tokens=settings_row.vllm_max_tokens,
    )


def _find_latest_phone_on_branch_thread(
    db: Session,
    ticket: Optional[Ticket],
) -> Optional[str]:
    if ticket is None or ticket.id is None:
        return None
    prior = (
        db.execute(
            select(TicketEmail)
            .where(
                TicketEmail.ticket_id == ticket.id,
                TicketEmail.thread_type == "BRANCH",
                TicketEmail.direction == "INBOUND",
            )
            .order_by(TicketEmail.id.desc())
        )
        .scalars()
        .all()
    )
    for em in prior:
        ph = extract_site_phone(em.body_text or "")
        if ph:
            return ph
    return None


def _load_ticket_thread_history(
    db: Session,
    ticket: Optional[Ticket],
) -> list[dict[str, Any]]:
    """Load all prior `TicketEmail` records on a correlated ticket so the classifier reads the full conversation thread."""
    if ticket is None or ticket.id is None:
        return []
    prior_rows = (
        db.execute(
            select(TicketEmail)
            .where(TicketEmail.ticket_id == ticket.id)
            .order_by(TicketEmail.id.asc())
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": em.id,
            "thread_type": em.thread_type,
            "direction": em.direction,
            "sender": em.sender,
            "recipients": list(em.recipients or []),
            "cc": list(em.cc or []),
            "subject": em.subject,
            "body_text": em.body_text or "",
            "sent_or_received_at": (
                em.sent_or_received_at.isoformat() if em.sent_or_received_at else ""
            ),
        }
        for em in prior_rows
    ]


def _ticket_is_awaiting_site_phone(db: Session, ticket: Ticket) -> bool:
    evt = db.execute(
        select(TicketEvent)
        .where(
            TicketEvent.ticket_id == ticket.id,
            TicketEvent.event_type.in_(["awaiting_site_phone", "contact_relayed"]),
        )
        .order_by(TicketEvent.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return evt is not None and evt.event_type == "awaiting_site_phone"


def _find_open_ticket_for_branch(db: Session, branch_id: int) -> Optional[Ticket]:
    closed_statuses = {TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value}
    tickets = (
        db.execute(select(Ticket).where(Ticket.branch_id == branch_id).order_by(Ticket.id.desc()))
        .scalars()
        .all()
    )
    return next((t for t in tickets if t.status not in closed_statuses), None)


def _next_ticket_number(db: Session) -> str:
    max_id = db.execute(select(func.max(Ticket.id))).scalar_one() or 60
    return f"NET-{1050 + int(max_id) + 1}"


def _correlate_envelope_to_ticket_and_branch(
    db: Session,
    envelope: EmailEnvelope,
) -> tuple[Optional[Ticket], Optional[Branch], str]:
    """Correlate an inbound email to an existing Ticket and Branch across 5 priority levels:
    1. `In-Reply-To` or `References` header matching an existing `TicketEmail.message_id`
    2. Explicit `[NET-XXXX]` / `NET-XXXX` ticket tag in subject or body
    3. ISP Case Reference (`244010`, `1-1312322942540`, `8407532`) matching an open `Ticket.isp_reference_number`
    4. Circuit ID (`QUO1-...`, `6181...`) matching `Branch.ll_circuit_id` or `Branch.backup_circuit_id`
    5. 4-digit Branch SAP Code (`2009`, `1173`, etc.) matching `Branch.branch_code`
    """
    # Priority 1: In-Reply-To / References header match
    candidate_mids: list[str] = []
    if envelope.in_reply_to:
        candidate_mids.append(envelope.in_reply_to.strip())
    for ref in reversed(envelope.references or []):
        if ref.strip() and ref.strip() not in candidate_mids:
            candidate_mids.append(ref.strip())

    for mid in candidate_mids:
        matched_email = db.execute(
            select(TicketEmail).where(TicketEmail.message_id == mid).limit(1)
        ).scalar_one_or_none()
        if matched_email is not None and matched_email.ticket_id is not None:
            t = db.get(Ticket, matched_email.ticket_id)
            if t is not None:
                b = db.get(Branch, t.branch_id) if t.branch_id else None
                return t, b, "HEADER_IN_REPLY_TO"

    # Priority 2: Explicit [NET-XXXX] ticket tag in subject or body
    ticket_tag = extract_ticket_number_tag(envelope.subject, envelope.body_text)
    if ticket_tag:
        t = db.execute(
            select(Ticket).where(func.upper(Ticket.ticket_number) == ticket_tag.upper()).limit(1)
        ).scalar_one_or_none()
        if t is not None:
            b = db.get(Branch, t.branch_id) if t.branch_id else None
            return t, b, "TICKET_TAG"

    # Priority 3: ISP Case Reference number match on an open ticket
    isp_ref = extract_isp_reference_number(envelope.subject, envelope.body_text)
    if isp_ref:
        t = db.execute(
            select(Ticket)
            .where(Ticket.isp_reference_number == isp_ref)
            .order_by(Ticket.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if t is not None:
            b = db.get(Branch, t.branch_id) if t.branch_id else None
            return t, b, "ISP_CASE_REF"

    # Priority 4: Circuit ID match (QUO1-... or WE 6181...)
    circuit_hint = extract_circuit_id_hint(envelope.subject, envelope.body_text)
    if circuit_hint:
        b = db.execute(
            select(Branch)
            .where(
                or_(
                    Branch.ll_circuit_id.ilike(f"%{circuit_hint}%"),
                    Branch.backup_circuit_id.ilike(f"%{circuit_hint}%"),
                )
            )
            .limit(1)
        ).scalar_one_or_none()
        if b is not None:
            open_t = _find_open_ticket_for_branch(db, b.id)
            return open_t, b, "CIRCUIT_ID"

    # Priority 5: Branch SAP Code match
    sap = extract_branch_sap_code(envelope.subject, envelope.body_text)
    branch = (
        find_branch_by_hint(db, sap)
        if sap
        else find_branch_by_hint(db, f"{envelope.subject} {envelope.body_text}")
    )
    if branch is not None:
        open_t = _find_open_ticket_for_branch(db, branch.id)
        return open_t, branch, "BRANCH_SAP_CODE"

    return None, None, "UNCORRELATED"


def _detect_correlated_thread_type(
    db: Session,
    envelope: EmailEnvelope,
    correlated_ticket: Optional[Ticket],
) -> Optional[str]:
    """Detect whether an inbound email is replying to an `ISP`, `BRANCH`, or `HUMAN_ESCALATION` thread.

    This enables single-mailbox Gmail testing (`test_redirect_email`) where the operator replies
    from their personal `@gmail.com` address to a redirected ISP escalation email.
    """
    explicit_hdr = (envelope.raw_headers or {}).get("X-Kz-Thread", "").strip().upper()
    if explicit_hdr in {"ISP", "BRANCH", "HUMAN_ESCALATION"}:
        return explicit_hdr

    candidate_mids: list[str] = []
    if envelope.in_reply_to:
        candidate_mids.append(envelope.in_reply_to.strip())
    for ref in reversed(envelope.references or []):
        if ref.strip() and ref.strip() not in candidate_mids:
            candidate_mids.append(ref.strip())

    for mid in candidate_mids:
        matched_email = db.execute(
            select(TicketEmail).where(TicketEmail.message_id == mid).limit(1)
        ).scalar_one_or_none()
        if matched_email is not None and matched_email.thread_type:
            return matched_email.thread_type.upper()

    body_raw = (envelope.body_text or "").lower()
    if "thread: isp" in body_raw or "[role:isp]" in body_raw:
        return "ISP"
    if (
        correlated_ticket is not None
        and correlated_ticket.status == TicketStatus.ESCALATED_TO_ISP.value
        and any(
            phrase in body_raw
            for phrase in (
                "dear noc",
                "kindly check l.l and 4g",
                "ll order number",
                "kindly check connection store",
            )
        )
    ):
        return "ISP"
    return None


async def process_replication_dashboard_report(
    db: Session,
    *,
    subject: str,
    html_content: str,
    message_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Flow 0: Parse `Replication Dashboard - <Date>` HTML table, create pre-tickets (`AWAITING_REGIONAL_IT`), and email Regional IT."""
    ensure_operational_seed_data(db)
    parsed_rows = parse_replication_dashboard_html(html_content)
    if not parsed_rows:
        return {
            "subject": subject,
            "dry_run": dry_run,
            "total_rows": 0,
            "total_rows_parsed": 0,
            "not_updated_count": 0,
            "notified_count": 0,
            "tickets_created": 0,
            "emails_sent": 0,
            "duplicates_skipped_count": 0,
            "duplicates_skipped": 0,
            "created_ticket_numbers": [],
            "summary": "No valid store rows found in HTML table.",
            "rows": [],
        }

    not_updated_rows = [r for r in parsed_rows if r["status"] == "Not Updated"]
    notified_count = 0
    duplicates_skipped = 0
    created_ticket_numbers: list[str] = []
    row_previews: list[dict[str, Any]] = []

    mid = message_id or f"<rep-{uuid4().hex[:10]}@kazyon.com>"
    report: Optional[ReplicationReport] = None
    if not dry_run:
        existing_rep = db.execute(
            select(ReplicationReport).where(ReplicationReport.message_id == mid).limit(1)
        ).scalar_one_or_none()
        if existing_rep is not None:
            mid = f"<rep-{uuid4().hex[:10]}@kazyon.com>"
        report = ReplicationReport(
            message_id=mid,
            subject=subject,
            report_generated_at=datetime.now(timezone.utc),
            total_rows=len(parsed_rows),
            not_updated_count=len(not_updated_rows),
            notified_count=0,
            duplicates_skipped_count=0,
            received_at=datetime.now(timezone.utc),
        )
        db.add(report)
        db.flush()

    for r in parsed_rows:
        code = r["branch_code"]
        branch = get_branch_by_code(db, code)
        reg_it = (
            branch.regional_it_email
            if branch and branch.regional_it_email
            else "CITSupport@kazyon.com"
        )
        linked_ticket_num: Optional[str] = None
        linked_ticket_id: Optional[int] = None

        if r["status"] == "Not Updated":
            open_t = _find_open_ticket_for_branch(db, branch.id) if branch else None
            if open_t is not None:
                duplicates_skipped += 1
                linked_ticket_num = open_t.ticket_number
                linked_ticket_id = open_t.id
                reg_it_display = "Open ticket exists"
            else:
                notified_count += 1
                reg_it_display = reg_it
                if not dry_run and branch is not None:
                    t_num = _next_ticket_number(db)
                    new_t = Ticket(
                        ticket_number=t_num,
                        title=f"{branch.name} · Replication Not Updated",
                        description=f"Originated from {subject} (Last Trans: {r['last_trans_raw']})",
                        trigger_source=TicketTriggerSource.REPLICATION_DASHBOARD.value,
                        status=TicketStatus.AWAITING_REGIONAL_IT.value,
                        priority=TicketPriority.MEDIUM.value,
                        branch_id=branch.id,
                        isp_id=branch.isp_id,
                        sender_email="replication@kazyon.com",
                        ai_automation_enabled=True,
                    )
                    db.add(new_t)
                    db.flush()
                    linked_ticket_num = new_t.ticket_number
                    linked_ticket_id = new_t.id
                    created_ticket_numbers.append(new_t.ticket_number)

                    await dispatch_outbound_email(
                        db,
                        ticket=new_t,
                        thread_type="BRANCH",
                        recipients=[reg_it],
                        cc=resolve_branch_regional_it_cc(branch, db=db),
                        branch=branch,
                        subject=f"[{new_t.ticket_number}] Store {branch.name} Not Updated in Replication Dashboard",
                        body_text=(
                            f"Dear Regional IT ({branch.region}),\n"
                            f"Store {branch.name} is listed as 'Not Updated' in {subject} "
                            f"(Last transaction: {r['last_trans_raw']}).\n"
                            "Kindly inspect the store router and reply with a router photo and active site contact phone."
                        ),
                        classification_label="REGIONAL_IT_NOTIFY",
                    )
                    db.add(
                        TicketEvent(
                            ticket_id=new_t.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="regional_it_notified",
                            summary=f"Notified Regional IT ({reg_it})",
                            details_json={"detail": f"From {subject}"},
                        )
                    )
                else:
                    linked_ticket_num = "NET-PREVIEW"
        else:
            reg_it_display = "—"

        if not dry_run and report is not None:
            db.add(
                ReplicationReportRow(
                    report_id=report.id,
                    branch_code=code,
                    store_name=f"{code} - {r['store_name']}"
                    if not r["store_name"].startswith(code)
                    else r["store_name"],
                    region=r["region"],
                    last_trans_raw=r["last_trans_raw"],
                    business_date=r["business_date"],
                    status=r["status"],
                    regional_it_email=reg_it_display,
                    regional_it_notified=r["status"] == "Not Updated"
                    and reg_it_display != "Open ticket exists",
                    linked_ticket_id=linked_ticket_id,
                    linked_ticket_number=linked_ticket_num,
                )
            )

        row_previews.append(
            {
                "id": code,
                "name": f"{code} - {r['store_name']}"
                if not r["store_name"].startswith(code)
                else r["store_name"],
                "region": r["region"],
                "last": r["last_trans_raw"],
                "biz": r["business_date"],
                "status": r["status"],
                "tone": "good" if r["status"] == "Updated" else "critical",
                "mail": reg_it_display,
                "ticket": linked_ticket_num or "",
            }
        )

    if not dry_run and report is not None:
        report.notified_count = notified_count
        report.duplicates_skipped_count = duplicates_skipped
        db.commit()

    first_mail = next(
        (p["mail"] for p in row_previews if p["status"] == "Not Updated"), "Regional IT"
    )
    return {
        "subject": subject,
        "dry_run": dry_run,
        "total_rows": len(parsed_rows),
        "total_rows_parsed": len(parsed_rows),
        "not_updated_count": len(not_updated_rows),
        "notified_count": notified_count,
        "tickets_created": len(created_ticket_numbers),
        "emails_sent": len(created_ticket_numbers),
        "duplicates_skipped_count": duplicates_skipped,
        "duplicates_skipped": duplicates_skipped,
        "created_ticket_numbers": created_ticket_numbers,
        "summary": (
            f"{'Dry run: ' if dry_run else ''}{len(parsed_rows)} row(s) parsed · "
            f"{len(not_updated_rows)} Not Updated · ticket {'would be ' if dry_run else ''}created "
            f"and {first_mail} emailed."
        ),
        "rows": row_previews,
    }


async def ingest_and_triage_eml(
    db: Session,
    raw_eml_bytes: bytes,
    *,
    filename: str = "uploaded.eml",
    deduplicate_strict: bool = False,
    diagnostic_scenario: Optional[str] = None,
    _from_harness: bool = False,
) -> dict[str, Any]:
    """Ingest a raw `.eml` file, correlate thread headers, classify via Gemma 4 26B, and execute the autonomous email loop."""
    if diagnostic_scenario is not None and (
        not _from_harness or get_settings().diagnostic_mode != "simulated"
    ):
        raise SupportAgentError(
            "diagnostic_scenario override is only permitted in simulated mode via the test harness",
            status_code=403,
        )

    ensure_operational_seed_data(db)
    ensure_directory_seeded(db)
    settings_row = ensure_system_settings(db)
    llm_options = vllm_call_options(settings_row)

    fallback_engineer = (
        settings_row.fallback_contacts[0]["email"]
        if settings_row.fallback_contacts and settings_row.fallback_contacts[0].get("email")
        else "noc-oncall@kazyon.com"
    )

    envelope: EmailEnvelope = parse_eml_bytes(raw_eml_bytes)
    original_message_id = envelope.message_id

    existing_mid = db.execute(
        select(TicketEmail).where(TicketEmail.message_id == envelope.message_id).limit(1)
    ).scalar_one_or_none()
    if existing_mid is not None:
        if existing_mid.classification_label == "LLM_UNAVAILABLE":
            db.delete(existing_mid)
            db.flush()
        elif deduplicate_strict:
            return {
                "email_id": existing_mid.id,
                "filename": filename,
                "subject": envelope.subject,
                "sender": envelope.sender,
                "classification_label": existing_mid.classification_label or "DUPLICATE_SKIPPED",
                "trigger_type": "DUPLICATE",
                "action": "SKIPPED_DUPLICATE_MESSAGE_ID",
                "ticket_number": "—",
                "outbound_emails": [],
                "actions_taken": ["Skipped duplicate Message-ID"],
            }
        else:
            envelope.message_id = f"<{envelope.message_id.strip('<>')}.sim.{uuid4().hex[:6]}>"

    # Multi-turn thread correlation first
    correlated_ticket, correlated_branch, correlation_method = (
        _correlate_envelope_to_ticket_and_branch(db, envelope)
    )
    correlated_thread_type = _detect_correlated_thread_type(db, envelope, correlated_ticket)

    # Anti-email-storm loop protection: check Auto-Submitted headers before triggering workflow
    if settings_row.ignore_auto_submitted and is_auto_submitted_email(
        envelope.raw_headers, envelope.subject
    ):
        logger.info("Ignoring auto-submitted email '%s'", envelope.subject)
        ignored_row = TicketEmail(
            ticket_id=correlated_ticket.id if correlated_ticket else None,
            thread_type="BRANCH",
            direction="INBOUND",
            message_id=envelope.message_id,
            in_reply_to=envelope.in_reply_to,
            sender=envelope.sender,
            recipients=envelope.recipients or [settings_row.mailbox_account],
            cc=envelope.cc,
            subject=envelope.subject,
            body_text=envelope.body_text,
            body_html=envelope.body_html,
            attachments_json=envelope.attachments,
            raw_headers=envelope.raw_headers,
            classification_label="AUTO_SUBMITTED_IGNORED",
            ai_analysis_json={
                "intent": "AUTO_SUBMITTED",
                "correlation_method": correlation_method,
                "action": "IGNORED_BY_LOOP_GUARD",
            },
            sent_or_received_at=datetime.now(timezone.utc),
        )
        db.add(ignored_row)
        db.commit()
        return {
            "email_id": ignored_row.id,
            "filename": filename,
            "subject": envelope.subject,
            "sender": envelope.sender,
            "classification_label": "AUTO_SUBMITTED_IGNORED",
            "trigger_type": "AUTO_SUBMITTED",
            "action": "IGNORED_AUTO_SUBMITTED",
            "branch_code": correlated_branch.branch_code if correlated_branch else None,
            "isp_reference_number": None,
            "ticket_number": correlated_ticket.ticket_number if correlated_ticket else "—",
            "correlation_method": correlation_method,
            "outbound_emails": [],
            "actions_taken": ["Ignored auto-submitted email via loop guard"],
            "triage": {"intent": "AUTO_SUBMITTED"},
        }

    prior_thread_history = _load_ticket_thread_history(db, correlated_ticket)

    try:
        triage = await classify_inbound_email(
            envelope,
            confidence_threshold_pct=settings_row.confidence_threshold,
            correlated_branch_code=correlated_branch.branch_code if correlated_branch else None,
            correlated_thread_type=correlated_thread_type,
            correlated_isp_name=correlated_branch.isp_name if correlated_branch else None,
            thread_history=prior_thread_history,
            llm_options=llm_options,
        )
    except LLMInferenceError as exc:
        retry_count = _increment_llm_retry_count(original_message_id)
        linked_ticket_err: Optional[Ticket] = correlated_ticket
        if linked_ticket_err is None and correlated_branch is not None:
            linked_ticket_err = _find_open_ticket_for_branch(db, correlated_branch.id)
        if linked_ticket_err is not None and envelope.attachments:
            relocate_attachments_to_ticket(envelope.attachments, linked_ticket_err.ticket_number)
        err_row = TicketEmail(
            ticket_id=linked_ticket_err.id if linked_ticket_err else None,
            thread_type="HUMAN_ESCALATION" if retry_count >= 3 else "BRANCH",
            direction="INBOUND",
            message_id=envelope.message_id,
            in_reply_to=envelope.in_reply_to,
            sender=envelope.sender,
            recipients=envelope.recipients or [settings_row.mailbox_account],
            cc=envelope.cc,
            subject=envelope.subject,
            body_text=envelope.body_text,
            body_html=envelope.body_html,
            attachments_json=envelope.attachments,
            raw_headers=envelope.raw_headers,
            classification_label="LLM_UNAVAILABLE",
            ai_analysis_json={
                "error": str(exc),
                "retry_count": retry_count,
                "correlation_method": correlation_method,
            },
            sent_or_received_at=datetime.now(timezone.utc),
        )
        db.add(err_row)
        db.flush()

        outbound_err_sent: list[dict[str, Any]] = []
        actions_err: list[str] = [f"vLLM classification failed (cycle {retry_count}/3): {exc}"]
        if linked_ticket_err is not None:
            db.add(
                TicketEvent(
                    ticket_id=linked_ticket_err.id,
                    actor_type="AI_AGENT",
                    actor_name="AI_AGENT",
                    event_type="llm_unavailable",
                    summary=f"vLLM unavailable during triage (attempt {retry_count}/3)",
                    details_json={"detail": str(exc), "retry_count": retry_count},
                )
            )
        if retry_count >= 3:
            if linked_ticket_err is not None:
                transition_ticket(
                    db,
                    linked_ticket_err,
                    TicketStatus.NEEDS_HUMAN_REVIEW,
                    actor_type="AI_AGENT",
                    actor_name="AI_AGENT",
                    reason=f"vLLM unavailable after {retry_count} retry cycles ({EscalationReason.LLM_UNAVAILABLE.value})",
                    force=True,
                )
                linked_ticket_err.ai_automation_enabled = False
                linked_ticket_err.escalation_reason = EscalationReason.LLM_UNAVAILABLE.value
                linked_ticket_err.human_escalated_to = fallback_engineer
            hum_llm = await dispatch_outbound_email(
                db,
                ticket=linked_ticket_err,
                thread_type="HUMAN_ESCALATION",
                recipients=[fallback_engineer],
                subject=f"[HUMAN REVIEW] LLM_UNAVAILABLE · {envelope.subject[:80]}",
                body_text=(
                    f"vLLM failed to classify inbound email after {retry_count} poll cycles.\n"
                    f"Escalation Reason: {EscalationReason.LLM_UNAVAILABLE.value}\n"
                    f"Error: {exc}\n"
                    f"Sender: {envelope.sender}\n"
                    f"Subject: {envelope.subject}\n\n"
                    f"Body Preview:\n{(envelope.body_text or '')[:600]}"
                ),
                in_reply_to=envelope.message_id,
                classification_label="HUMAN_ESCALATION",
            )
            outbound_err_sent.append(
                {
                    "id": hum_llm.id,
                    "thread_type": hum_llm.thread_type,
                    "to": ", ".join(hum_llm.recipients or []),
                    "subject": hum_llm.subject,
                    "classification_label": hum_llm.classification_label,
                    "message_id": hum_llm.message_id,
                    "in_reply_to": hum_llm.in_reply_to,
                }
            )
            action_err_label = "HUMAN_ESCALATED_LLM_UNAVAILABLE"
            actions_err.append(
                f"Escalated to {fallback_engineer} with reason LLM_UNAVAILABLE after {retry_count} failed cycles"
            )
        else:
            await asyncio.to_thread(enqueue_llm_retry_eml, raw_eml_bytes, original_message_id)
            action_err_label = "DEFERRED_LLM_RETRY"
            actions_err.append(
                f"Queued email for vLLM retry after {get_settings().llm_retry_backoff_sec}s backoff"
            )

        db.commit()
        return {
            "email_id": err_row.id,
            "filename": filename,
            "subject": envelope.subject,
            "sender": envelope.sender,
            "classification_label": "LLM_UNAVAILABLE",
            "trigger_type": "UNRECOGNIZED" if retry_count >= 3 else "DEFERRED",
            "action": action_err_label,
            "branch_code": correlated_branch.branch_code if correlated_branch else None,
            "isp_reference_number": (
                linked_ticket_err.isp_reference_number if linked_ticket_err else None
            ),
            "ticket_number": linked_ticket_err.ticket_number if linked_ticket_err else "—",
            "ticket_status": linked_ticket_err.status if linked_ticket_err else None,
            "correlation_method": correlation_method,
            "outbound_emails": outbound_err_sent,
            "actions_taken": actions_err,
            "triage": {"intent": "LLM_UNAVAILABLE", "retry_count": retry_count},
        }

    # Cross-check extracted branch code against any circuit ID in subject/body
    circuit_hint = extract_circuit_id_hint(envelope.subject, envelope.body_text)
    circuit_branch: Optional[Branch] = None
    if circuit_hint:
        circuit_branch = db.execute(
            select(Branch)
            .where(
                or_(
                    Branch.ll_circuit_id.ilike(f"%{circuit_hint}%"),
                    Branch.backup_circuit_id.ilike(f"%{circuit_hint}%"),
                )
            )
            .limit(1)
        ).scalar_one_or_none()

    extracted_branch = (
        find_branch_by_hint(db, triage.branch_code)
        if triage.branch_code
        else find_branch_by_hint(db, f"{envelope.subject} {envelope.body_text}")
    )
    branch: Optional[Branch]
    if (
        circuit_branch is not None
        and extracted_branch is not None
        and circuit_branch.id != extracted_branch.id
    ):
        branch = circuit_branch
    else:
        branch = correlated_branch or circuit_branch or extracted_branch

    linked_ticket: Optional[Ticket] = correlated_ticket
    if linked_ticket is None and branch is not None:
        linked_ticket = _find_open_ticket_for_branch(db, branch.id)

    prior_branch_phone = _find_latest_phone_on_branch_thread(db, linked_ticket)

    outbound_emails_sent: list[dict[str, Any]] = []
    actions_taken: list[str] = [
        f"Correlated via {correlation_method}"
        if correlation_method != "UNCORRELATED"
        else "Classified as new thread",
        f"Gemma 4 classified as {triage.classification_label} (intent={triage.intent}, confidence={triage.confidence:.2f})",
    ]
    action_label = triage.next_action

    newly_created_ticket = False
    # Create ticket if needed for BRANCH_INCIDENT or ISP_REPLY
    if (
        linked_ticket is None
        and branch is not None
        and triage.trigger_type in {"BRANCH_INCIDENT", "ISP_REPLY"}
    ):
        newly_created_ticket = True
        t_num = _next_ticket_number(db)
        relocated_paths = (
            relocate_attachments_to_ticket(envelope.attachments, t_num)
            if envelope.attachments
            else []
        )
        linked_ticket = Ticket(
            ticket_number=t_num,
            title=f"{branch.name} · {triage.classification_label}",
            description=envelope.body_text[:1000],
            trigger_source=TicketTriggerSource.DIRECT_EMAIL.value,
            status=TicketStatus.DIAGNOSING.value,
            priority=TicketPriority.HIGH.value,
            branch_id=branch.id,
            isp_id=branch.isp_id,
            sender_email=envelope.sender,
            site_contact_phone=triage.site_contact_phone,
            router_image_paths=relocated_paths,
            isp_reference_number=triage.isp_reference_number,
            ai_automation_enabled=not settings_row.global_ai_kill_switch,
        )
        db.add(linked_ticket)
        db.flush()
        db.add(
            TicketEvent(
                ticket_id=linked_ticket.id,
                actor_type="AI_AGENT",
                actor_name="AI_AGENT",
                event_type="ticket_created",
                summary=f"Ticket {linked_ticket.ticket_number} created from inbound email",
                details_json={"detail": f"From {envelope.sender} · {envelope.subject}"},
            )
        )
        actions_taken.append(f"Opened ticket {linked_ticket.ticket_number} for store {branch.name}")
    elif linked_ticket is not None and envelope.attachments:
        relocate_attachments_to_ticket(envelope.attachments, linked_ticket.ticket_number)

    thread_type = (
        "ISP"
        if triage.trigger_type == "ISP_REPLY"
        else ("HUMAN_ESCALATION" if triage.trigger_type == "UNRECOGNIZED" else "BRANCH")
    )

    raw_analysis_enriched = dict(triage.raw_analysis or {})
    raw_analysis_enriched["correlation_method"] = correlation_method
    if linked_ticket is not None:
        raw_analysis_enriched["ticket_number"] = linked_ticket.ticket_number

    inbound_row = TicketEmail(
        ticket_id=linked_ticket.id if linked_ticket else None,
        thread_type=thread_type,
        direction="INBOUND",
        message_id=envelope.message_id,
        in_reply_to=envelope.in_reply_to,
        sender=envelope.sender,
        recipients=envelope.recipients or [settings_row.mailbox_account],
        cc=envelope.cc,
        subject=envelope.subject,
        body_text=envelope.body_text,
        body_html=envelope.body_html,
        attachments_json=envelope.attachments,
        raw_headers=envelope.raw_headers,
        classification_label=triage.classification_label,
        ai_analysis_json=raw_analysis_enriched,
        sent_or_received_at=datetime.now(timezone.utc),
    )
    db.add(inbound_row)
    db.flush()

    def _record_outbound(em: TicketEmail) -> None:
        outbound_emails_sent.append(
            {
                "id": em.id,
                "thread_type": em.thread_type,
                "to": ", ".join(em.recipients or []),
                "cc": ", ".join(em.cc or []),
                "subject": em.subject,
                "classification_label": em.classification_label,
                "message_id": em.message_id,
                "in_reply_to": em.in_reply_to,
                "blocked_by_loop_guard": bool(
                    (em.ai_analysis_json or {}).get("blocked_by_loop_guard")
                ),
            }
        )

    # Execute autonomous workflow unless Global Kill-Switch or Ticket AI Pause is active
    if not settings_row.global_ai_kill_switch and (
        linked_ticket is None or linked_ticket.ai_automation_enabled
    ):
        try:
            if triage.trigger_type == "REPLICATION_REPORT":
                rep_res = await process_replication_dashboard_report(
                    db,
                    subject=envelope.subject,
                    html_content=envelope.body_html or envelope.body_text,
                    message_id=envelope.message_id,
                    dry_run=False,
                )
                action_label = "REPLICATION_PARSED_AND_REGIONAL_IT_NOTIFIED"
                actions_taken.append(rep_res["summary"])
            elif (
                triage.trigger_type == "BRANCH_INCIDENT"
                and linked_ticket is not None
                and branch is not None
            ):
                resolved_phone = (
                    triage.site_contact_phone
                    or linked_ticket.site_contact_phone
                    or prior_branch_phone
                )
                linked_ticket.site_contact_phone = resolved_phone
                if envelope.attachments:
                    linked_ticket.router_image_paths = [
                        str(a.get("stored_path") or a.get("filename", "router_photo.jpg"))
                        for a in envelope.attachments
                    ]

                awaiting_phone_flag = _ticket_is_awaiting_site_phone(db, linked_ticket)

                # Case B1: Regional IT replied with an updated site contact phone or action blocker completion
                if (
                    linked_ticket.status == TicketStatus.AWAITING_BRANCH_CONTACT.value
                    or triage.intent == "BRANCH_CONTACT_UPDATE"
                    or (
                        linked_ticket.status == TicketStatus.ESCALATED_TO_ISP.value
                        and awaiting_phone_flag
                        and bool(triage.site_contact_phone)
                    )
                ) and (
                    linked_ticket.site_contact_phone
                    or (
                        linked_ticket.status == TicketStatus.AWAITING_BRANCH_CONTACT.value
                        and linked_ticket.connection_failure_type == "BRANCH_ACTION_BLOCKER"
                        and not envelope.attachments
                    )
                ):
                    if linked_ticket.status == TicketStatus.AWAITING_BRANCH_CONTACT.value:
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.ESCALATED_TO_ISP,
                            reason="Regional IT supplied active site contact phone",
                        )
                    elif (
                        linked_ticket.status == TicketStatus.ESCALATED_TO_ISP.value
                        and awaiting_phone_flag
                    ):
                        pass
                    else:
                        raise InvalidStateTransitionError(
                            f"Illegal ticket state transition: {linked_ticket.status} -> {TicketStatus.ESCALATED_TO_ISP.value} (contact relay only valid from AWAITING_BRANCH_CONTACT)"
                        )

                    linked_ticket.next_followup_at = datetime.now(timezone.utc) + timedelta(
                        minutes=settings_row.followup_interval_minutes
                    )
                    isp_to, isp_cc = resolve_isp_recipients(branch, db=db)
                    case_str = linked_ticket.isp_reference_number or "open"
                    relay_subj = (
                        f"RE: store {branch.branch_code} (Case {case_str}) — Updated Site Contact"
                    )
                    relay_body = (
                        f"Dear {branch.isp_name} NOC,\n"
                        f"Regional IT provided an active site contact for store {branch.name} (SAP {branch.branch_code}):\n"
                        f"Site contact: {linked_ticket.site_contact_phone}\n"
                        f"Kindly call the site contact and resume investigation on Case {case_str}."
                    )
                    out_em = await dispatch_outbound_email(
                        db,
                        ticket=linked_ticket,
                        thread_type="ISP",
                        recipients=isp_to,
                        cc=isp_cc,
                        subject=relay_subj,
                        body_text=relay_body,
                        classification_label="CONTACT_RELAY_TO_ISP",
                    )
                    _record_outbound(out_em)
                    db.add(
                        TicketEvent(
                            ticket_id=linked_ticket.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="contact_relayed",
                            summary=f"Relayed active site contact ({linked_ticket.site_contact_phone}) to {branch.isp_name}",
                            details_json={"detail": f"To {isp_to[0]} · Case {case_str}"},
                        )
                    )
                    action_label = "RELAYED_CONTACT_TO_ISP"
                    actions_taken.append(
                        f"Relayed active site phone ({linked_ticket.site_contact_phone}) to {branch.isp_name} on ISP thread"
                    )

                # Case B2: Regional IT / Branch explicitly confirmed link is restored
                elif triage.intent == "BRANCH_RESOLUTION_CONFIRMED":
                    transition_ticket(
                        db,
                        linked_ticket,
                        TicketStatus.CLOSED,
                        reason="Branch / Regional IT confirmed link restoration",
                    )
                    db.add(
                        TicketEvent(
                            ticket_id=linked_ticket.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="ticket_closed",
                            summary="Branch / Regional IT confirmed link restoration; ticket closed",
                            details_json={"detail": f"Confirmed by {envelope.sender}"},
                        )
                    )
                    action_label = "CLOSED_BY_BRANCH_CONFIRMATION"
                    actions_taken.append(
                        "Closed ticket upon Branch / Regional IT restoration confirmation"
                    )

                # Case B3: Initial incident report or Regional IT reply with router photo (or cable fix)
                else:
                    if (
                        not newly_created_ticket
                        and linked_ticket.status != TicketStatus.DIAGNOSING.value
                    ):
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.DIAGNOSING,
                            reason="Branch incident / router photo received for diagnostics",
                        )

                    image_bytes_list = read_attachment_image_bytes(envelope.attachments)
                    vision_error: Optional[LLMInferenceError] = None
                    try:
                        vision = await inspect_router_photo(
                            branch_code=branch.branch_code,
                            image_filenames=[
                                str(a.get("filename", "")) for a in envelope.attachments
                            ],
                            email_body_hint=envelope.body_text,
                            image_bytes_list=image_bytes_list,
                            llm_options=llm_options,
                        )
                    except LLMInferenceError as exc:
                        # The photo is only a pre-check; live diagnostics still decide the outcome.
                        vision = None
                        vision_error = exc
                    if vision is not None:
                        linked_ticket.image_check_passed = vision.cables_plugged
                        linked_ticket.image_analysis_summary = vision.summary
                    elif vision_error is not None:
                        linked_ticket.image_check_passed = None
                        linked_ticket.image_analysis_summary = (
                            "Vision check unavailable (vLLM error); proceeded to diagnostics."
                        )
                        db.add(
                            TicketEvent(
                                ticket_id=linked_ticket.id,
                                actor_type="AI_AGENT",
                                actor_name="AI_AGENT",
                                event_type="vision_unavailable",
                                summary="Router photo vision check failed (vLLM); proceeding to diagnostics",
                                details_json={"detail": str(vision_error)},
                            )
                        )
                        actions_taken.append(
                            f"Vision check unavailable ({vision_error}); continued to diagnostics"
                        )
                    else:
                        linked_ticket.image_check_passed = None
                        linked_ticket.image_analysis_summary = (
                            "No router photo attached; vision check skipped."
                        )

                    if vision is not None and not vision.cables_plugged:
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.AWAITING_BRANCH,
                            reason="Vision check detected unplugged/loose cables",
                        )
                        linked_ticket.connection_failure_type = (
                            ConnectionFailureType.CABLE_UNPLUGGED.value
                        )
                        out_em = await dispatch_outbound_email(
                            db,
                            ticket=linked_ticket,
                            thread_type="BRANCH",
                            recipients=[envelope.sender],
                            cc=resolve_branch_regional_it_cc(branch, db=db),
                            branch=branch,
                            subject=f"RE: {envelope.subject}",
                            body_text=(
                                "Router photo check detected loose/unplugged cables or dark power LED. "
                                "Kindly verify physical cabling and send a fresh photo."
                            ),
                            in_reply_to=envelope.message_id,
                            classification_label="CABLE_FIX_REQUEST",
                        )
                        _record_outbound(out_em)
                        db.add(
                            TicketEvent(
                                ticket_id=linked_ticket.id,
                                actor_type="AI_AGENT",
                                actor_name="AI_AGENT",
                                event_type="vision_failed",
                                summary="Vision check detected unplugged/loose cables; requested reseat",
                                details_json={"detail": vision.summary},
                            )
                        )
                        action_label = "REQUESTED_CABLE_RESEAT"
                        actions_taken.append(
                            "Vision detected unplugged cables; emailed Regional IT to reseat & send fresh photo"
                        )
                    else:
                        if vision is not None:
                            db.add(
                                TicketEvent(
                                    ticket_id=linked_ticket.id,
                                    actor_type="AI_AGENT",
                                    actor_name="AI_AGENT",
                                    event_type="vision_passed",
                                    summary="Router photo check passed (cables seated, power LED on)",
                                    details_json={"detail": vision.summary},
                                )
                            )
                        elif vision_error is None:
                            db.add(
                                TicketEvent(
                                    ticket_id=linked_ticket.id,
                                    actor_type="AI_AGENT",
                                    actor_name="AI_AGENT",
                                    event_type="vision_skipped",
                                    summary="No router photo attached; skipped vision check and proceeded to diagnostics",
                                    details_json={"detail": "vision_skipped"},
                                )
                            )

                        sim_scen = cast(
                            Optional[
                                Literal[
                                    "LIVE_ICMP",
                                    "AUTO",
                                    "PASS",
                                    "FULL_OUTAGE",
                                    "LOCAL_LOOP_DOWN_ON_4G",
                                    "INTERNAL_LAN_SWITCH",
                                ]
                            ],
                            diagnostic_scenario,
                        )
                        try:
                            diag_res = await run_and_persist_diagnostics(
                                db,
                                DualPingTracerouteRequest(
                                    branch_code=branch.branch_code,
                                    ticket_id=linked_ticket.id,
                                    trigger_source="INITIAL",
                                    simulate_scenario=sim_scen,
                                ),
                                actor_name="AI_AGENT",
                            )
                        except DiagnosticExecutionError as diag_err:
                            transition_ticket(
                                db,
                                linked_ticket,
                                TicketStatus.NEEDS_HUMAN_REVIEW,
                                reason=f"Diagnostics unavailable: {diag_err}",
                            )
                            linked_ticket.escalation_reason = (
                                EscalationReason.DIAGNOSTICS_UNAVAILABLE.value
                            )
                            linked_ticket.human_escalated_to = fallback_engineer
                            db.add(
                                TicketEvent(
                                    ticket_id=linked_ticket.id,
                                    actor_type="AI_AGENT",
                                    actor_name="AI_AGENT",
                                    event_type="diagnostics_unavailable",
                                    summary=f"ICMP diagnostics unavailable: {diag_err}",
                                    details_json={"detail": str(diag_err)},
                                )
                            )
                            hum_diag = await dispatch_outbound_email(
                                db,
                                ticket=linked_ticket,
                                thread_type="HUMAN_ESCALATION",
                                recipients=[fallback_engineer],
                                subject=f"[HUMAN REVIEW] {linked_ticket.ticket_number} · DIAGNOSTICS_UNAVAILABLE",
                                body_text=(
                                    f"ICMP diagnostics could not be executed for store {branch.name} "
                                    f"(Ticket {linked_ticket.ticket_number}).\n"
                                    f"Reason: {diag_err}\n"
                                    "AI automation paused; manual investigation required."
                                ),
                                classification_label="HUMAN_ESCALATION",
                            )
                            _record_outbound(hum_diag)
                            action_label = "HUMAN_ESCALATED_DIAGNOSTICS_UNAVAILABLE"
                            actions_taken.append(
                                f"Diagnostics failed ({diag_err}); escalated to {fallback_engineer}"
                            )
                            diag_res = None

                        if diag_res is not None:
                            actions_taken.append(
                                f"Executed Dual-Ping + Traceroute → {diag_res.diagnosis_code} ({diag_res.summary})"
                            )
                            if diag_res.diagnosis_code in {
                                ConnectionFailureType.FULL_OUTAGE.value,
                                ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value,
                            }:
                                transition_ticket(
                                    db,
                                    linked_ticket,
                                    TicketStatus.ESCALATED_TO_ISP,
                                    reason=f"Diagnostics detected {diag_res.diagnosis_code}",
                                )
                                linked_ticket.connection_failure_type = diag_res.diagnosis_code
                                linked_ticket.last_isp_contact_at = datetime.now(timezone.utc)
                                linked_ticket.next_followup_at = datetime.now(
                                    timezone.utc
                                ) + timedelta(minutes=settings_row.welcome_sla_minutes)
                                subj, body, to_list, cc_list, tpl = format_isp_escalation_email(
                                    branch, site_contact_phone=linked_ticket.site_contact_phone
                                )
                                isp_out = await dispatch_outbound_email(
                                    db,
                                    ticket=linked_ticket,
                                    thread_type="ISP",
                                    recipients=to_list,
                                    cc=cc_list,
                                    subject=subj,
                                    body_text=body,
                                    classification_label="ESCALATION",
                                    ai_analysis_json={"template": tpl, "thread": "ISP"},
                                )
                                _record_outbound(isp_out)

                                branch_ack = await dispatch_outbound_email(
                                    db,
                                    ticket=linked_ticket,
                                    thread_type="BRANCH",
                                    recipients=[envelope.sender],
                                    cc=resolve_branch_regional_it_cc(branch, db=db),
                                    branch=branch,
                                    subject=f"RE: {envelope.subject}",
                                    body_text=(
                                        f"Router photo verified and automated network diagnostics completed for store {branch.name} "
                                        f"({diag_res.diagnosis_code}: IP1={'UP' if diag_res.ip_1_up else 'DOWN'}, "
                                        f"IP2={'SKIPPED' if diag_res.ip_2_up is None else ('UP' if diag_res.ip_2_up else 'DOWN')}).\n"
                                        f"Ticket {linked_ticket.ticket_number} has been escalated to {branch.isp_name} ({to_list[0]}) "
                                        f"and is now tracking the {settings_row.welcome_sla_minutes}-minute Welcome SLA."
                                    ),
                                    in_reply_to=envelope.message_id,
                                    classification_label="BRANCH_ACK_ESCALATED",
                                )
                                _record_outbound(branch_ack)
                                db.add(
                                    TicketEvent(
                                        ticket_id=linked_ticket.id,
                                        actor_type="AI_AGENT",
                                        actor_name="AI_AGENT",
                                        event_type="isp_escalated",
                                        summary=f"Escalated {diag_res.diagnosis_code} to {branch.isp_name} ({tpl})",
                                        details_json={
                                            "detail": f"To {to_list[0]} · Subject: {subj}"
                                        },
                                    )
                                )
                                if not linked_ticket.site_contact_phone:
                                    phone_req_out = await dispatch_outbound_email(
                                        db,
                                        ticket=linked_ticket,
                                        thread_type="BRANCH",
                                        recipients=[envelope.sender],
                                        cc=resolve_branch_regional_it_cc(branch, db=db),
                                        branch=branch,
                                        subject=f"ACTION [{linked_ticket.ticket_number}]: Active site phone needed for {branch.name}",
                                        body_text=(
                                            f"We have immediately escalated store {branch.name} (SAP {branch.branch_code}) "
                                            f"to {branch.isp_name} NOC so outage resolution is not delayed.\n"
                                            "However, no site contact phone number was found in your email. "
                                            "Kindly reply with an active phone number on site so we can forward it to the ISP."
                                        ),
                                        in_reply_to=envelope.message_id,
                                        classification_label="SITE_PHONE_REQUEST",
                                    )
                                    _record_outbound(phone_req_out)
                                    db.add(
                                        TicketEvent(
                                            ticket_id=linked_ticket.id,
                                            actor_type="AI_AGENT",
                                            actor_name="AI_AGENT",
                                            event_type="awaiting_site_phone",
                                            summary="Escalated without site phone; requested active phone from branch",
                                            details_json={"awaiting_site_phone": True},
                                        )
                                    )
                                    actions_taken.append(
                                        "Requested missing site contact phone from branch while escalating immediately"
                                    )
                                action_label = f"ESCALATED_TO_{branch.isp_name}"
                                actions_taken.append(
                                    f"Escalated to {branch.isp_name} ({to_list[0]}) and notified {envelope.sender}"
                                )
                            elif (
                                diag_res.diagnosis_code
                                == ConnectionFailureType.INTERNAL_LAN_SWITCH.value
                            ):
                                transition_ticket(
                                    db,
                                    linked_ticket,
                                    TicketStatus.INTERNAL_LAN_ISSUE,
                                    reason="IP1 UP, IP2 DOWN (internal LAN switch issue)",
                                )
                                linked_ticket.connection_failure_type = diag_res.diagnosis_code
                                lan_out = await dispatch_outbound_email(
                                    db,
                                    ticket=linked_ticket,
                                    thread_type="BRANCH",
                                    recipients=[envelope.sender],
                                    cc=resolve_branch_regional_it_cc(branch, db=db),
                                    branch=branch,
                                    subject=f"RE: {envelope.subject}",
                                    body_text=(
                                        f"Automated Dual-Ping for store {branch.name} shows Router IP1 ({branch.ip_1}) is UP "
                                        f"on primary MPLS, but LAN Switch IP2 ({branch.ip_2}) is DOWN.\n"
                                        "This indicates an internal LAN switch or patch cord issue rather than an ISP WAN outage. "
                                        "Kindly inspect the store switch power and uplink port."
                                    ),
                                    in_reply_to=envelope.message_id,
                                    classification_label="INTERNAL_SWITCH_ALERT",
                                )
                                _record_outbound(lan_out)
                                action_label = "RETURNED_TO_BRANCH_INTERNAL_SWITCH"
                                actions_taken.append(
                                    "Detected internal LAN switch issue (IP1 UP, IP2 DOWN); notified Regional IT"
                                )
                            else:
                                transition_ticket(
                                    db,
                                    linked_ticket,
                                    TicketStatus.CLOSED,
                                    reason="Both IP1 & IP2 reachable on primary link",
                                )
                                linked_ticket.connection_failure_type = (
                                    ConnectionFailureType.PASS.value
                                )
                                pass_out = await dispatch_outbound_email(
                                    db,
                                    ticket=linked_ticket,
                                    thread_type="BRANCH",
                                    recipients=[envelope.sender],
                                    cc=resolve_branch_regional_it_cc(branch, db=db),
                                    branch=branch,
                                    subject=f"RE: {envelope.subject}",
                                    body_text=(
                                        f"Automated Dual-Ping & Traceroute for store {branch.name} passed "
                                        f"(IP1 {branch.ip_1} UP, IP2 {branch.ip_2} UP on primary link). "
                                        f"Closing ticket {linked_ticket.ticket_number}."
                                    ),
                                    in_reply_to=envelope.message_id,
                                    classification_label="DIAGNOSTICS_PASS_NOTICE",
                                )
                                _record_outbound(pass_out)
                                action_label = "CLOSED_DIAGNOSTICS_PASSED"
                                actions_taken.append(
                                    "Both IP1 & IP2 reachable on primary link; closed ticket"
                                )

            elif triage.trigger_type == "ISP_REPLY" and linked_ticket is not None:
                if triage.isp_reference_number:
                    linked_ticket.isp_reference_number = triage.isp_reference_number
                linked_ticket.last_isp_contact_at = datetime.now(timezone.utc)

                if triage.intent == "AUTO_ACK":
                    db.add(
                        TicketEvent(
                            ticket_id=linked_ticket.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="isp_auto_ack",
                            summary="ISP automated acknowledgement logged (awaiting real case reference)",
                            details_json={"detail": envelope.subject},
                        )
                    )
                    action_label = "ISP_AUTO_ACK_LOGGED"
                    actions_taken.append(
                        "Logged automated ISP acknowledgement without starting 4-6h welcome loop"
                    )
                elif triage.intent in {"ISP_WELCOME", "INVESTIGATING_UPDATE"}:
                    if linked_ticket.status != TicketStatus.ESCALATED_TO_ISP.value:
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.ESCALATED_TO_ISP,
                            reason=f"ISP reply ({triage.intent})",
                        )
                    linked_ticket.isp_welcome_received = True
                    linked_ticket.next_followup_at = datetime.now(timezone.utc) + timedelta(
                        minutes=settings_row.followup_interval_minutes
                    )
                    db.add(
                        TicketEvent(
                            ticket_id=linked_ticket.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="isp_welcome",
                            summary=(
                                f"ISP Welcome mail received (Case #{triage.isp_reference_number or 'ack'})"
                                if triage.intent == "ISP_WELCOME"
                                else f"ISP investigation update logged (Case #{linked_ticket.isp_reference_number or 'open'})"
                            ),
                            details_json={
                                "detail": f"Next follow-up scheduled in {settings_row.followup_interval_minutes}m"
                            },
                        )
                    )
                    action_label = "ISP_WELCOME_RECORDED_4_6H_LOOP_STARTED"
                    actions_taken.append(
                        f"Recorded ISP Case #{linked_ticket.isp_reference_number or 'ack'} and started {settings_row.followup_interval_minutes}m follow-up loop"
                    )
                elif triage.intent == "SITE_CONTACT_UNREACHABLE":
                    if linked_ticket.status != TicketStatus.AWAITING_BRANCH_CONTACT.value:
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.AWAITING_BRANCH_CONTACT,
                            reason="ISP reported site contact unreachable",
                        )
                    linked_ticket.connection_failure_type = "SITE_CONTACT_UNREACHABLE"
                    target_rit = linked_ticket.sender_email or (
                        branch.regional_it_email
                        if branch and branch.regional_it_email
                        else "CITSupport@kazyon.com"
                    )
                    med_out = await dispatch_outbound_email(
                        db,
                        ticket=linked_ticket,
                        thread_type="BRANCH",
                        recipients=[target_rit],
                        cc=resolve_branch_regional_it_cc(branch, db=db),
                        branch=branch,
                        subject=f"URGENT [{linked_ticket.ticket_number}]: ISP cannot reach site contact",
                        body_text=(
                            f"The ISP reported that the site contact phone for store "
                            f"{branch.name if branch else linked_ticket.ticket_number} is unreachable/busy. "
                            "Kindly reply with an active phone number so we can relay it to the ISP."
                        ),
                        classification_label="CONTACT_BLOCKER_MEDIATION",
                    )
                    _record_outbound(med_out)
                    db.add(
                        TicketEvent(
                            ticket_id=linked_ticket.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="isp_escalated",
                            summary=f"ISP reported unreachable site contact; emailed {target_rit} for active phone",
                            details_json={
                                "detail": f"Case #{linked_ticket.isp_reference_number or 'open'}"
                            },
                        )
                    )
                    action_label = "MEDIATED_CONTACT_BLOCKER_WITH_BRANCH"
                    actions_taken.append(
                        f"Transitioned to AWAITING_BRANCH_CONTACT and emailed {target_rit} for active phone"
                    )
                elif triage.intent == "BRANCH_ACTION_BLOCKER":
                    if linked_ticket.status != TicketStatus.AWAITING_BRANCH_CONTACT.value:
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.AWAITING_BRANCH_CONTACT,
                            reason="ISP requested branch-side check",
                        )
                    linked_ticket.connection_failure_type = "BRANCH_ACTION_BLOCKER"
                    target_rit = linked_ticket.sender_email or (
                        branch.regional_it_email
                        if branch and branch.regional_it_email
                        else "CITSupport@kazyon.com"
                    )
                    med_out = await dispatch_outbound_email(
                        db,
                        ticket=linked_ticket,
                        thread_type="BRANCH",
                        recipients=[target_rit],
                        cc=resolve_branch_regional_it_cc(branch, db=db),
                        branch=branch,
                        subject=f"ACTION REQUIRED [{linked_ticket.ticket_number}]: ISP requested branch check",
                        body_text=(
                            f"The ISP requested an on-site check for store "
                            f"{branch.name if branch else linked_ticket.ticket_number} "
                            f"(Case #{linked_ticket.isp_reference_number or 'open'}):\n\n"
                            f"{triage.summary}\n\n"
                            "Kindly perform the requested action and reply with an update and active site phone."
                        ),
                        classification_label="BRANCH_ACTION_MEDIATION",
                    )
                    _record_outbound(med_out)
                    db.add(
                        TicketEvent(
                            ticket_id=linked_ticket.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="isp_escalated",
                            summary=f"ISP requested branch-side check; forwarded instructions to {target_rit}",
                            details_json={"detail": triage.summary},
                        )
                    )
                    action_label = "MEDIATED_BRANCH_ACTION_BLOCKER"
                    actions_taken.append(
                        f"Transitioned to AWAITING_BRANCH_CONTACT and forwarded ISP instructions to {target_rit}"
                    )
                elif triage.intent == "ISP_RESOLVED":
                    if branch is None:
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.NEEDS_HUMAN_REVIEW,
                            reason="ISP claimed resolution but ticket has no correlated branch for verification",
                        )
                        linked_ticket.escalation_reason = EscalationReason.OTHER.value
                        linked_ticket.human_escalated_to = fallback_engineer
                        action_label = "HUMAN_ESCALATED_MISSING_BRANCH"
                        actions_taken.append(
                            "Transitioned to NEEDS_HUMAN_REVIEW because branch is missing on ISP_RESOLVED"
                        )
                    else:
                        transition_ticket(
                            db,
                            linked_ticket,
                            TicketStatus.VERIFYING,
                            reason="ISP claimed resolution; running final verification",
                        )
                        ver_scen = cast(
                            Optional[
                                Literal[
                                    "LIVE_ICMP",
                                    "AUTO",
                                    "PASS",
                                    "FULL_OUTAGE",
                                    "LOCAL_LOOP_DOWN_ON_4G",
                                    "INTERNAL_LAN_SWITCH",
                                ]
                            ],
                            diagnostic_scenario,
                        )
                        try:
                            diag_res = await run_and_persist_diagnostics(
                                db,
                                DualPingTracerouteRequest(
                                    branch_code=branch.branch_code,
                                    ticket_id=linked_ticket.id,
                                    trigger_source="FINAL_VERIFICATION",
                                    simulate_scenario=ver_scen,
                                ),
                                actor_name="AI_AGENT",
                            )
                        except DiagnosticExecutionError as diag_err:
                            transition_ticket(
                                db,
                                linked_ticket,
                                TicketStatus.NEEDS_HUMAN_REVIEW,
                                reason=f"Final verification diagnostics unavailable: {diag_err}",
                            )
                            linked_ticket.escalation_reason = (
                                EscalationReason.DIAGNOSTICS_UNAVAILABLE.value
                            )
                            linked_ticket.human_escalated_to = fallback_engineer
                            db.add(
                                TicketEvent(
                                    ticket_id=linked_ticket.id,
                                    actor_type="AI_AGENT",
                                    actor_name="AI_AGENT",
                                    event_type="diagnostics_unavailable",
                                    summary=f"Final verification ICMP diagnostics unavailable: {diag_err}",
                                    details_json={"detail": str(diag_err)},
                                )
                            )
                            action_label = "HUMAN_ESCALATED_DIAGNOSTICS_UNAVAILABLE"
                            actions_taken.append(
                                f"Final verification failed due to missing ICMP ({diag_err}); escalated to human review"
                            )
                            diag_res = None

                        if diag_res is not None:
                            verified_pass = (
                                diag_res.diagnosis_code == ConnectionFailureType.PASS.value
                                and bool(diag_res.ip_1_up)
                                and bool(diag_res.ip_2_up)
                                and not bool(diag_res.four_g_hub_detected)
                            )
                            if verified_pass:
                                transition_ticket(
                                    db,
                                    linked_ticket,
                                    TicketStatus.CLOSED,
                                    reason="Final dual-ping & traceroute verification passed",
                                )
                                target_rit = linked_ticket.sender_email or (
                                    branch.regional_it_email
                                    if branch.regional_it_email
                                    else "CITSupport@kazyon.com"
                                )
                                confirm_out = await dispatch_outbound_email(
                                    db,
                                    ticket=linked_ticket,
                                    thread_type="BRANCH",
                                    recipients=[target_rit],
                                    cc=resolve_branch_regional_it_cc(branch, db=db),
                                    branch=branch,
                                    subject=f"[{linked_ticket.ticket_number}] Resolved: Store {branch.name} Link Restored & Verified",
                                    body_text=(
                                        f"Dear Regional IT ({branch.region}),\n"
                                        f"{branch.isp_name} reported resolution for store {branch.name} "
                                        f"(Case #{linked_ticket.isp_reference_number or 'closed'}).\n"
                                        f"Automated final verification confirmed IP1 ({branch.ip_1}) UP and IP2 ({branch.ip_2}) UP "
                                        f"with 0% packet loss on the primary link. Ticket {linked_ticket.ticket_number} is now closed."
                                    ),
                                    classification_label="RESOLUTION_CONFIRMATION",
                                )
                                _record_outbound(confirm_out)

                                isp_ack_to, isp_ack_cc = resolve_isp_recipients(branch, db=db)
                                isp_ack = await dispatch_outbound_email(
                                    db,
                                    ticket=linked_ticket,
                                    thread_type="ISP",
                                    recipients=isp_ack_to,
                                    cc=isp_ack_cc,
                                    subject=f"RE: {envelope.subject}",
                                    body_text=(
                                        f"Dear {branch.isp_name} NOC,\n"
                                        f"We have verified that both router IP1 ({branch.ip_1}) and switch IP2 ({branch.ip_2}) "
                                        f"for store {branch.branch_code} are up and stable. Thank you — confirming ticket closure."
                                    ),
                                    in_reply_to=envelope.message_id,
                                    classification_label="ISP_CLOSURE_ACK",
                                )
                                _record_outbound(isp_ack)

                                db.add(
                                    TicketEvent(
                                        ticket_id=linked_ticket.id,
                                        actor_type="AI_AGENT",
                                        actor_name="AI_AGENT",
                                        event_type="ticket_closed",
                                        summary="Final dual-ping verification passed; notified Branch & ISP and closed ticket",
                                        details_json={"detail": "IP1 UP, IP2 UP"},
                                    )
                                )
                                action_label = "VERIFIED_AND_CLOSED"
                                actions_taken.append(
                                    "Final verification Dual-Ping PASSED; sent closure confirmation to Regional IT & ISP"
                                )
                            else:
                                # Final verification failed — reject premature ISP closure and keep chasing!
                                transition_ticket(
                                    db,
                                    linked_ticket,
                                    TicketStatus.ESCALATED_TO_ISP,
                                    reason=f"Final verification failed ({diag_res.diagnosis_code})",
                                )
                                linked_ticket.connection_failure_type = diag_res.diagnosis_code
                                linked_ticket.next_followup_at = datetime.now(
                                    timezone.utc
                                ) + timedelta(minutes=settings_row.followup_interval_minutes)
                                reopen_to, reopen_cc = resolve_isp_recipients(branch, db=db)
                                reopen_out = await dispatch_outbound_email(
                                    db,
                                    ticket=linked_ticket,
                                    thread_type="ISP",
                                    recipients=reopen_to,
                                    cc=reopen_cc,
                                    subject=f"RE: {envelope.subject} [Verification Failed - Still Down]",
                                    body_text=(
                                        f"Dear {branch.isp_name} NOC,\n"
                                        f"Following your closure notice for store {branch.branch_code} "
                                        f"(Case #{linked_ticket.isp_reference_number or 'open'}), our automated verification "
                                        f"still detects {diag_res.diagnosis_code} (IP1={'UP' if diag_res.ip_1_up else 'DOWN'}, "
                                        f"IP2={'SKIPPED' if diag_res.ip_2_up is None else ('UP' if diag_res.ip_2_up else 'DOWN')}, "
                                        f"4G_Backup={bool(diag_res.four_g_hub_detected)}).\n"
                                        "Kindly keep the trouble ticket open and re-check the circuit."
                                    ),
                                    in_reply_to=envelope.message_id,
                                    classification_label="ISP_REOPEN_FAILED_VERIFY",
                                )
                                _record_outbound(reopen_out)
                                db.add(
                                    TicketEvent(
                                        ticket_id=linked_ticket.id,
                                        actor_type="AI_AGENT",
                                        actor_name="AI_AGENT",
                                        event_type="dual_ping",
                                        summary=f"ISP claimed closure, but verification failed ({diag_res.diagnosis_code}) — rejected closure",
                                        details_json={"detail": diag_res.summary},
                                    )
                                )
                                action_label = "REJECTED_PREMATURE_ISP_CLOSURE"
                                actions_taken.append(
                                    f"Final verification failed ({diag_res.diagnosis_code}); rejected closure on ISP thread"
                                )
                elif triage.intent == "SPECIAL_BLOCKER":
                    transition_ticket(
                        db,
                        linked_ticket,
                        TicketStatus.NEEDS_HUMAN_REVIEW,
                        reason=f"ISP special blocker ({triage.raw_analysis.get('escalation_reason') or 'OTHER'})",
                    )
                    linked_ticket.escalation_reason = str(
                        triage.raw_analysis.get("escalation_reason") or "OTHER"
                    )
                    linked_ticket.human_escalated_to = fallback_engineer
                    hum_out = await dispatch_outbound_email(
                        db,
                        ticket=linked_ticket,
                        thread_type="HUMAN_ESCALATION",
                        recipients=[fallback_engineer],
                        subject=f"[HUMAN REVIEW] {linked_ticket.ticket_number} · {linked_ticket.escalation_reason} (Store {branch.branch_code if branch else '—'})",
                        body_text=(
                            f"AI Automation paused for ticket {linked_ticket.ticket_number}.\n"
                            f"Escalation Reason: {linked_ticket.escalation_reason}\n"
                            f"ISP Case Ref: {linked_ticket.isp_reference_number or '—'}\n"
                            f"Inbound ISP Message ({envelope.sender}):\n{envelope.body_text[:600]}"
                        ),
                        classification_label="HUMAN_ESCALATION",
                    )
                    _record_outbound(hum_out)
                    db.add(
                        TicketEvent(
                            ticket_id=linked_ticket.id,
                            actor_type="AI_AGENT",
                            actor_name="AI_AGENT",
                            event_type="human_escalated",
                            summary=f"ISP special blocker ({linked_ticket.escalation_reason}) escalated to {fallback_engineer}",
                            details_json={"detail": triage.summary},
                        )
                    )
                    action_label = f"HUMAN_ESCALATED_{linked_ticket.escalation_reason}"
                    actions_taken.append(
                        f"Paused AI and escalated {linked_ticket.escalation_reason} to {fallback_engineer}"
                    )
            elif triage.trigger_type == "UNRECOGNIZED":
                if linked_ticket is not None:
                    transition_ticket(
                        db,
                        linked_ticket,
                        TicketStatus.NEEDS_HUMAN_REVIEW,
                        reason="Low confidence / unrecognized email",
                    )
                    linked_ticket.escalation_reason = EscalationReason.UNRECOGNIZED_EMAIL.value
                    linked_ticket.human_escalated_to = fallback_engineer
                hum_unrec = await dispatch_outbound_email(
                    db,
                    ticket=linked_ticket,
                    thread_type="HUMAN_ESCALATION",
                    recipients=[fallback_engineer],
                    subject=f"[HUMAN REVIEW] Unrecognized Email · {envelope.subject[:80]}",
                    body_text=(
                        "An inbound email could not be automatically classified or correlated with high confidence "
                        f"(confidence={triage.confidence:.2f} < threshold={settings_row.confidence_threshold:.2f}).\n"
                        f"Escalation Reason: {EscalationReason.UNRECOGNIZED_EMAIL.value}\n"
                        f"Sender: {envelope.sender}\n"
                        f"Subject: {envelope.subject}\n"
                        f"Message-ID: {envelope.message_id}\n\n"
                        f"Original Body Preview:\n{(envelope.body_text or '')[:600]}"
                    ),
                    in_reply_to=envelope.message_id,
                    classification_label="HUMAN_ESCALATION",
                )
                _record_outbound(hum_unrec)
                action_label = "ROUTED_TO_HUMAN_REVIEW_QUEUE"
                actions_taken.append(
                    f"Low confidence / unrecognized email routed to Human Review Queue and emailed report to {fallback_engineer}"
                )
        except InvalidStateTransitionError as trans_err:
            logger.warning(
                "Blocked illegal state transition on ticket %s: %s",
                linked_ticket.ticket_number if linked_ticket else "—",
                trans_err,
            )
            if linked_ticket is not None:
                db.add(
                    TicketEvent(
                        ticket_id=linked_ticket.id,
                        actor_type="AI_AGENT",
                        actor_name="AI_AGENT",
                        event_type="status_transition_blocked",
                        summary=f"Blocked illegal state transition ({trans_err}); attached email without outbound action",
                        details_json={"detail": str(trans_err)},
                    )
                )
            action_label = "LOGGED_ON_TIMELINE_TRANSITION_BLOCKED"
            actions_taken.append(
                f"Blocked illegal transition ({trans_err}); logged email on timeline without sending outbound mail"
            )
    else:
        action_label = (
            "LOGGED_ONLY_GLOBAL_KILL_SWITCH"
            if settings_row.global_ai_kill_switch
            else "LOGGED_ONLY_TICKET_AI_PAUSED"
        )
        actions_taken.append(f"Inbound email logged without autonomous action ({action_label})")

    if any(o["blocked_by_loop_guard"] for o in outbound_emails_sent) and apply_loop_guard_trip(
        db, linked_ticket
    ):
        actions_taken.append(
            f"Loop guard tripped; moved ticket to NEEDS_HUMAN_REVIEW "
            f"({EscalationReason.LOOP_GUARD_TRIPPED.value})"
        )

    db.commit()
    stage_trace = _build_sandbox_stage_trace(
        correlation_method=correlation_method,
        correlated_branch=branch,
        triage=triage,
        linked_ticket=linked_ticket,
        action_label=action_label,
        outbound_emails_sent=outbound_emails_sent,
        attachments_count=len(envelope.attachments or []),
    )
    suggested_next_steps = _build_suggested_next_steps(linked_ticket, branch)
    return {
        "email_id": inbound_row.id,
        "filename": filename,
        "subject": envelope.subject,
        "sender": envelope.sender,
        "classification_label": triage.classification_label,
        "trigger_type": triage.trigger_type,
        "action": action_label,
        "branch_code": branch.branch_code if branch else triage.branch_code,
        "isp_reference_number": (
            linked_ticket.isp_reference_number if linked_ticket else triage.isp_reference_number
        ),
        "ticket_number": linked_ticket.ticket_number if linked_ticket else "—",
        "ticket_status": linked_ticket.status if linked_ticket else None,
        "correlation_method": correlation_method,
        "outbound_emails": outbound_emails_sent,
        "actions_taken": actions_taken,
        "triage": triage.model_dump(),
        "stage_trace": stage_trace,
        "suggested_next_steps": suggested_next_steps,
    }


def _build_sandbox_stage_trace(
    *,
    correlation_method: str,
    correlated_branch: Optional[Branch],
    triage: UniversalEmailTriageResult,
    linked_ticket: Optional[Ticket],
    action_label: str,
    outbound_emails_sent: list[dict[str, Any]],
    attachments_count: int,
) -> list[dict[str, Any]]:
    """Build a structured 6-stage execution trace for the Interactive Mail Simulation Sandbox."""
    branch_label = (
        f"{correlated_branch.name} (SAP {correlated_branch.branch_code} · {correlated_branch.isp_name})"
        if correlated_branch
        else (triage.branch_code or "Uncorrelated")
    )
    stages: list[dict[str, Any]] = [
        {
            "step": 1,
            "name": "MIME & Thread Correlation",
            "status": "PASS" if correlation_method != "UNCORRELATED" else "INFO",
            "summary": f"Matched via {correlation_method}",
            "detail": f"Store: {branch_label} · Ticket: {linked_ticket.ticket_number if linked_ticket else 'New / None'}",
        },
        {
            "step": 2,
            "name": "Gemma 4 AI Classification",
            "status": "PASS" if triage.trigger_type != "UNRECOGNIZED" else "WARN",
            "summary": f"{triage.classification_label} · Intent: {triage.intent} ({int(round(triage.confidence * 100))}%)",
            "detail": triage.summary,
        },
    ]

    if linked_ticket is not None and linked_ticket.image_check_passed is not None:
        stages.append(
            {
                "step": 3,
                "name": "Router Photo Vision Check",
                "status": "PASS" if linked_ticket.image_check_passed else "FAIL",
                "summary": (
                    "Cables seated & power LED active"
                    if linked_ticket.image_check_passed
                    else "Loose/unplugged cable or dark power LED detected"
                ),
                "detail": linked_ticket.image_analysis_summary
                or f"Inspected {attachments_count} attached photo(s)",
            }
        )
    else:
        stages.append(
            {
                "step": 3,
                "name": "Router Photo Vision Check",
                "status": "SKIPPED",
                "summary": "Skipped (no router photo inspection required for this step)",
                "detail": f"Attachments present: {attachments_count}",
            }
        )

    if linked_ticket is not None and linked_ticket.connection_failure_type:
        diag_code = linked_ticket.connection_failure_type
        stages.append(
            {
                "step": 4,
                "name": "Dual-Ping & 4G Traceroute Diagnostics",
                "status": "PASS" if diag_code == "PASS" else "WARN",
                "summary": f"Diagnosis: {diag_code}",
                "detail": f"Classified store connectivity as {diag_code}",
            }
        )
    else:
        stages.append(
            {
                "step": 4,
                "name": "Dual-Ping & 4G Traceroute Diagnostics",
                "status": "SKIPPED",
                "summary": "No ICMP probe triggered on this turn",
                "detail": "Diagnostics run on initial incident triage and ISP resolution claims.",
            }
        )

    stages.append(
        {
            "step": 5,
            "name": "Ticket State Machine Transition",
            "status": "PASS",
            "summary": f"Status → {linked_ticket.status if linked_ticket else 'N/A'} ({action_label})",
            "detail": (
                f"ISP Case Ref: {linked_ticket.isp_reference_number or '—'} · Chasers: {linked_ticket.followup_count}"
                if linked_ticket
                else "No ticket state transition."
            ),
        }
    )

    if outbound_emails_sent:
        out_summary = ", ".join(
            f"{o['thread_type']} → {o['to']} ({o['classification_label']})"
            for o in outbound_emails_sent
        )
        stages.append(
            {
                "step": 6,
                "name": "Outbound Email Dispatch",
                "status": "PASS",
                "summary": f"Dispatched {len(outbound_emails_sent)} email(s)",
                "detail": out_summary,
            }
        )
    else:
        stages.append(
            {
                "step": 6,
                "name": "Outbound Email Dispatch",
                "status": "INFO",
                "summary": "No outbound email required on this turn",
                "detail": f"Completed with action {action_label}",
            }
        )
    return stages


def _build_suggested_next_steps(
    ticket: Optional[Ticket],
    branch: Optional[Branch],
) -> list[dict[str, str]]:
    """Return contextual next role-play replies for the operator in the Mail Simulation Sandbox."""
    sap = branch.branch_code if branch else "2009"
    isp = (branch.isp_name if branch else "NOOR").upper()
    if ticket is None:
        return [
            {
                "scenario": "BRANCH_INCIDENT",
                "role": "BRANCH",
                "label": f"Report Outage as Store {sap} (Regional IT)",
                "description": "Send initial store outage report with seated router photo.",
            }
        ]

    st = ticket.status
    if st == TicketStatus.AWAITING_REGIONAL_IT.value:
        return [
            {
                "scenario": "BRANCH_INCIDENT",
                "role": "BRANCH",
                "label": "Reply as Regional IT (Seated Router Photo)",
                "description": "Confirm outage and provide router photo + site phone.",
            },
            {
                "scenario": "CABLE_UNPLUGGED_PHOTO",
                "role": "BRANCH",
                "label": "Reply as Regional IT (Unplugged Cable Photo)",
                "description": "Send photo showing loose WAN cable to test Vision Check gate.",
            },
        ]
    if st == TicketStatus.AWAITING_BRANCH.value:
        return [
            {
                "scenario": "REGIONAL_IT_CABLE_FIXED",
                "role": "BRANCH",
                "label": "Reply as Regional IT (Cables Reseated + Fresh Photo)",
                "description": "Confirm cables are plugged in and trigger Dual-Ping + ISP escalation.",
            }
        ]
    if st == TicketStatus.ESCALATED_TO_ISP.value and not ticket.isp_welcome_received:
        return [
            {
                "scenario": "ISP_WELCOME",
                "role": "ISP",
                "label": f"Reply as {isp} NOC: Welcome + Case Reference",
                "description": "Acknowledge trouble ticket, assign Case #, and start 4h follow-up timer.",
            },
            {
                "scenario": "ISP_CONTACT_UNREACHABLE",
                "role": "ISP",
                "label": f"Reply as {isp} NOC: Site Contact Unreachable",
                "description": "Report that the store phone is switched off to test mediation flow.",
            },
            {
                "scenario": "ISP_QUOTA_BLOCKER",
                "role": "ISP",
                "label": f"Reply as {isp} NOC: 4G Quota Consumed",
                "description": "Report 4G bundle exhaustion to test Human Review escalation.",
            },
        ]
    if st == TicketStatus.ESCALATED_TO_ISP.value and ticket.isp_welcome_received:
        return [
            {
                "scenario": "ISP_RESOLVED",
                "role": "ISP",
                "label": f"Reply as {isp} NOC: Link Restored (Verify PASS)",
                "description": "Claim closure when Dual-Ping passes → closes ticket & notifies Branch + ISP.",
            },
            {
                "scenario": "ISP_RESOLVED_STILL_DOWN",
                "role": "ISP",
                "label": f"Reply as {isp} NOC: Premature Closure (Verify FAIL)",
                "description": "Claim closure while link is still down → agent rejects closure!",
            },
            {
                "scenario": "ISP_CONTACT_UNREACHABLE",
                "role": "ISP",
                "label": f"Reply as {isp} NOC: Site Contact Unreachable",
                "description": "Report that the store phone is unreachable → agent asks Regional IT.",
            },
        ]
    if st == TicketStatus.AWAITING_BRANCH_CONTACT.value:
        return [
            {
                "scenario": "REGIONAL_IT_NEW_PHONE",
                "role": "BRANCH",
                "label": "Reply as Regional IT: Active Shift Manager Phone",
                "description": "Provide new phone number → agent relays it to ISP NOC and resumes SLA timer.",
            }
        ]
    return [
        {
            "scenario": "BRANCH_INCIDENT",
            "role": "BRANCH",
            "label": f"New Incident on Store {sap}",
            "description": "Trigger a fresh store outage scenario.",
        }
    ]


async def record_failed_ingest(
    db: Session,
    raw_eml_bytes: bytes,
    *,
    filename: str,
    error: Exception,
) -> Optional[TicketEmail]:
    """Keep an inbound email whose ingest crashed, and report it to the human engineer.

    Called after the failed ingest was rolled back. IMAP has already marked the message Seen,
    so without this row the email would be lost (CLAUDE.md §10). The row is listed in the
    Human Review queue with reason `INGEST_FAILED`.
    """
    envelope = parse_eml_bytes(raw_eml_bytes)
    existing = db.execute(
        select(TicketEmail).where(TicketEmail.message_id == envelope.message_id).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return None

    settings_row = ensure_system_settings(db)
    fallback_engineer = (
        settings_row.fallback_contacts[0]["email"]
        if settings_row.fallback_contacts and settings_row.fallback_contacts[0].get("email")
        else "noc-oncall@kazyon.com"
    )
    failed_row = TicketEmail(
        ticket_id=None,
        thread_type="HUMAN_ESCALATION",
        direction="INBOUND",
        message_id=envelope.message_id,
        in_reply_to=envelope.in_reply_to,
        sender=envelope.sender,
        recipients=envelope.recipients or [settings_row.mailbox_account],
        cc=envelope.cc,
        subject=envelope.subject,
        body_text=envelope.body_text,
        body_html=envelope.body_html,
        attachments_json=envelope.attachments,
        raw_headers=envelope.raw_headers,
        classification_label=EscalationReason.INGEST_FAILED.value,
        ai_analysis_json={"error": f"{type(error).__name__}: {error}", "filename": filename},
        sent_or_received_at=datetime.now(timezone.utc),
    )
    db.add(failed_row)
    db.flush()
    await dispatch_outbound_email(
        db,
        ticket=None,
        thread_type="HUMAN_ESCALATION",
        recipients=[fallback_engineer],
        subject=f"[HUMAN REVIEW] INGEST_FAILED · {envelope.subject[:80]}",
        body_text=(
            "The agent failed while processing an inbound email; no automated action was taken.\n"
            f"Escalation Reason: {EscalationReason.INGEST_FAILED.value}\n"
            f"Error: {type(error).__name__}: {error}\n"
            f"Sender: {envelope.sender}\n"
            f"Subject: {envelope.subject}\n"
            f"Message-ID: {envelope.message_id}\n\n"
            f"Body Preview:\n{(envelope.body_text or '')[:600]}"
        ),
        in_reply_to=envelope.message_id,
        classification_label="HUMAN_ESCALATION",
    )
    db.commit()
    return failed_row


async def trigger_email_in_loop(
    db: Session,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build and inject an inbound email into the autonomous agent harness loop for any scenario or custom message."""
    ensure_operational_seed_data(db)
    ensure_directory_seeded(db)

    scenario = str(payload.get("scenario") or "BRANCH_INCIDENT").upper()
    ticket_number = str(payload.get("ticket_number") or "").strip().upper()
    branch_code = str(payload.get("branch_code") or "").strip()

    linked_ticket: Optional[Ticket] = None
    branch: Optional[Branch] = None

    if ticket_number and ticket_number.startswith("NET-"):
        linked_ticket = db.execute(
            select(Ticket).where(func.upper(Ticket.ticket_number) == ticket_number).limit(1)
        ).scalar_one_or_none()
        if linked_ticket and linked_ticket.branch_id:
            branch = db.get(Branch, linked_ticket.branch_id)

    if branch is None and branch_code:
        branch = get_branch_by_code(db, branch_code)
    if branch is None:
        branch = (
            get_branch_by_code(db, "2009")
            or db.execute(select(Branch).limit(1)).scalar_one_or_none()
        )

    if linked_ticket is None and branch is not None:
        linked_ticket = _find_open_ticket_for_branch(db, branch.id)

    sap = branch.branch_code if branch else (branch_code or "2009")
    store_name = branch.name if branch else f"{sap}-Store"
    isp_name = (branch.isp_name if branch else "NOOR").upper()
    isp_sender = (
        branch.isp_contact_mail
        if branch and branch.isp_contact_mail
        else (
            "ccc-eg@orange.com"
            if isp_name == "ORANGE"
            else ("psupport@te.eg" if isp_name == "WE" else "noc@noor.net")
        )
    )
    reg_it_sender = (
        branch.regional_it_email if branch and branch.regional_it_email else "GITSupport@kazyon.com"
    )
    ll_id = branch.ll_circuit_id if branch and branch.ll_circuit_id else f"QUO1-1031{sap}"
    g3_id = branch.backup_circuit_id if branch and branch.backup_circuit_id else f"620{sap}"

    # Look up latest message_id on BRANCH or ISP thread for realistic In-Reply-To / References threading
    role_override = str(payload.get("role") or "").strip().upper()
    target_thread = "ISP" if (scenario.startswith("ISP_") or role_override == "ISP") else "BRANCH"
    in_reply_to: Optional[str] = payload.get("in_reply_to")
    references_list: list[str] = []
    if linked_ticket is not None:
        thread_emails = (
            db.execute(
                select(TicketEmail)
                .where(
                    TicketEmail.ticket_id == linked_ticket.id,
                    TicketEmail.thread_type == target_thread,
                )
                .order_by(TicketEmail.id.asc())
            )
            .scalars()
            .all()
        )
        references_list = [e.message_id for e in thread_emails if e.message_id]
        if not in_reply_to and references_list:
            in_reply_to = references_list[-1]

    default_case_ref = (
        linked_ticket.isp_reference_number
        if linked_ticket and linked_ticket.isp_reference_number
        else (
            "1-1312322942540"
            if isp_name == "ORANGE"
            else ("8407532" if isp_name == "WE" else "244010")
        )
    )

    sender = str(payload.get("sender") or "").strip()
    subject = str(payload.get("subject") or "").strip()
    body_text = str(payload.get("body_text") or "").strip()
    body_html: Optional[str] = payload.get("body_html")
    attachments: list[str] = list(payload.get("attachments") or [])
    diag_scenario: Optional[str] = payload.get("diagnostic_scenario")

    if scenario == "REPLICATION_REPORT":
        sender = sender or "sap-replication@kazyon.com"
        subject = (
            subject or f"Replication Dashboard - {datetime.now(timezone.utc).strftime('%d/%m/%Y')}"
        )
        body_html = body_html or (
            "<table>"
            "<tr><th>ID</th><th>Store Name</th><th>Region</th><th>Last Trans.</th><th>Buss. Date</th><th>Status</th></tr>"
            f"<tr><td>{sap}</td><td>{store_name}</td><td>{branch.region if branch else 'Cairo'}</td>"
            "<td>21:15</td><td>Today</td><td>Not Updated</td></tr>"
            "</table>"
        )
        body_text = (
            body_text or f"Replication Dashboard table: store {sap} ({store_name}) is Not Updated."
        )
    elif scenario == "CABLE_UNPLUGGED_PHOTO":
        sender = sender or reg_it_sender
        t_tag = f"[{linked_ticket.ticket_number}] " if linked_ticket else ""
        subject = subject or f"{t_tag}Store {sap} ({store_name}) offline — router photo attached"
        body_text = body_text or (
            f"Dear Network Support,\n"
            f"Store {sap} ({store_name}) is down. Router photo attached (WAN cable appears loose/unplugged and power LED off).\n"
            f"Site contact: 010 2345 8817"
        )
        attachments = attachments or [f"router_{sap}_unplugged.jpg"]
    elif scenario == "REGIONAL_IT_CABLE_FIXED":
        sender = sender or reg_it_sender
        t_tag = f"[{linked_ticket.ticket_number}] " if linked_ticket else ""
        subject = (
            subject or f"RE: {t_tag}Store {sap} ({store_name}) — Cables reseated & fresh photo"
        )
        body_text = body_text or (
            f"Dear Network Support,\n"
            f"We reseated and plugged in all WAN/LAN RJ45 cables on the router at store {sap}. "
            f"Power LED is solid green now, but store is still offline. Fresh router photo attached.\n"
            f"Site contact: 010 2345 8817"
        )
        attachments = attachments or [f"router_{sap}_seated.jpg"]
    elif scenario == "ISP_WELCOME":
        sender = sender or isp_sender
        if isp_name == "ORANGE":
            subject = subject or f"RE: store {sap} # {ll_id}"
            body_text = body_text or (
                f"Dear Kazyon IT,\n"
                f"Your request for store {sap} ({ll_id}) has been registered with ticket number ({default_case_ref}).\n"
                "Our NOC engineers are checking the L.L and 4G backup link now."
            )
        elif isp_name == "WE":
            subject = (
                subject
                or f"Re: [Request ID :##RE-{default_case_ref}##] : Kazyon #E33209 #{ll_id} #{g3_id} #{sap}"
            )
            body_text = body_text or (
                f"Dear Value Customer,\n"
                f"We opened trouble ticket ref.tt#{default_case_ref} for store {sap} (LL {ll_id} / 4G {g3_id}) and we are checking now."
            )
        else:
            subject = (
                subject
                or f"NOOR NOC - Case No: {default_case_ref} - KAZYON - {store_name} - Ticket Initiation"
            )
            body_text = body_text or (
                f"Dear Kazyon Team,\n"
                f"Kindly note that we opened trouble ticket #{default_case_ref} for store {sap} ({store_name}) and are investigating the outage."
            )
    elif scenario == "ISP_CONTACT_UNREACHABLE":
        sender = sender or isp_sender
        subject = subject or (
            f"Re: NOOR NOC - Case No: {default_case_ref} - KAZYON - {store_name} - Ticket Update"
            if isp_name == "NOOR"
            else f"RE: store {sap} # {ll_id} (Case {default_case_ref})"
        )
        body_text = body_text or (
            f"Dear Kazyon Team,\n"
            f"Regarding store {sap} (Case #{default_case_ref}), we tried to call the site contact multiple times "
            "but the phone is switched off / unavailable. Kindly provide an available site contact number and restart the router."
        )
    elif scenario == "REGIONAL_IT_NEW_PHONE":
        sender = sender or reg_it_sender
        t_tag = f"[{linked_ticket.ticket_number}]" if linked_ticket else f"store {sap}"
        subject = subject or f"RE: URGENT {t_tag}: ISP cannot reach site contact"
        body_text = body_text or (
            f"Dear Network Support,\n"
            f"For store {sap} ({store_name}), the router has been restarted and the active phone number for the shift manager is 010 9988 7766.\n"
            "Kindly relay to the ISP NOC."
        )
    elif scenario == "ISP_RESOLVED":
        sender = sender or isp_sender
        subject = subject or (
            f"NOOR NOC - Ticket update #{default_case_ref} - KAZYON - {store_name} - Ticket Closure"
            if isp_name == "NOOR"
            else f"RE: store {sap} # {ll_id} — Ticket Closure ({default_case_ref})"
        )
        body_text = body_text or (
            f"Dear Kazyon IT,\n"
            f"Regarding store {sap} (Case #{default_case_ref}), the transmission problem has been solved and the link has been restored "
            "with 0% packet loss. Kindly confirm ticket closure."
        )
        if get_settings().diagnostic_mode == "simulated":
            diag_scenario = diag_scenario or "PASS"
    elif scenario == "ISP_RESOLVED_STILL_DOWN":
        sender = sender or isp_sender
        subject = subject or (
            f"NOOR NOC - Ticket update #{default_case_ref} - KAZYON - {store_name} - Ticket Closure"
            if isp_name == "NOOR"
            else f"RE: store {sap} # {ll_id} — Ticket Closure ({default_case_ref})"
        )
        body_text = body_text or (
            f"Dear Kazyon IT,\n"
            f"Regarding store {sap} (Case #{default_case_ref}), the link has been restored and working fine now. "
            "Closing trouble ticket."
        )
        if get_settings().diagnostic_mode == "simulated":
            diag_scenario = diag_scenario or "FULL_OUTAGE"
    elif scenario == "ISP_QUOTA_BLOCKER":
        sender = sender or isp_sender
        subject = subject or f"RE: store {sap} # {ll_id} (Case {default_case_ref})"
        body_text = body_text or (
            f"Dear Kazyon IT,\n"
            f"After checking store {sap} (Case #{default_case_ref}), please note that the 4G backup bundle quota is consumed. "
            "Kindly contact your Account Manager for quota renewal."
        )
    elif scenario == "UNRECOGNIZED":
        sender = sender or "vendor-invoices@external-supplier.com"
        subject = subject or "Monthly Fiber Conduit Lease Invoice #INV-2026-991"
        body_text = body_text or (
            "Please find attached the monthly accounting reconciliation statement for Q3 conduit leases."
        )
    else:
        # Default: BRANCH_INCIDENT or CUSTOM (supports acting as ISP or BRANCH)
        if role_override == "ISP":
            sender = sender or isp_sender
            subject = subject or f"RE: store {sap} # {ll_id} (Case {default_case_ref})"
            body_text = body_text or (
                f"Dear Kazyon IT,\n"
                f"Regarding store {sap} (Case #{default_case_ref}), our NOC team is checking the circuit."
            )
        else:
            sender = sender or reg_it_sender
            t_tag = f"[{linked_ticket.ticket_number}] " if linked_ticket else ""
            subject = subject or f"{t_tag}Store {sap} ({store_name}) network down"
            body_text = body_text or (
                f"Dear Network Support,\n"
                f"Store {sap} ({store_name}) is offline and POS terminals are not syncing.\n"
                f"Router photo is attached (cables seated, power LED on, WAN LED dark).\n"
                f"Site contact: 010 2345 8817"
            )
            if not attachments and scenario == "BRANCH_INCIDENT":
                attachments = [f"router_{sap}_photo.jpg"]

    raw_eml = build_synthetic_eml_bytes(
        sender=sender,
        recipients=["noc@kazyon.com"],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        in_reply_to=in_reply_to,
        references=references_list,
        attachment_filenames=attachments,
    )

    return await ingest_and_triage_eml(
        db,
        raw_eml,
        filename=f"loop_{scenario.lower()}_{sap}.eml",
        diagnostic_scenario=diag_scenario,
        _from_harness=True,
    )


async def reclassify_existing_email(
    db: Session,
    email_id: int,
) -> dict[str, Any]:
    """Re-run Gemma 4 classification and workflow correlation on an existing `TicketEmail` record."""
    em = db.get(TicketEmail, email_id)
    if em is None:
        from app.common.exceptions import EntityNotFoundError

        raise EntityNotFoundError("TicketEmail", str(email_id))

    raw_eml = build_synthetic_eml_bytes(
        sender=em.sender,
        recipients=list(em.recipients or ["noc@kazyon.com"]),
        cc=list(em.cc or []),
        subject=em.subject,
        body_text=em.body_text,
        body_html=em.body_html,
        in_reply_to=em.in_reply_to,
        attachment_filenames=[str(a.get("filename", "")) for a in (em.attachments_json or [])],
    )
    env = parse_eml_bytes(raw_eml)
    settings_row = ensure_system_settings(db)
    ticket = db.get(Ticket, em.ticket_id) if em.ticket_id else None
    branch = db.get(Branch, ticket.branch_id) if ticket and ticket.branch_id else None

    triage = await classify_inbound_email(
        env,
        confidence_threshold_pct=settings_row.confidence_threshold,
        correlated_branch_code=branch.branch_code if branch else None,
        thread_history=_load_ticket_thread_history(db, ticket),
        llm_options=vllm_call_options(settings_row),
    )
    em.classification_label = triage.classification_label
    em.ai_analysis_json = triage.raw_analysis
    db.commit()

    return {
        "email_id": em.id,
        "subject": em.subject,
        "classification_label": triage.classification_label,
        "trigger_type": triage.trigger_type,
        "intent": triage.intent,
        "confidence": triage.confidence,
        "ticket_number": ticket.ticket_number if ticket else "—",
        "triage": triage.model_dump(),
    }
