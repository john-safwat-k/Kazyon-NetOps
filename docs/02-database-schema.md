# 02 — Database Schema & Migrations

## 1. Migration Ownership
All schema changes are managed via **Alembic** under `backend/alembic/versions/`.
- **Initial Migration:** `0001_initial_baseline.py`
- **Auth Roles & Audit Trail:** `0002_auth_roles_and_audit_logs.py` (adds `users.last_login_at`, `roles`, and `audit_logs`)

## 2. Core Tables
- `users` (`app/auth/models.py`): Internal users, roles (`role_name`), `is_super_admin`, `is_active`, `permissions` (`JSONB`), and `last_login_at`.
- `roles` (`app/auth/models.py`): Reusable RBAC role definitions (`slug`, `display_name`, `description`, `is_system`, `permissions` `JSONB`) seeded on startup with `super_admin`, `support_engineer`, and `viewer`.
- `audit_logs` (`app/common/audit.py`): Immutable security, RBAC, and administrative audit trail (`actor_user_id`, `actor_username`, `action`, `resource_type`, `resource_id`, `summary`, `details_json`, `ip_address`, `created_at`).
- `network_providers` (`app/directory/models.py`): ISP records, escalation emails, CC lists, and `followup_interval_minutes`.
- `branches` (`app/directory/models.py`): Branch code, name, `target_ip`, `circuit_id`, `connection_type`, `contact_emails` (`JSONB`), and `isp_id` FK.
- `tickets` (`app/ticketing/models.py`): Ticket number, status, priority, `branch_id`, `isp_id`, `isp_reference_number`, `ai_automation_enabled`, `last_isp_contact_at`, `next_followup_at`, `followup_count`.
- `diagnostic_runs` (`app/ticketing/models.py`): Script execution history per ticket (`trigger_source`, `result_status`, `metrics_json`, `raw_output`, `duration_ms`).
- `ticket_emails` (`app/ticketing/models.py`): Inbound and outbound emails separated by `thread_type` (`BRANCH` vs `ISP`) with `Message-ID` deduplication and `ai_analysis_json`.
- `ticket_events` (`app/ticketing/models.py`): Chronological audit/timeline log per ticket.
