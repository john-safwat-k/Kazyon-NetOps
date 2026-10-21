"""SQLAlchemy models for Users, Roles, and Granular Permissions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, JSONVariant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Granular domain permissions + standardized resource:action matrix permissions
ALL_PERMISSIONS: list[str] = [
    # Tickets
    "tickets:view",
    "tickets:edit_status",
    "tickets:assign",
    "tickets:pause_ai",
    "tickets:delete",
    "tickets:read",
    "tickets:create",
    "tickets:update",
    "tickets:execute",
    # Diagnostics
    "diagnostics:view_logs",
    "diagnostics:trigger_manual",
    "diagnostics:read",
    "diagnostics:create",
    "diagnostics:update",
    "diagnostics:execute",
    # Emails
    "emails:view",
    "emails:send_manual_reply",
    "emails:force_isp_followup",
    "emails:read",
    "emails:create",
    "emails:update",
    "emails:delete",
    "emails:execute",
    # Replication
    "replication:view",
    "replication:upload",
    "replication:trigger_notify",
    "replication:read",
    "replication:create",
    "replication:delete",
    "replication:execute",
    # Branches & ISPs
    "branches:view",
    "branches:create",
    "branches:edit",
    "branches:import_sheet",
    "branches:read",
    "branches:update",
    "branches:delete",
    "isps:manage",
    "isps:read",
    "isps:create",
    "isps:update",
    "isps:delete",
    # Users & Roles
    "users:view",
    "users:create",
    "users:edit_permissions",
    "users:read",
    "users:update",
    "users:delete",
    "roles:manage",
    # Settings
    "settings:manage_mailbox",
    "settings:manage_agent_prompts",
    "settings:manage_sla_timers",
    "settings:read",
    "settings:create",
    "settings:update",
    "settings:delete",
    "settings:execute",
]


# Bidirectional alias map so checking either domain-specific or matrix permission succeeds
PERMISSION_EQUIVALENTS: dict[str, set[str]] = {
    "tickets:view": {"tickets:read"},
    "tickets:read": {"tickets:view"},
    "tickets:edit_status": {"tickets:update", "tickets:create"},
    "tickets:assign": {"tickets:update"},
    "tickets:pause_ai": {"tickets:execute", "tickets:update"},
    "tickets:update": {"tickets:edit_status", "tickets:assign"},
    "tickets:execute": {"tickets:pause_ai"},
    "diagnostics:view_logs": {"diagnostics:read"},
    "diagnostics:read": {"diagnostics:view_logs"},
    "diagnostics:trigger_manual": {"diagnostics:execute", "diagnostics:create"},
    "diagnostics:execute": {"diagnostics:trigger_manual"},
    "emails:view": {"emails:read"},
    "emails:read": {"emails:view"},
    "emails:send_manual_reply": {"emails:create", "emails:execute"},
    "emails:force_isp_followup": {"emails:execute"},
    "emails:execute": {"emails:send_manual_reply", "emails:force_isp_followup"},
    "replication:view": {"replication:read"},
    "replication:read": {"replication:view"},
    "replication:upload": {"replication:create"},
    "replication:create": {"replication:upload"},
    "replication:trigger_notify": {"replication:execute"},
    "replication:execute": {"replication:trigger_notify"},
    "branches:view": {"branches:read"},
    "branches:read": {"branches:view"},
    "branches:edit": {"branches:update"},
    "branches:update": {"branches:edit"},
    "branches:import_sheet": {"branches:create"},
    "branches:create": {"branches:import_sheet"},
    "isps:manage": {"isps:read", "isps:create", "isps:update", "isps:delete"},
    "isps:read": {"isps:manage"},
    "isps:update": {"isps:manage"},
    "users:view": {"users:read"},
    "users:read": {"users:view"},
    "users:edit_permissions": {"users:update", "roles:manage"},
    "users:update": {"users:edit_permissions"},
    "roles:manage": {"users:edit_permissions", "users:update", "users:create"},
    "settings:manage_mailbox": {"settings:update", "settings:execute"},
    "settings:manage_agent_prompts": {"settings:update"},
    "settings:manage_sla_timers": {"settings:update"},
    "settings:update": {
        "settings:manage_mailbox",
        "settings:manage_agent_prompts",
        "settings:manage_sla_timers",
    },
}


class Role(Base):
    """Reusable RBAC role template grouping a set of resource:action permissions."""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSONVariant, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


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
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
        perms_set: set[Any] = set(self.permissions or [])
        if "*" in perms_set or permission in perms_set:
            return True
        resource = permission.split(":", 1)[0] if ":" in permission else ""
        if resource and f"{resource}:*" in perms_set:
            return True
        equivalents = PERMISSION_EQUIVALENTS.get(permission, set())
        return bool(perms_set.intersection(equivalents))
