# Fix Plan: Critical Gaps in the Autonomous Agent Flow

**Date:** 2026-10-22
**Status:** Draft. Awaiting approval; no code changed yet.
**Source:** End-to-end audit of `backend/app/agent/workflow.py` against BRD v5.0 §4 (`plans/00-master-brd-and-roadmap.md`).

This plan fixes the six gaps that stop the agent from working on real mail. The other logic bugs found in the audit are listed at the end; several are fixed as a side effect of Gap 6.

---

## Decisions needed before starting

| # | Decision | Recommendation |
|---|---|---|
| D1 | Can the app container on `10.100.109.9` reach branch routers (`10.x.x.1/.2`) and run `ping`/`traceroute`? This needs the binaries in the image and `cap_add: NET_RAW`. | Confirm network reachability from the host first. Then add the binaries and the capability to both compose projects. |
| D2 | What happens when vLLM is down or returns invalid JSON? | Retry 3 times with backoff and log a timeline warning. If it still fails, set `NEEDS_HUMAN_REVIEW` with reason `LLM_UNAVAILABLE`. Deterministic rules can act alone only for high-precision triggers: Replication Dashboard subject, `Auto-Submitted`, and a header/`[NET-XXXX]` match combined with a regex-certain ISP closure. |
| D3 | Where are router photos stored? The parser currently discards the image bytes and keeps only the size. | Store them on disk in a new Docker volume, `data/attachments/<ticket_number>/<sha256>.<ext>`. Paths go into the existing `Ticket.router_image_paths` JSON column, so no migration is needed. |
| D4 | What does the loop guard do when Redis is unreachable? | Fail-safe, as CLAUDE.md §16 requires: block the send and record it as blocked. The per-process in-memory fallback is removed, because it does not protect a multi-worker deployment. |
| D5 | What if the branch email has no site phone number? | Escalate immediately with `site contact : will be shared shortly` and ask the sender for a phone number in the same step. When the reply arrives, the existing relay step (B1) forwards it. A full outage is never held back waiting for a phone number. |
| D6 | Gap 6 changes the **frozen** `TicketStateTransition` contract. Enforcement is additive, but existing code paths that currently "work" will start raising errors. | Approve the enforcement. Manual engineer overrides (UI drag-and-drop, `tickets:edit_status`) get a separate `force=True` path that is audited, not blocked. |

---

## Order of work

Each step is one commit and must pass `ruff`, `mypy` and `pytest`.

1. **Gap 6: State machine.** Every later step routes its status changes through this.
2. **Gap 4: Loop guard.**
3. **Gap 5: Made-up phone number.**
4. **Gaps 1 and 2: Live diagnostics and real final verification.**
5. **Gap 3: Real vLLM classification and vision.** This is the largest step.
6. Docs and walkthrough.

---

## Gap 6: Enforce ticket state transitions

**Problem:** `state_machine.py` only maps statuses to Kanban columns. Status is written directly 24 times across `agent/workflow.py`, `agent/scheduler.py` and `ticketing/service.py`, with no legality check. This also means `agent/` mutates `ticketing` models directly, which breaks CLAUDE.md §1.2.

**Changes**
- `ticketing/state_machine.py`: add `ALLOWED_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]]`, derived from BRD §4.1. Draft:
  - `AWAITING_REGIONAL_IT` → `DIAGNOSING`, `NEEDS_HUMAN_REVIEW`, `CLOSED`
  - `NEW`/`DIAGNOSING` → `AWAITING_BRANCH`, `INTERNAL_LAN_ISSUE`, `ESCALATED_TO_ISP`, `CLOSED`, `NEEDS_HUMAN_REVIEW`
  - `AWAITING_BRANCH` → `DIAGNOSING`, `NEEDS_HUMAN_REVIEW`, `CLOSED`
  - `INTERNAL_LAN_ISSUE` → `DIAGNOSING`, `CLOSED`, `NEEDS_HUMAN_REVIEW`
  - `ESCALATED_TO_ISP` → `AWAITING_BRANCH_CONTACT`, `VERIFYING`, `NEEDS_HUMAN_REVIEW`
  - `AWAITING_BRANCH_CONTACT` → `ESCALATED_TO_ISP`, `NEEDS_HUMAN_REVIEW`
  - `VERIFYING` → `CLOSED`, `RESOLVED`, `ESCALATED_TO_ISP`, `NEEDS_HUMAN_REVIEW`
  - `NEEDS_HUMAN_REVIEW` → any (human-driven)
  - `RESOLVED` → `CLOSED`
  - `CLOSED` → (none; re-opening creates a new ticket)
