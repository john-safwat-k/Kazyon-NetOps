"""Pydantic v2 DTOs for Tickets, Kanban Board, 360° Ticket Detail, Dashboard, Replication, Emails, Escalations, and Settings."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class KanbanTicketCardDto(BaseModel):
    id: str
    ticket_db_id: int
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    branch: str
    branch_code: str
    region: str
    failure: Optional[str] = None
    failure_code: Optional[str] = None
    trigger: str
    isp: Literal["NOOR", "ORANGE", "WE"]
    caseRef: Optional[str] = None
    checks: Optional[list[tuple[str, Literal["up", "down", "hub", "skip"]]]] = None
    sla: Optional[tuple[int, int]] = None
    note: Optional[str] = None
    aiPaused: bool = False
    status: str
    raw_status: str
    opened: str
    mttr: str = "—"
    col: int


class TicketCreateManualRequest(BaseModel):
    branch_code: str = Field(min_length=1, max_length=64)
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "HIGH"
    site_contact_phone: Optional[str] = None
    trigger_source: str = "DIRECT_EMAIL"
    description: str = "Store not syncing. Router photo attached by Regional IT."
    run_diagnostics: bool = True
    simulate_scenario: Optional[
        Literal[
            "AUTO",
            "PASS",
            "FULL_OUTAGE",
            "LOCAL_LOOP_DOWN_ON_4G",
            "INTERNAL_LAN_SWITCH",
        ]
    ] = "AUTO"


class TicketStatusUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    ai_automation_enabled: Optional[bool] = None
    isp_reference_number: Optional[str] = None
    site_contact_phone: Optional[str] = None
    kanban_col: Optional[int] = Field(default=None, ge=0, le=7)


class TicketNoteCreateRequest(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class TicketEmailReplyRequest(BaseModel):
    thread_type: Literal["BRANCH", "ISP"] = "BRANCH"
    body_text: str = Field(min_length=1, max_length=4000)
    subject: Optional[str] = None


class TicketEscalateHumanRequest(BaseModel):
    target_email: str = "noc-oncall@kazyon.com"
    reason: str = "OTHER"
    note: str = ""


class VisionOverrideRequest(BaseModel):
    cables_plugged: bool = True
    summary: Optional[str] = None


class TimelineEventDto(BaseModel):
    id: int
    time: str
    color: str
    title: str
    actor: str
    detail: str
    event_type: str


class TicketEmailItemDto(BaseModel):
    id: int
    from_addr: str
    to_addr: str
    cc_addr: str = ""
    when: str
    direction: str
    thread_type: str
    subject: str
    body: str
    outbound: bool
    classification_label: Optional[str] = None
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    thread_replies: list[dict[str, Any]] = Field(default_factory=list)


class TicketDetail360Response(BaseModel):
    ticket_db_id: int
    ticket_number: str
    title: str
    description: Optional[str] = None
    status: str
    stage_label: str
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    trigger_source: str
    ai_automation_enabled: bool
    opened_at: str
    sender_email: str
    site_contact_phone: str
    isp_reference_number: str
    isp_welcome_received: bool
    followup_count: int
    sla_minutes_left: int
    sla_total_minutes: int
    sla_summary_text: str
    branch: dict[str, Any]
    isp: dict[str, Any]
    vision: dict[str, Any]
    events: list[TimelineEventDto]
    diagnostic_runs: list[dict[str, Any]]
    branch_emails: list[TicketEmailItemDto]
    isp_emails: list[TicketEmailItemDto]


class DashboardSummaryResponse(BaseModel):
    range_key: str
    range_label: str
    total_branches: int = 1150
    regions_list: list[str] = Field(default_factory=list)
    kpis: dict[str, int]
    services: list[dict[str, str]]
    by_isp: list[dict[str, Any]]
    mttr_by_isp: list[dict[str, Any]]
    by_type: list[dict[str, Any]]
    by_region: list[dict[str, Any]]
    watchlist: list[dict[str, Any]]


class ReplicationParseRequest(BaseModel):
    subject: str = "Replication Dashboard - 21/10/2026"
    html_content: str
    dry_run: bool = True


class EscalationItemDto(BaseModel):
    key: str
    ticket_number: Optional[str] = None
    email_id: Optional[int] = None
    reason: str
    isp: Optional[str] = None
    case_ref: Optional[str] = None
    when: str
    title: str
    quote: str
    from_addr: str
    summary: str
    engineer_email: str
    primary_action: str


class SystemSettingsDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    global_ai_kill_switch: bool
    mailbox_account: str
    imap_host: str
    imap_port: int
    imap_use_ssl: bool = True
    imap_folder: str = "INBOX"
    imap_username: str = ""
    imap_credentials_configured: bool = False
    smtp_host: str
    smtp_port: int
    smtp_security: Literal["starttls", "ssl", "none"]
    smtp_enabled: bool
    smtp_username: str = ""
    # True when SMTP login is configured in DB or environment (password never returned)
    smtp_credentials_configured: bool = False
    test_redirect_email: str = ""
    poll_interval_sec: int
    vllm_endpoint: str
    vllm_temperature: float
    vllm_max_tokens: int
    confidence_threshold: int
    welcome_sla_minutes: int
    followup_interval_minutes: int
    max_chasers_before_human: int
    max_outbound_emails_per_ticket_hour: int
    ignore_auto_submitted: bool
    diagnostic_timeout_sec: int
    ping_count: int
    traceroute_max_hops: int
    fallback_contacts: list[dict[str, str]]


SmtpSecurity = Literal["starttls", "ssl", "none"]


class SystemSettingsUpdateRequest(BaseModel):
    """Partial update for Page 12; omitted fields keep their saved value."""

    global_ai_kill_switch: Optional[bool] = None
    mailbox_account: Optional[str] = Field(default=None, min_length=3, max_length=255)
    imap_host: Optional[str] = Field(default=None, max_length=255)
    imap_port: Optional[int] = Field(default=None, ge=1, le=65535)
    imap_use_ssl: Optional[bool] = None
    imap_folder: Optional[str] = Field(default=None, max_length=120)
    imap_username: Optional[str] = Field(default=None, max_length=255)
    imap_password: Optional[str] = Field(default=None, max_length=255)
    smtp_host: Optional[str] = Field(default=None, max_length=255)
    smtp_port: Optional[int] = Field(default=None, ge=1, le=65535)
    smtp_security: Optional[SmtpSecurity] = None
    smtp_enabled: Optional[bool] = None
    smtp_username: Optional[str] = Field(default=None, max_length=255)
    smtp_password: Optional[str] = Field(default=None, max_length=255)
    test_redirect_email: Optional[str] = Field(default=None, max_length=255)
    poll_interval_sec: Optional[int] = Field(default=None, ge=10, le=3600)
    vllm_endpoint: Optional[str] = Field(
        default=None, max_length=255, pattern=r"^https?://[^\s/]+(:\d+)?(/.*)?$"
    )
    vllm_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    vllm_max_tokens: Optional[int] = Field(default=None, ge=64, le=32768)
    confidence_threshold: Optional[int] = Field(default=None, ge=0, le=100)
    welcome_sla_minutes: Optional[int] = Field(default=None, ge=5, le=10080)
    followup_interval_minutes: Optional[int] = Field(default=None, ge=5, le=10080)
    max_chasers_before_human: Optional[int] = Field(default=None, ge=1, le=100)
    max_outbound_emails_per_ticket_hour: Optional[int] = Field(default=None, ge=1, le=100)
    ignore_auto_submitted: Optional[bool] = None
    diagnostic_timeout_sec: Optional[int] = Field(default=None, ge=2, le=60)
    ping_count: Optional[int] = Field(default=None, ge=1, le=20)
    traceroute_max_hops: Optional[int] = Field(default=None, ge=1, le=64)
    fallback_contacts: Optional[list[dict[str, str]]] = None


class SmtpConnectionTestRequest(BaseModel):
    """Optional unsaved values from the Page 12 form; omitted fields use the saved settings."""

    smtp_host: Optional[str] = Field(default=None, max_length=255)
    smtp_port: Optional[int] = Field(default=None, ge=1, le=65535)
    smtp_security: Optional[SmtpSecurity] = None
    smtp_username: Optional[str] = Field(default=None, max_length=255)
    smtp_password: Optional[str] = Field(default=None, max_length=255)
    mailbox_account: Optional[str] = Field(default=None, max_length=255)


class SmtpConnectionTestResult(BaseModel):
    ok: bool
    host: str
    port: int
    security: SmtpSecurity
    authenticated: bool
    credentials_configured: bool
    stage: Literal["config", "connect", "ehlo", "tls", "auth", "sender", "done"]
    latency_ms: int
    server_banner: Optional[str] = None
    error: Optional[str] = None


class ImapConnectionTestRequest(BaseModel):
    """Optional unsaved values from the Page 12 form; omitted fields use the saved settings."""

    imap_host: Optional[str] = Field(default=None, max_length=255)
    imap_port: Optional[int] = Field(default=None, ge=1, le=65535)
    imap_use_ssl: Optional[bool] = None
    imap_folder: Optional[str] = Field(default=None, max_length=120)
    imap_username: Optional[str] = Field(default=None, max_length=255)
    imap_password: Optional[str] = Field(default=None, max_length=255)


class ImapConnectionTestResult(BaseModel):
    ok: bool
    host: str
    port: int
    use_ssl: bool
    folder: str
    authenticated: bool
    credentials_configured: bool
    stage: Literal["config", "connect", "auth", "select", "done"]
    latency_ms: int
    message_count: Optional[int] = None
    unseen_count: Optional[int] = None
    error: Optional[str] = None


class SendTestEmailRequest(BaseModel):
    """Send a live test email via configured SMTP (e.g. Gmail round-trip test)."""

    recipient: Optional[str] = Field(default=None, max_length=255)
    subject: Optional[str] = Field(default=None, max_length=255)
    body_text: Optional[str] = Field(default=None, max_length=4000)
    branch_code: str = Field(default="1084", max_length=16)


class SendTestEmailResult(BaseModel):
    ok: bool
    recipient: str
    subject: str
    message_id: str
    latency_ms: int
    error: Optional[str] = None


class VllmConnectionTestRequest(BaseModel):
    vllm_endpoint: Optional[str] = Field(
        default=None, max_length=255, pattern=r"^https?://[^\s/]+(:\d+)?(/.*)?$"
    )


class VllmConnectionTestResult(BaseModel):
    ok: bool
    endpoint: str
    configured_model: str
    model_available: bool
    available_models: list[str] = Field(default_factory=list)
    latency_ms: int
    error: Optional[str] = None
