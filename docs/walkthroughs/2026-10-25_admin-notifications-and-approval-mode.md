# Walkthrough: Admin Action Email Notifications & Agent Execution Mode (Approval vs Autonomous)

**Date:** 2026-10-25

## Summary of Changes

1. **Database & Alembic Migration (`0006_admin_notifications_and_approval_mode`)**:
   - Added `admin_notification_email` (`String(255)`), `notify_admin_on_every_action` (`Boolean`, default `True`), and `require_admin_approval_before_action` (`Boolean`, default `False`) to `system_settings`.
   - Added `pending_admin_action_json` (`JSON`, nullable) to `tickets` and `ADMIN_APPROVAL_REQUIRED` to `EscalationReason`.

2. **Admin Action Notification Emails (`backend/app/email_engine/smtp_sender.py`)**:
   - Implemented `resolve_admin_notification_email` (resolving `admin_notification_email` $\rightarrow$ `test_redirect_email` $\rightarrow$ `escalation_email`) and `dispatch_admin_action_email`.
   - Configured `thread_type="ADMIN_NOTIFICATION"` to bypass the per-ticket anti-storm loop guard so Admin action/approval emails are never blocked by Branch/ISP thread counters.

3. **Autonomous vs Approval Mode Gate (`backend/app/ticketing/service.py`, `backend/app/agent/workflow.py`, `backend/app/agent/scheduler.py`)**:
   - Added `apply_or_queue_ticket_action`, `approve_pending_ticket_action`, and `reject_pending_ticket_action`.
   - **Autonomous Mode (`require_admin_approval_before_action = False`)**: The agent executes its workflow action immediately and emails `[AGENT ACTION EXECUTED]` to the Admin (when `notify_admin_on_every_action = True`) with full diagnostic, triage, and outbound email details.
   - **Approval Mode (`require_admin_approval_before_action = True`)**: The agent runs read-only triage, router photo vision inspection, and Dual-Ping/Traceroute diagnostics first, then stores the proposed transition and draft outbound Branch/ISP emails in `ticket.pending_admin_action_json`, moves the ticket to `NEEDS_HUMAN_REVIEW` (`escalation_reason="ADMIN_APPROVAL_REQUIRED"`), and emails `[ADMIN APPROVAL REQUIRED]` to the Admin.
   - Added `POST /api/v1/tickets/{ticket_identifier}/approve-action` and `POST /api/v1/tickets/{ticket_identifier}/reject-action` endpoints.

4. **Frontend Console UI (`SettingsView.tsx`, `HumanReviewView.tsx`, `TicketDetailView.tsx`)**:
   - Added the **Admin Action Email Notifications & Execution Mode** card in `SettingsView.tsx` with one-click switching between **Proceed Without Asking (Autonomous)** and **Ask Admin Before Acting (Approval Mode)**, Admin Notification Email input, and per-action email notification toggle.
   - Updated `HumanReviewView.tsx` and `TicketDetailView.tsx` to display the proposed status, summary, diagnostic/triage context, draft outbound emails, and **Approve & Execute** / **Reject Action** controls.

5. **Verification**:
   - Added `backend/tests/test_admin_notifications_and_approval.py` covering settings persistence, autonomous admin action emails, and approval/rejection workflows.
   - `ruff format`, `ruff check`, `mypy app/`, `pytest` (`236 passed`), and `npm run build` all pass with zero errors.
