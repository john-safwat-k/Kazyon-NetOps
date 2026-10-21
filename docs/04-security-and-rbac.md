# 04 — Security, Authentication & Permission-Based RBAC

## 1. Super Admin & System Roles Bootstrap
On startup, `ensure_initial_admin()` (`app/auth/service.py`):
1. Seeds the 3 built-in system RBAC roles (`super_admin`, `support_engineer`, `viewer`) in the `roles` table via `ensure_default_roles()`.
2. Checks if a `User` with `is_super_admin=True` exists. If not, it seeds the initial Super Admin from `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `ADMIN_EMAIL` and records an `auth.bootstrap_super_admin` audit log entry.
3. In `production` (`APP_ENV=production`), startup fails fast if `SECRET_KEY`, `ENCRYPTION_KEY`, or `ADMIN_PASSWORD` is left at its default placeholder.

## 2. Granular Permissions & 8×5 Permission Matrix (`ALL_PERMISSIONS`)
Access control is enforced via FastAPI dependencies `get_current_user` and `require_permission("<resource>:<action>")` in `app/auth/dependencies.py`.
Both domain-specific permissions and standardized 8-resource $\times$ 5-action (`read`, `create`, `update`, `delete`, `execute`) matrix permissions are supported and bidirectionally mapped (`PERMISSION_EQUIVALENTS` in `app/auth/models.py`):

- **Tickets (`tickets:*`):** `tickets:view`, `tickets:edit_status`, `tickets:assign`, `tickets:pause_ai`, `tickets:delete` + `tickets:read`, `tickets:create`, `tickets:update`, `tickets:execute`
- **Diagnostics (`diagnostics:*`):** `diagnostics:view_logs`, `diagnostics:trigger_manual` + `diagnostics:read`, `diagnostics:create`, `diagnostics:update`, `diagnostics:execute`
- **Emails (`emails:*`):** `emails:view`, `emails:send_manual_reply`, `emails:force_isp_followup` + `emails:read`, `emails:create`, `emails:update`, `emails:delete`, `emails:execute`
- **Replication (`replication:*`):** `replication:view`, `replication:upload`, `replication:trigger_notify` + `replication:read`, `replication:create`, `replication:delete`, `replication:execute`
- **Branches (`branches:*`):** `branches:view`, `branches:create`, `branches:edit`, `branches:import_sheet` + `branches:read`, `branches:update`, `branches:delete`
- **ISPs (`isps:*`):** `isps:manage` + `isps:read`, `isps:create`, `isps:update`, `isps:delete`
- **Users & Roles (`users:*`, `roles:manage`):** `users:view`, `users:create`, `users:edit_permissions`, `roles:manage` + `users:read`, `users:update`, `users:delete`
- **Settings (`settings:*`):** `settings:manage_mailbox`, `settings:manage_agent_prompts`, `settings:manage_sla_timers` + `settings:read`, `settings:create`, `settings:update`, `settings:delete`, `settings:execute`

## 3. Safety & Lockout Protections
- A signed-in administrator cannot suspend their own account (`ValidationError` `400`).
- The last active Super Admin cannot be suspended or demoted (`ValidationError` `400`).
- System roles (`super_admin`, `support_engineer`, `viewer`) cannot be deleted, and `super_admin` permissions cannot be restricted.
- Every login, user creation/update, permission change, role modification, and password reset is logged to `audit_logs` (`app/common/audit.py`) and invalidates the Redis user permission cache (`it_net:auth:user:{id}`).