- Add `assert_transition(current, target)`, which raises `InvalidStateTransitionError` (already in `common/exceptions.py`).
- `ticketing/service.py`: add a public `transition_ticket(db, ticket, target, *, actor_type, actor_name, reason, force=False)`. It validates the transition, sets `status`, `resolved_at` and `next_followup_at` side effects, writes a `status_changed` `TicketEvent`, and emits the WebSocket event.
- Replace all 24 direct `.status =` writes with `transition_ticket(...)`. The UI and API status endpoint use `force=True`, which is audited.
- Workflow: catch `InvalidStateTransitionError`, log a timeline warning, and do **not** send that step's email. This stops two bugs:
  - The B1 contact relay firing on a `DIAGNOSING` ticket.
  - A repeat branch email re-escalating a ticket that is already `ESCALATED_TO_ISP`. In that state, B3 becomes "log and attach to the timeline".

**Tests:** one table-driven test over every legal and illegal pair. Workflow tests for "contact update on a DIAGNOSING ticket" (no ISP email) and "second branch email on an escalated ticket" (no second escalation).

---

## Gap 4: Make the loop guard actually block

**Problem:** `dispatch_outbound_email` ignores the `bool` returned by `check_and_increment_outbound_allowance`.

**Changes**
- `email_engine/loop_guard.py`: return `False` when Redis is unavailable (D4) and remove `_in_memory_counters`. Keep a test-only override through settings (`LOOP_GUARD_FAIL_OPEN_FOR_TESTS`, which is rejected when `APP_ENV=production`).
- `email_engine/smtp_sender.py`: if the guard returns `False`, skip SMTP. Still persist the `TicketEmail` row with `ai_analysis_json.blocked_by_loop_guard = true` and `smtp_live_sent = false`, so the attempt shows in the email log.
- Workflow and scheduler: when a send is blocked, add an `email_blocked` timeline event. After the second block on the same ticket within an hour, transition to `NEEDS_HUMAN_REVIEW` with reason `LOOP_GUARD_TRIPPED`, a new `EscalationReason` value that is additive.
- While here: run `smtplib` through `asyncio.to_thread` (CLAUDE.md §15). This makes `dispatch_outbound_email` async; all its callers are already async apart from `run_sla_chaser_cycle`, which becomes async too.
- On SMTP failure, raise or record `EmailDeliveryError` instead of a silent warning, and add an `email_delivery_failed` timeline event.

**Tests:** guard limit hit leads to no SMTP call, a recorded blocked row and a timeline event. Redis down leads to a blocked send. The MAX_OUTBOUND+1 send triggers the human escalation.

---

## Gap 5: Never send a made-up site phone number

**Problem:** `workflow.py:464` defaults `site_contact_phone` to `"010 2345 8817"`, which then goes to the ISP.

**Changes**
- Remove the literal. Resolve the phone in this order: the triage result, then the most recent phone on the ticket's BRANCH thread, then `None`.
- `email_engine/smtp_sender.format_isp_escalation_email`: when the phone is `None`, render `site contact : will be shared shortly`, following D5.
- Workflow: when escalating without a phone, also email the sender on the BRANCH thread asking for an active number. Record `awaiting_site_phone=true` in the timeline. The existing B1 relay then sends the number to the ISP when it arrives.
- Remove the matching made-up defaults in `trigger_email_in_loop` scenario bodies only when they would reach real recipients. The harness keeps them because it is test-only.

**Tests:** a branch email with no phone produces an escalation body with no phone digits plus a branch request for a phone. A later reply with a phone produces the relay.

---

## Gaps 1 and 2: Live diagnostics and real final verification

**Problem:** the autonomous flow defaults to `simulate_scenario="AUTO"`, which derives the result from branch-code digits. Final verification defaults to `"PASS"`, so every ISP closure closes the ticket.

