"""System-wide audit trail models and helpers for admin, RBAC, and operational mutations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.common.database import Base, JSONVariant

logger = logging.getLogger("it_net.audit")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """Immutable audit log entry for security, RBAC, user, and system settings mutations."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    actor_username: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True, nullable=False
    )


def record_audit_event(
    db: Session,
    *,
    actor_username: str,
    action: str,
    resource_type: str,
    summary: str,
    actor_user_id: Optional[int] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    commit: bool = False,
) -> AuditLog:
    """Persist an audit log record for administrative or RBAC actions."""
    entry = AuditLog(
        actor_user_id=actor_user_id,
        actor_username=actor_username,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        summary=summary,
        details_json=details or {},
        ip_address=ip_address,
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    logger.info(
        "AUDIT [%s] actor=%s resource=%s:%s summary=%s",
        action,
        actor_username,
        resource_type,
        resource_id or "-",
        summary,
    )
    return entry
