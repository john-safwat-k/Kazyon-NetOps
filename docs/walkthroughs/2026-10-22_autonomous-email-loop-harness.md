# Walkthrough — Autonomous Email Loop Trigger & Multi-Turn Agent Harness

- **Date:** 2026-10-22
- **Summary:** Wired the autonomous agent harness directly into the inbound/outbound email loop (`BRANCH`, `ISP`, and `HUMAN_ESCALATION` threads) with background IMAP + local `.eml` dropbox polling, live/sandboxed SMTP dispatch with automatic `In-Reply-To` and `References` header chaining, 5-tier multi-turn thread correlation, quote-stripped reply classification, end-to-end blocker mediation (`CABLE_UNPLUGGED` $\rightarrow$ reseated reply; `SITE_CONTACT_UNREACHABLE` $\rightarrow$ Regional IT new phone reply relayed to ISP; `ISP_RESOLVED` $\rightarrow$ final verification Dual-Ping pass closure or failed-verification closure rejection), and an interactive **Autonomous Email Loop Trigger & Multi-Turn Harness** panel in `MailboxTriageView.tsx` (Page 8).

## Files Changed
- **`backend/app/email_engine/`**
  - `imap_poller.py` (created): Non-blocking (`asyncio.to_thread`) IMAP4 SSL poller, local `data/imports/inbox/*.eml` dropbox consumer, and live IMAP/SMTP connectivity tester (`test_mailbox_connectivity`).
  - `parser.py` (updated): Added `extract_ticket_number_tag`, `extract_circuit_id_hint`, `strip_reply_quotes`, and `build_synthetic_eml_bytes`.
  - `smtp_sender.py` (updated): Auto-populates `In-Reply-To` and `References` from prior emails on the same ticket thread, enforces `[NET-XXXX]` correlation tags on `BRANCH` and `HUMAN_ESCALATION` subjects, and dispatches via `smtplib.SMTP` when live SMTP credentials are configured.
- **`backend/app/agent/`**
  - `classifier.py` (updated): Quote-aware reply classification (`strip_reply_quotes`), reseated cable photo detection, `BRANCH_CONTACT_UPDATE` intent detection, and `BRANCH_RESOLUTION_CONFIRMED` intent detection.
  - `workflow.py` (updated): Added `_correlate_envelope_to_ticket_and_branch` (5-tier correlation: `In-Reply-To`/`References` $\rightarrow$ `[NET-XXXX]` tag $\rightarrow$ ISP Case `#` $\rightarrow$ Circuit ID $\rightarrow$ 4-digit SAP code), full multi-turn loop responses in `ingest_and_triage_eml`, `trigger_email_in_loop`, and `reclassify_existing_email`.
  - `scheduler.py` (updated): Added `run_email_loop_cycle_once`, `get_email_loop_status`, and background asyncio worker lifecycle (`start_background_email_loop` / `stop_background_email_loop`).
- **`backend/app/ticketing/` & `backend/app/main.py`**
  - `router.py` (updated): Added `GET /api/v1/emails/loop-status`, `POST /api/v1/emails/poll-now`, `POST /api/v1/emails/trigger`, `POST /api/v1/emails/{email_id}/reclassify`, and wired `POST /api/v1/settings/test-connection` to `test_mailbox_connectivity`.
  - `service.py` (updated): Enriched `list_mailbox_triage_logs` with `thread_type`, `in_reply_to`, `branch_code`, `ticket_status`, and badge tones for all multi-turn outbound/inbound email templates.
  - `main.py` (updated): Starts and stops the background email loop worker inside the FastAPI `lifespan`.
- **`frontend/`**
  - `src/lib/api.ts` (updated): Added `EmailLoopStatusDTO`, `EmailLoopTriggerResponseDTO`, `emailsApi.loopStatus`, `emailsApi.pollNow`, `emailsApi.triggerInLoop`, and `emailsApi.reclassify`.
  - `src/views/MailboxTriageView.tsx` (updated): Added the interactive **Autonomous Email Loop Trigger & Multi-Turn Harness** panel, step-by-step execution trace, correlated thread viewer, and in-thread **"Reply in loop"** workflow.
- **`backend/tests/`**
  - `test_brd_end_to_end.py` (updated): Added `test_multi_turn_email_loop_harness_end_to_end` verifying the 9-step multi-turn email loop across Branch and ISP threads.

## Contract Changes
- None of the 4 frozen contracts (`DiagnosticScriptContract`, `EmailEnvelope`, `LLMClassificationContract`, `TicketStatus`) were broken.

## API / WebSocket Changes
- Added `GET /api/v1/emails/loop-status`
- Added `POST /api/v1/emails/poll-now`
- Added `POST /api/v1/emails/trigger`
- Added `POST /api/v1/emails/{email_id}/reclassify`
- Updated `docs/03-api-reference.md`.

## Schema Changes
- None required (uses existing `tickets`, `ticket_emails`, `ticket_events`, and `system_settings` tables).

## Security & RBAC Impact
- All new `/api/v1/emails/*` endpoints enforce `Depends(require_permission("emails:view"))`.

## Configuration
- Existing `IMAP_*` and `SMTP_*` variables in `app/common/config.py` and `system_settings` are used automatically; local dropbox folder `data/imports/inbox/` is also polled on every cycle.

## Known Limitations / Follow-Up
- None.
