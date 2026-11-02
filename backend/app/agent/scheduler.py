"""Proactive 2-Hour Welcome SLA, 4–6 Hour ISP Follow-Up Scheduler & Autonomous Email Loop Runner (BRD §4.2)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.workflow import (
    ingest_and_triage_eml,
    record_failed_ingest,
    run_proactive_fleet_scan,
    serialize_fleet_scan_run,
)
from app.common.contracts import EscalationReason, TicketStatus
from app.common.database import SessionLocal
from app.directory.models import Branch
from app.email_engine.imap_poller import poll_inbound_mailbox_raw
from app.email_engine.smtp_listener import get_listener_status
from app.email_engine.smtp_sender import (
    dispatch_admin_action_email,
    dispatch_outbound_email,
    format_isp_escalation_email,
    resolve_fallback_engineer_email,
    resolve_isp_recipients,
    smtp_transport_config_from_row,
)
from app.observability.event_bus import event_bus
from app.ticketing.models import FleetScanRun, Ticket, TicketEmail, TicketEvent
from app.ticketing.service import (
    apply_loop_guard_trip,
    apply_or_queue_ticket_action,
    ensure_system_settings,
    transition_ticket,
)

logger = logging.getLogger("it_net.agent.scheduler")

_CAIRO_TZ = ZoneInfo("Africa/Cairo")
_loop_task: Optional[asyncio.Task[None]] = None
_active_fleet_scan_task: Optional[asyncio.Task[dict[str, Any]]] = None
_wake_event: Optional[asyncio.Event] = None
_loop_telemetry: dict[str, Any] = {
    "background_loop_running": False,
    "last_poll_at": datetime.now(timezone.utc),
    "poll_count": 1,
    "messages_ingested_total": 0,
    "chasers_sent_total": 0,
    "last_fleet_scan_at": None,
}


def _parse_hhmm_minutes(hhmm: str, default_minutes: int) -> int:
    try:
        parts = (hhmm or "").strip().split(":")
        if len(parts) != 2:
            return default_minutes
        h = int(parts[0])
        m = int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
    except Exception:
        pass
    return default_minutes


def is_within_store_window(
    now_utc: datetime,
    window_start: str = "08:00",
    window_end: str = "23:00",
) -> bool:
    """Return True if `now_utc` converted to `Africa/Cairo` falls within `[window_start, window_end]`."""
    aware = now_utc if now_utc.tzinfo else now_utc.replace(tzinfo=timezone.utc)
    cairo_dt = aware.astimezone(_CAIRO_TZ)
    curr_mins = cairo_dt.hour * 60 + cairo_dt.minute
    start_mins = _parse_hhmm_minutes(window_start, 8 * 60)
    end_mins = _parse_hhmm_minutes(window_end, 23 * 60)
    if start_mins <= end_mins:
        return start_mins <= curr_mins <= end_mins
    # Overnight window crossing midnight (e.g. 22:00 -> 06:00)
    return curr_mins >= start_mins or curr_mins <= end_mins


def cancel_active_fleet_scan() -> bool:
    """Cancel an in-flight scheduled fleet scan task immediately when disabled in Settings."""
    global _active_fleet_scan_task
    if _active_fleet_scan_task is not None and not _active_fleet_scan_task.done():
        _active_fleet_scan_task.cancel()
        return True
    return False


async def run_scheduled_fleet_scan_if_due(
    db: Session,
    *,
    now_utc: Optional[datetime] = None,
) -> dict[str, Any]:
    """Check if the 3-Hour (`fleet_scan_interval_minutes`) Proactive Fleet Scan is enabled,
    within Cairo store operating hours, and due to run; if so, execute it and record `FleetScanRun`.
    """
    global _active_fleet_scan_task
    settings_row = ensure_system_settings(db)
    if settings_row.global_ai_kill_switch:
        return {"skipped": True, "reason": "global_ai_kill_switch"}
    if not settings_row.fleet_scan_enabled:
        return {"skipped": True, "reason": "fleet_scan_disabled"}

    now = now_utc or datetime.now(timezone.utc)
    w_start = settings_row.fleet_scan_window_start or "08:00"
    w_end = settings_row.fleet_scan_window_end or "23:00"
    if not is_within_store_window(now, w_start, w_end):
        return {"skipped": True, "reason": "outside_store_hours_window"}

    interval_min = max(15, int(settings_row.fleet_scan_interval_minutes or 180))
    last_run = db.execute(
        select(FleetScanRun)
        .where(FleetScanRun.status.in_(["COMPLETED", "MASS_OUTAGE_GUARD"]))
        .order_by(FleetScanRun.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    if last_run is not None and last_run.started_at is not None:
        last_dt = (
            last_run.started_at
            if last_run.started_at.tzinfo
            else last_run.started_at.replace(tzinfo=timezone.utc)
        )
        elapsed_min = (now - last_dt).total_seconds() / 60.0
        if elapsed_min < float(interval_min):
            return {
                "skipped": True,
                "reason": "interval_not_elapsed",
                "minutes_until_next": round(float(interval_min) - elapsed_min, 1),
            }

    task = asyncio.create_task(
        run_proactive_fleet_scan(db, triggered_by="SCHEDULER", dry_run=False)
    )
    _active_fleet_scan_task = task
    try:
        scan_res = await task
    finally:
        if _active_fleet_scan_task is task:
            _active_fleet_scan_task = None

    _loop_telemetry["last_fleet_scan_at"] = now
    await event_bus.broadcast("fleet_scan.completed", scan_res)
    return {"skipped": False, "scan": scan_res}


def get_fleet_scan_status(db: Session, *, limit: int = 15) -> dict[str, Any]:
    """Return Proactive Fleet Scan configuration, live scheduler state, and recent `FleetScanRun` history."""
    settings_row = ensure_system_settings(db)
    now = datetime.now(timezone.utc)
    w_start = settings_row.fleet_scan_window_start or "08:00"
    w_end = settings_row.fleet_scan_window_end or "23:00"
    interval_min = max(15, int(settings_row.fleet_scan_interval_minutes or 180))

    recent_rows = (
        db.execute(select(FleetScanRun).order_by(FleetScanRun.id.desc()).limit(limit))
        .scalars()
        .all()
    )
    recent_dtos = [serialize_fleet_scan_run(r) for r in recent_rows]

    last_completed = next(
        (r for r in recent_rows if r.status in {"COMPLETED", "MASS_OUTAGE_GUARD"}),
        None,
    )
    next_due_at: Optional[str] = None
    if settings_row.fleet_scan_enabled and not settings_row.global_ai_kill_switch:
        if last_completed is not None and last_completed.started_at is not None:
            last_dt = (
                last_completed.started_at
                if last_completed.started_at.tzinfo
                else last_completed.started_at.replace(tzinfo=timezone.utc)
            )
            next_due_at = (last_dt + timedelta(minutes=interval_min)).isoformat()
        else:
            next_due_at = now.isoformat()

    return {
        "enabled": bool(settings_row.fleet_scan_enabled),
        "global_ai_kill_switch": bool(settings_row.global_ai_kill_switch),
        "running": bool(_active_fleet_scan_task is not None and not _active_fleet_scan_task.done()),
        "interval_minutes": interval_min,
        "window_start": w_start,
        "window_end": w_end,
        "mass_outage_pct": int(settings_row.fleet_scan_mass_outage_pct or 5),
        "within_store_window": is_within_store_window(now, w_start, w_end),
        "last_run": serialize_fleet_scan_run(last_completed) if last_completed else None,
        "next_due_at": next_due_at,
        "recent_runs": recent_dtos,
    }


async def run_sla_chaser_cycle(db: Session) -> dict[str, Any]:
    """Check all open `ESCALATED_TO_ISP` tickets whose `next_followup_at` has expired and send chasers."""
    settings_row = ensure_system_settings(db)
    if settings_row.global_ai_kill_switch:
        return {"skipped": True, "reason": "global_ai_kill_switch", "chased_count": 0}

    now = datetime.now(timezone.utc)
    tickets = (
        db.execute(
            select(Ticket).where(
                Ticket.status == TicketStatus.ESCALATED_TO_ISP.value,
                Ticket.ai_automation_enabled.is_(True),
            )
        )
        .scalars()
        .all()
    )

    fallback_engineer = resolve_fallback_engineer_email(settings_row)

    chased = 0
    escalated_to_human = 0
    for t in tickets:
        if t.next_followup_at is None:
            continue
        nf = (
            t.next_followup_at
            if t.next_followup_at.tzinfo
            else t.next_followup_at.replace(tzinfo=timezone.utc)
        )
        if nf > now:
            continue

        branch = db.get(Branch, t.branch_id) if t.branch_id else None
        if t.followup_count >= settings_row.max_chasers_before_human:
            transition_ticket(
                db,
                t,
                TicketStatus.NEEDS_HUMAN_REVIEW,
                actor_type="AI_AGENT",
                actor_name="AI_AGENT",
                reason=EscalationReason.MAX_RETRIES.value,
            )
            t.escalation_reason = EscalationReason.MAX_RETRIES.value
            t.human_escalated_to = fallback_engineer
            escalated_to_human += 1
            await dispatch_outbound_email(
                db,
                ticket=t,
                thread_type="HUMAN_ESCALATION",
                recipients=[fallback_engineer],
                subject=f"[HUMAN REVIEW] {t.ticket_number} · MAX_RETRIES ({t.followup_count} unanswered ISP chasers)",
                body_text=(
                    f"Ticket {t.ticket_number} ({branch.name if branch else 'Store'}) reached "
                    f"{t.followup_count} unanswered ISP follow-up chasers.\n"
                    f"AI automation has been paused and escalated to {fallback_engineer}."
                ),
                classification_label="HUMAN_ESCALATION",
            )
            db.add(
                TicketEvent(
                    ticket_id=t.id,
                    actor_type="AI_AGENT",
                    actor_name="AI_AGENT",
                    event_type="human_escalated",
                    summary=f"Escalated after {t.followup_count} unanswered ISP chasers",
                    details_json={"detail": "MAX_RETRIES reached"},
                )
            )
            await dispatch_admin_action_email(
                db,
                settings_row=settings_row,
                ticket=t,
                branch=branch,
                action_label="HUMAN_ESCALATED_MAX_RETRIES",
                action_summary=f"Escalated ticket {t.ticket_number} to {fallback_engineer} after {t.followup_count} unanswered ISP chasers",
                details_lines=[
                    f"Escalation Reason: {EscalationReason.MAX_RETRIES.value}",
                    f"Unanswered Chasers Sent: {t.followup_count}",
                ],
                approval_required=False,
            )
            continue

        if branch is not None:
            if not t.isp_welcome_received:
                subj, body, to_list, cc_list, _ = format_isp_escalation_email(
                    branch, site_contact_phone=t.site_contact_phone, db=db
                )
                subj = f"RE: {subj} [2h Welcome SLA Reminder]"
                interval = settings_row.welcome_sla_minutes
            else:
                to_list, cc_list = resolve_isp_recipients(branch, db=db)
                subj = f"RE: store {branch.branch_code} (Case {t.isp_reference_number or 'open'})"
                body = (
                    f"Dear {branch.isp_name} NOC,\n"
                    f"Kindly share an investigation update for store {branch.name}."
                )
                interval = settings_row.followup_interval_minutes

            next_chaser_num = t.followup_count + 1
            act_status, sent_ems, _admin_em = await apply_or_queue_ticket_action(
                db,
                settings_row=settings_row,
                ticket=t,
                branch=branch,
                action_label="ISP_CHASER_SENT",
                summary=f"Send automated SLA chaser #{next_chaser_num} to {branch.isp_name} ({to_list[0]})",
                target_status=TicketStatus.ESCALATED_TO_ISP,
                transition_reason=f"Automated SLA chaser #{next_chaser_num}",
                followup_minutes=interval,
                increment_followup_count=True,
                update_last_isp_contact=True,
                proposed_emails=[
                    {
                        "thread_type": "ISP",
                        "recipients": to_list,
                        "cc": cc_list,
                        "subject": subj,
                        "body_text": body,
                        "classification_label": "CHASER",
                    }
                ],
                proposed_events=[
                    {
                        "event_type": "chaser_scheduled",
                        "summary": f"Automated SLA chaser #{next_chaser_num} sent to {branch.isp_name}",
                        "details_json": {"detail": subj},
                    }
                ],
                context_lines=[
                    f"Chaser Number: #{next_chaser_num} (max before human={settings_row.max_chasers_before_human})",
                    f"Welcome Received: {t.isp_welcome_received}",
                    f"ISP Case Ref: {t.isp_reference_number or 'pending'}",
                ],
            )
            if act_status != "AWAITING_ADMIN_APPROVAL":
                out_em = sent_ems[0] if sent_ems else None
                if out_em is not None and (out_em.ai_analysis_json or {}).get(
                    "blocked_by_loop_guard"
                ):
                    if apply_loop_guard_trip(db, t):
                        escalated_to_human += 1
                else:
                    chased += 1

    db.commit()
    _loop_telemetry["chasers_sent_total"] = (
        int(_loop_telemetry.get("chasers_sent_total", 0)) + chased
    )
    return {
        "skipped": False,
        "chased_count": chased,
        "escalated_to_human_count": escalated_to_human,
    }


async def run_email_loop_cycle_once(db: Session) -> dict[str, Any]:
    """Execute one full cycle of the Email Agent Harness Loop:
    1. Poll inbound SMTP `.eml` dropbox (`data/imports/inbox/`) and vLLM retry queue
    2. Ingest, correlate, classify, and execute autonomous actions on each new message
    3. Run the 2h Welcome SLA & 4–6h ISP Follow-Up Chaser cycle
    """
    ensure_system_settings(db)
    raw_messages = await poll_inbound_mailbox_raw(db=db)

    ingested_results: list[dict[str, Any]] = []
    for fname, raw_bytes in raw_messages:
        try:
            res = await ingest_and_triage_eml(
                db,
                raw_bytes,
                filename=fname,
                deduplicate_strict=True,
            )
            ingested_results.append(res)
            await event_bus.broadcast("email.ingested", res)
        except Exception as exc:
            logger.error("Failed to ingest email '%s' in loop cycle: %s", fname, exc)
            db.rollback()
            try:
                await record_failed_ingest(db, raw_bytes, filename=fname, error=exc)
            except Exception as record_exc:
                logger.error("Could not record failed ingest for '%s': %s", fname, record_exc)
                db.rollback()

    chaser_res = await run_sla_chaser_cycle(db)
    if chaser_res.get("chased_count", 0) > 0 or chaser_res.get("escalated_to_human_count", 0) > 0:
        await event_bus.broadcast("sla.chaser_ran", chaser_res)

    try:
        fleet_scan_res = await run_scheduled_fleet_scan_if_due(db)
    except asyncio.CancelledError:
        logger.info("In-flight scheduled fleet scan cancelled via Settings.")
        fleet_scan_res = {"skipped": True, "reason": "cancelled"}
    except Exception as exc:
        logger.warning("Scheduled proactive fleet scan failed: %s", exc)
        db.rollback()
        fleet_scan_res = {"skipped": True, "reason": f"error: {exc}"}

    now = datetime.now(timezone.utc)
    _loop_telemetry["last_poll_at"] = now
    _loop_telemetry["poll_count"] = int(_loop_telemetry.get("poll_count", 0)) + 1
    _loop_telemetry["messages_ingested_total"] = int(
        _loop_telemetry.get("messages_ingested_total", 0)
    ) + len(ingested_results)

    return {
        "polled_at": now.isoformat(),
        "messages_fetched": len(raw_messages),
        "messages_ingested": len(ingested_results),
        "ingested": ingested_results,
        "sla_chaser": chaser_res,
        "fleet_scan": fleet_scan_res,
        "poll_count": _loop_telemetry["poll_count"],
    }


def get_email_loop_status(db: Session) -> dict[str, Any]:
    """Return live telemetry for the Email Agent Harness Loop (Page 8 & Page 12)."""
    settings_row = ensure_system_settings(db)
    now = datetime.now(timezone.utc)
    last_poll_dt: datetime = _loop_telemetry.get("last_poll_at") or now
    secs_ago = max(0, int((now - last_poll_dt).total_seconds()))

    inbound_count = int(
        db.execute(
            select(func.count()).select_from(TicketEmail).where(TicketEmail.direction == "INBOUND")
        ).scalar_one()
        or 0
    )
    outbound_count = int(
        db.execute(
            select(func.count()).select_from(TicketEmail).where(TicketEmail.direction == "OUTBOUND")
        ).scalar_one()
        or 0
    )
    open_isp_threads = int(
        db.execute(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.status == TicketStatus.ESCALATED_TO_ISP.value)
        ).scalar_one()
        or 0
    )
    awaiting_branch_threads = int(
        db.execute(
            select(func.count())
            .select_from(Ticket)
            .where(
                Ticket.status.in_(
                    [
                        TicketStatus.AWAITING_REGIONAL_IT.value,
                        TicketStatus.AWAITING_BRANCH.value,
                        TicketStatus.AWAITING_BRANCH_CONTACT.value,
                    ]
                )
            )
        ).scalar_one()
        or 0
    )

    smtp_cfg = smtp_transport_config_from_row(settings_row)

    return {
        "background_loop_running": bool(_loop_telemetry.get("background_loop_running", False)),
        "global_ai_kill_switch": settings_row.global_ai_kill_switch,
        "poll_interval_sec": settings_row.poll_interval_sec,
        "last_poll_at": last_poll_dt.isoformat(),
        "seconds_since_last_poll": secs_ago,
        "poll_count": int(_loop_telemetry.get("poll_count", 1)),
        "inbound_count": inbound_count,
        "outbound_count": outbound_count,
        "open_isp_threads_count": open_isp_threads,
        "awaiting_branch_threads_count": awaiting_branch_threads,
        "mailbox_account": settings_row.mailbox_account,
        "smtp_host": settings_row.smtp_host,
        "smtp_port": settings_row.smtp_port,
        "smtp_security": settings_row.smtp_security,
        "smtp_enabled": smtp_cfg.enabled,
        "smtp_credentials_configured": smtp_cfg.credentials_configured,
        "test_redirect_email": smtp_cfg.test_redirect_email,
        "smtp_listener": get_listener_status(),
        "fleet_scan": get_fleet_scan_status(db, limit=5),
    }


async def _background_email_loop_worker() -> None:
    """Async background task running inside FastAPI lifespan to poll IMAP and run SLA chasers."""
    _loop_telemetry["background_loop_running"] = True
    try:
        while True:
            interval = 30
            db: Session = SessionLocal()
            try:
                settings_row = ensure_system_settings(db)
                interval = max(10, int(settings_row.poll_interval_sec or 30))
                await run_email_loop_cycle_once(db)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Background email loop cycle warning: %s", exc)
            finally:
                db.close()
            await _sleep_until_next_poll(interval)
    except asyncio.CancelledError:
        logger.info("Background email loop task cancelled cleanly.")
    finally:
        _loop_telemetry["background_loop_running"] = False


def request_immediate_poll() -> None:
    """Wake the poller now instead of at the next interval (called when the SMTP listener
    stores a message). Must be called from the event loop thread."""
    if _wake_event is not None:
        _wake_event.set()


async def _sleep_until_next_poll(interval: float) -> None:
    global _wake_event
    if _wake_event is None:
        _wake_event = asyncio.Event()
    try:
        await asyncio.wait_for(_wake_event.wait(), timeout=interval)
    except asyncio.TimeoutError:
        pass
    _wake_event.clear()


def start_background_email_loop() -> None:
    """Start the background IMAP poller & SLA chaser loop in the active event loop."""
    global _loop_task
    if _loop_task is None or _loop_task.done():
        _loop_task = asyncio.create_task(_background_email_loop_worker())
        _loop_telemetry["background_loop_running"] = True


async def stop_background_email_loop() -> None:
    """Cancel and await the background IMAP poller & SLA chaser loop on FastAPI shutdown."""
    global _loop_task
    cancel_active_fleet_scan()
    if _loop_task is not None and not _loop_task.done():
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
    _loop_task = None
    _loop_telemetry["background_loop_running"] = False
