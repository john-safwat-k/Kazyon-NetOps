"""Comprehensive service layer for Tickets, Kanban Board, 360° Detail, Dashboard, Replication, Escalations, Mailbox, and Settings."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, cast

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.agent.vllm_client import probe_vllm_endpoint
from app.auth.models import User
from app.common.audit import record_audit_event
from app.common.config import get_settings
from app.common.crypto import encrypt_secret
from app.common.contracts import (
    ConnectionFailureType,
    EscalationReason,
    TicketPriority,
    TicketStatus,
    TicketTriggerSource,
)
from app.common.exceptions import EntityNotFoundError, InvalidStateTransitionError
from app.diagnostics.base import DualPingTracerouteRequest
from app.diagnostics.service import list_recent_diagnostic_runs, run_and_persist_diagnostics
from app.directory.models import Branch
from app.directory.service import ensure_directory_seeded, get_branch_by_code
from app.email_engine.imap_poller import (
    imap_transport_config_from_row,
    test_imap_connection_sync,
)
from app.email_engine.parser import split_email_thread_replies
from app.email_engine.smtp_sender import (
    _send_via_live_smtp_sync,
    dispatch_outbound_email,
    format_isp_escalation_email,
    load_smtp_transport_config,
    resolve_branch_regional_it_cc,
    resolve_isp_recipients,
    smtp_transport_config_from_row,
    test_smtp_connection_sync,
)
from app.observability.event_bus import event_bus
from app.ticketing.models import (
    DiagnosticRun,
    ReplicationReport,
    ReplicationReportRow,
    SystemSettings,
    Ticket,
    TicketEmail,
    TicketEvent,
)
from app.ticketing.schemas import (
    DashboardSummaryResponse,
    EscalationItemDto,
    ImapConnectionTestRequest,
    ImapConnectionTestResult,
    KanbanTicketCardDto,
    SendTestEmailRequest,
    SendTestEmailResult,
    SmtpConnectionTestRequest,
    SmtpConnectionTestResult,
    SystemSettingsDto,
    SystemSettingsUpdateRequest,
    TicketCreateManualRequest,
    TicketDetail360Response,
    TicketEmailItemDto,
    TicketEmailReplyRequest,
    TicketEscalateHumanRequest,
    TicketNoteCreateRequest,
    TicketStatusUpdateRequest,
    TimelineEventDto,
    VisionOverrideRequest,
    VllmConnectionTestRequest,
    VllmConnectionTestResult,
)
from app.ticketing.state_machine import (
    assert_transition,
    compute_sla_tuple,
    resolve_human_stage_label,
    resolve_kanban_column,
)

logger = logging.getLogger("it_net.ticketing.service")

FAILURE_DISPLAY_NAMES: dict[str, str] = {
    ConnectionFailureType.FULL_OUTAGE.value: "Full outage",
    ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value: "Local loop down (4G)",
    ConnectionFailureType.INTERNAL_LAN_SWITCH.value: "Internal switch",
    ConnectionFailureType.CABLE_UNPLUGGED.value: "Cables unplugged",
    "QUOTA_CONSUMED": "Quota consumed",
    "MSAN_MIGRATION": "MSAN migration",
    "INTERNAL_BOX_CABLE": "New internal cable needed",
    "SITE_CONTACT_UNREACHABLE": "Site contact unreachable",
    "ROUTER_PHOTO_CHECK": "Router photo check",
}

DEMO_TICKET_NUMBERS: set[str] = {
    "NET-1058",
    "NET-1057",
    "NET-1055",
    "NET-1054",
    "NET-1053",
    "NET-1052",
    "NET-1051",
    "NET-1050",
    "NET-1049",
    "NET-1047",
    "NET-1046",
    "NET-1044",
    "NET-1041",
    "NET-1040",
}


def ensure_system_settings(db: Session) -> SystemSettings:
    """Ensure singleton `system_settings` row (`config_key='global'`) exists."""
    row = db.execute(
        select(SystemSettings).where(SystemSettings.config_key == "global").limit(1)
    ).scalar_one_or_none()
    if row is not None:
        return row

    row = SystemSettings(
        config_key="global",
        global_ai_kill_switch=False,
        mailbox_account="itsupport-agent@kazyon.com",
        imap_host="outlook.office365.com",
        imap_port=993,
        smtp_host="",
        smtp_port=587,
        smtp_security="starttls",
        smtp_enabled=False,
        poll_interval_sec=30,
        vllm_endpoint=f"{get_settings().vllm_base_url.rstrip('/')}/v1",
        vllm_temperature=get_settings().vllm_temperature,
        vllm_max_tokens=get_settings().vllm_max_tokens,
        confidence_threshold=80,
        welcome_sla_minutes=120,
        followup_interval_minutes=300,
        max_chasers_before_human=4,
        max_outbound_emails_per_ticket_hour=6,
        ignore_auto_submitted=True,
        diagnostic_timeout_sec=20,
        ping_count=4,
        traceroute_max_hops=15,
        fallback_contacts=[
            {"ini": "NO", "email": "noc-oncall@kazyon.com", "role": "On-duty engineer"},
            {
                "ini": "IT",
                "email": "ITInfrastructure@kazyon.com",
                "role": "HQ IT Infrastructure team",
            },
        ],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def purge_legacy_demo_data(db: Session) -> None:
    """Remove any previously seeded demo tickets, demo emails, and demo replication reports."""
    demo_reps = (
        db.execute(
            select(ReplicationReport).where(ReplicationReport.message_id.like("<rep-%@kazyon.com>"))
        )
        .scalars()
        .all()
    )
    for rep in demo_reps:
        db.execute(delete(ReplicationReportRow).where(ReplicationReportRow.report_id == rep.id))
        db.delete(rep)

    db.execute(delete(TicketEmail).where(TicketEmail.message_id.like("<%.kz@kazyon.com>")))

    demo_tickets = (
        db.execute(select(Ticket).where(Ticket.ticket_number.in_(DEMO_TICKET_NUMBERS)))
        .scalars()
        .all()
    )
    for t in demo_tickets:
        db.execute(delete(TicketEvent).where(TicketEvent.ticket_id == t.id))
        db.execute(delete(DiagnosticRun).where(DiagnosticRun.ticket_id == t.id))
        db.execute(delete(TicketEmail).where(TicketEmail.ticket_id == t.id))
        db.delete(t)

    db.commit()


def ensure_operational_seed_data(db: Session) -> None:
    """Ensure real Excel store directory (1,150 stores, 3 ISPs) and system settings exist, with no demo data."""
    ensure_directory_seeded(db)
    ensure_system_settings(db)


def _build_kanban_card_dto(db: Session, ticket: Ticket) -> KanbanTicketCardDto:
    branch = db.get(Branch, ticket.branch_id) if ticket.branch_id else None
    branch_code = branch.branch_code if branch else "0000"
    branch_label = branch.name if branch else ticket.title.split(" · ")[0]
    region = branch.region if branch and branch.region else "Cairo"
    isp_raw = (branch.isp_name if branch else "NOOR").upper()
    if isp_raw not in {"NOOR", "ORANGE", "WE"}:
        isp_raw = "NOOR"

    col = resolve_kanban_column(ticket)
    stage_label = resolve_human_stage_label(ticket)
    sla = compute_sla_tuple(ticket)

    latest_diag = db.execute(
        select(DiagnosticRun)
        .where(DiagnosticRun.ticket_id == ticket.id)
        .order_by(DiagnosticRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    checks: Optional[list[tuple[str, Literal["up", "down", "hub", "skip"]]]] = None
    if latest_diag is not None:
        checks = []
        if latest_diag.ip_1_up is not None:
            checks.append(("IP1", "up" if latest_diag.ip_1_up else "down"))
        if latest_diag.ip_1_up is False:
            checks.append(("IP2", "skip"))
        elif latest_diag.ip_2_up is not None:
            checks.append(("IP2", "up" if latest_diag.ip_2_up else "down"))
        if latest_diag.four_g_hub_detected:
            checks.append(("4G", "hub"))

    failure_label = FAILURE_DISPLAY_NAMES.get(ticket.connection_failure_type or "")
    note: Optional[str] = None
    if col == 0:
        note = "Replication: Not Updated"
    elif col == 1:
        note = "Vision: analysing photo"
    elif col == 2:
        note = (
            "Awaiting new photo"
            if ticket.status == TicketStatus.AWAITING_BRANCH.value
            else f"Returned to {branch.regional_it_email.split('@')[0] if branch and branch.regional_it_email else 'Regional IT'}"
        )
    elif col == 5:
        note = "Re-pinging after ISP closure"
    elif col == 6:
        note = "Engineer notified"
    elif col == 7:
        closed_time = ticket.resolved_at.strftime("%H:%M") if ticket.resolved_at else ""
        note = f"Closed {closed_time}".strip()

    mttr_str = "—"
    if ticket.resolved_at and ticket.created_at:
        c_dt = (
            ticket.created_at
            if ticket.created_at.tzinfo
            else ticket.created_at.replace(tzinfo=timezone.utc)
        )
        r_dt = (
            ticket.resolved_at
            if ticket.resolved_at.tzinfo
            else ticket.resolved_at.replace(tzinfo=timezone.utc)
        )
        hours = max(0.1, abs((r_dt - c_dt).total_seconds()) / 3600.0)
        mttr_str = f"{hours:.1f}h"

    opened_str = ticket.created_at.strftime("%d %b %H:%M") if ticket.created_at else "—"
    prio = ticket.priority if ticket.priority in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else "MEDIUM"

    return KanbanTicketCardDto(
        id=ticket.ticket_number,
        ticket_db_id=ticket.id,
        priority=cast(Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"], prio),
        branch=branch_label,
        branch_code=branch_code,
        region=region,
        failure=failure_label,
        failure_code=ticket.connection_failure_type or "—",
        trigger=ticket.trigger_source,
        isp=cast(Literal["NOOR", "ORANGE", "WE"], isp_raw),
        caseRef=ticket.isp_reference_number or None,
        checks=checks,
        sla=sla,
        note=note,
        aiPaused=not ticket.ai_automation_enabled,
        status=stage_label,
        raw_status=ticket.status,
        opened=opened_str,
        mttr=mttr_str,
        col=col,
    )


def list_ticket_cards(
    db: Session,
    *,
    search: Optional[str] = None,
    isp: Optional[str] = None,
    region: Optional[str] = None,
    priority: Optional[str] = None,
    trigger: Optional[str] = None,
    failure_type: Optional[str] = None,
    ai_paused_only: bool = False,
) -> list[KanbanTicketCardDto]:
    """List all tickets formatted as `KanbanTicketCardDto` for Page 3 (Kanban) & Page 4 (Tickets List)."""
    tickets = db.execute(select(Ticket).order_by(Ticket.id.desc())).scalars().all()
    cards = [_build_kanban_card_dto(db, t) for t in tickets]

    results: list[KanbanTicketCardDto] = []
    for c in cards:
        if isp and isp.upper() not in {"ALL", "ISP: ALL"} and c.isp != isp.upper():
            continue
        if (
            region
            and region.lower() not in {"all", "region: all"}
            and c.region.lower() != region.lower()
        ):
            continue
        if priority and priority.upper() != "ALL" and c.priority != priority.upper():
            continue
        if (
            trigger
            and trigger.upper() not in {"ALL", "TRIGGER: ALL"}
            and c.trigger != trigger.upper()
        ):
            continue
        if (
            failure_type
            and failure_type.upper() not in {"ALL", "FAILURE: ALL"}
            and c.failure_code != failure_type
        ):
            continue
        if ai_paused_only and not c.aiPaused:
            continue
        if search:
            q = search.strip().lower()
            haystack = (
                f"{c.id} {c.branch} {c.branch_code} {c.caseRef or ''} {c.region} {c.isp}".lower()
            )
            if q not in haystack:
                continue
        results.append(c)
    return results


def get_dashboard_summary(db: Session, range_key: str = "7d") -> DashboardSummaryResponse:
    """Compute Executive & Live SLA Dashboard KPIs, bar charts, and SLA watchlist from real DB rows (Page 2)."""
    now = datetime.now(timezone.utc)
    cutoff_days = 1 if range_key == "24h" else (30 if range_key == "30d" else 7)
    cutoff = now - timedelta(days=cutoff_days)

    all_tickets = db.execute(select(Ticket).order_by(Ticket.id.desc())).scalars().all()
    cards = [_build_kanban_card_dto(db, t) for t in all_tickets]

    # Filter tickets within range for charts
    range_tickets: list[Ticket] = []
    for t in all_tickets:
        c_dt = (
            t.created_at
            if t.created_at and t.created_at.tzinfo
            else (t.created_at.replace(tzinfo=timezone.utc) if t.created_at else now)
        )
        if c_dt >= cutoff:
            range_tickets.append(t)

    range_cards = [_build_kanban_card_dto(db, t) for t in range_tickets]

    open_cards = [c for c in cards if c.col < 7]
    unrecognized_emails_count = (
        db.execute(
            select(func.count())
            .select_from(TicketEmail)
            .where(
                TicketEmail.ticket_id.is_(None),
                TicketEmail.classification_label == "UNRECOGNIZED",
            )
        ).scalar_one()
        or 0
    )
    review_cards = [c for c in cards if c.col == 6]
    welcome_overdue = [c for c in cards if c.col == 3 and c.sla is not None and c.sla[0] < 0]
    followup_overdue = [c for c in cards if c.col == 4 and c.sla is not None and c.sla[0] < 0]

    latest_rep = db.execute(
        select(ReplicationReport).order_by(ReplicationReport.id.desc()).limit(1)
    ).scalar_one_or_none()
    repl_not_updated = latest_rep.not_updated_count if latest_rep else 0

    range_label = (
        "today" if range_key == "24h" else ("last 30 days" if range_key == "30d" else "last 7 days")
    )

    watch_candidates = [c for c in cards if c.col in {3, 4} and c.sla is not None]
    watch_candidates.sort(key=lambda x: x.sla[0] if x.sla else 9999)
    watchlist: list[dict[str, Any]] = []
    for w in watch_candidates[:6]:
        watchlist.append(
            {
                "id": w.id,
                "branch": w.branch,
                "region": w.region,
                "failure": w.failure or "Full outage",
                "isp": w.isp,
                "checks": [{"label": lbl, "state": st} for lbl, st in (w.checks or [])],
                "stage": "Escalated · Welcome" if w.col == 3 else "With ISP",
                "tone": "critical" if (w.sla and w.sla[0] < 0) else "brand",
                "left": w.sla[0] if w.sla else 45,
                "total": w.sla[1] if w.sla else 120,
            }
        )

    # Real store counts per ISP and Region from the 1,150-store directory
    isp_store_rows = db.execute(
        select(Branch.isp_name, func.count()).group_by(Branch.isp_name)
    ).all()
    isp_store_counts = {str(r[0]).upper(): int(r[1]) for r in isp_store_rows if r[0]}

    region_store_rows = db.execute(
        select(Branch.region, func.count()).group_by(Branch.region)
    ).all()
    region_store_counts = {str(r[0]): int(r[1]) for r in region_store_rows if r[0]}

    # Outages by ISP (from range_cards)
    isp_outages = {"NOOR": 0, "ORANGE": 0, "WE": 0}
    for c in range_cards:
        isp_outages[c.isp] = isp_outages.get(c.isp, 0) + 1

    # MTTR by ISP (from resolved tickets in range)
    mttr_buckets: dict[str, list[float]] = {"NOOR": [], "ORANGE": [], "WE": []}
    for t in range_tickets:
        if t.resolved_at and t.created_at:
            branch = db.get(Branch, t.branch_id) if t.branch_id else None
            isp_k = (branch.isp_name if branch else "NOOR").upper()
            c_dt = (
                t.created_at if t.created_at.tzinfo else t.created_at.replace(tzinfo=timezone.utc)
            )
            r_dt = (
                t.resolved_at
                if t.resolved_at.tzinfo
                else t.resolved_at.replace(tzinfo=timezone.utc)
            )
            hrs = max(0.1, abs((r_dt - c_dt).total_seconds()) / 3600.0)
            if isp_k in mttr_buckets:
                mttr_buckets[isp_k].append(hrs)

    mttr_by_isp = [
        {
            "label": k,
            "value": round(sum(vals) / len(vals), 1) if vals else 0.0,
            "hint": f"{isp_store_counts.get(k, 0)} stores",
        }
        for k, vals in mttr_buckets.items()
    ]

    # Outages by failure type
    type_counts = {
        "Full outage": 0,
        "4G / LL down": 0,
        "Internal switch": 0,
        "Cables": 0,
    }
    for c in range_cards:
        fc = c.failure_code or ""
        if fc == ConnectionFailureType.FULL_OUTAGE.value:
            type_counts["Full outage"] += 1
        elif fc == ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value:
            type_counts["4G / LL down"] += 1
        elif fc == ConnectionFailureType.INTERNAL_LAN_SWITCH.value:
            type_counts["Internal switch"] += 1
        elif fc == ConnectionFailureType.CABLE_UNPLUGGED.value:
            type_counts["Cables"] += 1

    # Outages by region (include canonical + any custom regions from uploaded branches)
    canonical_regions = ["Behera", "Cairo", "New October", "Assyut", "Giza"]
    extra_regions = sorted(r for r in region_store_counts if r and r not in canonical_regions)
    all_regions = canonical_regions + extra_regions
    region_outages = {r: 0 for r in all_regions}
    for c in range_cards:
        if c.region in region_outages:
            region_outages[c.region] += 1
        elif c.region:
            region_outages[c.region] = region_outages.get(c.region, 0) + 1
            if c.region not in all_regions:
                all_regions.append(c.region)

    total_branches = sum(isp_store_counts.values()) or int(
        db.execute(select(func.count()).select_from(Branch)).scalar_one() or 0
    )

    return DashboardSummaryResponse(
        range_key=range_key,
        range_label=range_label,
        total_branches=total_branches,
        regions_list=all_regions,
        kpis={
            "open": len(open_cards),
            "review": len(review_cards) + int(unrecognized_emails_count),
            "welcome": len(welcome_overdue),
            "followup": len(followup_overdue),
            "repl": repl_not_updated,
        },
        services=[
            {
                "name": "vLLM · Gemma 4 26B",
                "detail": "10.100.109.9:8002 · Ready",
                "state": "ok",
            },
            {
                "name": "IMAP / SMTP Mailbox",
                "detail": "Service account active",
                "state": "ok",
            },
            {"name": "PostgreSQL 16", "detail": "Connected", "state": "ok"},
            {"name": "Redis 7", "detail": "Loop guard active", "state": "ok"},
        ],
        by_isp=[
            {
                "label": k,
                "value": isp_outages.get(k, 0),
                "hint": f"{isp_store_counts.get(k, 0)} stores",
            }
            for k in ("NOOR", "ORANGE", "WE")
        ],
        mttr_by_isp=mttr_by_isp,
        by_type=[{"label": lbl, "value": val} for lbl, val in type_counts.items()],
        by_region=[
            {
                "label": r,
                "value": region_outages.get(r, 0),
                "hint": f"{region_store_counts.get(r, 0)} stores",
            }
            for r in all_regions
        ],
        watchlist=watchlist,
    )


def get_ticket_by_number_or_id(db: Session, ticket_identifier: str) -> Ticket:
    ident = ticket_identifier.strip().upper()
    if ident.isdigit():
        t = db.get(Ticket, int(ident))
    else:
        t = db.execute(
            select(Ticket).where(func.upper(Ticket.ticket_number) == ident).limit(1)
        ).scalar_one_or_none()
    if t is None:
        raise EntityNotFoundError("Ticket", ticket_identifier)
    return t


def get_ticket_360_detail(db: Session, ticket_identifier: str) -> TicketDetail360Response:
    """Build the full 360° Ticket Detail response with 4 tabs (Timeline, Tests & Vision, Branch Emails, ISP Emails)."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)
    branch = db.get(Branch, ticket.branch_id) if ticket.branch_id else None

    sap_code = branch.branch_code if branch else "—"
    store_name = branch.name if branch else ticket.title.split(" · ")[0]
    ip_1 = branch.ip_1 if branch else "—"
    ip_2 = branch.ip_2 if branch else "—"
    region = branch.region if branch and branch.region else "—"
    reg_it = (
        branch.regional_it_email
        if branch and branch.regional_it_email
        else (ticket.sender_email or "—")
    )
    isp_name = (branch.isp_name if branch else "NOOR").upper()
    isp_mail = branch.isp_contact_mail if branch else "noc@noor.net"
    ll_id = branch.ll_circuit_id if branch and branch.ll_circuit_id else "—"
    g3_id = branch.backup_circuit_id if branch and branch.backup_circuit_id else "—"
    hub_ip = branch.four_g_hub_ip if branch and branch.four_g_hub_ip else "—"

    sla_tuple = compute_sla_tuple(ticket) or (120, 120)
    stage_label = resolve_human_stage_label(ticket)

    events_db = (
        db.execute(
            select(TicketEvent)
            .where(TicketEvent.ticket_id == ticket.id)
            .order_by(TicketEvent.id.desc())
        )
        .scalars()
        .all()
    )
    color_map = {
        "chaser_scheduled": "info",
        "isp_welcome": "good",
        "isp_escalated": "brand-600",
        "traceroute_hub": "info",
        "dual_ping": "critical",
        "vision_passed": "good",
        "human_escalated": "critical",
        "diagnostic_triggered": "info",
    }
    timeline_items: list[TimelineEventDto] = []
    for ev in events_db:
        timeline_items.append(
            TimelineEventDto(
                id=ev.id,
                time=ev.created_at.strftime("%H:%M") if ev.created_at else "00:00",
                color=color_map.get(ev.event_type, "ink-muted"),
                title=ev.summary,
                actor=ev.actor_name or ev.actor_type,
                detail=str((ev.details_json or {}).get("detail") or ev.event_type),
                event_type=ev.event_type,
            )
        )

    runs_raw = list_recent_diagnostic_runs(db, ticket_id=ticket.id, limit=15)
    runs_dtos: list[dict[str, Any]] = []
    for idx, r in enumerate(runs_raw):
        tone = (
            "good"
            if r.result_status == "PASS"
            else ("critical" if r.result_status == "FAIL" else "warning")
        )
        runs_dtos.append(
            {
                "id": r.id,
                "label": r.trigger_source,
                "when": r.executed_at[11:16] if len(r.executed_at) >= 16 else r.executed_at,
                "ms": f"{r.duration_ms / 1000.0:.1f} s",
                "open": idx == 0,
                "result": r.result_status,
                "diagnosis_code": r.diagnosis_code,
                "tone": tone,
                "checks": [c.model_dump() for c in r.checks],
                "log": r.raw_output,
            }
        )

    emails_db = (
        db.execute(
            select(TicketEmail)
            .where(TicketEmail.ticket_id == ticket.id)
            .order_by(TicketEmail.id.asc())
        )
        .scalars()
        .all()
    )
    branch_emails: list[TicketEmailItemDto] = []
    isp_emails: list[TicketEmailItemDto] = []
    for em in emails_db:
        dto = TicketEmailItemDto(
            id=em.id,
            from_addr=em.sender,
            to_addr=", ".join(em.recipients or []),
            cc_addr=", ".join(em.cc or []),
            when=em.sent_or_received_at.strftime("%H:%M") if em.sent_or_received_at else "00:00",
            direction="Outbound" if em.direction == "OUTBOUND" else "Inbound",
            thread_type=em.thread_type,
            subject=em.subject,
            body=em.body_text,
            outbound=em.direction == "OUTBOUND",
            classification_label=em.classification_label,
            attachments=list(em.attachments_json or []),
            thread_replies=split_email_thread_replies(em.body_text or ""),
        )
        if em.thread_type == "ISP":
            isp_emails.append(dto)
        else:
            branch_emails.append(dto)

    prio = ticket.priority if ticket.priority in {"CRITICAL", "HIGH", "MEDIUM", "LOW"} else "HIGH"
    has_photo = bool(ticket.router_image_paths)

    return TicketDetail360Response(
        ticket_db_id=ticket.id,
        ticket_number=ticket.ticket_number,
        title=f"{store_name} · {FAILURE_DISPLAY_NAMES.get(ticket.connection_failure_type or '', 'Network Incident')}",
        description=ticket.description,
        status=ticket.status,
        stage_label=stage_label,
        priority=cast(Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"], prio),
        trigger_source=ticket.trigger_source,
        ai_automation_enabled=ticket.ai_automation_enabled,
        opened_at=ticket.created_at.strftime("%d %b %H:%M") if ticket.created_at else "—",
        sender_email=ticket.sender_email or reg_it,
        site_contact_phone=ticket.site_contact_phone or "",
        isp_reference_number=ticket.isp_reference_number or "",
        isp_welcome_received=ticket.isp_welcome_received,
        followup_count=ticket.followup_count,
        sla_minutes_left=sla_tuple[0],
        sla_total_minutes=sla_tuple[1],
        sla_summary_text=(
            f"Welcome mail {'received' if ticket.isp_welcome_received else 'pending'} · "
            f"{ticket.followup_count} chasers sent"
        ),
        branch={
            "code": sap_code,
            "name": store_name,
            "ip1": ip_1,
            "ip2": ip_2,
            "region": region,
            "regional_it_email": reg_it,
        },
        isp={
            "name": isp_name,
            "support_email": isp_mail,
            "ll_circuit_id": ll_id,
            "backup_circuit_id": g3_id,
            "four_g_hub_ip": hub_ip,
        },
        vision={
            "has_photo": has_photo,
            "photo_filename": (
                ticket.router_image_paths[0] if ticket.router_image_paths else "No photo attached"
            ),
            "cables_plugged": ticket.image_check_passed is not False,
            "power_led_on": ticket.image_check_passed is not False,
            "wan_led_on": False,
            "confidence": 0.91 if has_photo else 0.0,
            "summary": ticket.image_analysis_summary or "No router photo analyzed yet.",
        },
        events=timeline_items,
        diagnostic_runs=runs_dtos,
        branch_emails=branch_emails,
        isp_emails=isp_emails,
    )


async def create_manual_ticket(
    db: Session,
    payload: TicketCreateManualRequest,
    *,
    actor: User,
) -> KanbanTicketCardDto:
    """Create a manual ticket from Page 3 / Page 2 and optionally trigger initial diagnostics."""
    branch = get_branch_by_code(db, payload.branch_code)

    max_id = db.execute(select(func.max(Ticket.id))).scalar_one() or 0
    ticket_number = f"NET-{1001 + int(max_id)}"

    ticket = Ticket(
        ticket_number=ticket_number,
        title=f"{branch.name if branch else payload.branch_code} · Manual Incident",
        description=payload.description,
        trigger_source=payload.trigger_source,
        status=TicketStatus.DIAGNOSING.value,
        priority=payload.priority,
        branch_id=branch.id if branch else None,
        isp_id=branch.isp_id if branch else None,
        sender_email=actor.email,
        site_contact_phone=payload.site_contact_phone or "",
        router_image_paths=[],
        image_check_passed=True,
        ai_automation_enabled=True,
    )
    db.add(ticket)
    db.flush()

    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            event_type="ticket_created",
            summary=f"Manual ticket {ticket.ticket_number} created",
            details_json={"detail": f"Created by {actor.display_name}"},
        )
    )
    db.commit()
    db.refresh(ticket)

    if payload.run_diagnostics and branch is not None:
        diag_res = await run_and_persist_diagnostics(
            db,
            DualPingTracerouteRequest(
                branch_code=branch.branch_code,
                ticket_id=ticket.id,
                trigger_source="INITIAL",
                simulate_scenario=payload.simulate_scenario or "AUTO",
            ),
            actor_name="AI_AGENT",
        )
        if diag_res.diagnosis_code in {
            ConnectionFailureType.FULL_OUTAGE.value,
            ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value,
        }:
            transition_ticket(
                db,
                ticket,
                TicketStatus.ESCALATED_TO_ISP,
                actor_type="AI_AGENT",
                actor_name="AI_AGENT",
                reason=diag_res.diagnosis_code,
            )
            ticket.connection_failure_type = diag_res.diagnosis_code
            ticket.next_followup_at = datetime.now(timezone.utc) + timedelta(minutes=120)
            subj, body, to_list, cc_list, tpl = format_isp_escalation_email(
                branch, site_contact_phone=ticket.site_contact_phone
            )
            await dispatch_outbound_email(
                db,
                ticket=ticket,
                thread_type="ISP",
                recipients=to_list,
                cc=cc_list,
                subject=subj,
                body_text=body,
                classification_label="ESCALATION",
                ai_analysis_json={"template": tpl, "thread": "ISP"},
            )
            db.add(
                TicketEvent(
                    ticket_id=ticket.id,
                    actor_type="AI_AGENT",
                    actor_name="AI_AGENT",
                    event_type="isp_escalated",
                    summary=f"Escalated to {branch.isp_name}",
                    details_json={"detail": f"Subject: {subj}"},
                )
            )
        elif diag_res.diagnosis_code == ConnectionFailureType.INTERNAL_LAN_SWITCH.value:
            transition_ticket(
                db,
                ticket,
                TicketStatus.INTERNAL_LAN_ISSUE,
                actor_type="AI_AGENT",
                actor_name="AI_AGENT",
                reason=diag_res.diagnosis_code,
            )
            ticket.connection_failure_type = diag_res.diagnosis_code
        else:
            transition_ticket(
                db,
                ticket,
                TicketStatus.CLOSED,
                actor_type="AI_AGENT",
                actor_name="AI_AGENT",
                reason="Initial diagnostics passed",
            )
        db.commit()
        db.refresh(ticket)

    return _build_kanban_card_dto(db, ticket)


