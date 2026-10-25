"""FastAPI routers for `/api/v1/tickets`, `/api/v1/dashboard`, `/api/v1/replication`, `/api/v1/escalations`, `/api/v1/emails`, `/api/v1/settings`, and `/ws/tickets`."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.agent.scheduler import get_email_loop_status, run_email_loop_cycle_once
from app.agent.workflow import (
    ingest_and_triage_eml,
    process_replication_dashboard_report,
    reclassify_existing_email,
    trigger_email_in_loop,
)
from app.auth.dependencies import require_permission
from app.auth.models import User
from app.common.database import get_db
from app.diagnostics.base import DualPingTracerouteRequest
from app.diagnostics.service import run_and_persist_diagnostics
from app.directory.models import Branch
from app.observability.event_bus import event_bus
from app.ticketing.schemas import (
    DashboardSummaryResponse,
    EscalationItemDto,
    KanbanTicketCardDto,
    ReplicationParseRequest,
    SendTestEmailRequest,
    SendTestEmailResult,
    SmtpConnectionTestRequest,
    SmtpConnectionTestResult,
    SystemSettingsDto,
    SystemSettingsUpdateRequest,
    TicketCreateManualRequest,
    TicketDetail360Response,
    TicketEmailReplyRequest,
    TicketEscalateHumanRequest,
    TicketNoteCreateRequest,
    TicketStatusUpdateRequest,
    VisionOverrideRequest,
    VllmConnectionTestRequest,
    VllmConnectionTestResult,
)
from app.ticketing.service import (
    add_ticket_note,
    approve_pending_ticket_action,
    convert_unrecognized_email_to_ticket,
    create_manual_ticket,
    escalate_ticket_to_human_engineer,
    force_ticket_isp_followup,
    get_dashboard_summary,
    get_system_settings_dto,
    get_ticket_360_detail,
    get_ticket_by_number_or_id,
    list_human_escalations,
    list_mailbox_triage_logs,
    list_replication_reports,
    list_ticket_cards,
    override_ticket_vision_verdict,
    reject_pending_ticket_action,
    send_live_test_email,
    send_ticket_manual_reply,
    test_smtp_settings,
    test_vllm_settings,
    update_system_settings,
    update_ticket_status_or_meta,
)

tickets_router = APIRouter(prefix="/api/v1/tickets", tags=["Ticketing & Kanban"])
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["Executive & SLA Dashboard"])
replication_router = APIRouter(prefix="/api/v1/replication", tags=["Replication Dashboard Monitor"])
escalations_router = APIRouter(prefix="/api/v1/escalations", tags=["Human Review & Escalations"])
emails_router = APIRouter(prefix="/api/v1/emails", tags=["Mailbox & Email Triage"])
settings_router = APIRouter(prefix="/api/v1/settings", tags=["AI Agent, Mailbox & SLA Settings"])
ws_router = APIRouter(tags=["Real-Time WebSocket Bus"])


@dashboard_router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary_endpoint(
    range_key: str = Query(default="7d", alias="range"),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("tickets:view")),
) -> DashboardSummaryResponse:
    """Return Page 2 Executive & Live SLA Dashboard KPIs, bar charts, and SLA watchlist."""
    return get_dashboard_summary(db, range_key=range_key)


@tickets_router.get("", response_model=list[KanbanTicketCardDto])
async def list_tickets_endpoint(
    search: Optional[str] = Query(default=None),
    isp: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    trigger: Optional[str] = Query(default=None),
    failure_type: Optional[str] = Query(default=None),
    ai_paused_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("tickets:view")),
) -> list[KanbanTicketCardDto]:
    """List tickets for Page 3 (Kanban Board) and Page 4 (Tickets List & Export)."""
    return list_ticket_cards(
        db,
        search=search,
        isp=isp,
        region=region,
        priority=priority,
        trigger=trigger,
        failure_type=failure_type,
        ai_paused_only=ai_paused_only,
    )


@tickets_router.post("", response_model=KanbanTicketCardDto, status_code=status.HTTP_201_CREATED)
async def create_manual_ticket_endpoint(
    payload: TicketCreateManualRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:edit_status")),
) -> KanbanTicketCardDto:
    """Create a manual ticket and trigger initial dual-ping + traceroute diagnostics."""
    card = await create_manual_ticket(db, payload, actor=actor)
    await event_bus.broadcast("ticket.created", card.model_dump())
    return card


@tickets_router.get("/{ticket_identifier}", response_model=TicketDetail360Response)
async def get_ticket_detail_endpoint(
    ticket_identifier: str,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("tickets:view")),
) -> TicketDetail360Response:
    """Return Page 5 Ticket 360° Detail View (Timeline, Tests & Vision, Branch Emails, ISP Emails)."""
    return get_ticket_360_detail(db, ticket_identifier)


@tickets_router.patch("/{ticket_identifier}", response_model=TicketDetail360Response)
async def update_ticket_endpoint(
    ticket_identifier: str,
    payload: TicketStatusUpdateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:edit_status")),
) -> TicketDetail360Response:
    """Update ticket status, Kanban column, priority, AI pause state, ISP case ref, or site contact."""
    detail = update_ticket_status_or_meta(db, ticket_identifier, payload, actor=actor)
    await event_bus.broadcast(
        "ticket.updated",
        {
            "ticket_number": detail.ticket_number,
            "status": detail.status,
            "ai_automation_enabled": detail.ai_automation_enabled,
        },
    )
    return detail


@tickets_router.post("/{ticket_identifier}/notes", response_model=TicketDetail360Response)
async def add_ticket_note_endpoint(
    ticket_identifier: str,
    payload: TicketNoteCreateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:view")),
) -> TicketDetail360Response:
    """Add an internal engineer note to a ticket's timeline."""
    return add_ticket_note(db, ticket_identifier, payload, actor=actor)


