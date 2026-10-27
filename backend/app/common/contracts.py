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

    AWAITING_REGIONAL_IT = "AWAITING_REGIONAL_IT"
    NEW = "NEW"
    DIAGNOSING = "DIAGNOSING"
    AWAITING_BRANCH = "AWAITING_BRANCH"
    INTERNAL_LAN_ISSUE = "INTERNAL_LAN_ISSUE"
    ESCALATED_TO_ISP = "ESCALATED_TO_ISP"
    AWAITING_BRANCH_CONTACT = "AWAITING_BRANCH_CONTACT"
    VERIFYING = "VERIFYING"
    AWAITING_BRANCH_CONFIRMATION = "AWAITING_BRANCH_CONFIRMATION"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketTriggerSource(StrEnum):
    """How a network support ticket was originated."""

    DIRECT_EMAIL = "DIRECT_EMAIL"
    REPLICATION_DASHBOARD = "REPLICATION_DASHBOARD"
    UNKNOWN_ESCALATION = "UNKNOWN_ESCALATION"
    MANUAL = "MANUAL"
    PROACTIVE_SCAN = "PROACTIVE_SCAN"


class ConnectionFailureType(StrEnum):
    """Standardized root cause diagnosis from the dual-ping & 4G traceroute harness."""

    FULL_OUTAGE = "FULL_OUTAGE"
    LOCAL_LOOP_DOWN_ON_4G = "LOCAL_LOOP_DOWN_ON_4G"
    INTERNAL_LAN_SWITCH = "INTERNAL_LAN_SWITCH"
    CABLE_UNPLUGGED = "CABLE_UNPLUGGED"
    PASS = "PASS"


class EscalationReason(StrEnum):
    """Reason a ticket or email was escalated to a Human IT Engineer."""

    ADMIN_APPROVAL_REQUIRED = "ADMIN_APPROVAL_REQUIRED"
    UNRECOGNIZED_EMAIL = "UNRECOGNIZED_EMAIL"
    QUOTA_CONSUMED = "QUOTA_CONSUMED"
    INTERNAL_BOX_CABLE = "INTERNAL_BOX_CABLE"
    MSAN_MIGRATION = "MSAN_MIGRATION"
    MAX_RETRIES = "MAX_RETRIES"
    LOOP_GUARD_TRIPPED = "LOOP_GUARD_TRIPPED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    DIAGNOSTICS_UNAVAILABLE = "DIAGNOSTICS_UNAVAILABLE"
    INGEST_FAILED = "INGEST_FAILED"
    MASS_OUTAGE_SUSPECTED = "MASS_OUTAGE_SUSPECTED"
    OTHER = "OTHER"


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
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class RouterPhotoVisionAnalysis(BaseModel):
    """Guided-JSON output from Gemma 4 26B A4B when inspecting an attached router photo."""

    cables_plugged: bool = True
    power_led_on: bool = True
    wan_led_on: bool = False
    summary: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class BranchEmailAnalysis(BaseModel):
    """Guided-JSON output from Gemma 4 26B A4B when classifying an inbound branch email."""

    is_network_issue: bool
    branch_identifier: Optional[str] = None
    site_contact_phone: Optional[str] = None
    has_router_photo: bool = False
    reported_symptoms: str
    urgency: TicketPriority = TicketPriority.MEDIUM
    is_resolution_confirmation: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class IspResponseAnalysis(BaseModel):
    """Guided-JSON output from Gemma 4 26B A4B when classifying an inbound ISP response."""

    intent: Literal[
        "AUTO_ACK",
        "ISP_WELCOME",
        "INVESTIGATING_UPDATE",
        "SITE_CONTACT_UNREACHABLE",
        "BRANCH_ACTION_BLOCKER",
        "RESOLUTION_CLAIM",
        "INFO_REQUEST",
        "SPECIAL_BLOCKER",
    ]
    isp_ticket_number: Optional[str] = None
    special_blocker_reason: Optional[str] = None
    eta: Optional[str] = None
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class UniversalEmailTriageResult(BaseModel):
    """Unified triage result combining deterministic header/regex rules and Gemma 4 26B analysis."""

    trigger_type: Literal[
        "REPLICATION_REPORT",
        "BRANCH_INCIDENT",
        "ISP_REPLY",
        "UNRECOGNIZED",
    ]
    classification_label: str
    branch_code: Optional[str] = None
    isp_name: Optional[str] = None
    isp_reference_number: Optional[str] = None
    site_contact_phone: Optional[str] = None
    intent: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    next_action: str
    summary: str
    raw_analysis: dict[str, Any] = Field(default_factory=dict)
