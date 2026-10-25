# Walkthrough — Re-Audit Fixes for the Autonomous Agent Flow

**Date:** 2026-10-22
**Task slug:** `reaudit-agent-fixes`
**Follows:** [`2026-10-22_critical-agent-gaps.md`](2026-10-22_critical-agent-gaps.md)

---

## Summary

A re-audit of the critical-gaps work against BRD v5.0 §4 found five remaining bugs. This change fixes all five:
1. Emails deferred while vLLM was down were never retried, because IMAP had already marked them Seen.
2. A vLLM failure during the router-photo check crashed the ingest, and the scheduler's rollback lost the email.
3. An ISP closure arriving while the ticket was `AWAITING_BRANCH_CONTACT` was blocked by the state machine, so the ticket was stuck.
4. ORANGE/WE final verification skipped the 4G-hub traceroute when both pings passed.
5. The loop guard had two problems: all ticketless mail shared one `GLOBAL` counter, and `smtp_sender` changed ticket status directly, bypassing the state machine.

## Files changed

**`agent/`**
- `workflow.py`:
  - Queues deferred emails for retry.
  - Catches `LLMInferenceError` from `inspect_router_photo` and continues to diagnostics.
  - Reports `blocked_by_loop_guard` on each outbound record, and calls `apply_loop_guard_trip` before commit.
  - New `record_failed_ingest()`.
- `scheduler.py`:
  - Calls `record_failed_ingest()` after a rolled-back ingest.
  - Calls `apply_loop_guard_trip()` when a chaser is blocked.

**`email_engine/`**
- `imap_poller.py`: new `enqueue_llm_retry_eml()` and `_consume_llm_retry_queue_sync()`. `poll_inbound_mailbox_raw()` now also returns queued emails whose backoff has passed.
- `smtp_sender.py`:
  - Mail with no ticket uses the loop-guard key `NO-TICKET:<In-Reply-To or recipients>`.
  - The status change on a trip moved out to `ticketing/service.apply_loop_guard_trip`. The sender only records the block.

**`ticketing/`**
- `state_machine.py`: `AWAITING_BRANCH_CONTACT → VERIFYING` is now allowed.
- `service.py`:
  - New `apply_loop_guard_trip()`, which uses `transition_ticket` and is never forced.
  - The Human Review list now includes ticketless `LLM_UNAVAILABLE` and `INGEST_FAILED` emails.

**`diagnostics/`**
- `executor.py`: new `verify_local_loop` flag. When both IPs are up on an ORANGE/WE branch, it runs a traceroute to `IP1`, and a 4G hub in the path gives `LOCAL_LOOP_DOWN_ON_4G`.
- `service.py`: passes `verify_local_loop=True` for `FINAL_VERIFICATION` runs.

**`common/`**
- `config.py`: `llm_retry_queue_dir` and `llm_retry_backoff_sec`.
- `contracts.py`: `EscalationReason.INGEST_FAILED`.

**`tests/`**
- `test_reaudit_fixes.py` (new, 10 tests).
- `test_critical_agent_gaps.py`: the loop-guard test now escalates through `apply_loop_guard_trip`.

**Config and docs**
- `.env.example`, `.env.dev.example`, `.env.prod.example`
- `docs/01-project-overview.md`, `docs/03-api-reference.md`, `docs/04-security-and-rbac.md`, `docs/05-deployment-dev-prod.md`
- This walkthrough and the index entry. Corrections were added to `2026-10-22_critical-agent-gaps.md`.

## Contract changes

- **`TicketStateTransition`:** one added legal transition, `AWAITING_BRANCH_CONTACT → VERIFYING`. The change is additive; no existing transition was removed.
- **`DiagnosticScriptContract`:** unchanged. `verify_local_loop` is an executor keyword, not part of `DiagnosticInput`/`DiagnosticOutput`.
- **`EmailEnvelope`, `LLMClassificationContract`:** unchanged.
- **`EscalationReason`** (not a frozen contract): added `INGEST_FAILED`.

## API / WebSocket changes

No endpoints were added or removed. Changed behaviour is documented in `docs/03-api-reference.md`:
- `POST /api/v1/emails/poll-now` also drains the vLLM retry queue and records crashed ingests as `INGEST_FAILED`.
- `POST /api/v1/emails/trigger`: each `outbound_emails` item now has `blocked_by_loop_guard`.
- `GET /api/v1/escalations` can return the reason `INGEST_FAILED`, and lists ticketless `LLM_UNAVAILABLE` emails.

## Schema changes

None. There is no Alembic migration. The retry queue lives on disk, and new labels and reasons are values in existing string columns.

## Security & RBAC impact

- No new permissions.
- The loop-guard trip now goes through `transition_ticket`, so it can no longer reopen a `CLOSED` ticket and is logged as a normal `status_changed` event.
- Ticketless mail is rate-limited per inbound message instead of through one shared counter.

## Configuration

| Key | Default | Purpose |
| :--- | :--- | :--- |
| `LLM_RETRY_QUEUE_DIR` | `./data/imports/llm_retry` (`/app/data/imports/llm_retry` in dev/prod) | Where deferred raw `.eml` files wait for vLLM |
| `LLM_RETRY_BACKOFF_SEC` | `300` | Minimum wait before a queued email is re-ingested |

## Verification

- `pytest`: 183 passed, including the 10 new tests.
- `ruff check` and `mypy app/` pass.
- Mutation check: reverting the bug 3 or bug 4 fix makes the matching new tests fail.

## Known limitations / follow-ups

- **Gemma accuracy is still unverified.** The golden `Info/*.eml` suite runs against the keyword-based `FakeVllm`. Replaying the 63 samples against the live vLLM at `10.100.109.9:8002` (it was unreachable from the development machine) and saving the real outputs as the fixture is still outstanding. The replay should also confirm vLLM accepts `guided_json` and `response_format` together.
- **Retry count fallback is per process.** With Redis unavailable, the retry counter falls back to process memory, so a restart resets it. The queued file itself is durable.
- **Not part of this change** (from the earlier fix plan's follow-up list):
  - A branch "resolution confirmation" still closes the ticket without a verification ping.
  - `followup_count` is not reset after the Welcome email.
  - No Redis locks around diagnostics/escalation.
  - Stalled `AWAITING_BRANCH_CONTACT` / `AWAITING_BRANCH` / `AWAITING_REGIONAL_IT` tickets are not chased.
  - A ticket created directly from an ISP closure email (`DIAGNOSING → VERIFYING`) is still blocked.
