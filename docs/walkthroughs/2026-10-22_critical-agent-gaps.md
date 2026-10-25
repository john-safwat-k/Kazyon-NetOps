# Walkthrough — Critical Gaps in the Autonomous Agent Flow (`Gaps 1–6`)

**Date:** `2026-10-22`  
**Task Slug:** `critical-agent-gaps`  
**Reference Plan:** Fix Plan: Critical Gaps in the Autonomous Agent Flow (BRD v5.0 §4)

---

## 1. Summary of Changes

This implementation resolves the six critical gaps identified in the end-to-end audit of `backend/app/agent/workflow.py` against BRD v5.0 §4:

1. **Gap 6 — Enforce Ticket State Transitions (`ticketing/state_machine.py`, `ticketing/service.py`, `agent/workflow.py`):**
   - Added `ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]]` and `assert_transition(current, target)` in `backend/app/ticketing/state_machine.py` raising `InvalidStateTransitionError`.
   - Added `transition_ticket(db, ticket, target, *, actor_type, actor_name, reason, force=False)` in `backend/app/ticketing/service.py`, which validates the transition, applies `resolved_at` / `next_followup_at` / `ai_automation_enabled` side effects, logs a `status_changed` `TicketEvent`, records an `AuditLog` (`ticket.status_forced`) when `force=True` is used by an engineer, and broadcasts `ticket.updated` over WebSocket.
   - Replaced all direct `.status =` mutations across `workflow.py`, `scheduler.py`, and `service.py` with `transition_ticket(...)`. *(Correction from the re-audit: `smtp_sender.py` still set the status directly on a loop-guard trip; fixed in [`2026-10-22_reaudit-agent-fixes.md`](2026-10-22_reaudit-agent-fixes.md).)*
   - Caught `InvalidStateTransitionError` in `ingest_and_triage_eml` so illegal transitions (such as a B1 contact update on a `DIAGNOSING` ticket or a repeat branch email on an already `ESCALATED_TO_ISP` ticket) log a `status_transition_blocked` timeline warning and do not dispatch duplicate outbound emails.

2. **Gap 4 — Make the Loop Guard Actually Block (`email_engine/loop_guard.py`, `email_engine/smtp_sender.py`, `agent/scheduler.py`):**
   - Removed the per-process `_in_memory_counters` fallback in `backend/app/email_engine/loop_guard.py`; when Redis is unreachable, `check_and_increment_outbound_allowance` returns fail-safe `False` (unless `LOOP_GUARD_FAIL_OPEN_FOR_TESTS=true` in non-production tests).
   - Converted `dispatch_outbound_email` to `async` and executed `smtplib.SMTP` via `asyncio.to_thread`.
   - When `check_and_increment_outbound_allowance` returns `False`, live SMTP is skipped, `TicketEmail.ai_analysis_json.blocked_by_loop_guard = True` is persisted, an `email_blocked` `TicketEvent` is logged, and on the second blocked send within 1 hour the ticket transitions to `NEEDS_HUMAN_REVIEW` with `EscalationReason.LOOP_GUARD_TRIPPED`. *(Re-audit: this escalation now lives in `ticketing/service.apply_loop_guard_trip`, and ticketless mail no longer shares one `GLOBAL` counter.)*
   - On SMTP delivery failure, `EmailDeliveryError` is caught and recorded with an `email_delivery_failed` timeline event.

3. **Gap 5 — Never Send a Made-Up Site Phone Number (`agent/workflow.py`, `email_engine/smtp_sender.py`):**
   - Removed the hardcoded `"010 2345 8817"` phone literal from `workflow.py`.
   - Resolved `site_contact_phone` in strict order: `triage.site_contact_phone` $\rightarrow$ existing `ticket.site_contact_phone` $\rightarrow$ latest phone extracted from inbound emails on the ticket's `BRANCH` thread $\rightarrow$ `None`.
   - Updated `format_isp_escalation_email` to render `site contact : will be shared shortly` when `site_contact_phone` is `None`.
   - When escalating without a phone number, `workflow.py` immediately escalates the outage to the ISP, sends a `SITE_PHONE_REQUEST` email on the `BRANCH` thread asking for an active phone number, and logs an `awaiting_site_phone` event so Case B1 relays the number to the ISP as soon as the branch replies.

