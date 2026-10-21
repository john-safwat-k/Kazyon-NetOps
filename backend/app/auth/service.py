"""Authentication & Permission-Based RBAC service."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.models import ALL_PERMISSIONS, PERMISSION_EQUIVALENTS, Role, User
from app.auth.schemas import (
    PermissionCatalogResponse,
    PermissionResourceMeta,
    RoleCreateRequest,
    RoleResponse,
    RoleUpdateRequest,
    UserCreateRequest,
    UserListResponse,
    UserPermissionsUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.common.audit import AuditLog, record_audit_event
from app.common.cache import cache_delete, cache_get_json, cache_set_json
from app.common.config import get_settings
from app.common.exceptions import (
    AuthenticationError,
    DuplicateResourceError,
    EntityNotFoundError,
    ValidationError,
)

logger = logging.getLogger("it_net.auth")

MATRIX_ACTIONS: list[str] = ["read", "create", "update", "delete", "execute"]

MATRIX_RESOURCES: list[dict[str, Any]] = [
    {
        "resource": "tickets",
        "description": "Board, list, detail, manual tickets",
        "not_applicable_actions": [],
        "domain_permissions": [
            "tickets:view",
            "tickets:edit_status",
            "tickets:assign",
            "tickets:pause_ai",
            "tickets:delete",
        ],
    },
    {
        "resource": "diagnostics",
        "description": "Ping and traceroute runs",
        "not_applicable_actions": ["delete"],
        "domain_permissions": ["diagnostics:view_logs", "diagnostics:trigger_manual"],
    },
    {
        "resource": "emails",
        "description": "Mailbox log, replies, .eml upload",
        "not_applicable_actions": [],
        "domain_permissions": [
            "emails:view",
            "emails:send_manual_reply",
            "emails:force_isp_followup",
        ],
    },
    {
        "resource": "replication",
        "description": "Replication reports",
        "not_applicable_actions": ["update"],
        "domain_permissions": [
            "replication:view",
            "replication:upload",
            "replication:trigger_notify",
        ],
    },
    {
        "resource": "branches",
        "description": "1,150-branch directory",
        "not_applicable_actions": ["execute"],
        "domain_permissions": [
            "branches:view",
            "branches:create",
            "branches:edit",
            "branches:import_sheet",
        ],
    },
    {
        "resource": "isps",
        "description": "ISP emails, hubs, templates",
        "not_applicable_actions": ["execute"],
        "domain_permissions": ["isps:manage"],
    },
    {
        "resource": "users",
        "description": "Users and roles",
        "not_applicable_actions": ["execute"],
        "domain_permissions": [
            "users:view",
            "users:create",
            "users:edit_permissions",
            "roles:manage",
        ],
    },
    {
        "resource": "settings",
        "description": "Mailbox, vLLM, SLA, kill-switch",
        "not_applicable_actions": [],
        "domain_permissions": [
            "settings:manage_mailbox",
            "settings:manage_agent_prompts",
            "settings:manage_sla_timers",
        ],
    },
]

ENGINEER_DEFAULT_PERMISSIONS: list[str] = [
    # Matrix permissions
    "tickets:read",
    "tickets:create",
    "tickets:update",
    "tickets:execute",
    "diagnostics:read",
    "diagnostics:create",
    "diagnostics:update",
    "diagnostics:execute",
    "emails:read",
    "emails:create",
    "emails:update",
    "emails:execute",
    "replication:read",
    "replication:create",
    "replication:execute",
    "branches:read",
    "branches:update",
    "isps:read",
    "isps:create",
    # Domain-specific permissions
    "tickets:view",
    "tickets:edit_status",
    "tickets:assign",
    "tickets:pause_ai",
    "diagnostics:view_logs",
    "diagnostics:trigger_manual",
    "emails:view",
    "emails:send_manual_reply",
    "emails:force_isp_followup",
    "replication:view",
    "replication:upload",
    "replication:trigger_notify",
    "branches:view",
    "branches:edit",
]

VIEWER_DEFAULT_PERMISSIONS: list[str] = [
    "tickets:read",
    "tickets:view",
    "diagnostics:read",
    "diagnostics:view_logs",
    "emails:read",
    "emails:view",
    "replication:read",
    "replication:view",
    "branches:read",
    "branches:view",
    "isps:read",
]

SYSTEM_ROLES: list[dict[str, Any]] = [
    {
        "slug": "super_admin",
        "display_name": "Super Admin",
        "description": "Full platform access across all resources, users, roles, and AI/SLA settings.",
        "is_system": True,
        "permissions": list(ALL_PERMISSIONS),
    },
    {
        "slug": "support_engineer",
        "display_name": "HQ Network Engineer",
        "description": "Operates the Kanban board, triggers diagnostics, replies to emails, and manages branch incidents.",
        "is_system": True,
        "permissions": list(ENGINEER_DEFAULT_PERMISSIONS),
    },
    {
        "slug": "viewer",
        "display_name": "Viewer / Auditor",
        "description": "Read-only access to SLA dashboards, tickets, diagnostics, replication reports, and branch directory.",
        "is_system": True,
        "permissions": list(VIEWER_DEFAULT_PERMISSIONS),
    },
]


def _user_cache_key(user_id: int) -> str:
    return f"it_net:auth:user:{user_id}"


def invalidate_user_cache(user_id: int) -> None:
    """Invalidate the cached user identity/permissions entry in Redis."""
    cache_delete(_user_cache_key(user_id))


def expand_permissions(permissions: list[str]) -> list[str]:
    """Expand a permission list with its bidirectional domain/matrix equivalents."""
    expanded: set[str] = set()
    for perm in permissions:
        cleaned = perm.strip()
        if not cleaned:
            continue
        expanded.add(cleaned)
        for eq in PERMISSION_EQUIVALENTS.get(cleaned, set()):
            expanded.add(eq)
    return sorted(expanded)


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user: User) -> str:
    """Issue a signed JWT containing user identity and role metadata."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.auth_token_expire_hours)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "role_name": user.role_name,
        "is_super_admin": user.is_super_admin,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode a signed JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if not isinstance(payload, dict) or "sub" not in payload:
            raise AuthenticationError("Malformed authentication token")
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Authentication token has expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid authentication token") from exc


