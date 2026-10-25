"""Deterministic Ticket Lifecycle State Machine & 8-Column Kanban Mapping (CLAUDE.md §1.1 & BRD §5)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.common.contracts import TicketStatus
from app.common.exceptions import InvalidStateTransitionError
from app.ticketing.models import Ticket

ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.AWAITING_REGIONAL_IT: frozenset(
        {
            TicketStatus.DIAGNOSING,
            TicketStatus.NEEDS_HUMAN_REVIEW,
            TicketStatus.CLOSED,
        }
    ),
    TicketStatus.NEW: frozenset(
        {
            TicketStatus.DIAGNOSING,
            TicketStatus.AWAITING_BRANCH,
            TicketStatus.INTERNAL_LAN_ISSUE,
            TicketStatus.ESCALATED_TO_ISP,
            TicketStatus.CLOSED,
            TicketStatus.NEEDS_HUMAN_REVIEW,
        }
    ),
    TicketStatus.DIAGNOSING: frozenset(
        {
            TicketStatus.AWAITING_BRANCH,
            TicketStatus.INTERNAL_LAN_ISSUE,
            TicketStatus.ESCALATED_TO_ISP,
            TicketStatus.CLOSED,
            TicketStatus.NEEDS_HUMAN_REVIEW,
        }
    ),
    TicketStatus.AWAITING_BRANCH: frozenset(
        {
            TicketStatus.DIAGNOSING,
            TicketStatus.NEEDS_HUMAN_REVIEW,
            TicketStatus.CLOSED,
        }
    ),
    TicketStatus.AWAITING_BRANCH_CONFIRMATION: frozenset(
        {
            TicketStatus.DIAGNOSING,
            TicketStatus.RESOLVED,
            TicketStatus.CLOSED,
            TicketStatus.NEEDS_HUMAN_REVIEW,
        }
    ),
    TicketStatus.INTERNAL_LAN_ISSUE: frozenset(
        {
            TicketStatus.DIAGNOSING,
            TicketStatus.CLOSED,
            TicketStatus.NEEDS_HUMAN_REVIEW,
        }
    ),
    TicketStatus.ESCALATED_TO_ISP: frozenset(
        {
            TicketStatus.AWAITING_BRANCH_CONTACT,
            TicketStatus.VERIFYING,
            TicketStatus.NEEDS_HUMAN_REVIEW,
        }
    ),
    # VERIFYING: the ISP may claim resolution while we are still waiting on a site contact.
    TicketStatus.AWAITING_BRANCH_CONTACT: frozenset(
        {
            TicketStatus.ESCALATED_TO_ISP,
            TicketStatus.VERIFYING,
            TicketStatus.NEEDS_HUMAN_REVIEW,
        }
    ),
    TicketStatus.VERIFYING: frozenset(
        {
            TicketStatus.CLOSED,
            TicketStatus.RESOLVED,
            TicketStatus.ESCALATED_TO_ISP,
            TicketStatus.NEEDS_HUMAN_REVIEW,
        }
    ),
    TicketStatus.NEEDS_HUMAN_REVIEW: frozenset(
        s for s in TicketStatus if s != TicketStatus.NEEDS_HUMAN_REVIEW
    ),
    TicketStatus.RESOLVED: frozenset(
        {
            TicketStatus.CLOSED,
        }
    ),
    TicketStatus.CLOSED: frozenset(),
}


def assert_transition(current: TicketStatus | str, target: TicketStatus | str) -> None:
    """Validate that transitioning a ticket from `current` to `target` is legal per BRD §4.1."""
    try:
        curr_enum = TicketStatus(str(current))
    except ValueError as exc:
        raise InvalidStateTransitionError(f"Unknown current ticket status '{current}'") from exc
    try:
        tgt_enum = TicketStatus(str(target))
    except ValueError as exc:
        raise InvalidStateTransitionError(f"Unknown target ticket status '{target}'") from exc

    allowed = ALLOWED_TRANSITIONS.get(curr_enum, frozenset())
    if tgt_enum not in allowed:
        raise InvalidStateTransitionError(
            f"Illegal ticket state transition: {curr_enum.value} -> {tgt_enum.value}"
        )


KANBAN_COLUMNS: list[tuple[int, str, str]] = [
    (0, "Awaiting Regional IT", ""),
    (1, "New & Diagnosing", ""),
    (2, "Branch / Internal Action", ""),
    (3, "Escalated to ISP · 2h", "isp"),
    (4, "With ISP · 4–6h loop", "isp"),
    (5, "Verifying Fix", ""),
    (6, "Needs Human Review", "human"),
    (7, "Resolved / Closed", "done"),
]


def resolve_kanban_column(ticket: Ticket) -> int:
    """Map a `Ticket` status + `isp_welcome_received` flag to one of the 8 Kanban columns (0..7)."""
    status = ticket.status
    if status == TicketStatus.AWAITING_REGIONAL_IT.value:
        return 0
    if status in {TicketStatus.NEW.value, TicketStatus.DIAGNOSING.value}:
        return 1
    if status in {
        TicketStatus.AWAITING_BRANCH.value,
        TicketStatus.INTERNAL_LAN_ISSUE.value,
        TicketStatus.AWAITING_BRANCH_CONFIRMATION.value,
    }:
        return 2
    if status == TicketStatus.ESCALATED_TO_ISP.value:
        return 4 if ticket.isp_welcome_received else 3
    if status == TicketStatus.AWAITING_BRANCH_CONTACT.value:
        return 4
    if status == TicketStatus.VERIFYING.value:
        return 5
    if status == TicketStatus.NEEDS_HUMAN_REVIEW.value:
        return 6
    if status in {TicketStatus.RESOLVED.value, TicketStatus.CLOSED.value}:
        return 7
    return 1


def resolve_human_stage_label(ticket: Ticket) -> str:
    """Return the human-readable stage badge label for a ticket."""
    col = resolve_kanban_column(ticket)
    if col == 0:
        return "Awaiting Regional IT"
    if col == 1:
        return "Diagnosing"
    if col == 2:
        if ticket.status == TicketStatus.INTERNAL_LAN_ISSUE.value:
            return "Internal LAN Issue"
        return "Awaiting Branch"
    if col == 3:
        return "Escalated to ISP"
    if col == 4:
        return "With ISP"
    if col == 5:
        return "Verifying"
    if col == 6:
        return "Needs Human Review"
    return "Closed" if ticket.status == TicketStatus.CLOSED.value else "Resolved"


def compute_sla_tuple(
    ticket: Ticket,
    *,
    now: Optional[datetime] = None,
) -> Optional[tuple[int, int]]:
    """Compute `(minutes_left, total_minutes)` for `SlaTimer` on columns 3 & 4."""
    col = resolve_kanban_column(ticket)
    if col not in {3, 4}:
        return None
    total = 120 if col == 3 else 300
    ref_time = now or datetime.now(timezone.utc)
    if ticket.next_followup_at is not None:
        nf = (
            ticket.next_followup_at
            if ticket.next_followup_at.tzinfo
            else ticket.next_followup_at.replace(tzinfo=timezone.utc)
        )
        minutes_left = int(round((nf - ref_time).total_seconds() / 60.0))
        return (minutes_left, total)
    return (45 if col == 3 else 120, total)