def transition_ticket(
    db: Session,
    ticket: Ticket,
    target: TicketStatus | str,
    *,
    actor_type: str = "AI_AGENT",
    actor_name: str = "AI_AGENT",
    reason: str = "",
    force: bool = False,
) -> Ticket:
    """Validate and apply a ticket state transition, recording a `status_changed` event and broadcasting WS."""
    old_status = str(ticket.status)
    target_enum = TicketStatus(str(target))
    target_str = target_enum.value

    if not force:
        assert_transition(old_status, target_enum)

    now = datetime.now(timezone.utc)
    ticket.status = target_str
    if target_enum in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
        ticket.resolved_at = now
        ticket.next_followup_at = None
    elif target_enum == TicketStatus.NEEDS_HUMAN_REVIEW:
        ticket.ai_automation_enabled = False
        ticket.next_followup_at = None

    summary = (
        f"Status changed {old_status} → {target_str}"
        if not reason
        else f"Status changed {old_status} → {target_str} ({reason})"
    )
    details: dict[str, Any] = {
        "from_status": old_status,
        "to_status": target_str,
        "forced": force,
    }
    if reason:
        details["detail"] = reason

    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type=actor_type,
            actor_name=actor_name,
            event_type="status_changed",
            summary=summary,
            details_json=details,
        )
    )
    if force and actor_type == "ENGINEER":
        record_audit_event(
            db,
            actor_user_id=None,
            actor_username=actor_name,
            action="ticket.status_forced",
            resource_type="ticket",
            resource_id=ticket.ticket_number,
            summary=f"Forced ticket status {old_status} -> {target_str} ({reason or 'UI override'})",
        )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            event_bus.broadcast(
                "ticket.updated",
                {
                    "ticket_number": ticket.ticket_number,
                    "from_status": old_status,
                    "status": target_str,
                    "forced": force,
                },
            )
        )
    except RuntimeError:
        pass

    return ticket


