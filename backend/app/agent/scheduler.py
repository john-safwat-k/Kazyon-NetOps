"""Proactive 2-Hour Welcome SLA, 4–6 Hour ISP Follow-Up Scheduler & Autonomous Email Loop Runner (BRD §4.2)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.workflow import ingest_and_triage_eml, record_failed_ingest
from app.common.contracts import EscalationReason, TicketStatus
from app.common.database import SessionLocal
from app.directory.models import Branch
from app.email_engine.imap_poller import (
    imap_transport_config_from_row,
    poll_inbound_mailbox_raw,
)
from app.email_engine.smtp_listener import get_listener_status
from app.email_engine.smtp_sender import (
    dispatch_outbound_email,
    format_isp_escalation_email,
    resolve_isp_recipients,
    smtp_transport_config_from_row,
)
from app.observability.event_bus import event_bus
from app.ticketing.models import Ticket, TicketEmail, TicketEvent
from app.ticketing.service import (
    apply_loop_guard_trip,
    ensure_system_settings,
    transition_ticket,
)

logger = logging.getLogger("it_net.agent.scheduler")

_loop_task: Optional[asyncio.Task[None]] = None
_wake_event: Optional[asyncio.Event] = None
_loop_telemetry: dict[str, Any] = {
    "background_loop_running": False,
    "last_poll_at": datetime.now(timezone.utc),
    "poll_count": 1,
    "messages_ingested_total": 0,
    "chasers_sent_total": 0,
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

    fallback_engineer = (
        settings_row.fallback_contacts[0]["email"]
        if settings_row.fallback_contacts and settings_row.fallback_contacts[0].get("email")
        else "noc-oncall@kazyon.com"
    )

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

            out_em = await dispatch_outbound_email(
                db,
                ticket=t,
                thread_type="ISP",
                recipients=to_list,
                cc=cc_list,
                subject=subj,
                body_text=body,
                classification_label="CHASER",
            )
            if (out_em.ai_analysis_json or {}).get("blocked_by_loop_guard"):
                if apply_loop_guard_trip(db, t):
                    escalated_to_human += 1
            else:
                t.followup_count += 1
                t.last_isp_contact_at = now
                t.next_followup_at = now + timedelta(minutes=interval)
                chased += 1
                db.add(
                    TicketEvent(
                        ticket_id=t.id,
                        actor_type="AI_AGENT",
                        actor_name="AI_AGENT",
                        event_type="chaser_scheduled",
                        summary=f"Automated SLA chaser #{t.followup_count} sent to {branch.isp_name}",
                        details_json={"detail": subj},
                    )
                )

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
    1. Poll IMAP mailbox & local `.eml` dropbox (`data/imports/inbox/`)
    2. Ingest, correlate, classify, and execute autonomous actions on each new message
    3. Run the 2h Welcome SLA & 4–6h ISP Follow-Up Chaser cycle
    """
    settings_row = ensure_system_settings(db)
    imap_cfg = imap_transport_config_from_row(settings_row)
    raw_messages = await poll_inbound_mailbox_raw(
        imap_host=settings_row.imap_host,
        imap_port=settings_row.imap_port,
        imap_config=imap_cfg,
    )

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

    imap_cfg = imap_transport_config_from_row(settings_row)
    smtp_cfg = smtp_transport_config_from_row(settings_row)
    host_lower = (settings_row.imap_host or settings_row.smtp_host or "").lower()
    if "gmail.com" in host_lower:
        provider_preset = "gmail"
    elif "office365" in host_lower or "outlook" in host_lower:
        provider_preset = "office365"
    elif "kazyon.com" in host_lower:
        provider_preset = "kazyon"
    else:
        provider_preset = "custom"

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
        "imap_host": settings_row.imap_host,
        "imap_port": settings_row.imap_port,
        "imap_credentials_configured": imap_cfg.credentials_configured,
        "smtp_host": settings_row.smtp_host,
        "smtp_port": settings_row.smtp_port,
        "smtp_enabled": smtp_cfg.enabled,
        "smtp_credentials_configured": smtp_cfg.credentials_configured,
        "test_redirect_email": smtp_cfg.test_redirect_email,
        "provider_preset": provider_preset,
        "smtp_listener": get_listener_status(),
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
    if _loop_task is not None and not _loop_task.done():
        _loop_task.cancel()
        try:
            await _loop_task
        except asyncio.CancelledError:
            pass
    _loop_task = None
    _loop_telemetry["background_loop_running"] = False
