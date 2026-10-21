"""FastAPI dependencies for JWT authentication and granular RBAC permission enforcement."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.service import decode_access_token, get_cached_or_db_user
from app.common.database import get_db
from app.common.exceptions import AuthenticationError, PermissionDeniedError

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve and verify the currently authenticated active user from a Bearer JWT."""
    token: Optional[str] = None
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
    elif "token" in request.query_params:
        token = request.query_params.get("token")

    if not token:
        raise AuthenticationError("Missing Bearer authentication token")

    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthenticationError("Invalid user subject in authentication token") from exc

    user = get_cached_or_db_user(db, user_id)
    if not user.is_active:
        raise AuthenticationError("User account is suspended")
    return user


def require_permission(permission: str) -> Callable[[User], User]:
    """FastAPI dependency factory enforcing a granular `resource:action` permission."""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.has_permission(permission):
            raise PermissionDeniedError(permission)
        return current_user

    return _dependency


def require_any_permission(*permissions: str) -> Callable[[User], User]:
    """FastAPI dependency factory enforcing at least one of the specified permissions."""

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        for perm in permissions:
            if current_user.has_permission(perm):
                return current_user
        raise PermissionDeniedError(permissions[0] if permissions else "unknown")

    return _dependency