LOOP_GUARD_TRIP_THRESHOLD = 2

# Ticketless inbound emails the agent gave up on, shown in the Human Review queue
_TICKETLESS_ESCALATION_SUMMARIES: dict[str, str] = {
    EscalationReason.INGEST_FAILED.value: "The agent crashed while processing this email; no automated action was taken.",
    EscalationReason.LLM_UNAVAILABLE.value: "vLLM was unavailable for every retry cycle; the email was never classified.",
}


def apply_loop_guard_trip(db: Session, ticket: Optional[Ticket]) -> bool:
    """Move a ticket to `NEEDS_HUMAN_REVIEW` once the loop guard blocked >= 2 sends in the last hour.

    Goes through `transition_ticket` (never forced), so a closed ticket is left as it is.
    Returns True when the ticket was escalated.
    """
    if ticket is None or ticket.id is None:
        return False
    if ticket.status == TicketStatus.NEEDS_HUMAN_REVIEW.value:
        return False

    db.flush()
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    blocked_count = int(
        db.execute(
            select(func.count(TicketEvent.id)).where(
                TicketEvent.ticket_id == ticket.id,
                TicketEvent.event_type == "email_blocked",
                TicketEvent.created_at >= one_hour_ago,
            )
        ).scalar_one()
        or 0
    )
    if blocked_count < LOOP_GUARD_TRIP_THRESHOLD:
        return False

    try:
        transition_ticket(
            db,
            ticket,
            TicketStatus.NEEDS_HUMAN_REVIEW,
            reason=(
                f"{EscalationReason.LOOP_GUARD_TRIPPED.value}: loop guard blocked "
                f"{blocked_count} outbound emails within 1 hour"
            ),
        )
    except InvalidStateTransitionError as exc:
        logger.warning(
            "Loop guard tripped on ticket %s but escalation is not allowed: %s",
            ticket.ticket_number,
            exc,
        )
        return False
    ticket.escalation_reason = EscalationReason.LOOP_GUARD_TRIPPED.value
    return True