**Changes**
- `common/config.py`: add `DIAGNOSTIC_MODE: Literal["live", "simulated"]`. Default `live`. Fail fast at startup if `APP_ENV=production` and the mode is `simulated`.
- `agent/workflow.py`:
  - Remove the `"AUTO"` and `"PASS"` defaults. The production path (`run_email_loop_cycle_once` and `.eml` upload) passes `simulate_scenario=None`, which `diagnostics/service.py` maps to `LIVE_ICMP` when the mode is `live`.
  - `diagnostic_scenario` overrides are honoured only from `trigger_email_in_loop`, the test harness, and only when the mode is `simulated`. Otherwise the request is refused with a 403 problem-detail.
- `diagnostics/executor.py`: keep the simulation code, but reach it only through an explicit scenario. Remove `KNOWN_BRANCH_SCENARIOS` and the digit-based `_resolve_scenario` fallback from the default path.
- Final verification (FR-6.5): close only when IP1 and IP2 are both UP, **and**, for ORANGE/WE, the traceroute does not pass through the 4G hub. Today `diagnosis_code == PASS` already encodes this, which the tests will confirm.
- If ICMP binaries or permissions are missing, `DiagnosticExecutionError` produces a timeline warning and `NEEDS_HUMAN_REVIEW` with reason `DIAGNOSTICS_UNAVAILABLE`. It never falls back to simulation.
- Deployment (D1): add `iputils-ping` and `traceroute` to the backend image, and `cap_add: [NET_RAW]` to `it-net-agent-dev` and `it-net-agent-prod`.

**Tests:** inject a fake runner for `run_live_ping`/`run_live_traceroute` and cover:
- IP1 down → escalate
- IP1 up + IP2 down on NOOR → LAN issue
- ORANGE via hub → escalate
- ORANGE not via hub → LAN issue
- ISP closure with IP1 still down → rejected closure and no close
- Production config with `simulated` mode → startup failure

The existing `test_brd_end_to_end.py` keeps running with `DIAGNOSTIC_MODE=simulated` set in `conftest.py`.

---

## Gap 3: Real vLLM classification and router-photo vision

**Problem:** `classifier.py` is keyword rules only, and the "vision" check reads filenames and two hardcoded branch codes. `vllm_client.py` and `prompts.py` are unused. Replaying the 65 `Info/*.eml` files showed missed closures (WE `RE-8368058`), a missed branch-action blocker (`RE-8389062`), and wrong branch codes (`243981` read as 1000, `#6181183…#1251` read as 1183).

**Contracts:** use the existing frozen schemas **unchanged**: `BranchEmailAnalysis`, `IspResponseAnalysis` (which already has `AUTO_ACK`, `BRANCH_ACTION_BLOCKER` and `RESOLUTION_CLAIM`) and `RouterPhotoVisionAnalysis`. `UniversalEmailTriageResult` stays the workflow's input. No contract edits.

**Changes**
- `agent/vllm_client.py`: add `async def guided_json(messages, schema: type[BaseModel], *, images: list[bytes] | None = None) -> BaseModel`. It posts to `/v1/chat/completions` with `guided_json=schema.model_json_schema()` (or `response_format` json_schema), sends images as base64 `image_url` parts, validates the reply with Pydantic, and retries per D2. On final failure it raises `LLMInferenceError`.
- `email_engine/parser.py`: keep the image bytes for `image/*` parts (max 5 images, 8 MB each) and persist them per D3. The `EmailEnvelope` attachment dicts gain a `stored_path` key. The `attachments` field is a `list[dict]`, so this is additive.
- `agent/prompts.py`: tighten the prompts with the real NOOR/ORANGE/WE phrasings from BRD §3.2. This includes the intent definitions for `BRANCH_ACTION_BLOCKER` ("restart router / reset SIM / connect cable on port"), `AUTO_ACK` versus `ISP_WELCOME`, and the special blockers.
- `agent/classifier.py` becomes a two-stage pipeline:
  1. **Deterministic stage**, which stays in code: sender to party (ISP domain, Regional IT mailbox, replication), `Auto-Submitted`, Replication Dashboard, and entity extraction (ticket tag, ISP ref, circuit ID, phone).
  2. **LLM stage:** `IspResponseAnalysis` for ISP mail and `BranchEmailAnalysis` for branch mail. Then map them to `UniversalEmailTriageResult`, using the model's real `confidence` against `settings.confidence_threshold`, so low confidence goes to `UNRECOGNIZED` and then human review.
  - Delete the filename and hardcoded-branch vision heuristic. `inspect_router_photo` sends the stored image bytes with `ROUTER_PHOTO_VISION_PROMPT`. No image means "no vision verdict": the timeline says so and the flow goes straight to diagnostics, as the BRD allows when only a code and phone are given.