@tickets_router.post(
    "/{ticket_identifier}/rerun-diagnostics", response_model=TicketDetail360Response
)
async def rerun_ticket_diagnostics_endpoint(
    ticket_identifier: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("diagnostics:trigger_manual")),
) -> TicketDetail360Response:
    """Trigger an immediate manual diagnostic run on a ticket (Page 5 action bar)."""
    ticket = get_ticket_by_number_or_id(db, ticket_identifier)
    branch = db.get(Branch, ticket.branch_id) if ticket.branch_id else None
    branch_code = branch.branch_code if branch else "1173"
    await run_and_persist_diagnostics(
        db,
        DualPingTracerouteRequest(
            branch_code=branch_code,
            ticket_id=ticket.id,
            trigger_source="MANUAL",
        ),
        actor_name=actor.display_name,
    )
    return get_ticket_360_detail(db, ticket.ticket_number)


@tickets_router.post("/{ticket_identifier}/force-followup", response_model=TicketDetail360Response)
async def force_ticket_followup_endpoint(
    ticket_identifier: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("emails:force_isp_followup")),
) -> TicketDetail360Response:
    """Force an immediate ISP follow-up chaser email on a ticket."""
    return await force_ticket_isp_followup(db, ticket_identifier, actor=actor)


@tickets_router.post("/{ticket_identifier}/reply", response_model=TicketDetail360Response)
async def reply_ticket_email_endpoint(
    ticket_identifier: str,
    payload: TicketEmailReplyRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("emails:send_manual_reply")),
) -> TicketDetail360Response:
    """Send a manual reply on the Branch or ISP email thread of a ticket."""
    return await send_ticket_manual_reply(db, ticket_identifier, payload, actor=actor)


@tickets_router.post("/{ticket_identifier}/escalate", response_model=TicketDetail360Response)
async def escalate_ticket_human_endpoint(
    ticket_identifier: str,
    payload: TicketEscalateHumanRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:edit_status")),
) -> TicketDetail360Response:
    """Escalate a ticket to a human engineer (`NEEDS_HUMAN_REVIEW`), pause AI, and send report."""
    return await escalate_ticket_to_human_engineer(db, ticket_identifier, payload, actor=actor)


