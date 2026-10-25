# 01 — Project Overview & Architecture

## 1. System Purpose
The **IT Network Support AI Agent & Ticketing Harness** (`Kazyon NetOps`) automates end-to-end branch network troubleshooting and ISP escalation across all **1,150+ Kazyon store branches** and **3 Network Service Providers (`NOOR`, `ORANGE`, `WE`)** across **5 Egyptian regions**:
- **Trigger Path A (`DIRECT_EMAIL`):** Receives incident emails from Regional IT (`GITSupport`, `CITSupport`, `BITSupport`, `newoctregion`, `assiutregion`), persists attached `image/*` router photos to `data/attachments/<ticket_number>/<sha256>.<ext>`, verifies router photos using `Gemma 4 26B A4B` multimodal vision (`guided_json`), and runs live OS Dual-Ping (`IP1` Router, `IP2` Switch) + `ORANGE`/`WE` 4G Hub Traceroute diagnostics (`DIAGNOSTIC_MODE=live`).
- **Trigger Path B (`REPLICATION_DASHBOARD`):** Parses daily `Replication Dashboard - <Date>` HTML table reports, detects `Not Updated` stores, deduplicates against open tickets, opens `AWAITING_REGIONAL_IT` tickets, and notifies the corresponding Regional IT mailbox.
- **ISP Escalation & SLA Loop:** Sends provider-specific formatted escalation emails (`NOOR`, `ORANGE`, `WE`; rendering `site contact : will be shared shortly` and requesting an active phone from the branch when none is provided), tracks the **2-hour ISP Welcome Mail SLA**, extracts ISP ticket reference numbers (`#<digits>`, `1-13...`, `#840...`), and enforces the **4–6 hour Follow-Up Chaser Loop**.
- **Blocker Mediation & Human Fallback:** Mediates `SITE_CONTACT_UNREACHABLE` and `BRANCH_ACTION_BLOCKER` with Regional IT (and automatically relays Regional IT's updated phone number back to the ISP on the `ISP` thread), logs `AUTO_ACK` without prematurely starting the 4–6h loop, handles `ISP_RESOLVED` via real final re-verification dual-ping + traceroute (closing on `PASS` or rejecting premature closure on `FAIL`), and escalates out-of-flow blockers (`QUOTA_CONSUMED`, `INTERNAL_BOX_CABLE`, `MSAN_MIGRATION`, `UNRECOGNIZED_EMAIL`, `MAX_RETRIES`, `LOOP_GUARD_TRIPPED`, `LLM_UNAVAILABLE`, `DIAGNOSTICS_UNAVAILABLE`, `INGEST_FAILED`) to `NEEDS_HUMAN_REVIEW` while pausing AI automation.
  - Final verification also runs when the ISP claims resolution while the ticket is `AWAITING_BRANCH_CONTACT`.
  - For `ORANGE`/`WE` branches, final verification always runs a traceroute to `IP1`, even when both pings pass. A 4G hub in the path means the branch is still on backup (`LOCAL_LOOP_DOWN_ON_4G`), and the closure is rejected. Initial triage keeps the BRD matrix: both IPs up closes the ticket without a traceroute.
- **Enforced State Machine & Fail-Safe Loop Guard (`ticketing/state_machine.py`, `email_engine/loop_guard.py`):** All ticket status transitions are validated through `assert_transition` / `transition_ticket` (`ALLOWED_TRANSITIONS`); manual UI overrides (`force=True`) are audited. Outbound SMTP runs asynchronously via `asyncio.to_thread` and is guarded by a fail-safe Redis counter (`MAX_OUTBOUND_EMAILS_PER_TICKET_HOUR=6`) that blocks excess sends and escalates on repeated blocks.
  - The counter is per ticket. Mail with no ticket (for example unrecognized-email reports) is counted per inbound message (`NO-TICKET:<In-Reply-To>`), so one noisy thread cannot block every other report.
  - `smtp_sender.py` only records the block (`blocked_by_loop_guard`, `email_blocked` event). The escalation is decided by `ticketing/service.apply_loop_guard_trip`, called from the workflow and the SLA chaser. After 2 blocks within an hour it moves the ticket to `NEEDS_HUMAN_REVIEW` (`LOOP_GUARD_TRIPPED`) through `transition_ticket`, so a closed ticket is never reopened.
- **Autonomous Multi-Turn Email Loop Harness (`email_engine/` + `agent/`):** Built-in Inbound SMTP listener (`smtp_listener.py`) + local `.eml` dropbox (`data/imports/inbox/`) + live/sandboxed SMTP dispatcher (`smtp_sender.py`) using the corporate service mailbox `noc@kazyon.com` (`mail.kazyon.com:587` STARTTLS) with 5-tier thread correlation (`In-Reply-To`/`References` headers, `[NET-XXXX]` tags, ISP Case `#`, Circuit ID, and 4-digit Branch SAP code), reply quote stripping, two-stage `vLLM` `guided_json` classification, and interactive multi-turn loop triggering in the console.
  - **No inbound email is dropped.** The dropbox poller has three safety paths:
    - **vLLM down during classification:** the raw `.eml` is written to the retry queue (`LLM_RETRY_QUEUE_DIR`, default `data/imports/llm_retry/`). The poller re-ingests it once `LLM_RETRY_BACKOFF_SEC` (default 300 s) has passed. After 3 failed cycles the email goes to `NEEDS_HUMAN_REVIEW` with `LLM_UNAVAILABLE`.
    - **vLLM down during the router-photo check:** the photo verdict is skipped (`vision_unavailable` timeline event) and live diagnostics still decide the outcome.
    - **Any other crash while ingesting:** the scheduler rolls back, stores the email with label `INGEST_FAILED`, and emails the human engineer. The email appears in the Human Review queue.
- **Inbound mail via the built-in SMTP listener (`email_engine/smtp_listener.py`):** the system uses SMTP only (no IMAP), so the company mail server forwards branch and ISP mail for `noc@kazyon.com` straight to the agent.
  - It is a receive-only SMTP server, off by default (`SMTP_LISTENER_ENABLED`). Inside the container it listens on port 2525; the published host port is 2525 on `dev` and 2524 on `prod`.
  - Access is limited by client IP (`SMTP_LISTENER_ALLOWED_CLIENTS`) and by recipient (`SMTP_LISTENER_ALLOWED_RECIPIENTS`, default the Page 12 sender address `noc@kazyon.com`). There is no AUTH or STARTTLS.
  - Each message is written durably (fsync, then rename) to `data/imports/inbox/` **before** the agent answers `250`. The listener then wakes the poller, so the email goes through the normal ingest path: Message-ID dedup, the vLLM retry queue and `INGEST_FAILED`.
  - DATA must use CRLF. A message with a bare LF or CR is rejected, and only `CRLF . CRLF` ends DATA (SMTP-smuggling safe).
  - Status (port, allowed clients, accepted / rejected / refused counts, last message, error) appears on Page 12 and in `GET /api/v1/emails/loop-status`.
- **Page 12 settings drive the running agent (`system_settings`):**
  - **Outbound SMTP (`smtp_sender.py`):** Uses `mail.kazyon.com:587` (`starttls`) with the service mailbox `noc@kazyon.com` (`smtp_username`, `smtp_password_encrypted` encrypted at rest via Fernet derived from `ENCRYPTION_KEY`, with `.env` fallback).
  - **Outbound mail** uses the saved SMTP host, port, security mode (`starttls` / `ssl` / `none` for an internal relay), sender address (`mailbox_account`), encrypted SMTP login (`smtp_username` / `smtp_password_encrypted`), and per-ticket email limit.
  - **Safe Test Redirect Email (`test_redirect_email`):** Optional setting that routes all outbound Branch, ISP (`noc@noor.net`, `ccc-eg@orange.com`, `psupport@te.eg`), and Human Escalation emails to a test inbox with `X-Kz-Original-To` and a `[KAZYON SANDBOX REDIRECT]` banner so real ISPs are never accidentally emailed during testing. When the operator replies to a redirected `ISP` thread email, `_detect_correlated_thread_type` and `classify_inbound_email` automatically route their reply as an `ISP_REPLY`.
  - **Interactive Mail Simulation Sandbox (Page 8 — `MailboxTriageView.tsx`):** Provides a step-by-step Branch ↔ AI Agent ↔ ISP role-play simulator (`role: "BRANCH" | "ISP"`), a 6-stage pipeline execution trace (`stage_trace`), contextual next-turn role-play buttons (`suggested_next_steps`), and one-click live SMTP round-trip email testing (`POST /api/v1/settings/send-test-email`).
  - **Real sending is off** until "Send real email" (`smtp_enabled`) is turned on. Until then, emails are recorded on tickets with `smtp_delivery_disabled: true`.
  - **vLLM calls** use the saved endpoint, temperature and max tokens. There is one connection pool per endpoint.
  - **Diagnostics** use the saved timeout, ping count and traceroute max hops.
  - **"Test SMTP connection" makes a real connection:** connect, EHLO, TLS, login, and sender accepted (`MAIL FROM` + `RSET`, nothing sent). It reports the exact step that failed.
  - **"Test vLLM"** calls `/v1/models` and checks the configured model is served.
- **12-Screen Kazyon NetOps Console:** Provides full visibility across Executive & SLA Dashboard, 8-Column Kanban Board, Master Tickets List & Export, 360° Ticket Detail View, Replication Monitor, Human Review Queue, Mailbox & `.eml` Triage Simulator, Network Diagnostics Sandbox, 1,150-Store & ISP Directory, Users/Roles/RBAC Matrix, and AI/Mailbox/SLA Settings.

## 2. Technology Stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, `openpyxl`
- **AI Engine:** `google/gemma-4-26B-A4B-it` (`NVFP4`) on `vLLM` at `http://10.100.109.9:8002` (`guided_json` structured output + multimodal vision)
- **Database:** PostgreSQL 16 (`dev` and `prod` containers) / SQLite (local development & tests)
- **Cache & Anti-Storm Loop Guard:** Redis 7 (fail-safe closed when Redis is unreachable in production)
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS (`Kazyon NetOps Design System` — `Hanken Grotesk`, light/dark CSS variable tokens in `frontend/src/styles/tokens.css`, Tailwind preset in `frontend/tailwind/kazyon-netops.preset.js`, typed UI primitives in `frontend/src/design-system/`, and 12 console views in `frontend/src/views/`).

## 3. Core Contracts (`backend/app/common/contracts.py`)
1. `DiagnosticInput` & `DiagnosticOutput` (`DiagnosticStatus`: `PASS`, `FAIL`, `DEGRADED`, `ERROR`)
2. `EmailEnvelope`
3. `BranchEmailAnalysis`, `IspResponseAnalysis`, `RouterPhotoVisionAnalysis`, and `UniversalEmailTriageResult` (Guided JSON schemas for `vLLM`)
4. `TicketStatus` (11 lifecycle states mapped to 8 Kanban columns), `TicketPriority`, `TicketTriggerSource`, `ConnectionFailureType`, and `EscalationReason`

## 4. UI Design System & Console Views
- **Canonical Source:** `design/kazyon-netops-design-system/` and `design/Kazyon NetOps Console.html` (12-screen light & dark prototype).
- **Frontend Views (`frontend/src/views/`):**
  1. `LoginView.tsx` — Page 1: Login & Environment Selector (`PROD :8084` / `DEV :8085`)
  2. `DashboardView.tsx` — Page 2: Executive & Live SLA Dashboard
  3. `KanbanBoardView.tsx` — Page 3: 8-Column Ticket Kanban Board & Manual Ticket Modal
  4. `TicketsListView.tsx` — Page 4: Master Tickets List, Multi-Criteria Filter & CSV/Excel Export
  5. `TicketDetailView.tsx` — Page 5: Ticket 360° Detail (Timeline, Vision & Test Results, Branch Emails, ISP Emails)
  6. `ReplicationMonitorView.tsx` — Page 6: Replication Dashboard Monitor & HTML Report Parser
  7. `HumanReviewView.tsx` — Page 7: Human Review & Out-of-Flow Escalation Queue
  8. `MailboxTriageView.tsx` — Page 8: Mailbox & `.eml` Triage Simulator (with `Info/*.eml` samples)
  9. `DiagnosticsSandboxView.tsx` — Page 9: Network Diagnostics Sandbox (`IP1`/`IP2` Dual-Ping & 4G Hub Traceroute)
  10. `DirectoryView.tsx` — Page 10: 1,150-Store Branches & 3-ISP Directory + Excel Bulk Seeder
  11. `UsersRbacView.tsx` — Page 11: Users, Roles & 8$\times$5 Granular Permission Matrix
  12. `SettingsView.tsx` — Page 12: AI Agent, Mailbox, SLA Timers, Admin Action Email Notifications & Execution Mode (`Proceed Without Asking` vs `Ask Admin Before Acting`), & Global Master Kill-Switch