- **Branch-code extraction fix** (`parser.extract_branch_sap_code`):
  - Prefer the branch of a correlated ticket.
  - For WE subjects (`Kazyon #E33209 #<LL> #<3G> #<SAP>`), take the last `#`-separated 4-digit token.
  - Never take 4 digits out of a longer number such as `6181183` or `243981`.
  - Cross-check the extracted code against `Branch.ll_circuit_id`/`backup_circuit_id`. If they conflict, use the circuit match.
- Workflow additions for the new intents:
  - `BRANCH_ACTION_BLOCKER`: relay the ISP's instructions to the sender on the BRANCH thread and set `AWAITING_BRANCH_CONTACT`. The branch reply is relayed back.
  - `AUTO_ACK`: log only. This does **not** set `isp_welcome_received`, because BRD Step 4 needs a case number.
- `LLMInferenceError` in ingest: store the inbound email, add a `llm_unavailable` timeline event, and queue a retry. Retry state goes in Redis with a key per `message_id`, picked up by the next loop cycle. After 3 failed cycles, set `NEEDS_HUMAN_REVIEW` (CLAUDE.md §10). The email is never dropped.
- Related fix in the same commit: in `scheduler.run_email_loop_cycle_once`, wrap each message's ingest in its own try/except and rollback. One bad email must not abort the batch and leave the rest marked Seen in IMAP.

**Tests**
- A `FakeVllm` fixture that returns recorded JSON, so CI never calls `10.100.109.9`.
- A **golden regression test** over all 65 `Info/*.eml` files, with the expected `(trigger_type, intent, branch_code, isp_ref)` per file in `tests/fixtures/info_eml_expected.json`. The recorded LLM outputs are captured once against the live dev vLLM and checked in.
- Vision: pass and fail images, plus the no-image path.
- vLLM timeout produces a retry and then human review, with the email row persisted.
- Low confidence routes to human review.

---

## Out of scope here (follow-up phase)

These come from the same audit and are tracked separately:
- The branch "resolution confirmation" keyword match closes on "not restored". It is replaced by `BranchEmailAnalysis.is_resolution_confirmation` in Gap 3 and closes only after a verification ping.
- ISP_RESOLVED with no matched branch is silent. After Gap 3 it should go to human review.
- `followup_count` should reset after the Welcome email, so the 2h and 4–6h chasers have separate retry budgets.
- Redis locks per ticket/branch around diagnostics and escalation, and a lock-safe `_next_ticket_number` (CLAUDE.md §15). `common/cache.py` has no lock helper yet.
- Chasers for `AWAITING_BRANCH_CONTACT`, `AWAITING_BRANCH` and `AWAITING_REGIONAL_IT` that stall.

---

## Schema, config and docs impact

- **Migrations:** none planned. All new state lives in existing JSON columns or Redis. The new `EscalationReason` values are strings in an existing `String` column.
- **New settings and env vars** (`.env.example`, `.env.dev.example`, `.env.prod.example`):
  - `DIAGNOSTIC_MODE`
  - `ATTACHMENTS_DIR`
  - `LLM_MAX_RETRIES`
  - `LLM_REQUEST_TIMEOUT_SEC`
  - `LOOP_GUARD_FAIL_OPEN_FOR_TESTS` (test only)
- **Deployment:** `NET_RAW` capability, ping and traceroute packages, and an attachments volume for each environment.
- **Docs:**
  - `01-project-overview.md`: classifier pipeline and diagnostic mode.
  - `03-api-reference.md`: harness scenario overrides limited to simulated mode.
  - `04-security-and-rbac.md`: `NET_RAW`, attachment storage, and the `force` status override.
  - `05-deployment-dev-prod.md`: compose and image changes.
  - Walkthrough `docs/walkthroughs/2026-10-22_critical-agent-gaps.md`, plus the walkthroughs `README.md` index.