def update_ticket_status_or_meta(
    db: Session,
    ticket_identifier: str,
    payload: TicketStatusUpdateRequest,
    *,
    actor: User,
) -> TicketDetail360Response:
    """Update ticket status, Kanban column drag-drop, priority, AI pause toggle, ISP ref, or phone."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)

    if payload.kanban_col is not None:
        col_to_status = {
            0: TicketStatus.AWAITING_REGIONAL_IT.value,
            1: TicketStatus.DIAGNOSING.value,
            2: TicketStatus.INTERNAL_LAN_ISSUE.value,
            3: TicketStatus.ESCALATED_TO_ISP.value,
            4: TicketStatus.ESCALATED_TO_ISP.value,
            5: TicketStatus.VERIFYING.value,
            6: TicketStatus.NEEDS_HUMAN_REVIEW.value,
            7: TicketStatus.RESOLVED.value,
        }
        target_col_status = col_to_status.get(payload.kanban_col, ticket.status)
        if target_col_status != ticket.status:
            transition_ticket(
                db,
                ticket,
                target_col_status,
                actor_type="ENGINEER",
                actor_name=actor.display_name,
                reason=f"Kanban column drag-drop to col {payload.kanban_col}",
                force=True,
            )
        if payload.kanban_col == 3:
            ticket.isp_welcome_received = False
        elif payload.kanban_col == 4:
            ticket.isp_welcome_received = True
        elif payload.kanban_col == 7 and ticket.resolved_at is None:
            ticket.resolved_at = datetime.now(timezone.utc)

    if payload.status is not None and payload.status != ticket.status:
        transition_ticket(
            db,
            ticket,
            payload.status,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            reason="Manual status update",
            force=True,
        )

    if payload.priority is not None:
        ticket.priority = payload.priority

    if payload.ai_automation_enabled is not None:
        ticket.ai_automation_enabled = payload.ai_automation_enabled
        db.add(
            TicketEvent(
                ticket_id=ticket.id,
                actor_type="ENGINEER",
                actor_name=actor.display_name,
                event_type="ai_paused" if not payload.ai_automation_enabled else "ai_resumed",
                summary="AI automation paused"
                if not payload.ai_automation_enabled
                else "AI automation resumed",
                details_json={"detail": f"By {actor.display_name}"},
            )
        )

    if payload.isp_reference_number is not None:
        ticket.isp_reference_number = payload.isp_reference_number.strip() or None

    if payload.site_contact_phone is not None:
        ticket.site_contact_phone = payload.site_contact_phone.strip() or None

    db.commit()
    db.refresh(ticket)
    return get_ticket_360_detail(db, ticket.ticket_number)


def add_ticket_note(
    db: Session,
    ticket_identifier: str,
    payload: TicketNoteCreateRequest,
    *,
    actor: User,
) -> TicketDetail360Response:
    """Append an internal engineer note to the ticket timeline."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            event_type="internal_note",
            summary=payload.note.strip(),
            details_json={"detail": "Internal note"},
        )
    )
    db.commit()
    return get_ticket_360_detail(db, ticket.ticket_number)