@tickets_router.post("/{ticket_identifier}/override-vision", response_model=TicketDetail360Response)
async def override_vision_endpoint(
    ticket_identifier: str,
    payload: VisionOverrideRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:edit_status")),
) -> TicketDetail360Response:
    """Override the Gemma 4 26B router photo vision verdict on a ticket."""
    return override_ticket_vision_verdict(db, ticket_identifier, payload, actor=actor)


@tickets_router.post("/{ticket_identifier}/approve-action", response_model=TicketDetail360Response)
async def approve_pending_ticket_action_endpoint(
    ticket_identifier: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:edit_status")),
) -> TicketDetail360Response:
    """Approve and execute a pending AI agent action on a ticket in Approval Mode."""
    detail = await approve_pending_ticket_action(db, ticket_identifier, actor=actor)
    await event_bus.broadcast(
        "ticket.updated",
        {
            "ticket_number": detail.ticket_number,
            "status": detail.status,
            "ai_automation_enabled": detail.ai_automation_enabled,
        },
    )
    return detail


@tickets_router.post("/{ticket_identifier}/reject-action", response_model=TicketDetail360Response)
async def reject_pending_ticket_action_endpoint(
    ticket_identifier: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:edit_status")),
) -> TicketDetail360Response:
    """Reject a pending AI agent action on a ticket without dispatching proposed emails."""
    detail = await reject_pending_ticket_action(db, ticket_identifier, actor=actor)
    await event_bus.broadcast(
        "ticket.updated",
        {
            "ticket_number": detail.ticket_number,
            "status": detail.status,
            "ai_automation_enabled": detail.ai_automation_enabled,
        },
    )
    return detail


@replication_router.get("/reports")
async def list_replication_reports_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("replication:view")),
) -> list[dict[str, Any]]:
    """List ingested `Replication Dashboard` reports and their store breakdown rows (Page 6)."""
    return list_replication_reports(db)


@replication_router.post("/parse")
async def parse_replication_report_endpoint(
    payload: ReplicationParseRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("replication:upload")),
) -> dict[str, Any]:
    """Parse an uploaded or pasted `Replication Dashboard` HTML table (dry run or live)."""
    return await process_replication_dashboard_report(
        db,
        subject=payload.subject,
        html_content=payload.html_content,
        dry_run=payload.dry_run,
    )


@escalations_router.get("", response_model=list[EscalationItemDto])
async def list_escalations_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("tickets:view")),
) -> list[EscalationItemDto]:
    """List items in the Human Review & Out-of-Flow Escalation Queue (Page 7)."""
    return list_human_escalations(db)


@escalations_router.post("/convert-email/{email_id}")
async def convert_unrecognized_email_endpoint(
    email_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("tickets:edit_status")),
) -> dict[str, Any]:
    """Convert an unmatched `UNRECOGNIZED` email from the Human Review Queue into a tracked ticket."""
    return convert_unrecognized_email_to_ticket(db, email_id, actor=actor)


@emails_router.get("")
async def list_emails_triage_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("emails:view")),
) -> list[dict[str, Any]]:
    """List all inbound and outbound emails processed by the service account (Page 8)."""
    return list_mailbox_triage_logs(db)


@emails_router.get("/loop-status")
async def get_email_loop_status_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("emails:view")),
) -> dict[str, Any]:
    """Return live status of the background Email Agent Harness Loop and SLA Chaser worker."""
    return get_email_loop_status(db)


@emails_router.post("/poll-now")
async def poll_mailbox_and_sla_loop_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("emails:view")),
) -> dict[str, Any]:
    """Trigger an immediate IMAP + local dropbox poll and run the 2h/4–6h SLA chaser cycle."""
    return await run_email_loop_cycle_once(db)


@emails_router.post("/trigger")
async def trigger_email_in_loop_endpoint(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("emails:view")),
) -> dict[str, Any]:
    """Inject a scenario or custom email into the autonomous agent harness loop with full thread correlation."""
    res = await trigger_email_in_loop(db, payload)
    await event_bus.broadcast("email.ingested", res)
    return res


