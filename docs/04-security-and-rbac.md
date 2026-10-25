# 04 — Security, Authentication & Permission-Based RBAC

## 1. Super Admin & System Roles Bootstrap
On startup, `ensure_initial_admin()` (`app/auth/service.py`):
1. Seeds the 3 built-in system RBAC roles (`super_admin`, `support_engineer`, `viewer`) in the `roles` table via `ensure_default_roles()`.
2. Checks if a `User` with `is_super_admin=True` exists. If not, it seeds the initial Super Admin from `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `ADMIN_EMAIL` and records an `auth.bootstrap_super_admin` audit log entry.
3. In `production` (`APP_ENV=production`), startup fails fast if `SECRET_KEY`, `ENCRYPTION_KEY`, or `ADMIN_PASSWORD` is left at its default placeholder, or if `DIAGNOSTIC_MODE=simulated` or `LOOP_GUARD_FAIL_OPEN_FOR_TESTS=true` is set.
4. Manual ticket status overrides performed by engineers via UI drag-and-drop or `PATCH /api/v1/tickets/{id}` pass `force=True` to `transition_ticket` and record an immutable `ticket.status_forced` entry in `audit_logs`.
5. `diagnostic_scenario` simulation overrides are restricted exclusively to the test harness (`trigger_email_in_loop`) when `DIAGNOSTIC_MODE=simulated`; any attempt to pass `diagnostic_scenario` in `live` mode or outside the harness is rejected with `403 Forbidden`.

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
- **Page 12 connection tests & encrypted credentials:** `POST /api/v1/settings/test-smtp`, `POST /api/v1/settings/test-imap`, and `POST /api/v1/settings/test-vllm` require `settings:read`; `POST /api/v1/settings/send-test-email` requires `settings:update`.
  - IMAP and SMTP App Passwords saved via Page 12 (`imap_password`, `smtp_password`) are encrypted at rest in `system_settings` (`imap_password_encrypted`, `smtp_password_encrypted`) using symmetric Fernet encryption derived from `ENCRYPTION_KEY` (`app/common/crypto.py`).
  - Passwords and ciphertext are never returned by `GET /api/v1/settings` or `PUT /api/v1/settings`; only `imap_credentials_configured` and `smtp_credentials_configured` booleans are exposed.
  - Test results and audit logs never echo passwords.
  - When `test_redirect_email` is configured on Page 12, live SMTP delivery routes all outbound Branch, ISP, and Human Escalation emails exclusively to `test_redirect_email` so real ISP NOCs are never emailed during Gmail testing.
  - The unauthenticated `GET /api/v1/system/vllm-status` endpoint was removed.
- **Inbound SMTP listener:** an unauthenticated port that can create tickets and trigger ISP escalations, so it is locked down:
  - It is off by default.
  - Only IPs/CIDRs in `SMTP_LISTENER_ALLOWED_CLIENTS` may connect; others get `554` on connect. When enabled, an empty or invalid list stops startup, and `0.0.0.0/0` (or `::/0`) is refused in `production`.
  - Only allowed recipients are accepted (the default is the Page 12 sender address).
  - Messages are limited by size (25 MB by default), recipient count (50), connections (20) and time (5 min per command, 10 min per DATA).
  - DATA is strict CRLF, so SMTP smuggling (`\n.\r\n`) cannot split one message into two.
  - Accepted mail is treated as untrusted input: it goes through the same classifier and state machine as any other email, never straight to an action.
  - Also restrict the published port with the host firewall to the mail server's IP.
- **Outbound delivery off by default:** `system_settings.smtp_enabled` defaults to `false`, so a new or `dev` install never emails ISPs or branches until an admin turns it on. The change is recorded in `audit_logs` (`settings.updated`).
- **Anti-email-storm loop guard:** outbound mail is limited per ticket (`MAX_OUTBOUND_EMAILS_PER_TICKET_HOUR`), and mail with no ticket is limited per inbound message (`NO-TICKET:<In-Reply-To>`). If Redis is unreachable, sends are blocked (fail-safe). After 2 blocked sends within an hour, `apply_loop_guard_trip` moves the ticket to `NEEDS_HUMAN_REVIEW` (`LOOP_GUARD_TRIPPED`) and pauses AI. It goes through the state machine (never forced), so it cannot reopen a closed ticket.
- Every login, user creation/update, permission change, role modification, and password reset is logged to `audit_logs` (`app/common/audit.py`) and invalidates the Redis user permission cache (`it_net:auth:user:{id}`).
