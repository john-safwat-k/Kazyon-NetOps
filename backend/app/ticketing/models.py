"""SQLAlchemy models for Tickets, DiagnosticRuns, TicketEmails, and TicketEvents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.contracts import TicketPriority, TicketStatus
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
    isp_reference_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ai_automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    """Record of an automated or manual troubleshooting script execution for a ticket."""

    __tablename__ = "diagnostic_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trigger_source: Mapped[str] = mapped_column(String(48), nullable=False)
    result_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict, nullable=False)
    raw_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class TicketEmail(Base):
    """Inbound or outbound email linked to a ticket (Branch thread or ISP thread)."""

    __tablename__ = "ticket_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
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
