"""REST API routers for Authentication (`/api/v1/auth`), Users (`/api/v1/users`), and Roles (`/api/v1/roles`)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_permission
from app.auth.models import User
from app.auth.schemas import (
    AdminResetPasswordRequest,
    AuditLogListResponse,
    AuditLogResponse,
    ChangePasswordRequest,
    LoginRequest,
    PermissionCatalogResponse,
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
    TokenResponse,
    UserCreateRequest,
    UserListResponse,
    UserPermissionsUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.auth.service import (
    admin_reset_user_password,
    authenticate_user,
    change_own_password,
    create_access_token,
    create_role,
    create_user,
    delete_role,
    get_permission_catalog,
    get_user_by_id,
    list_audit_logs,
    list_roles,
    list_users,
    update_role,
    update_user,
    update_user_permissions,
)
from app.common.config import get_settings
from app.common.database import get_db

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
users_router = APIRouter(prefix="/api/v1/users", tags=["Users & RBAC"])
roles_router = APIRouter(prefix="/api/v1/roles", tags=["Roles & Permission Matrix"])


def _client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# ==============================================================================
# /api/v1/auth/*
# ==============================================================================


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username or email and password to receive a signed JWT."""
    settings = get_settings()
    user = authenticate_user(
        db,
        payload.username_or_email,
        payload.password,
        ip_address=_client_ip(request),
    )
    token = create_access_token(user)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in_sec=settings.auth_token_expire_hours * 3600,
        user=UserResponse.model_validate(user),
    )


@auth_router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user's profile and active permission set."""
    return UserResponse.model_validate(current_user)


@auth_router.post("/change-password", response_model=UserResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Change the currently authenticated user's password."""
    updated = change_own_password(
        db,
        current_user,
        payload.current_password,
        payload.new_password,
        ip_address=_client_ip(request),
    )
    return UserResponse.model_validate(updated)


@auth_router.get("/permissions", response_model=PermissionCatalogResponse)
async def list_permissions(
    _current_user: User = Depends(get_current_user),
) -> PermissionCatalogResponse:
    """Return the full catalog of granular permissions and RBAC matrix metadata."""
    return get_permission_catalog()


@auth_router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    resource_type: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_permission("users:view")),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """List security and RBAC audit trail records (requires `users:view`)."""
    items, total = list_audit_logs(
        db,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ==============================================================================
# /api/v1/users/*
# ==============================================================================


@users_router.get("", response_model=UserListResponse)
async def get_users(
    search: Optional[str] = Query(default=None),
    role_name: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _current_user: User = Depends(require_permission("users:view")),
    db: Session = Depends(get_db),
) -> UserListResponse:
    """List users with pagination and filtering (requires `users:view`)."""
    return list_users(
        db,
        search=search,
        role_name=role_name,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:create")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Create / invite a new user (requires `users:create`)."""
    user = create_user(
        db,
        payload,
        actor=current_user,
        ip_address=_client_ip(request),
    )
    return UserResponse.model_validate(user)


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user_endpoint(
    user_id: int,
    _current_user: User = Depends(require_permission("users:view")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Get a single user by ID (requires `users:view`)."""
    user = get_user_by_id(db, user_id)
    return UserResponse.model_validate(user)


@users_router.patch("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:edit_permissions")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Update a user's profile, role, or active/suspended status (requires `users:edit_permissions`)."""
    user = update_user(
        db,
        user_id,
        payload,
        actor=current_user,
        ip_address=_client_ip(request),
    )
    return UserResponse.model_validate(user)


@users_router.put("/{user_id}/permissions", response_model=UserResponse)
async def update_user_permissions_endpoint(
    user_id: int,
    payload: UserPermissionsUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:edit_permissions")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Replace a user's granular permission list (requires `users:edit_permissions`)."""
    user = update_user_permissions(
        db,
        user_id,
        payload,
        actor=current_user,
        ip_address=_client_ip(request),
    )
    return UserResponse.model_validate(user)


@users_router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_user_password_endpoint(
    user_id: int,
    payload: AdminResetPasswordRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:edit_permissions")),
    db: Session = Depends(get_db),
) -> UserResponse:
    """Reset a user's password as an administrator (requires `users:edit_permissions`)."""
    user = admin_reset_user_password(
        db,
        user_id,
        payload.new_password,
        actor=current_user,
        ip_address=_client_ip(request),
    )
    return UserResponse.model_validate(user)


# ==============================================================================
# /api/v1/roles/*
# ==============================================================================


@roles_router.get("", response_model=list[RoleResponse])
async def get_roles_endpoint(
    _current_user: User = Depends(require_permission("users:view")),
    db: Session = Depends(get_db),
) -> list[RoleResponse]:
    """List all system and custom RBAC roles (requires `users:view`)."""
    return list_roles(db)


@roles_router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role_endpoint(
    payload: RoleCreateRequest,
    request: Request,
    current_user: User = Depends(require_permission("roles:manage")),
    db: Session = Depends(get_db),
) -> RoleResponse:
    """Create a new custom RBAC role (requires `roles:manage`)."""
    return create_role(
        db,
        payload,
        actor=current_user,
        ip_address=_client_ip(request),
    )


@roles_router.put("/{role_slug}", response_model=RoleResponse)
async def update_role_endpoint(
    role_slug: str,
    payload: RoleUpdateRequest,
    request: Request,
    current_user: User = Depends(require_permission("roles:manage")),
    db: Session = Depends(get_db),
) -> RoleResponse:
    """Update a role's permission matrix and sync assigned users (requires `roles:manage`)."""
    return update_role(
        db,
        role_slug,
        payload,
        actor=current_user,
        ip_address=_client_ip(request),
    )


@roles_router.delete("/{role_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role_endpoint(
    role_slug: str,
    request: Request,
    current_user: User = Depends(require_permission("roles:manage")),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a custom RBAC role (requires `roles:manage`)."""
    delete_role(
        db,
        role_slug,
        actor=current_user,
        ip_address=_client_ip(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