@emails_router.post("/{email_id}/reclassify")
async def reclassify_email_endpoint(
    email_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("emails:view")),
) -> dict[str, Any]:
    """Re-run Gemma 4 26B classification on an existing email in the triage log."""
    res = await reclassify_existing_email(db, email_id)
    await event_bus.broadcast("email.reclassified", res)
    return res


@emails_router.get("/info-samples")
async def list_info_eml_samples_endpoint(
    _user: User = Depends(require_permission("emails:view")),
) -> list[str]:
    """List the real `.eml` files available in `Info/` for one-click simulation on Page 8."""
    info_dir = Path(__file__).resolve().parent.parent.parent.parent / "Info"
    if not info_dir.exists():
        return []
    return sorted(p.name for p in info_dir.glob("*.eml"))


@emails_router.post("/simulate-eml")
async def simulate_eml_upload_endpoint(
    file: Optional[UploadFile] = File(default=None),
    sample_filename: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("emails:view")),
) -> dict[str, Any]:
    """Simulate inbound email triage from an uploaded `.eml` file or a sample `.eml` in `Info/`."""
    if file is not None:
        raw_bytes = await file.read()
        fname = file.filename or "uploaded.eml"
    elif sample_filename:
        info_dir = Path(__file__).resolve().parent.parent.parent.parent / "Info"
        target = (info_dir / Path(sample_filename).name).resolve()
        if not target.exists():
            from app.common.exceptions import EntityNotFoundError

            raise EntityNotFoundError("EmlSample", sample_filename)
        raw_bytes = target.read_bytes()
        fname = target.name
    else:
        from app.common.exceptions import ValidationError

        raise ValidationError(
            "Provide either an uploaded .eml file or a sample_filename query parameter"
        )

    res = await ingest_and_triage_eml(db, raw_bytes, filename=fname)
    await event_bus.broadcast("email.ingested", res)
    return res


@settings_router.get("", response_model=SystemSettingsDto)
async def get_settings_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("settings:read")),
) -> SystemSettingsDto:
    """Return AI Agent, Mailbox, SLA timers, Global Kill-Switch, and Fallback Contacts (Page 12)."""
    return get_system_settings_dto(db)


@settings_router.put("", response_model=SystemSettingsDto)
async def update_settings_endpoint(
    payload: SystemSettingsUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("settings:update")),
) -> SystemSettingsDto:
    """Update AI Agent, Mailbox, SLA timers, Global Kill-Switch, or Fallback Contacts (Page 12)."""
    ip_addr = request.client.host if request.client else None
    return update_system_settings(db, payload, actor=actor, ip_address=ip_addr)


@settings_router.post("/test-smtp", response_model=SmtpConnectionTestResult)
async def test_smtp_settings_endpoint(
    payload: SmtpConnectionTestRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("settings:read")),
) -> SmtpConnectionTestResult:
    """Open a real SMTP session (connect, EHLO, TLS, login) without sending mail (Page 12)."""
    return await test_smtp_settings(db, payload)


@settings_router.post("/send-test-email", response_model=SendTestEmailResult)
async def send_test_email_endpoint(
    payload: SendTestEmailRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("settings:update")),
) -> SendTestEmailResult:
    """Send a live test email via configured SMTP."""
    return await send_live_test_email(db, payload)


@settings_router.post("/test-vllm", response_model=VllmConnectionTestResult)
async def test_vllm_settings_endpoint(
    payload: VllmConnectionTestRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("settings:read")),
) -> VllmConnectionTestResult:
    """Call vLLM `GET /v1/models` and confirm the configured model is served (Page 12)."""
    return await test_vllm_settings(db, payload)


@ws_router.websocket("/ws/tickets")
async def tickets_websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time WebSocket stream for Kanban board, Ticket 360° updates, and email triage events."""
    await event_bus.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_bus.disconnect(websocket)
    except Exception:
        event_bus.disconnect(websocket)
