"""SQLAlchemy models for Network Providers (ISPs) and Company Branches."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.common.database import Base, JSONVariant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NetworkProvider(Base):
    """External Network / Internet Service Provider (ISP) record (`NOOR`, `ORANGE`, `WE`)."""

    __tablename__ = "network_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    support_email: Mapped[str] = mapped_column(String(255), nullable=False)
    cc_emails: Mapped[list[str]] = mapped_column(JSONVariant, default=list, nullable=False)
    four_g_hub_ip: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    welcome_sla_minutes: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    followup_sla_minutes: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    followup_interval_minutes: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    account_manager_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    escalation_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class Branch(Base):
    """Company branch record seeded via Excel (`Copy of All store ISP (2).xlsx`) and managed in UI."""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    branch_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_1: Mapped[str] = mapped_column(String(128), default="10.0.0.1", nullable=False)
    ip_2: Mapped[str] = mapped_column(String(128), default="10.0.0.2", nullable=False)
    target_ip: Mapped[str] = mapped_column(String(128), default="10.0.0.1", nullable=False)
    circuit_id: Mapped[str] = mapped_column(String(128), index=True, default="", nullable=False)
    connection_type: Mapped[str] = mapped_column(String(64), default="FIBER", nullable=False)
    isp_name: Mapped[str] = mapped_column(String(64), default="NOOR", index=True, nullable=False)
    isp_contact_mail: Mapped[str] = mapped_column(
        String(255), default="noc@noor.net", nullable=False
    )
    regional_it_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    four_g_hub_ip: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ll_circuit_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    backup_circuit_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    contact_emails: Mapped[list[str]] = mapped_column(JSONVariant, default=list, nullable=False)
    isp_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("network_providers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    extra_metadata: Mapped[dict[str, str]] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