async def send_ticket_manual_reply(
    db: Session,
    ticket_identifier: str,
    payload: TicketEmailReplyRequest,
    *,
    actor: User,
) -> TicketDetail360Response:
    """Send a manual reply on either the `BRANCH` or `ISP` thread of a ticket."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)
    branch = db.get(Branch, ticket.branch_id) if ticket.branch_id else None

    if payload.thread_type == "ISP":
        if branch is not None:
            isp_to_list, cc_list = resolve_isp_recipients(branch, db=db)
            to_addr = isp_to_list[0] if isp_to_list else "noc@noor.net"
        else:
            to_addr = "noc@noor.net"
            cc_list = ["ITInfrastructure@kazyon.com"]
        subj = (
            payload.subject or f"RE: store {branch.branch_code if branch else ticket.ticket_number}"
        )
    else:
        to_addr = ticket.sender_email or (
            branch.regional_it_email
            if branch and branch.regional_it_email
            else "CITSupport@kazyon.com"
        )
        subj = (
            payload.subject
            or f"RE: [{ticket.ticket_number}] {branch.name if branch else 'Branch Issue'}"
        )
        cc_list = resolve_branch_regional_it_cc(branch, db=db)

    await dispatch_outbound_email(
        db,
        ticket=ticket,
        thread_type=payload.thread_type,
        recipients=[to_addr],
        cc=cc_list,
        branch=branch,
        subject=subj,
        body_text=payload.body_text.strip(),
        classification_label="MANUAL_REPLY",
    )
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            event_type="email_sent",
            summary=f"Manual reply sent on {payload.thread_type} thread",
            details_json={"detail": f"To {to_addr}"},
        )
    )
    db.commit()
    return get_ticket_360_detail(db, ticket.ticket_number)


async def force_ticket_isp_followup(
    db: Session,
    ticket_identifier: str,
    *,
    actor: User,
) -> TicketDetail360Response:
    """Force an immediate ISP follow-up chaser email outside the scheduled 2h/4–6h loop."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)
    branch = db.get(Branch, ticket.branch_id) if ticket.branch_id else None
    isp_name = branch.isp_name if branch else "NOOR"
    to_addr = branch.isp_contact_mail if branch else "noc@noor.net"
    sap = branch.branch_code if branch else ticket.ticket_number
    case_ref = ticket.isp_reference_number or "pending"

    subj = f"RE: store {sap} — Follow-up #{ticket.followup_count + 1} (Case {case_ref})"
    body = (
        f"Dear {isp_name} NOC,\n"
        f"Kindly share an urgent update on store {sap} (ticket ref: {case_ref}).\n"
        f"Site contact: {ticket.site_contact_phone or 'will be shared shortly'}"
    )
    await dispatch_outbound_email(
        db,
        ticket=ticket,
        thread_type="ISP",
        recipients=[to_addr],
        cc=["ITInfrastructure@kazyon.com"],
        subject=subj,
        body_text=body,
        classification_label="CHASER",
    )
    ticket.followup_count += 1
    ticket.last_isp_contact_at = datetime.now(timezone.utc)
    ticket.next_followup_at = datetime.now(timezone.utc) + timedelta(minutes=300)
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            event_type="isp_escalated",
            summary=f"Follow-up chaser sent to {isp_name}",
            details_json={"detail": f"Manual, outside the 4–6h loop (To {to_addr})"},
        )
    )
    db.commit()
    return get_ticket_360_detail(db, ticket.ticket_number)


