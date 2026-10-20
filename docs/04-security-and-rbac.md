# 04 — Security, Authentication & Permission-Based RBAC

## 1. Super Admin Bootstrap
On startup, `ensure_initial_admin()` checks if a `User` with `is_super_admin=True` exists. If not, it seeds the initial Super Admin from `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `ADMIN_EMAIL`. In `production` (`APP_ENV=production`), startup fails fast if `SECRET_KEY`, `ENCRYPTION_KEY`, or `ADMIN_PASSWORD` is left at its default placeholder.

## 2. Granular Permissions (`ALL_PERMISSIONS`)
- **Tickets:** `tickets:view`, `tickets:edit_status`, `tickets:assign`, `tickets:pause_ai`, `tickets:delete`
- **Diagnostics:** `diagnostics:view_logs`, `diagnostics:trigger_manual`
- **Emails:** `emails:view`, `emails:send_manual_reply`, `emails:force_isp_followup`
- **Branches & ISPs:** `branches:view`, `branches:create`, `branches:edit`, `branches:import_sheet`, `isps:manage`
- **Users & Roles:** `users:view`, `users:create`, `users:edit_permissions`, `roles:manage`
- **Settings:** `settings:manage_mailbox`, `settings:manage_agent_prompts`, `settings:manage_sla_timers`
