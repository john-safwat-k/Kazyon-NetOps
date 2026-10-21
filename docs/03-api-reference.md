# 03 — API & WebSocket Reference

## Health & System Status

### `GET /api/health`
- **Auth:** Public (used by Docker healthcheck and `deploy.sh`)
- **Response (`200 OK`):**
  ```json
  {
    "status": "ok",
    "service": "IT Network Support AI Agent",
    "environment": "development",
    "env_slug": "dev",
    "version": "1.0.0",
    "vllm_base_url": "http://10.100.109.9:8002",
    "vllm_model": "google/gemma-4-26B-A4B-it"
  }
  ```

### `GET /api/v1/system/vllm-status`
- **Description:** Probes `http://10.100.109.9:8002/v1/models` to verify `Gemma 4 26B A4B` readiness.

---

## Authentication (`/api/v1/auth`)

### `POST /api/v1/auth/login`
- **Auth:** Public
- **Body:** `{"username_or_email": "admin", "password": "..."}`
- **Response (`200 OK`):** `TokenResponse` containing `access_token`, `token_type: "bearer"`, `expires_in_sec`, and sanitized `user` (`UserResponse`).

### `GET /api/v1/auth/me`
- **Auth:** Bearer JWT (`get_current_user`)
- **Response (`200 OK`):** `UserResponse` (`id`, `username`, `email`, `display_name`, `role_name`, `is_super_admin`, `is_active`, `permissions`, `last_login_at`).

### `POST /api/v1/auth/change-password`
- **Auth:** Bearer JWT (`get_current_user`)
- **Body:** `{"current_password": "...", "new_password": "..."}`
- **Response (`200 OK`):** `UserResponse`

### `GET /api/v1/auth/permissions`
- **Auth:** Bearer JWT (`get_current_user`)
- **Response (`200 OK`):** `PermissionCatalogResponse` (`all_permissions`, `matrix_actions`, and `resources` metadata for the 8-resource $\times$ 5-action RBAC matrix).

### `GET /api/v1/auth/audit-logs`
- **Auth:** `require_permission("users:view")`
- **Query Params:** `resource_type`, `limit` (default `50`), `offset` (default `0`)
- **Response (`200 OK`):** `AuditLogListResponse`

---

## Users & Granular RBAC (`/api/v1/users`)

### `GET /api/v1/users`
- **Auth:** `require_permission("users:view")`
- **Query Params:** `search`, `role_name`, `is_active`, `limit`, `offset`
- **Response (`200 OK`):** `UserListResponse` (`items`, `total`, `active_count`, `suspended_count`, `limit`, `offset`)

### `POST /api/v1/users`
- **Auth:** `require_permission("users:create")`
- **Body:** `UserCreateRequest` (`email`, `display_name`, `password`, `role_name`, optional `username`, `is_super_admin`, `is_active`, `permissions`)
- **Response (`201 Created`):** `UserResponse`

### `GET /api/v1/users/{user_id}`
- **Auth:** `require_permission("users:view")`
- **Response (`200 OK`):** `UserResponse`

### `PATCH /api/v1/users/{user_id}`
- **Auth:** `require_permission("users:edit_permissions")`
- **Body:** `UserUpdateRequest` (`username`, `email`, `display_name`, `role_name`, `is_super_admin`, `is_active`)
- **Response (`200 OK`):** `UserResponse`

### `PUT /api/v1/users/{user_id}/permissions`
- **Auth:** `require_permission("users:edit_permissions")`
- **Body:** `UserPermissionsUpdateRequest` (`permissions`, optional `role_name`, `is_super_admin`)
- **Response (`200 OK`):** `UserResponse`

### `POST /api/v1/users/{user_id}/reset-password`
- **Auth:** `require_permission("users:edit_permissions")`
- **Body:** `AdminResetPasswordRequest` (`new_password`)
- **Response (`200 OK`):** `UserResponse`

---

## Roles & Permission Matrix (`/api/v1/roles`)

### `GET /api/v1/roles`
- **Auth:** `require_permission("users:view")`
- **Response (`200 OK`):** `list[RoleResponse]` (`id`, `slug`, `display_name`, `description`, `is_system`, `permissions`, `user_count`)

### `POST /api/v1/roles`
- **Auth:** `require_permission("roles:manage")`
- **Body:** `RoleCreateRequest` (`display_name`, optional `slug`, `description`, `base_role_slug`, `permissions`)
- **Response (`201 Created`):** `RoleResponse`

### `PUT /api/v1/roles/{role_slug}`
- **Auth:** `require_permission("roles:manage")`
- **Body:** `RoleUpdateRequest` (`display_name`, `description`, `permissions`, `sync_assigned_users`)
- **Response (`200 OK`):** `RoleResponse`

### `DELETE /api/v1/roles/{role_slug}`
- **Auth:** `require_permission("roles:manage")`
- **Response (`204 No Content`)**
