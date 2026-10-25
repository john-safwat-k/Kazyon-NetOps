"""SQLAlchemy models for Tickets, DiagnosticRuns, TicketEmails, TicketEvents, ReplicationReports, and SystemSettings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, false as sa_false
from sqlalchemy.orm import Mapped, mapped_column

from app.common.contracts import TicketPriority, TicketStatus, TicketTriggerSource
from app.common.database import Base, JSONVariant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Ticket(Base):
    """Network support incident ticket tracked on the Jira-style Kanban board."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_source: Mapped[str] = mapped_column(
        String(48), default=TicketTriggerSource.DIRECT_EMAIL.value, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(48), default=TicketStatus.NEW.value, index=True, nullable=False
    )
    priority: Mapped[str] = mapped_column(
        String(24), default=TicketPriority.MEDIUM.value, index=True, nullable=False
    )
    branch_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("branches.id", ondelete="SET NULL"), index=True, nullable=True
    )
    isp_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("network_providers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    assigned_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    sender_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    site_contact_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    router_image_paths: Mapped[list[str]] = mapped_column(JSONVariant, default=list, nullable=False)
    image_check_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    image_analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    connection_failure_type: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True
    )
    isp_welcome_received: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    isp_reference_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ai_automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    escalation_reason: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    human_escalated_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_isp_contact_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    followup_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class DiagnosticRun(Base):
    """Record of an automated or manual troubleshooting script execution (ticket or sandbox)."""

    __tablename__ = "diagnostic_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=True
    )
    branch_code: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    trigger_source: Mapped[str] = mapped_column(String(48), nullable=False)
    ip_1_up: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ip_2_up: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    four_g_hub_detected: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    detected_hub_ip: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    result_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    diagnosis_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict, nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class TicketEmail(Base):
    """Inbound or outbound email processed by the service account (Branch, ISP, or Triage)."""

    __tablename__ = "ticket_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=True
    )
    thread_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(JSONVariant, default=list, nullable=False)
    cc: Mapped[list[str]] = mapped_column(JSONVariant, default=list, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    raw_headers: Mapped[dict[str, str]] = mapped_column(JSONVariant, default=dict, nullable=False)
    classification_label: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True
    )
    ai_analysis_json: Mapped[dict[str, Any]] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )
    sent_or_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class TicketEvent(Base):
    """Chronological timeline/audit event for a ticket (status change, AI action, note)."""

    __tablename__ = "ticket_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ReplicationReport(Base):
    """Ingested 'Replication Dashboard - <Date>' email report."""

    __tablename__ = "replication_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    report_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notified_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicates_skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class ReplicationReportRow(Base):
    """Parsed store row from a Replication Dashboard HTML table."""

    __tablename__ = "replication_report_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("replication_reports.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    branch_code: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    store_name: Mapped[str] = mapped_column(String(200), nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_trans_raw: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    business_date: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    regional_it_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    regional_it_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    linked_ticket_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="SET NULL"), index=True, nullable=True
    )
    linked_ticket_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)


class SystemSettings(Base):
    """Singleton/keyed runtime configuration for AI Agent, Mailbox, SLA timers, and Fallback Contacts."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, default="global", nullable=False
    )
    global_ai_kill_switch: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mailbox_account: Mapped[str] = mapped_column(
        String(255), default="itsupport-agent@kazyon.com", nullable=False
    )
    imap_host: Mapped[str] = mapped_column(
        String(255), default="outlook.office365.com", nullable=False
    )
    imap_port: Mapped[int] = mapped_column(Integer, default=993, nullable=False)
    imap_use_ssl: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    imap_folder: Mapped[str] = mapped_column(
        String(128), default="INBOX", server_default="INBOX", nullable=False
    )
    imap_username: Mapped[str] = mapped_column(
        String(255), default="", server_default="", nullable=False
    )
    imap_password_encrypted: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    smtp_host: Mapped[str] = mapped_column(
        String(255), default="smtp.office365.com", nullable=False
    )
    smtp_port: Mapped[int] = mapped_column(Integer, default=587, nullable=False)
    # "starttls" (587), "ssl" (465) or "none" (internal relay, usually 25)
    smtp_security: Mapped[str] = mapped_column(
        String(16), default="starttls", server_default="starttls", nullable=False
    )
    # Real outbound delivery is off until an admin turns it on from Page 12
    smtp_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sa_false(), nullable=False
    )
    smtp_username: Mapped[str] = mapped_column(
        String(255), default="", server_default="", nullable=False
    )
    smtp_password_encrypted: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    # Optional test email address that intercepts all outbound emails (Branch, ISP, Human)
    test_redirect_email: Mapped[str] = mapped_column(
        String(255), default="", server_default="", nullable=False
    )
    poll_interval_sec: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    vllm_endpoint: Mapped[str] = mapped_column(
        String(255), default="http://10.100.109.9:8002/v1", nullable=False
    )
    vllm_temperature: Mapped[float] = mapped_column(default=0.1, nullable=False)
    vllm_max_tokens: Mapped[int] = mapped_column(Integer, default=2048, nullable=False)
    confidence_threshold: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    welcome_sla_minutes: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    followup_interval_minutes: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_chasers_before_human: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    max_outbound_emails_per_ticket_hour: Mapped[int] = mapped_column(
        Integer, default=6, nullable=False
    )
    ignore_auto_submitted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    diagnostic_timeout_sec: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    ping_count: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    traceroute_max_hops: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    fallback_contacts: Mapped[list[dict[str, str]]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