async def escalate_ticket_to_human_engineer(
    db: Session,
    ticket_identifier: str,
    payload: TicketEscalateHumanRequest,
    *,
    actor: User,
) -> TicketDetail360Response:
    """Transition a ticket to `NEEDS_HUMAN_REVIEW`, pause AI, and email the full incident report."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)
    transition_ticket(
        db,
        ticket,
        TicketStatus.NEEDS_HUMAN_REVIEW,
        actor_type="ENGINEER",
        actor_name=actor.display_name,
        reason=payload.reason,
        force=True,
    )
    ticket.escalation_reason = payload.reason
    ticket.human_escalated_to = payload.target_email

    await dispatch_outbound_email(
        db,
        ticket=ticket,
        thread_type="HUMAN_ESCALATION",
        recipients=[payload.target_email],
        subject=f"[HUMAN REVIEW] {ticket.ticket_number} · {payload.reason}",
        body_text=f"Escalated by {actor.display_name}.\nReason: {payload.reason}\nNote: {payload.note}",
        classification_label="HUMAN_ESCALATION",
    )
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            event_type="human_escalated",
            summary="Escalated to human engineer",
            details_json={"detail": f"Report emailed to {payload.target_email}"},
        )
    )
    db.commit()
    return get_ticket_360_detail(db, ticket.ticket_number)


def override_ticket_vision_verdict(
    db: Session,
    ticket_identifier: str,
    payload: VisionOverrideRequest,
    *,
    actor: User,
) -> TicketDetail360Response:
    """Allow an engineer to override the Gemma 4 26B router photo vision verdict."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)
    ticket.image_check_passed = payload.cables_plugged
    if payload.summary:
        ticket.image_analysis_summary = payload.summary
    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            event_type="vision_passed",
            summary="Vision verdict overridden by engineer",
            details_json={"detail": f"Cables plugged={payload.cables_plugged}"},
        )
    )
    db.commit()
    return get_ticket_360_detail(db, ticket.ticket_number)


