# 02 — Database Schema & Migrations

## 1. Migration Ownership
All schema changes are managed via **Alembic** under `backend/alembic/versions/`.
- **Initial Migration:** `0001_initial_baseline.py`

## 2. Core Tables
- `users` (`app/auth/models.py`): Internal users, roles, `is_super_admin`, and `permissions` (`JSONB`).
- `network_providers` (`app/directory/models.py`): ISP records, escalation emails, CC lists, and `followup_interval_minutes`.
- `branches` (`app/directory/models.py`): Branch code, name, `target_ip`, `circuit_id`, `connection_type`, `contact_emails` (`JSONB`), and `isp_id` FK.
- `tickets` (`app/ticketing/models.py`): Ticket number, status, priority, `branch_id`, `isp_id`, `isp_reference_number`, `ai_automation_enabled`, `last_isp_contact_at`, `next_followup_at`, `followup_count`.
- `diagnostic_runs` (`app/ticketing/models.py`): Script execution history per ticket (`trigger_source`, `result_status`, `metrics_json`, `raw_output`, `duration_ms`).
- `ticket_emails` (`app/ticketing/models.py`): Inbound and outbound emails separated by `thread_type` (`BRANCH` vs `ISP`) with `Message-ID` deduplication and `ai_analysis_json`.
- `ticket_events` (`app/ticketing/models.py`): Chronological audit/timeline log per ticket.
