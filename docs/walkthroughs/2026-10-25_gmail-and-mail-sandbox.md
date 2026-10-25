# Walkthrough — Interactive Mail Simulation Sandbox & Live Gmail Testing Support

**Date:** 2026-10-25  
**Scope:** End-to-end Interactive Mail Simulation Sandbox (Page 8) and full Gmail (`imap.gmail.com:993` + `smtp.gmail.com:587`) testing support with encrypted App Passwords, safe test redirection, and single-mailbox role-play correlation.

---

## 1. Summary of Changes

1. **Symmetric Fernet Credential Encryption (`backend/app/common/crypto.py`):**
   - Added `encrypt_secret` and `decrypt_secret` derived via SHA-256 from `Settings.encryption_key` so Gmail / Exchange App Passwords configured in the UI are encrypted at rest in `system_settings` and never exposed in API responses or logs.
2. **Database Schema & Migration (`0005_gmail_and_redirect`):**
   - Added `imap_use_ssl`, `imap_folder`, `imap_username`, `imap_password_encrypted`, `smtp_username`, `smtp_password_encrypted`, and `test_redirect_email` to `system_settings` (`backend/app/ticketing/models.py` and `_ensure_sqlite_dev_columns` in `backend/app/main.py`).
3. **Live IMAP Connection Tester & Poller (`backend/app/email_engine/imap_poller.py`):**
   - Added `ImapTransportConfig`, `imap_transport_config_from_row`, and `test_imap_connection_sync` (connects via `IMAP4_SSL`/`IMAP4`, authenticates with saved or unsaved form credentials, selects `INBOX`, and counts total + `UNSEEN` messages).
   - Updated `poll_inbound_mailbox_raw` and `scheduler.py` (`run_email_loop_cycle_once`, `get_email_loop_status`) to use the saved DB IMAP configuration with `.env` fallback.
4. **Safe Test Redirect & Encrypted SMTP Login (`backend/app/email_engine/smtp_sender.py`):**
   - Updated `smtp_transport_config_from_row` to decrypt `smtp_password_encrypted` (falling back to `.env`) and load `test_redirect_email`.
   - When `test_redirect_email` is set, `_send_via_live_smtp_sync` routes all live outbound Branch, ISP (`noc@noor.net`, `ccc-eg@orange.com`, `psupport@te.eg`), and Human Escalation emails exclusively to `test_redirect_email`, adding `X-Kz-Original-To` and a `[KAZYON SANDBOX REDIRECT]` banner while preserving logical `recipients` on `TicketEmail` records.
5. **Single-Mailbox Gmail Role-Play & 6-Stage Execution Trace (`backend/app/agent/classifier.py`, `backend/app/agent/workflow.py`):**
   - Added `_detect_correlated_thread_type` and `correlated_thread_type` / `correlated_isp_name` support in `classify_inbound_email` so when an operator replies from their `@gmail.com` inbox to a redirected ISP escalation email (or selects `role: "ISP"` in the Sandbox), the agent recognizes the reply as an `ISP_REPLY`.
   - Added `_build_sandbox_stage_trace` (6-stage pipeline breakdown) and `_build_suggested_next_steps` (contextual next role-play actions) to `ingest_and_triage_eml` and `trigger_email_in_loop`.
6. **Frontend Settings & Interactive Sandbox (`frontend/src/views/SettingsView.tsx`, `frontend/src/views/MailboxTriageView.tsx`):**
   - **Page 12 (`SettingsView.tsx`):** Added **Mail Provider Quick Presets** (`Gmail Testing`, `Kazyon Exchange`, `Office 365`), **Inbound email (IMAP Poller — Gmail / Exchange)** card with live **Test IMAP connection**, **Copy Gmail login to Outbound SMTP**, **Safe Test Redirect Email**, and **Send live test email to Inbox**.
   - **Page 8 (`MailboxTriageView.tsx`):** Added the **Mailbox Transport & Safe Redirect Status Banner**, **Role-Play Actor Selector** (`Act as Branch` vs `Act as ISP NOC`), **6-Stage Pipeline Execution Trace** cards, and one-click **Interactive Role-Play Next Step** buttons.

---

## 2. Verification & Quality Gates

- `ruff format --check app/ tests/` — Passed
- `ruff check app/ tests/` — Passed
- `mypy app/` — Passed (`0` issues across 48 source files)
- `pytest` — All tests in `tests/test_settings_connections.py` (30 passed) and `tests/test_brd_end_to_end.py` / `tests/test_critical_agent_gaps.py` / `tests/test_reaudit_fixes.py` / `tests/test_smtp_listener.py` (192 passed) succeeded.
- `cd frontend && npm run build` (`tsc --noEmit && vite build`) — Passed cleanly.