def list_human_escalations(db: Session) -> list[EscalationItemDto]:
    """Return real Human Review & Out-of-Flow Escalation Queue items from the database (Page 7)."""
    items: list[EscalationItemDto] = []

    db_escalated = (
        db.execute(
            select(Ticket)
            .where(Ticket.status == TicketStatus.NEEDS_HUMAN_REVIEW.value)
            .order_by(Ticket.id.desc())
        )
        .scalars()
        .all()
    )
    for t in db_escalated:
        branch = db.get(Branch, t.branch_id) if t.branch_id else None
        latest_email = db.execute(
            select(TicketEmail)
            .where(TicketEmail.ticket_id == t.id)
            .order_by(TicketEmail.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        items.append(
            EscalationItemDto(
                key=f"ticket-{t.id}",
                ticket_number=t.ticket_number,
                reason=t.escalation_reason or "OTHER",
                isp=branch.isp_name if branch else "NOOR",
                case_ref=t.isp_reference_number,
                when=t.updated_at.strftime("%d %b %H:%M") if t.updated_at else "—",
                title=t.title,
                quote=latest_email.body_text[:220]
                if latest_email and latest_email.body_text
                else (t.description or "Escalated to human engineer."),
                from_addr=latest_email.sender
                if latest_email
                else (t.sender_email or "NetOps Agent"),
                summary=f"Escalated to {t.human_escalated_to or 'noc-oncall@kazyon.com'}.",
                engineer_email=t.human_escalated_to or "noc-oncall@kazyon.com",
                primary_action="Mark handled",
            )
        )

    unmatched_emails = (
        db.execute(
            select(TicketEmail)
            .where(
                TicketEmail.ticket_id.is_(None),
                TicketEmail.direction == "INBOUND",
                or_(
                    TicketEmail.classification_label == "UNRECOGNIZED",
                    and_(
                        TicketEmail.thread_type == "HUMAN_ESCALATION",
                        TicketEmail.classification_label.in_(
                            list(_TICKETLESS_ESCALATION_SUMMARIES)
                        ),
                    ),
                ),
            )
            .order_by(TicketEmail.id.desc())
        )
        .scalars()
        .all()
    )
    for em in unmatched_emails:
        label = em.classification_label or "UNRECOGNIZED"
        items.append(
            EscalationItemDto(
                key=f"email-{em.id}",
                ticket_number=None,
                email_id=em.id,
                reason=(
                    label
                    if label in _TICKETLESS_ESCALATION_SUMMARIES
                    else EscalationReason.UNRECOGNIZED_EMAIL.value
                ),
                isp=None,
                case_ref=None,
                when=em.sent_or_received_at.strftime("%d %b %H:%M")
                if em.sent_or_received_at
                else "—",
                title=f"Unmatched email: “{em.subject}”",
                quote=em.body_text[:220] if em.body_text else em.subject,
                from_addr=em.sender,
                summary=_TICKETLESS_ESCALATION_SUMMARIES.get(
                    label,
                    "Unrecognized inbound email with low classification confidence or no matching branch.",
                ),
                engineer_email="noc-oncall@kazyon.com",
                primary_action="Convert to ticket",
            )
        )

    return items


def convert_unrecognized_email_to_ticket(
    db: Session,
    email_id: int,
    *,
    actor: User,
) -> dict[str, Any]:
    """Convert an unmatched `UNRECOGNIZED` email from Page 7 into a tracked ticket (`NEEDS_HUMAN_REVIEW`)."""
    em = db.get(TicketEmail, email_id)
    if em is None:
        raise EntityNotFoundError("TicketEmail", str(email_id))
    if em.ticket_id is not None:
        existing = db.get(Ticket, em.ticket_id)
        if existing is not None:
            return {
                "email_id": em.id,
                "ticket_number": existing.ticket_number,
                "status": existing.status,
            }

    # Try to find a branch hint or fallback to None
    from app.email_engine.parser import extract_branch_sap_code

    code = extract_branch_sap_code(em.subject, em.body_text)
    branch: Optional[Branch] = None
    if code:
        branch = db.execute(select(Branch).where(Branch.branch_code == code)).scalar_one_or_none()

    max_id = db.execute(select(func.max(Ticket.id))).scalar_one() or 0
    ticket_number = f"NET-{1001 + int(max_id)}"
    while (
        db.execute(select(Ticket).where(Ticket.ticket_number == ticket_number)).scalar_one_or_none()
        is not None
    ):
        max_id += 1
        ticket_number = f"NET-{1001 + int(max_id)}"

    ticket = Ticket(
        ticket_number=ticket_number,
        title=f"Converted Email · {em.subject[:80]}",
        description=em.body_text or em.subject,
        trigger_source=TicketTriggerSource.UNKNOWN_ESCALATION.value,
        status=TicketStatus.NEEDS_HUMAN_REVIEW.value,
        priority=TicketPriority.MEDIUM.value,
        branch_id=branch.id if branch else None,
        isp_id=branch.isp_id if branch else None,
        sender_email=em.sender,
        router_image_paths=[],
        image_check_passed=False,
        ai_automation_enabled=False,
        escalation_reason="UNRECOGNIZED_EMAIL",
        human_escalated_to=actor.email,
    )
    db.add(ticket)
    db.flush()

    em.ticket_id = ticket.id
    em.classification_label = "INCIDENT_REPORT"

    db.add(
        TicketEvent(
            ticket_id=ticket.id,
            actor_type="ENGINEER",
            actor_name=actor.display_name,
            event_type="ticket_created",
            summary=f"Converted unrecognized email #{em.id} into ticket {ticket.ticket_number}",
            details_json={"detail": f"From {em.sender} · Subject: {em.subject}"},
        )
    )
    db.commit()
    db.refresh(ticket)
    return {
        "email_id": em.id,
        "ticket_number": ticket.ticket_number,
        "status": ticket.status,
    }


def list_replication_reports(db: Session) -> list[dict[str, Any]]:
    """Return real ingested `Replication Dashboard` reports and their store breakdown rows for Page 6."""
    reports = (
        db.execute(select(ReplicationReport).order_by(ReplicationReport.id.desc())).scalars().all()
    )
    result: list[dict[str, Any]] = []
    for rep in reports:
        rows = (
            db.execute(
                select(ReplicationReportRow)
                .where(ReplicationReportRow.report_id == rep.id)
                .order_by(ReplicationReportRow.id.asc())
            )
            .scalars()
            .all()
        )
        result.append(
            {
                "id": rep.id,
                "subject": rep.subject,
                "received": rep.received_at.strftime("%d %b %H:%M") if rep.received_at else "—",
                "total": rep.total_rows,
                "nu": rep.not_updated_count,
                "notified": rep.notified_count,
                "duplicates_skipped": rep.duplicates_skipped_count,
                "tone": "critical"
                if rep.not_updated_count > 14
                else ("warning" if rep.not_updated_count > 0 else "good"),
                "rows": [
                    {
                        "id": r.branch_code,
                        "name": r.store_name,
                        "region": r.region or "Cairo",
                        "last": r.last_trans_raw or "—",
                        "biz": r.business_date or "—",
                        "status": r.status,
                        "tone": "good" if r.status == "Updated" else "critical",
                        "mail": r.regional_it_email or "—",
                        "ticket": r.linked_ticket_number or "",
                    }
                    for r in rows
                ],
            }
        )
    return result


CLASSIFICATION_BADGE_TONES: dict[str, str] = {
    "ISP_WELCOME": "good",
    "ISP_BLOCKER": "warning",
    "INCIDENT_REPORT": "brand",
    "REPLICATION_REPORT": "info",
    "ESCALATION": "brand",
    "BRANCH_ACK_ESCALATED": "info",
    "CONTACT_BLOCKER_MEDIATION": "warning",
    "CONTACT_RELAY_TO_ISP": "info",
    "CABLE_FIX_REQUEST": "warning",
    "INTERNAL_SWITCH_ALERT": "warning",
    "DIAGNOSTICS_PASS_NOTICE": "good",
    "RESOLUTION_CONFIRMATION": "good",
    "ISP_CLOSURE_ACK": "good",
    "ISP_REOPEN_FAILED_VERIFY": "critical",
    "REGIONAL_IT_NOTIFY": "info",
    "HUMAN_ESCALATION": "critical",
    "UNRECOGNIZED": "critical",
    "CHASER": "neutral",
    "ISP_CLOSURE": "good",
    "AUTO_SUBMITTED_IGNORED": "neutral",
}


def list_mailbox_triage_logs(db: Session) -> list[dict[str, Any]]:
    """Return real inbound and outbound emails from the database for Page 8."""
    emails = (
        db.execute(select(TicketEmail).order_by(TicketEmail.id.desc()).limit(150)).scalars().all()
    )
    results: list[dict[str, Any]] = []
    for em in emails:
        ticket_num = "—"
        branch_code = ""
        ticket_status = ""
        if em.ticket_id is not None:
            t = db.get(Ticket, em.ticket_id)
            if t is not None:
                ticket_num = t.ticket_number
                ticket_status = t.status
                if t.branch_id is not None:
                    b = db.get(Branch, t.branch_id)
                    if b is not None:
                        branch_code = b.branch_code
        att_list = list(em.attachments_json or [])
        att_str = (
            ", ".join(
                f"{a.get('filename', 'file')} ({a.get('size_label') or str(a.get('size_bytes', 0)) + ' B'})"
                for a in att_list
            )
            if att_list
            else "None"
        )
        headers_dict = dict(em.raw_headers or {})
        headers_text = "\n".join(f"{k}: {v}" for k, v in headers_dict.items())
        dir_short = "IN" if em.direction == "INBOUND" else "OUT"
        cls_label = em.classification_label or (
            "INCIDENT_REPORT" if dir_short == "IN" else "ESCALATION"
        )
        parsed_replies = split_email_thread_replies(em.body_text or "")
        results.append(
            {
                "id": em.id,
                "time": em.sent_or_received_at.strftime("%H:%M")
                if em.sent_or_received_at
                else "00:00",
                "dir": dir_short,
                "dtone": "info" if dir_short == "IN" else "outline",
                "thread_type": em.thread_type,
                "from": em.sender,
                "to": ", ".join(em.recipients or []),
                "cc": ", ".join(em.cc or []),
                "who": em.sender
                if dir_short == "IN"
                else (em.recipients[0] if em.recipients else "noc@noor.net"),
                "subject": em.subject,
                "cls": cls_label,
                "ctone": CLASSIFICATION_BADGE_TONES.get(cls_label, "neutral"),
                "ticket": ticket_num,
                "ticket_status": ticket_status,
                "branch_code": branch_code,
                "in_reply_to": em.in_reply_to or "",
                "body": em.body_text,
                "thread_reply_count": len(parsed_replies),
                "thread_replies": parsed_replies,
                "att": att_str,
                "json": json.dumps(em.ai_analysis_json or {}, indent=2),
                "mid": em.message_id,
                "headers": headers_text,
            }
        )
    return results


def _settings_dto(row: SystemSettings) -> SystemSettingsDto:
    dto = SystemSettingsDto.model_validate(row)
    imap_cfg = imap_transport_config_from_row(row)
    smtp_cfg = smtp_transport_config_from_row(row)
    dto.imap_username = row.imap_username or imap_cfg.username
    dto.imap_credentials_configured = imap_cfg.credentials_configured
    dto.smtp_username = row.smtp_username or smtp_cfg.username
    dto.smtp_credentials_configured = smtp_cfg.credentials_configured
    dto.test_redirect_email = row.test_redirect_email or ""
    return dto


def get_system_settings_dto(db: Session) -> SystemSettingsDto:
    return _settings_dto(ensure_system_settings(db))


def update_system_settings(
    db: Session,
    payload: SystemSettingsUpdateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> SystemSettingsDto:
    row = ensure_system_settings(db)
    changes = payload.model_dump(exclude_none=True)
    for k, v in changes.items():
        if k == "imap_password":
            clean_pw = v.strip() if isinstance(v, str) else ""
            row.imap_password_encrypted = encrypt_secret(clean_pw) if clean_pw else ""
        elif k == "smtp_password":
            clean_pw = v.strip() if isinstance(v, str) else ""
            row.smtp_password_encrypted = encrypt_secret(clean_pw) if clean_pw else ""
        else:
            setattr(row, k, v.strip() if isinstance(v, str) else v)

    changed_keys = sorted(changes)
    keys_preview = ", ".join(changed_keys[:8])
    if len(changed_keys) > 8:
        keys_preview += f" +{len(changed_keys) - 8} more"
    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="settings.updated",
        resource_type="settings",
        resource_id="global",
        summary=(
            f"Updated AI Agent, Mailbox & SLA settings ({keys_preview or 'no changes'}; "
            f"kill_switch={row.global_ai_kill_switch}, smtp_enabled={row.smtp_enabled})"
        ),
        details={"updated_fields": changed_keys},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    return _settings_dto(row)


async def test_smtp_settings(
    db: Session, payload: SmtpConnectionTestRequest
) -> SmtpConnectionTestResult:
    """Open a real SMTP session with the saved settings, overridden by any unsaved form values."""
    saved = load_smtp_transport_config(db)
    username = (
        payload.smtp_username.strip()
        if payload.smtp_username is not None and payload.smtp_username.strip()
        else saved.username
    )
    password = (
        payload.smtp_password.strip()
        if payload.smtp_password is not None and payload.smtp_password.strip()
        else saved.password
    )
    from_addr = (
        payload.mailbox_account.strip()
        if payload.mailbox_account is not None and payload.mailbox_account.strip()
        else saved.from_address
    )
    cfg = replace(
        saved,
        host=(payload.smtp_host if payload.smtp_host is not None else saved.host).strip(),
        port=payload.smtp_port or saved.port,
        security=payload.smtp_security or saved.security,
        username=username,
        password=password,
        from_address=from_addr,
    )
    result = await asyncio.to_thread(test_smtp_connection_sync, cfg)
    return SmtpConnectionTestResult.model_validate(result)


async def test_imap_settings(
    db: Session, payload: ImapConnectionTestRequest
) -> ImapConnectionTestResult:
    """Open a real IMAP session with the saved settings, overridden by any unsaved form values."""
    row = ensure_system_settings(db)
    saved = imap_transport_config_from_row(row)
    username = (
        payload.imap_username.strip()
        if payload.imap_username is not None and payload.imap_username.strip()
        else saved.username
    )
    password = (
        payload.imap_password.strip()
        if payload.imap_password is not None and payload.imap_password.strip()
        else saved.password
    )
    cfg = replace(
        saved,
        host=(payload.imap_host if payload.imap_host is not None else saved.host).strip(),
        port=payload.imap_port or saved.port,
        use_ssl=payload.imap_use_ssl if payload.imap_use_ssl is not None else saved.use_ssl,
        folder=(payload.imap_folder.strip() if payload.imap_folder else saved.folder) or "INBOX",
        username=username,
        password=password,
    )
    result = await asyncio.to_thread(test_imap_connection_sync, cfg)
    return ImapConnectionTestResult.model_validate(result)


async def send_live_test_email(db: Session, payload: SendTestEmailRequest) -> SendTestEmailResult:
    """Send a live test email through the configured SMTP server (e.g. Gmail round-trip test)."""
    import time as _time
    from uuid import uuid4 as _uuid4

    started = _time.perf_counter()
    saved = load_smtp_transport_config(db)
    cfg = replace(saved, enabled=True, test_redirect_email="")
    recipient = (
        (payload.recipient or "").strip()
        or saved.test_redirect_email
        or saved.username
        or saved.from_address
    )
    sap = (payload.branch_code or "1084").strip()
    subject = (
        payload.subject or ""
    ).strip() or f"Store {sap} network down — Gmail Live Round-Trip Test"
    body = (payload.body_text or "").strip() or (
        f"Dear Network Support,\n"
        f"Store {sap} is offline and POS terminals are not syncing.\n"
        f"Router photo checked: all cables seated and power LED is green.\n"
        f"Site contact: 010 2345 8817\n\n"
        f"[Sent via Kazyon Live SMTP Round-Trip Tester]"
    )
    mid = f"<test-{_uuid4().hex[:12]}@kazyon.com>"
    try:
        await asyncio.to_thread(
            _send_via_live_smtp_sync,
            sender=cfg.from_address,
            recipients=[recipient],
            cc=[],
            subject=subject,
            body_text=body,
            raw_headers={"Message-ID": mid, "X-Kz-Thread": "BRANCH"},
            transport=cfg,
        )
        return SendTestEmailResult(
            ok=True,
            recipient=recipient,
            subject=subject,
            message_id=mid,
            latency_ms=int((_time.perf_counter() - started) * 1000),
            error=None,
        )
    except Exception as exc:
        return SendTestEmailResult(
            ok=False,
            recipient=recipient,
            subject=subject,
            message_id=mid,
            latency_ms=int((_time.perf_counter() - started) * 1000),
            error=str(exc),
        )


async def test_vllm_settings(
    db: Session, payload: VllmConnectionTestRequest
) -> VllmConnectionTestResult:
    """Call the vLLM `/v1/models` endpoint (saved or unsaved form value) and check the model is served."""
    endpoint = payload.vllm_endpoint or ensure_system_settings(db).vllm_endpoint
    probe = await probe_vllm_endpoint(endpoint)
    return VllmConnectionTestResult.model_validate(probe)
