"""Anti-Email-Storm Loop Guard & Auto-Submitted header filter (CLAUDE.md §6 & BRD FR-2.3)."""

from __future__ import annotations

import logging
from typing import Optional

from app.common.cache import get_redis
from app.common.config import get_settings

logger = logging.getLogger("it_net.email_engine.loop_guard")


def is_auto_submitted_email(raw_headers: dict[str, str], subject: str) -> bool:
    """Return True if headers indicate an automatic vacation/out-of-office responder that must not loop."""
    auto_sub = (
        raw_headers.get("Auto-Submitted") or raw_headers.get("auto-submitted") or ""
    ).lower()
    if auto_sub and auto_sub != "no":
        return True
    precedence = (raw_headers.get("Precedence") or "").lower()
    if precedence in {"bulk", "junk", "auto_reply"}:
        return True
    subj_lower = subject.lower()
    if subj_lower.startswith(("automatic reply:", "out of office:", "auto:")):
        return True
    return False


def check_and_increment_outbound_allowance(
    ticket_number: str,
    *,
    max_per_hour: Optional[int] = None,
) -> bool:
    """Enforce `MAX_OUTBOUND_EMAILS_PER_TICKET_HOUR` per ticket using Redis (fail-safe when Redis is unreachable)."""
    settings = get_settings()
    limit = max_per_hour or settings.max_outbound_emails_per_ticket_hour
    key = f"it_net:loop_guard:outbound:{ticket_number}"
    client = get_redis()
    if client is not None:
        try:
            current = client.incr(key)
            if int(current) == 1:
                client.expire(key, 3600)
            allowed = int(current) <= limit
            if not allowed:
                logger.warning(
                    "Loop guard blocked outbound email for ticket=%s (count=%s > limit=%d)",
                    ticket_number,
                    current,
                    limit,
                )
            return allowed
        except Exception as exc:
            logger.error(
                "Redis loop guard error for ticket=%s (fail-safe blocking unless test override): %s",
                ticket_number,
                exc,
            )
            return bool(settings.loop_guard_fail_open_for_tests)

    if settings.loop_guard_fail_open_for_tests:
        return True

    logger.error(
        "Redis client unavailable for loop guard on ticket=%s — blocking outbound email (fail-safe)",
        ticket_number,
    )
    return False