def ensure_default_roles(db: Session) -> list[Role]:
    """Seed the built-in system roles (`super_admin`, `support_engineer`, `viewer`) if missing."""
    existing_roles = {r.slug: r for r in db.execute(select(Role)).scalars().all()}
    created_any = False
    for role_def in SYSTEM_ROLES:
        slug = role_def["slug"]
        if slug not in existing_roles:
            role = Role(
                slug=slug,
                display_name=role_def["display_name"],
                description=role_def["description"],
                is_system=role_def["is_system"],
                permissions=expand_permissions(role_def["permissions"]),
            )
            db.add(role)
            existing_roles[slug] = role
            created_any = True
    if created_any:
        db.commit()
    return list(existing_roles.values())


def ensure_initial_admin(db: Session) -> User:
    """Bootstrap default roles and the initial Super Admin account if none exists."""
    ensure_default_roles(db)
    settings = get_settings()
    stmt = select(User).where(User.is_super_admin.is_(True)).limit(1)
    existing_admin = db.execute(stmt).scalar_one_or_none()
    if existing_admin is not None:
        return existing_admin

    logger.info("Bootstrapping initial Super Admin account ('%s')...", settings.admin_username)
    admin = User(
        username=settings.admin_username,
        email=settings.admin_email or "admin@kazyon.com",
        display_name=settings.admin_display_name,
        password_hash=hash_password(settings.admin_password),
        role_name="super_admin",
        is_super_admin=True,
        is_active=True,
        permissions=list(ALL_PERMISSIONS),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    record_audit_event(
        db,
        actor_user_id=admin.id,
        actor_username="system",
        action="auth.bootstrap_super_admin",
        resource_type="user",
        resource_id=str(admin.id),
        summary=f"Bootstrapped initial Super Admin '{admin.username}' ({admin.email})",
        commit=True,
    )
    return admin


def authenticate_user(
    db: Session,
    username_or_email: str,
    password: str,
    *,
    ip_address: Optional[str] = None,
) -> User:
    """Authenticate a user by username or email and password."""
    identifier = username_or_email.strip()
    stmt = (
        select(User)
        .where(
            or_(
                func.lower(User.username) == identifier.lower(),
                func.lower(User.email) == identifier.lower(),
            )
        )
        .limit(1)
    )
    user = db.execute(stmt).scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        logger.warning("Failed sign-in attempt for identifier='%s'", identifier)
        raise AuthenticationError("Invalid username/email or password")

    if not user.is_active:
        logger.warning("Blocked sign-in attempt for suspended user '%s'", user.username)
        raise AuthenticationError("Your account has been suspended. Contact your Super Admin.")

    user.last_login_at = datetime.now(timezone.utc)
    record_audit_event(
        db,
        actor_user_id=user.id,
        actor_username=user.username,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        summary=f"User '{user.username}' signed in",
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    invalidate_user_cache(user.id)
    return user


def get_user_by_id(db: Session, user_id: int) -> User:
    """Fetch a user by primary key or raise EntityNotFoundError."""
    user = db.get(User, user_id)
    if user is None:
        raise EntityNotFoundError("User", user_id)
    return user


def get_cached_or_db_user(db: Session, user_id: int) -> User:
    """Resolve active user for request authentication using Redis cache-aside."""
    cached = cache_get_json(_user_cache_key(user_id))
    user = db.get(User, user_id)
    if user is None:
        raise AuthenticationError("Authenticated user no longer exists")
    if cached is None:
        cache_set_json(
            _user_cache_key(user_id),
            {
                "id": user.id,
                "username": user.username,
                "is_active": user.is_active,
                "is_super_admin": user.is_super_admin,
                "permissions": user.permissions,
            },
        )
    return user


def list_users(
    db: Session,
    *,
    search: Optional[str] = None,
    role_name: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> UserListResponse:
    """List users with optional search, role filter, status filter, and pagination."""
    stmt = select(User)
    if search:
        q = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.username).like(q),
                func.lower(User.email).like(q),
                func.lower(User.display_name).like(q),
            )
        )
    if role_name:
        stmt = stmt.where(User.role_name == role_name)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    active_count = db.execute(
        select(func.count()).select_from(User).where(User.is_active.is_(True))
    ).scalar_one()
    suspended_count = db.execute(
        select(func.count()).select_from(User).where(User.is_active.is_(False))
    ).scalar_one()

    rows = (
        db.execute(
            stmt.order_by(User.is_super_admin.desc(), User.id.asc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in rows],
        total=int(total),
        active_count=int(active_count),
        suspended_count=int(suspended_count),
        limit=limit,
        offset=offset,
    )


def _normalize_role_slug(role_input: str) -> str:
    slug = role_input.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "hq_network_engineer": "support_engineer",
        "network_engineer": "support_engineer",
        "engineer": "support_engineer",
        "viewer_/_it_manager": "viewer",
        "viewer_/_auditor": "viewer",
        "admin": "super_admin",
    }
    return aliases.get(slug, re.sub(r"[^a-z0-9_]", "", slug) or "support_engineer")


