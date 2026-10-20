"""Frozen architectural contracts across the IT Network Support AI Agent harness.

See CLAUDE.md §1.1 — changing any of these contracts is a breaking change by default.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class TicketStatus(StrEnum):
    """Canonical lifecycle statuses for Jira-style network support tickets."""

    NEW = "NEW"
    DIAGNOSING = "DIAGNOSING"
    ESCALATED_TO_ISP = "ESCALATED_TO_ISP"
    VERIFYING = "VERIFYING"
    AWAITING_BRANCH_CONFIRMATION = "AWAITING_BRANCH_CONFIRMATION"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(StrEnum):
    """Urgency/severity level for a network support ticket."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DiagnosticStatus(StrEnum):
    """Standardized outcome of a troubleshooting script execution."""

    PASS = "PASS"
    FAIL = "FAIL"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class DiagnosticInput(BaseModel):
    """Standardized input passed to any pluggable network troubleshooting script."""

    ticket_number: str
    branch_code: str
    branch_name: str
    target_ip: str
    circuit_id: str
    connection_type: str = "FIBER"
    extra_meta: dict[str, Any] = Field(default_factory=dict)


class DiagnosticOutput(BaseModel):
    """Standardized output returned by any pluggable network troubleshooting script."""

    status: DiagnosticStatus
    summary: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    raw_output: str = ""
    duration_ms: int = 0


class EmailEnvelope(BaseModel):
    """Immutable normalized inbound email representation."""

    message_id: str
    in_reply_to: Optional[str] = None
    references: list[str] = Field(default_factory=list)
    sender: str
    recipients: list[str] = Field(default_factory=list)
    cc: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    body_html: Optional[str] = None
    received_at: datetime
    raw_headers: dict[str, str] = Field(default_factory=dict)


class BranchEmailAnalysis(BaseModel):
    """Guided-JSON output from Gemma 4 26B A4B when classifying an inbound branch email."""

    is_network_issue: bool
    branch_identifier: Optional[str] = None
    reported_symptoms: str
    urgency: TicketPriority = TicketPriority.MEDIUM
    is_resolution_confirmation: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class IspResponseAnalysis(BaseModel):
    """Guided-JSON output from Gemma 4 26B A4B when classifying an inbound ISP response."""

    intent: Literal[
        "AUTO_ACK",
        "INVESTIGATING_UPDATE",
        "RESOLUTION_CLAIM",
        "INFO_REQUEST",
    ]
    isp_ticket_number: Optional[str] = None
    eta: Optional[str] = None
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
