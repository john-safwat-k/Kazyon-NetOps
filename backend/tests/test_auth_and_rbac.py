"""Comprehensive integration tests for Authentication, JWT, Users CRUD, Roles, Permission Matrix, and Audit Logs."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.auth.models  # noqa: F401
import app.common.audit  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.auth.service import ensure_initial_admin
from app.common.config import get_settings
from app.common.database import Base, get_db
from app.main import app


@pytest.fixture()
def client_and_db(tmp_path: Path) -> Generator[tuple[TestClient, Session], None, None]:
    """Provide an isolated SQLite database and TestClient for each test."""
    db_file = tmp_path / f"test_auth_{uuid4().hex}.db"
    test_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, future=True
    )

    session = TestingSessionLocal()
    ensure_initial_admin(session)

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client, session
    app.dependency_overrides.clear()
    session.close()
    test_engine.dispose()


def _login_as_admin(client: TestClient) -> tuple[str, dict[str, str]]:
    settings = get_settings()
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return token, {"Authorization": f"Bearer {token}"}


def test_login_and_get_me(client_and_db: tuple[TestClient, Session]) -> None:
    client, _ = client_and_db
    settings = get_settings()

    # Login by username
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == settings.admin_username
    assert body["user"]["is_super_admin"] is True
    assert "password_hash" not in body["user"]

    # Login by email (case-insensitive)
    resp_email = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "ADMIN@KAZYON.COM",
            "password": settings.admin_password,
        },
    )
    assert resp_email.status_code == 200

    # Verify /me
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == (settings.admin_email or "admin@kazyon.com")
    assert me_data["last_login_at"] is not None


def test_invalid_login_and_missing_token_return_401(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_db

    bad_resp = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "admin", "password": "wrong-password"},
    )
    assert bad_resp.status_code == 401
    problem = bad_resp.json()
    assert problem["type"] == "AuthenticationError"
    assert problem["status"] == 401

    unauth_resp = client.get("/api/v1/auth/me")
    assert unauth_resp.status_code == 401

    malformed_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert malformed_resp.status_code == 401


def test_user_lifecycle_and_granular_rbac_enforcement(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_db
    _, admin_headers = _login_as_admin(client)

    # 1. Create a Viewer user (has read permissions on tickets/branches, but NO users:view or users:create)
    create_viewer = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "ahmed.farouk@kazyon.com",
            "display_name": "Ahmed Farouk",
            "password": "ViewerPassword123!",
            "role_name": "viewer",
        },
    )
    assert create_viewer.status_code == 201, create_viewer.text
    viewer_user = create_viewer.json()
    assert viewer_user["username"] == "ahmed.farouk"
    assert viewer_user["role_name"] == "viewer"
    assert viewer_user["is_super_admin"] is False
    assert "tickets:read" in viewer_user["permissions"]
    assert "tickets:view" in viewer_user["permissions"]
    assert "users:view" not in viewer_user["permissions"]

    # 2. Authenticate as Viewer
    viewer_login = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "ahmed.farouk@kazyon.com", "password": "ViewerPassword123!"},
    )
    assert viewer_login.status_code == 200
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}

    # 3. Viewer attempting to list users must receive 403 PermissionDeniedError
    forbidden_resp = client.get("/api/v1/users", headers=viewer_headers)
    assert forbidden_resp.status_code == 403
    err = forbidden_resp.json()
    assert err["type"] == "PermissionDeniedError"
    assert err["details"]["required_permission"] == "users:view"

    # 4. Super Admin grants `users:read` (which expands to `users:view`) to the Viewer
    grant_resp = client.put(
        f"/api/v1/users/{viewer_user['id']}/permissions",
        headers=admin_headers,
        json={"permissions": ["tickets:read", "users:read"]},
    )
    assert grant_resp.status_code == 200
    assert "users:view" in grant_resp.json()["permissions"]

    # 5. Viewer can now list users, but still cannot create users
    allowed_list = client.get("/api/v1/users", headers=viewer_headers)
    assert allowed_list.status_code == 200
    assert allowed_list.json()["total"] == 2

    still_forbidden_create = client.post(
        "/api/v1/users",
        headers=viewer_headers,
        json={
            "email": "new@kazyon.com",
            "display_name": "New User",
            "password": "Password123!",
            "role_name": "viewer",
        },
    )
    assert still_forbidden_create.status_code == 403

    # 6. Suspend Viewer account and verify login is blocked
    suspend_resp = client.patch(
        f"/api/v1/users/{viewer_user['id']}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["is_active"] is False

    blocked_me = client.get("/api/v1/auth/me", headers=viewer_headers)
    assert blocked_me.status_code == 401

    blocked_login = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "ahmed.farouk@kazyon.com", "password": "ViewerPassword123!"},
    )
    assert blocked_login.status_code == 401


def test_cannot_suspend_or_demote_last_super_admin(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_db
    _, admin_headers = _login_as_admin(client)

    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    admin_id = me["id"]

    # Cannot suspend own account
    suspend_self = client.patch(
        f"/api/v1/users/{admin_id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert suspend_self.status_code == 400

    # Cannot demote last Super Admin
    demote_self = client.patch(
        f"/api/v1/users/{admin_id}",
        headers=admin_headers,
        json={"is_super_admin": False, "role_name": "viewer"},
    )
    assert demote_self.status_code == 400


def test_roles_permission_matrix_and_sync(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_db
    _, admin_headers = _login_as_admin(client)

    # 1. Verify default system roles exist
    roles_resp = client.get("/api/v1/roles", headers=admin_headers)
    assert roles_resp.status_code == 200
    roles = {r["slug"]: r for r in roles_resp.json()}
    assert {"super_admin", "support_engineer", "viewer"}.issubset(roles.keys())

    # 2. Create a user with support_engineer role
    eng_resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "mona.adel@kazyon.com",
            "display_name": "Mona Adel",
            "password": "EngineerPassword123!",
            "role_name": "support_engineer",
        },
    )
    assert eng_resp.status_code == 201
    eng_id = eng_resp.json()["id"]
    assert "branches:create" not in eng_resp.json()["permissions"]

    # 3. Update support_engineer role matrix to include `branches:create` and sync assigned users
    new_perms = list(roles["support_engineer"]["permissions"]) + ["branches:create"]
    upd_role = client.put(
        "/api/v1/roles/support_engineer",
        headers=admin_headers,
        json={"permissions": new_perms, "sync_assigned_users": True},
    )
    assert upd_role.status_code == 200
    assert "branches:create" in upd_role.json()["permissions"]

    # Verify the assigned engineer automatically received `branches:create`
    eng_after = client.get(f"/api/v1/users/{eng_id}", headers=admin_headers).json()
    assert "branches:create" in eng_after["permissions"]

    # 4. Create and delete a custom role
    custom_role = client.post(
        "/api/v1/roles",
        headers=admin_headers,
        json={
            "display_name": "Regional IT Liaison",
            "base_role_slug": "viewer",
        },
    )
    assert custom_role.status_code == 201
    assert custom_role.json()["slug"] == "regional_it_liaison"
    assert custom_role.json()["is_system"] is False

    del_resp = client.delete("/api/v1/roles/regional_it_liaison", headers=admin_headers)
    assert del_resp.status_code == 204


def test_password_reset_and_audit_logs(
    client_and_db: tuple[TestClient, Session],
) -> None:
    client, _ = client_and_db
    _, admin_headers = _login_as_admin(client)

    create_resp = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "karim.hassan@kazyon.com",
            "display_name": "Karim Hassan",
            "password": "InitialPassword123!",
            "role_name": "support_engineer",
        },
    )
    user_id = create_resp.json()["id"]

    # Admin resets user password
    reset_resp = client.post(
        f"/api/v1/users/{user_id}/reset-password",
        headers=admin_headers,
        json={"new_password": "ResetPassword456!"},
    )
    assert reset_resp.status_code == 200

    # User logs in with reset password and changes their own password
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "karim.hassan@kazyon.com", "password": "ResetPassword456!"},
    )
    assert login_resp.status_code == 200
    user_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    chg_resp = client.post(
        "/api/v1/auth/change-password",
        headers=user_headers,
        json={
            "current_password": "ResetPassword456!",
            "new_password": "FinalUserPassword789!",
        },
    )
    assert chg_resp.status_code == 200

    # Verify audit trail captured all events
    audit_resp = client.get("/api/v1/auth/audit-logs", headers=admin_headers)
    assert audit_resp.status_code == 200
    actions = {item["action"] for item in audit_resp.json()["items"]}
    assert "user.created" in actions
    assert "user.password_reset" in actions
    assert "auth.password_changed" in actions
    assert "auth.login" in actions
