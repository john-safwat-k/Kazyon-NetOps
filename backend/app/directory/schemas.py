"""Pydantic v2 DTOs for Branches, Network Providers (ISPs), and Excel bulk seeding."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


classIspNameLiteral = str


class IspResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    support_email: str
    cc_emails: list[str]
    four_g_hub_ip: Optional[str] = None
    welcome_sla_minutes: int
    followup_sla_minutes: int
    account_manager_email: Optional[str] = None
    escalation_template: Optional[str] = None
    is_active: bool
    store_count: int = 0
    created_at: datetime
    updated_at: datetime


class IspUpdateRequest(BaseModel):
    support_email: Optional[str] = None
    cc_emails: Optional[list[str]] = None
    four_g_hub_ip: Optional[str] = None
    welcome_sla_minutes: Optional[int] = Field(default=None, ge=15, le=1440)
    followup_sla_minutes: Optional[int] = Field(default=None, ge=30, le=2880)
    account_manager_email: Optional[str] = None
    escalation_template: Optional[str] = None
    is_active: Optional[bool] = None


class BranchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    branch_code: str
    name: str
    ip_1: str
    ip_2: str
    region: Optional[str] = None
    regional_it_email: Optional[str] = None
    isp_name: str
    isp_contact_mail: str
    four_g_hub_ip: Optional[str] = None
    ll_circuit_id: Optional[str] = None
    backup_circuit_id: Optional[str] = None
    isp_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class BranchListResponse(BaseModel):
    items: list[BranchResponse]
    total: int
    limit: int
    offset: int
    regions_count: dict[str, int] = Field(default_factory=dict)
    isps_count: dict[str, int] = Field(default_factory=dict)


class BranchCreateRequest(BaseModel):
    branch_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    region: str = Field(default="Cairo", max_length=128)
    ip_1: Optional[str] = None
    ip_2: Optional[str] = None
    regional_it_email: Optional[str] = None
    isp_name: str = Field(default="NOOR", max_length=64)
    isp_contact_mail: Optional[str] = None
    four_g_hub_ip: Optional[str] = None
    ll_circuit_id: Optional[str] = None
    backup_circuit_id: Optional[str] = None
    is_active: bool = True


class BranchUpdateRequest(BaseModel):
    branch_code: Optional[str] = None
    name: Optional[str] = None
    region: Optional[str] = None
    ip_1: Optional[str] = None
    ip_2: Optional[str] = None
    regional_it_email: Optional[str] = None
    isp_name: Optional[str] = None
    isp_contact_mail: Optional[str] = None
    four_g_hub_ip: Optional[str] = None
    ll_circuit_id: Optional[str] = None
    backup_circuit_id: Optional[str] = None
    is_active: Optional[bool] = None


class SeedRowPreview(BaseModel):
    action: str
    branch_code: str
    name: str
    region: str
    ip_1: str
    ip_2: str
    isp_name: str
    isp_contact_mail: str
    regional_it_email: str
    four_g_hub_ip: Optional[str] = None
    ll_circuit_id: Optional[str] = None
    backup_circuit_id: Optional[str] = None


class SeedResultSummary(BaseModel):
    dry_run: bool
    replace_existing: bool = False
    source_filename: str
    total_rows_parsed: int
    unchanged_count: int
    updated_count: int
    created_count: int
    deleted_count: int = 0
    warnings_count: int
    warnings: list[str] = Field(default_factory=list)
    by_isp: dict[str, int] = Field(default_factory=dict)
    by_region: dict[str, int] = Field(default_factory=dict)
    preview_rows: list[SeedRowPreview] = Field(default_factory=list)
