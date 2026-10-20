"""SQLAlchemy models for Users, Roles, and Granular Permissions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, JSONVariant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


ALL_PERMISSIONS: list[str] = [
    "tickets:view",
    "tickets:edit_status",
    "tickets:assign",
    "tickets:pause_ai",
    "tickets:delete",
    "diagnostics:view_logs",
    "diagnostics:trigger_manual",
    "emails:view",
    "emails:send_manual_reply",
    "emails:force_isp_followup",
    "branches:view",
    "branches:create",
    "branches:edit",
    "branches:import_sheet",
    "isps:manage",
    "users:view",
    "users:create",
    "users:edit_permissions",
    "roles:manage",
    "settings:manage_mailbox",
    "settings:manage_agent_prompts",
    "settings:manage_sla_timers",
]


class User(Base):
    """Internal system user with role and granular permission overrides."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_name: Mapped[str] = mapped_column(String(64), default="support_engineer", nullable=False)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSONVariant, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def has_permission(self, permission: str) -> bool:
        if not self.is_active:
            return False
        if self.is_super_admin:
            return True
        perms: list[Any] = self.permissions or []
        return permission in perms or "*" in perms
