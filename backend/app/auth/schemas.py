"""Pydantic v2 DTOs for Authentication, Users, Roles, and Permission Matrix."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials payload for `/api/v1/auth/login`."""

    username_or_email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class UserResponse(BaseModel):
    """Sanitized User DTO returned from API endpoints (never includes password_hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    display_name: str
    role_name: str
    is_super_admin: bool
    is_active: bool
    permissions: list[str]
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """JWT access token response paired with the authenticated User DTO."""

    access_token: str
    token_type: str = "bearer"
    expires_in_sec: int
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    """Self-service password change request."""

    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=6, max_length=255)


class UserCreateRequest(BaseModel):
    """Super Admin / User Admin payload to create/invite a new user."""

    username: Optional[str] = Field(default=None, max_length=64)
    email: str = Field(..., min_length=3, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=6, max_length=255)
    role_name: str = Field(default="support_engineer", max_length=64)
    is_super_admin: bool = False
    is_active: bool = True
    permissions: Optional[list[str]] = None


class UserUpdateRequest(BaseModel):
    """Partial update payload for user profile, role, and active/suspended state."""

    username: Optional[str] = Field(default=None, min_length=2, max_length=64)
    email: Optional[str] = Field(default=None, min_length=3, max_length=255)
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    role_name: Optional[str] = Field(default=None, min_length=2, max_length=64)
    is_super_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class UserPermissionsUpdateRequest(BaseModel):
    """Update payload for a user's granular permission list and/or role."""

    permissions: list[str] = Field(default_factory=list)
    role_name: Optional[str] = Field(default=None, max_length=64)
    is_super_admin: Optional[bool] = None


class AdminResetPasswordRequest(BaseModel):
    """Admin-initiated password reset payload."""

    new_password: str = Field(..., min_length=6, max_length=255)


class UserListResponse(BaseModel):
    """Paginated list of users with summary counters."""

    items: list[UserResponse]
    total: int
    active_count: int
    suspended_count: int
    limit: int
    offset: int


class RoleResponse(BaseModel):
    """RBAC Role DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display_name: str
    description: Optional[str] = None
    is_system: bool
    permissions: list[str]
    user_count: int = 0
    created_at: datetime
    updated_at: datetime


class RoleCreateRequest(BaseModel):
    """Create a new custom RBAC role."""

    slug: Optional[str] = Field(default=None, max_length=64)
    display_name: str = Field(..., min_length=2, max_length=128)
    description: Optional[str] = Field(default=None, max_length=500)
    base_role_slug: Optional[str] = Field(default=None, max_length=64)
    permissions: Optional[list[str]] = None


class RoleUpdateRequest(BaseModel):
    """Update a role's display name, description, or permission set."""

    display_name: Optional[str] = Field(default=None, min_length=2, max_length=128)
    description: Optional[str] = Field(default=None, max_length=500)
    permissions: Optional[list[str]] = None
    sync_assigned_users: bool = True


class PermissionResourceMeta(BaseModel):
    """Metadata for one row of the interactive RBAC Permission Matrix."""

    resource: str
    description: str
    actions: list[str]
    not_applicable_actions: list[str] = Field(default_factory=list)
    domain_permissions: list[str] = Field(default_factory=list)


class PermissionCatalogResponse(BaseModel):
    """Full catalog of permissions, matrix rows, and standard actions."""

    all_permissions: list[str]
    matrix_actions: list[str]
    resources: list[PermissionResourceMeta]


class AuditLogResponse(BaseModel):
    """Audit trail entry DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: Optional[int] = None
    actor_username: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    summary: str
    details_json: dict[str, Any]
    ip_address: Optional[str] = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """Paginated list of audit trail entries."""

    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int
