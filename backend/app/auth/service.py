"""Authentication & Permission-Based RBAC service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import ALL_PERMISSIONS, User
from app.common.config import get_settings

logger = logging.getLogger("it_net.auth")


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
        "is_super_admin": user.is_super_admin,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def ensure_initial_admin(db: Session) -> User:
    """Bootstrap the initial Super Admin account if no Super Admin exists in the database."""
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
    return admin