def _resolve_role_permissions(db: Session, role_slug: str, is_super_admin: bool) -> list[str]:
    if is_super_admin or role_slug == "super_admin":
        return list(ALL_PERMISSIONS)
    role = db.execute(select(Role).where(Role.slug == role_slug).limit(1)).scalar_one_or_none()
    if role is not None:
        return expand_permissions(list(role.permissions or []))
    if role_slug == "viewer":
        return expand_permissions(VIEWER_DEFAULT_PERMISSIONS)
    return expand_permissions(ENGINEER_DEFAULT_PERMISSIONS)


def create_user(
    db: Session,
    payload: UserCreateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> User:
    """Create a new user account with role defaults or custom permissions."""
    ensure_default_roles(db)
    email = payload.email.strip().lower()
    raw_username = (payload.username or email.split("@", 1)[0]).strip().lower()
    username = re.sub(r"[^a-z0-9._-]", ".", raw_username).strip(".") or "user"

    existing_email = db.execute(
        select(User).where(func.lower(User.email) == email).limit(1)
    ).scalar_one_or_none()
    if existing_email is not None:
        raise DuplicateResourceError(f"A user with email '{email}' already exists")

    existing_username = db.execute(
        select(User).where(func.lower(User.username) == username).limit(1)
    ).scalar_one_or_none()
    if existing_username is not None:
        if payload.username:
            raise DuplicateResourceError(f"A user with username '{username}' already exists")
        username = f"{username}.{int(datetime.now(timezone.utc).timestamp()) % 10000}"

    role_slug = _normalize_role_slug(payload.role_name)
    is_super = payload.is_super_admin or role_slug == "super_admin"
    if payload.permissions is not None:
        perms = list(ALL_PERMISSIONS) if is_super else expand_permissions(list(payload.permissions))
    else:
        perms = _resolve_role_permissions(db, role_slug, is_super)

    user = User(
        username=username,
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role_name="super_admin" if is_super else role_slug,
        is_super_admin=is_super,
        is_active=payload.is_active,
        permissions=perms,
    )
    db.add(user)
    db.flush()

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="user.created",
        resource_type="user",
        resource_id=str(user.id),
        summary=f"Created user '{user.username}' ({user.email}) with role '{user.role_name}'",
        details={
            "username": user.username,
            "email": user.email,
            "role_name": user.role_name,
            "is_super_admin": user.is_super_admin,
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    return user


def update_user(
    db: Session,
    user_id: int,
    payload: UserUpdateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> User:
    """Update a user's profile, role, or active/suspended status."""
    user = get_user_by_id(db, user_id)
    changes: dict[str, Any] = {}

    if payload.username is not None and payload.username.strip().lower() != user.username.lower():
        new_username = payload.username.strip().lower()
        dup = db.execute(
            select(User)
            .where(func.lower(User.username) == new_username, User.id != user.id)
            .limit(1)
        ).scalar_one_or_none()
        if dup is not None:
            raise DuplicateResourceError(f"Username '{new_username}' is already taken")
        changes["username"] = {"from": user.username, "to": new_username}
        user.username = new_username

    if payload.email is not None and payload.email.strip().lower() != user.email.lower():
        new_email = payload.email.strip().lower()
        dup = db.execute(
            select(User).where(func.lower(User.email) == new_email, User.id != user.id).limit(1)
        ).scalar_one_or_none()
        if dup is not None:
            raise DuplicateResourceError(f"Email '{new_email}' is already registered")
        changes["email"] = {"from": user.email, "to": new_email}
        user.email = new_email

    if payload.display_name is not None and payload.display_name.strip() != user.display_name:
        changes["display_name"] = {"from": user.display_name, "to": payload.display_name.strip()}
        user.display_name = payload.display_name.strip()

    if payload.is_active is not None and payload.is_active != user.is_active:
        if not payload.is_active and user.id == actor.id:
            raise ValidationError("You cannot suspend your own currently signed-in account")
        if not payload.is_active and user.is_super_admin:
            active_admins = db.execute(
                select(func.count())
                .select_from(User)
                .where(User.is_super_admin.is_(True), User.is_active.is_(True), User.id != user.id)
            ).scalar_one()
            if active_admins == 0:
                raise ValidationError("Cannot suspend the last active Super Admin account")
        changes["is_active"] = {"from": user.is_active, "to": payload.is_active}
        user.is_active = payload.is_active

    if payload.role_name is not None or payload.is_super_admin is not None:
        new_role = (
            _normalize_role_slug(payload.role_name)
            if payload.role_name is not None
            else user.role_name
        )
        new_super = (
            payload.is_super_admin
            if payload.is_super_admin is not None
            else (new_role == "super_admin")
        )
        if user.is_super_admin and not new_super:
            other_admins = db.execute(
                select(func.count())
                .select_from(User)
                .where(User.is_super_admin.is_(True), User.is_active.is_(True), User.id != user.id)
            ).scalar_one()
            if other_admins == 0:
                raise ValidationError("Cannot demote the last active Super Admin account")
        if new_role != user.role_name or new_super != user.is_super_admin:
            changes["role_name"] = {"from": user.role_name, "to": new_role}
            changes["is_super_admin"] = {"from": user.is_super_admin, "to": new_super}
            user.role_name = "super_admin" if new_super else new_role
            user.is_super_admin = new_super
            user.permissions = _resolve_role_permissions(db, user.role_name, new_super)

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="user.updated",
        resource_type="user",
        resource_id=str(user.id),
        summary=f"Updated user '{user.username}'",
        details=changes,
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    invalidate_user_cache(user.id)
    return user


def update_user_permissions(
    db: Session,
    user_id: int,
    payload: UserPermissionsUpdateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> User:
    """Update a user's granular permission list."""
    user = get_user_by_id(db, user_id)
    old_perms = list(user.permissions or [])

    if payload.role_name is not None:
        user.role_name = _normalize_role_slug(payload.role_name)
    if payload.is_super_admin is not None:
        if user.is_super_admin and not payload.is_super_admin:
            other_admins = db.execute(
                select(func.count())
                .select_from(User)
                .where(User.is_super_admin.is_(True), User.is_active.is_(True), User.id != user.id)
            ).scalar_one()
            if other_admins == 0:
                raise ValidationError("Cannot demote the last active Super Admin account")
        user.is_super_admin = payload.is_super_admin

    user.permissions = (
        list(ALL_PERMISSIONS)
        if user.is_super_admin
        else expand_permissions(list(payload.permissions))
    )

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="user.permissions_updated",
        resource_type="user",
        resource_id=str(user.id),
        summary=f"Updated granular permissions for user '{user.username}' ({len(user.permissions)} permissions)",
        details={"previous_count": len(old_perms), "new_count": len(user.permissions)},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    invalidate_user_cache(user.id)
    return user


def admin_reset_user_password(
    db: Session,
    user_id: int,
    new_password: str,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> User:
    """Reset a user's password as an administrator."""
    user = get_user_by_id(db, user_id)
    user.password_hash = hash_password(new_password)
    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="user.password_reset",
        resource_type="user",
        resource_id=str(user.id),
        summary=f"Admin '{actor.username}' reset password for user '{user.username}'",
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    invalidate_user_cache(user.id)
    return user


def change_own_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
    *,
    ip_address: Optional[str] = None,
) -> User:
    """Allow an authenticated user to change their own password."""
    if not verify_password(current_password, user.password_hash):
        raise ValidationError("Current password is incorrect")
    user.password_hash = hash_password(new_password)
    record_audit_event(
        db,
        actor_user_id=user.id,
        actor_username=user.username,
        action="auth.password_changed",
        resource_type="user",
        resource_id=str(user.id),
        summary=f"User '{user.username}' changed their password",
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(user)
    invalidate_user_cache(user.id)
    return user


def list_roles(db: Session) -> list[RoleResponse]:
    """Return all system and custom RBAC roles with assigned user counts."""
    ensure_default_roles(db)
    roles = db.execute(select(Role).order_by(Role.is_system.desc(), Role.id.asc())).scalars().all()
    counts = dict(
        db.execute(select(User.role_name, func.count(User.id)).group_by(User.role_name)).all()
    )
    results: list[RoleResponse] = []
    for role in roles:
        dto = RoleResponse.model_validate(role)
        dto.user_count = int(counts.get(role.slug, 0))
        results.append(dto)
    return results


def create_role(
    db: Session,
    payload: RoleCreateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> RoleResponse:
    """Create a custom RBAC role optionally cloned from an existing template."""
    ensure_default_roles(db)
    raw_slug = payload.slug or payload.display_name
    slug = re.sub(r"[^a-z0-9_]", "", raw_slug.strip().lower().replace(" ", "_").replace("-", "_"))
    if not slug:
        raise ValidationError("Role name must contain alphanumeric characters")

    existing = db.execute(select(Role).where(Role.slug == slug).limit(1)).scalar_one_or_none()
    if existing is not None:
        raise DuplicateResourceError(f"Role '{slug}' already exists")

    if payload.permissions is not None:
        perms = expand_permissions(list(payload.permissions))
    elif payload.base_role_slug:
        base_slug = _normalize_role_slug(payload.base_role_slug)
        if base_slug in {"empty", "none"}:
            perms = []
        else:
            perms = _resolve_role_permissions(db, base_slug, False)
    else:
        perms = expand_permissions(VIEWER_DEFAULT_PERMISSIONS)

    role = Role(
        slug=slug,
        display_name=payload.display_name.strip(),
        description=(payload.description or f"Custom role: {payload.display_name.strip()}"),
        is_system=False,
        permissions=perms,
    )
    db.add(role)
    db.flush()

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="role.created",
        resource_type="role",
        resource_id=role.slug,
        summary=f"Created role '{role.display_name}' ({role.slug}) with {len(perms)} permissions",
        details={"slug": role.slug, "permissions_count": len(perms)},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(role)
    return RoleResponse.model_validate(role)


def update_role(
    db: Session,
    role_slug: str,
    payload: RoleUpdateRequest,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> RoleResponse:
    """Update a role's permissions and optionally sync users assigned to that role."""
    ensure_default_roles(db)
    normalized_slug = _normalize_role_slug(role_slug)
    role = db.execute(
        select(Role).where(Role.slug == normalized_slug).limit(1)
    ).scalar_one_or_none()
    if role is None:
        raise EntityNotFoundError("Role", role_slug)
    if role.slug == "super_admin" and payload.permissions is not None:
        raise ValidationError("Super Admin permissions are locked and cannot be restricted")

    if payload.display_name is not None:
        role.display_name = payload.display_name.strip()
    if payload.description is not None:
        role.description = payload.description.strip()
    if payload.permissions is not None:
        role.permissions = expand_permissions(list(payload.permissions))
        if payload.sync_assigned_users:
            assigned_users = (
                db.execute(
                    select(User).where(
                        User.role_name == role.slug,
                        User.is_super_admin.is_(False),
                    )
                )
                .scalars()
                .all()
            )
            for u in assigned_users:
                u.permissions = list(role.permissions)
                invalidate_user_cache(u.id)

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="role.updated",
        resource_type="role",
        resource_id=role.slug,
        summary=f"Updated role '{role.display_name}' ({role.slug}) permissions ({len(role.permissions)} active)",
        details={"slug": role.slug, "permissions": role.permissions},
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(role)

    user_count = db.execute(
        select(func.count()).select_from(User).where(User.role_name == role.slug)
    ).scalar_one()
    dto = RoleResponse.model_validate(role)
    dto.user_count = int(user_count)
    return dto


def delete_role(
    db: Session,
    role_slug: str,
    *,
    actor: User,
    ip_address: Optional[str] = None,
) -> None:
    """Delete a custom non-system role."""
    role = db.execute(select(Role).where(Role.slug == role_slug).limit(1)).scalar_one_or_none()
    if role is None:
        raise EntityNotFoundError("Role", role_slug)
    if role.is_system:
        raise ValidationError(f"System role '{role.display_name}' cannot be deleted")

    assigned_count = db.execute(
        select(func.count()).select_from(User).where(User.role_name == role.slug)
    ).scalar_one()
    if assigned_count > 0:
        raise ValidationError(
            f"Cannot delete role '{role.display_name}' while {assigned_count} user(s) are assigned to it"
        )

    record_audit_event(
        db,
        actor_user_id=actor.id,
        actor_username=actor.username,
        action="role.deleted",
        resource_type="role",
        resource_id=role.slug,
        summary=f"Deleted custom role '{role.display_name}' ({role.slug})",
        ip_address=ip_address,
    )
    db.delete(role)
    db.commit()


def get_permission_catalog() -> PermissionCatalogResponse:
    """Return the full catalog of granular permissions and matrix metadata."""
    resources = [
        PermissionResourceMeta(
            resource=item["resource"],
            description=item["description"],
            actions=list(MATRIX_ACTIONS),
            not_applicable_actions=list(item["not_applicable_actions"]),
            domain_permissions=list(item["domain_permissions"]),
        )
        for item in MATRIX_RESOURCES
    ]
    return PermissionCatalogResponse(
        all_permissions=list(ALL_PERMISSIONS),
        matrix_actions=list(MATRIX_ACTIONS),
        resources=resources,
    )


def list_audit_logs(
    db: Session,
    *,
    resource_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """Return paginated audit trail logs."""
    stmt = select(AuditLog)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = (
        db.execute(stmt.order_by(AuditLog.id.desc()).limit(limit).offset(offset)).scalars().all()
    )
    return list(items), int(total)