4. **Gaps 1 & 2 — Live Diagnostics and Real Final Verification (`common/config.py`, `diagnostics/executor.py`, `agent/workflow.py`, `docker-compose.yml`):**
   - Added `DIAGNOSTIC_MODE: Literal["live", "simulated"] = "live"` in `backend/app/common/config.py` with a startup `@model_validator` that refuses to start if `APP_ENV=production` and `DIAGNOSTIC_MODE=simulated` (or `LOOP_GUARD_FAIL_OPEN_FOR_TESTS=true`).
   - Removed the `"AUTO"` and `"PASS"` fallback defaults in `workflow.py`. In `live` mode, both initial diagnostics and final verification execute real OS `ping` and `traceroute` (`LIVE_ICMP`).
   - Restricted `diagnostic_scenario` overrides to `trigger_email_in_loop` when `DIAGNOSTIC_MODE=simulated`; any other override raises a `403` `SupportAgentError`.
   - Added `_check_icmp_execution_error` in `backend/app/diagnostics/executor.py` so missing ICMP binaries or missing `CAP_NET_RAW` permissions raise `DiagnosticExecutionError`, transitioning the ticket to `NEEDS_HUMAN_REVIEW` with `EscalationReason.DIAGNOSTICS_UNAVAILABLE`.
   - Added `cap_add: [NET_RAW]` to `docker-compose.yml`.

5. **Gap 3 — Real `vLLM` Classification, Router-Photo Persistence & Vision (`agent/vllm_client.py`, `email_engine/parser.py`, `agent/classifier.py`, `agent/prompts.py`, `agent/workflow.py`):**
   - Implemented `guided_json(messages, schema, *, images=None)` in `backend/app/agent/vllm_client.py` posting `guided_json` and `response_format` JSON schemas to `vLLM` `/v1/chat/completions`, encoding multimodal `images` as base64 `image_url` parts, validating with Pydantic, retrying `LLM_MAX_RETRIES=3` times with exponential backoff, and raising `LLMInferenceError`.
   - Updated `parse_eml_bytes` in `backend/app/email_engine/parser.py` to persist up to 5 `image/*` attachments ($\le 8\text{ MB}$ each) on disk under `data/attachments/<ticket_number>/<sha256>.<ext>` and store their paths in `Ticket.router_image_paths`.
   - Fixed `extract_branch_sap_code` so WE subjects (`Kazyon #E33209 #6181183#6201898#1251`) take the last `#`-separated 4-digit token (`1251`) and never slice 4 digits out of longer 5–7 digit numbers.
   - Replaced keyword-only classification in `backend/app/agent/classifier.py` with the two-stage pipeline: Stage 1 deterministic rules (Replication Dashboard HTML, `Auto-Submitted`, entity extraction, and D2 header-matched closure fallback) + Stage 2 `guided_json` (`IspResponseAnalysis`, `BranchEmailAnalysis`, and `RouterPhotoVisionAnalysis`).
   - When an email has no `image/*` attachments, `inspect_router_photo` returns `None`, `workflow.py` logs `vision_skipped`, and proceeds directly to ICMP diagnostics.
   - Added `AUTO_ACK` (logs `isp_auto_ack` without starting the 4–6h welcome loop) and `BRANCH_ACTION_BLOCKER` (transitions to `AWAITING_BRANCH_CONTACT` and forwards ISP instructions to Regional IT) handlers in `workflow.py`.
   - Added 3-cycle retry tracking (`_increment_llm_retry_count`) on `LLMInferenceError`, escalating to `NEEDS_HUMAN_REVIEW` with `EscalationReason.LLM_UNAVAILABLE` after 3 failed poll cycles.

---

## 2. Verification & Test Suite

- **Golden `.eml` Regression Suite (`backend/tests/fixtures/info_eml_expected.json`):** Runs all 63 real `.eml` files in `Info/*.eml`. *(Re-audit: the expected labels come from the keyword-based `FakeVllm` in `tests/conftest.py`, not from Gemma, so this suite checks the pipeline wiring, not model accuracy. Replaying the samples against the live vLLM is still outstanding.)*
- **Comprehensive Unit & Integration Tests (`backend/tests/test_critical_agent_gaps.py`, `backend/tests/test_brd_end_to_end.py`, `backend/tests/test_auth_and_rbac.py`, `backend/tests/test_health_and_contracts.py`):** 173 tests passing (`ruff format --check`, `ruff check`, `mypy app/`, `pytest`, and `npm run build`).
