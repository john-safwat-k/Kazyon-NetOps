# IT Network Support AI Agent & Ticketing Harness — Claude Development Rules

> **Claude must read and follow every rule in this file before starting _any_ task.**
> These rules are non-negotiable and apply to **every kind of work** — a new module, an email adapter update, a diagnostic script runner, a Jira-board view, a bug fix, a refactor, a chore, a one-line hot-fix, a spike, or a question whose answer leads to a code change. "It's only a small change" is never grounds to skip a rule.
>
> A task does not end with the code running or an endpoint responding `200`. **A task ends only when the relevant `docs/*.md` files have been updated** to reflect the change (see §21 — Post-Task Documentation Updates). Any PR that changes behaviour without touching the matching docs is incomplete.
>
> Scope: the **IT Network Support AI Agent & Ticketing Harness** — an autonomous network operations backend and Jira-style ticketing web application that receives branch network incident emails, resolves the reporting branch and circuit, runs automated troubleshooting scripts, escalates confirmed outages to the mapped Network Service Provider (ISP), polls/chases the ISP on a schedule until resolved, re-runs diagnostics upon ISP resolution claims, confirms restoration with the branch, and tracks every email, diagnostic test output, and state transition in a Role-Based Access Control (RBAC) web console.
>
> Technology stack: **Python 3.12+, FastAPI (async), SQLAlchemy 2.0, Alembic migrations, Pydantic v2 for schemas/settings, PostgreSQL 16 (`dev` and `prod`) / SQLite (local unit tests only), Redis 7 for caching, distributed locks, and background task queues (Celery / async workers), Self-Hosted LLM (`google/gemma-4-26B-A4B-it` NVFP4 on `vLLM` at `http://10.100.109.9:8002/v1`), pytest, ruff + mypy.** The web UI (Jira-style ticketing board, ticket detail drawer/view, branch/ISP directory, RBAC admin) is **Vite + React 18 + TypeScript + Tailwind CSS**. If the team later deviates from any of these choices, update this file in the same PR — do not let the rules silently drift from reality.

---

## 0. Pre-Task Checklist

Before writing a single line of code, Claude must:

1. Read this file in full.
2. **Create a written plan** for the task — listing every module that will be created or modified, the layer/package it lives in, which architectural contract it touches (`InboundEmailEvent`, `DiagnosticScriptContract`, `LLMClassificationContract`, `TicketStateTransition`), and any decisions made — and **wait for explicit approval** when required before proceeding.
3. **Check `docs/03-api-reference.md`** to confirm the endpoint or webhook being changed doesn't already exist under a different name or path.
4. **Check the relevant package** for the feature (`app/auth/`, `app/directory/`, `app/ticketing/`, `app/email_engine/`, `app/diagnostics/`, `app/agent/`) before adding a new module, schema, or handler. Extend or reuse what's there rather than duplicating it.
5. Grep the codebase for existing services, routers, schemas, and utility modules that already cover the requirement. If something exists, extend or parameterise it rather than reinventing it; justify any new implementation in the walkthrough.
6. State the plan and wait for approval on any destructive or irreversible action (dropping/altering a production table, editing a committed Alembic migration, force-push, deleting generated files, rotating a live credential, changing a **frozen contract** — see §1.1 — in a breaking way, etc.).

---

## 1. Project Structure & Package Organization

The codebase is organised **by architectural domain layer**, with clear boundaries between cross-cutting infrastructure (`common/`), authentication & RBAC (`auth/`), branch/ISP directory (`directory/`), ticketing & timeline (`ticketing/`), email ingestion/dispatch (`email_engine/`), diagnostic script execution (`diagnostics/`), and the autonomous AI agent & scheduler (`agent/`). Do **not** flatten this into one monolithic `controllers/`, `models/` directory.

```
backend/
  app/
    main.py                    FastAPI entrypoint: lifespan, router mounting, WS endpoints — NO business logic here
    common/                    Cross-cutting code shared by every layer
      contracts.py             Frozen contracts: DiagnosticInput/Output, EmailEnvelope, LLM structured schemas (§1.1)
      config.py                Typed settings (pydantic-settings), env-var driven, fail-fast on missing prod secrets
      database.py              SQLAlchemy 2.0 engine/session/Base + JSONVariant (JSONB on Postgres, JSON on SQLite)
      cache.py                 Redis client, cache-aside helpers, distributed branch locks, rate-limit counters
      exceptions.py            Domain exception types + RFC 7807 global exception handler
      logging.py               Structured logging setup + credential/PII redaction filters
      audit.py                 Who/when audit trail helpers for every ticket and admin mutation

    auth/                      Authentication & Permission-Based RBAC layer
      models.py                User, Role, Permission, UserPermission / RolePermission tables
      schemas.py               Login, Token, User, Role, Permission DTOs
      dependencies.py          JWT verification + `require_permission("resource:action")` FastAPI dependency
      service.py               Password hashing, token issuance, Super Admin bootstrap, permission matrix evaluation
      router.py                `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/roles/*`

    directory/                 Branch & Network Provider (ISP) Directory layer
      models.py                Branch, ISP, BranchCircuit models
      schemas.py               Branch/ISP CRUD schemas + Excel/CSV bulk seed preview/result DTOs
      seeder.py                Excel (`.xlsx`) and `.csv` parser and idempotent upsert seeder for branches & ISPs
      service.py               Branch lookup (by email, code, IP, name), ISP escalation mapping
      router.py                `/api/v1/branches/*`, `/api/v1/isps/*`

    ticketing/                 Jira-Style Ticketing System & Timeline layer
      models.py                Ticket, TicketEvent (audit/timeline), TicketEmail, DiagnosticRun
      schemas.py               Kanban card DTOs, TicketDetail full view (updates, test results, req/resp emails)
      state_machine.py         Deterministic ticket lifecycle transitions & SLA timer calculations
      service.py               Ticket CRUD, status transitions, manual override (Pause/Resume AI), timeline logging
      router.py                `/api/v1/tickets/*`

    email_engine/              Inbound Email Polling & Outbound Dispatch layer
      imap_poller.py           Inbound mailbox reader (IMAP / API) with Message-ID deduplication
      smtp_sender.py           Outbound email sender with thread correlation (`In-Reply-To`, `References`, `[NET-XXXX]`)
      parser.py                MIME parsing, reply quote stripping, attachment extraction, Branch vs ISP thread separation
      loop_guard.py            Redis-backed outbound email rate limiter per ticket/recipient (anti-email-storm)

    diagnostics/               Pluggable Network Troubleshooting Script Harness
      base.py                  `DiagnosticRunner` protocol & standardized JSON input/output contract
      executor.py              Sandboxed subprocess/async script runner with strict wall-clock timeouts
      scripts/                 Directory for pluggable network diagnostic scripts (ping, traceroute, SNMP/router checks)
      service.py               Orchestrates script runs, persists `DiagnosticRun` results, emits timeline events

    agent/                     Autonomous AI Support Agent & ISP Follow-up Scheduler
      vllm_client.py           OpenAI-compatible async client targeting `Gemma 4 26B A4B NVFP4` at `10.100.109.9:8002`
      prompts.py               System prompts for branch email triage, ISP response classification, and email drafting
      classifier.py            Guided-JSON structured classification of inbound Branch & ISP emails
      workflow.py              End-to-end autonomous agent state coordinator (Ingest -> Diagnose -> Escalate -> Verify -> Confirm)
      scheduler.py             Proactive ISP follow-up chaser loop & SLA expiration poller

    observability/             Real-time WebSocket event bus for Kanban UI & System Health
      event_bus.py             Broadcasts live ticket updates, diagnostic completions, and email arrivals over `/ws/tickets`

  alembic/                     Alembic database migrations
  scripts/                     Container entrypoint, healthcheck, and operational CLI utilities
  tests/                       Pytest automated test suite
frontend/                      React 18 + Vite + TypeScript + Tailwind CSS Web UI
  src/
    views/                     KanbanBoardView, TicketDetailView, BranchesView, IspsView, UsersRbacView, SettingsView
    components/                TicketCard, TimelineFeed, DiagnosticResultCard, EmailThreadViewer, PermissionMatrix
    lib/                       Typed API client, auth context, WebSocket hook
```

### 1.1 Frozen contracts — treat these as versioned and governed, not as "just another module"

Four contracts are the seams that hold the autonomous harness together. Changing any of them is a **breaking change by default**:

- **`DiagnosticScriptContract`** (`common/contracts.py`) — every troubleshooting script receives a standardized `DiagnosticInput` JSON payload (`branch_id`, `branch_code`, `target_ip`, `circuit_id`, `connection_type`, `extra_meta`) and must output a standardized `DiagnosticOutput` JSON payload (`status`: `PASS | FAIL | DEGRADED | ERROR`, `metrics`, `raw_output`, `summary`, `duration_ms`). Replacing or adding a troubleshooting script in the future must never require changing the ticketing or agent workflow code.
- **`EmailEnvelope` schema** (`common/contracts.py`) — every inbound email from a branch or ISP is normalized into this immutable Pydantic model (`message_id`, `in_reply_to`, `references`, `sender`, `recipients`, `cc`, `subject`, `body_text`, `body_html`, `received_at`, `raw_headers`) before the agent or parser inspects it.
- **`LLMClassificationContract` schemas** (`common/contracts.py`) — Pydantic schemas passed to `vLLM` guided decoding (`BranchEmailAnalysis`, `IspResponseAnalysis`, `DraftedSupportEmail`). The AI agent never parses free-form prose from the LLM to make a state transition decision.
- **`TicketStatus` & `TicketStateTransition` machine** (`ticketing/state_machine.py`) — ticket statuses (`NEW`, `DIAGNOSING`, `ESCALATED_TO_ISP`, `VERIFYING`, `AWAITING_BRANCH_CONFIRMATION`, `NEEDS_HUMAN_REVIEW`, `RESOLVED`, `CLOSED`) and their legal transitions are governed centrally.

### 1.2 Package boundary rules

- Every domain package (`auth/`, `directory/`, `ticketing/`, `email_engine/`, `diagnostics/`, `agent/`) may depend on `common/` freely.
- `common/` never imports from any domain package.
- `diagnostics/` executes scripts and returns `DiagnosticOutput`; it never sends emails or mutates ISP state directly.
- `email_engine/` handles transport, MIME parsing, thread headers, and loop protection; it never decides ticket business logic.
- `agent/` coordinates `directory/`, `diagnostics/`, `email_engine/`, and `ticketing/` through their public `service.py` interfaces — never by mutating another package's SQLAlchemy models directly across boundaries.
- Package-private (`_leading_underscore`) is the default for helper functions not meant to be imported outside a package.

---

## 2. Git Commits

- Create a commit after every completed, working unit of change.
- Commit message format:

  ```
  <type>(<scope>): <short description>

  <body — what changed and why, if non-obvious>

  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

- Valid types: `feat`, `fix`, `refactor`, `docs`, `chore`, `build`, `perf`, `security`.
- Scope is the layer/package: `common`, `auth`, `directory`, `ticketing`, `email-engine`, `diagnostics`, `agent`, `frontend`, `deploy`, `db`, `config`, `docs`.
- Never commit:
  - `.env`, `.env.dev`, `.env.prod`, `certs/`, or any file containing real credentials, passwords, or private keys.
  - `node_modules/`, `.venv/`, `__pycache__/`, `frontend/dist/`, build artifacts.
  - Failing builds (`pytest` + `ruff check` + `mypy` must all pass before committing).
  - Commented-out code — delete instead, git preserves history.
  - A modified, already-applied Alembic migration (see §5 — never edit a migration once it has shipped).
- Never run `--no-verify`, `git push --force` on `main` / `develop`, or `git reset --hard` without explicit user instruction.

---

## 3. Walkthrough History

- After every completed feature module, workflow milestone, or significant refactor, create or update a walkthrough document.
- Location: `docs/walkthroughs/YYYY-MM-DD_<short-slug>.md`
- Each walkthrough file must contain:
  - **Date** of the change.
  - **Summary** — one paragraph describing what was built or changed and why.
  - **Files changed** — every module created or modified, grouped by layer/package.
  - **Contract changes** — did this touch `DiagnosticScriptContract`, `EmailEnvelope`, `LLMClassificationContract`, or `TicketStateTransition`? If yes, call it out explicitly.
  - **API/WebSocket changes** — endpoints added, removed, or altered, and whether `docs/03-api-reference.md` was updated.
  - **Schema changes** — new Alembic migration(s), what they do, backward-compatibility (§5.3).
  - **Security & RBAC impact** — new permissions added to the permission matrix, changed authorization rules, or new script execution surface.
  - **Configuration** — new settings keys, new environment variables in `.env.example` / `.env.dev.example` / `.env.prod.example`.
  - **Known limitations or follow-up tasks** — anything intentionally deferred.
- The walkthrough index at `docs/walkthroughs/README.md` must be updated with a one-line entry linking to the new file.

---

## 4. Secrets, Multi-Environment Configuration & Dual Deployment (`dev` & `prod` on `10.100.109.9`)

- No credential, API key, database password, or mailbox password is ever hardcoded in `app/common/config.py`, any `.env*` committed to the repo, or Python source. Every secret is loaded via `pydantic-settings` from environment variables.
- **Dual-Environment Isolation on `10.100.109.9`:**
  Both `dev` and `prod` environments run on the same server (`10.100.109.9`) with **strictly isolated Docker Compose projects, container names, networks, volumes, and host ports**:
  - **DEV Environment (`./deploy.sh --env dev`):**
    - Compose Project: `it-net-support-dev`
    - Remote Directory: `~/it-network-support-agent-dev`
    - Containers: `it-net-agent-dev`, `it-net-postgres-dev`, `it-net-redis-dev`
    - Volumes: `pgdata_dev`, `redisdata_dev`
    - Exposed Ports: App `8085`, Postgres `5435`, Redis `6385`
  - **PROD Environment (`./deploy.sh --env prod`):**
    - Compose Project: `it-net-support-prod`
    - Remote Directory: `~/it-network-support-agent-prod`
    - Containers: `it-net-agent-prod`, `it-net-postgres-prod`, `it-net-redis-prod`
    - Volumes: `pgdata_prod`, `redisdata_prod`
    - Exposed Ports: App `8084`, Postgres `5434`, Redis `6384`
  - **Shared On-Prem AI Inference (`10.100.109.9:8002`):**
    - Both `dev` and `prod` connect to the `vLLM` server on `http://10.100.109.9:8002` serving `google/gemma-4-26B-A4B-it` (`NVFP4`).
- Provide `.env.example`, `.env.dev.example`, and `.env.prod.example` in the repo with safe placeholders. Never commit `.env`, `.env.dev`, or `.env.prod`.
- If `APP_ENV=production` and any security-critical secret (`SECRET_KEY`, `ENCRYPTION_KEY`, `ADMIN_PASSWORD`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`) is still set to its placeholder default, the application must **fail fast at startup**.

---

## 5. Database, Models & Migrations

### 5.1 Migrations

- Schema changes go through **Alembic** migrations under `backend/alembic/versions/`, one logical schema change per migration, named descriptively (`<rev>_<short_slug>.py`).
- **Never edit a migration file that has already been applied in `dev` or `prod`**. Ship a new migration instead.
- SQLite is acceptable for **local unit tests or offline laptop checks only**. Both `dev` and `prod` deployments on `10.100.109.9` run **PostgreSQL 16** managed by Alembic (`alembic upgrade head` runs automatically inside `deploy.sh` before starting the app container).

### 5.2 Models (SQLAlchemy 2.0)

- One SQLAlchemy `models.py` per domain package (`auth/models.py`, `directory/models.py`, `ticketing/models.py`), all registered in `backend/alembic/env.py`.
- Use `JSONVariant = JSON().with_variant(JSONB, "postgresql")` from `app/common/database.py` for all structured JSON columns (diagnostic metrics, contact email lists, event details, permission sets) so PostgreSQL indexes and stores `JSONB` natively while local SQLite tests continue to work seamlessly.
- Every model carries `created_at` and `updated_at` as timezone-aware UTC timestamps (`datetime.now(timezone.utc)`).

### 5.3 Zero-Downtime Migrations

- Never combine a column removal/rename with the release that stops using it.
- Adding a `NOT NULL` column to an existing table requires a `server_default` or a backfill step in the migration.

### 5.4 Queries

- Any query returning a list that can grow unbounded (tickets list, email logs, diagnostic runs, audit timeline) must support pagination (`limit` / `offset` or cursor).

---

## 6. Autonomous Agent & Deterministic Workflow Rules

Every ticket lifecycle follows strict guardrails combining LLM intelligence with deterministic state transitions:

```
Inbound Email (Branch or ISP)
      |
Email Engine (MIME parse, Message-ID dedup, Thread correlation)
      |
AI Classifier (vLLM Gemma 4 26B A4B -> Guided JSON Schema)
      |
Deterministic Workflow Engine (ticketing/state_machine.py + agent/workflow.py)
      |---> Diagnostic Harness (sandboxed script execution -> JSON output)
      |---> Outbound Email Dispatch (ISP escalation / ISP chaser / Branch confirmation)
      |---> Ticket Timeline & WebSocket Broadcast (/ws/tickets)
```

### Rules

- **Never let a free-form LLM loop directly mutate ticket status or send arbitrary emails.** The LLM (`Gemma 4 26B A4B` on `vLLM`) is called with structured JSON output schemas (`LLMClassificationContract`) to classify intent, extract entities (branch code, ISP ticket reference, ETA), summarize raw logs, and draft email bodies. The Python workflow engine validates the structured output and executes deterministic state transitions.
- **Strict Separation of Branch and ISP Email Threads:** Every ticket tracks two distinct communication channels: `BRANCH_THREAD` and `ISP_THREAD`. Outbound ISP escalations and automated ISP chasers must never CC the branch unless explicitly configured, and raw ISP internal replies are logged to the ticket timeline before any branch communication is triggered.
- **Anti-Email-Storm Loop Protection:** `email_engine/loop_guard.py` must enforce a Redis-backed rate limit per ticket (e.g., max $N$ outbound emails per ticket per hour) and ignore auto-responders (`Auto-Submitted` headers) from re-triggering state transitions.
- **Manual Override ("Pause AI"):** Every ticket has an `ai_automation_enabled: bool` flag. When an engineer pauses AI on a ticket via the UI, the background agent and ISP chaser scheduler must skip autonomous actions on that ticket while still logging inbound emails to the ticket's detail view.

---

## 7. DTOs & Schemas (Pydantic v2)

- Request/response/internal-message schemas are **Pydantic v2 models**, never raw dicts passed across layer boundaries.
- Never return a SQLAlchemy ORM instance directly from a FastAPI router — always serialize through an explicit Pydantic response schema (`model_config = ConfigDict(from_attributes=True)`).
- Never include `password_hash`, raw SMTP/IMAP credentials, or internal encryption keys in any response schema.

---

## 8. API & WebSocket Conventions

- Base path: `/api/v1/<resource>` for all REST APIs; `/api/health` for container and deployment health checks; `/ws/tickets` for real-time Kanban board and ticket detail live updates.
- Every endpoint (except `/api/health` and `/api/v1/auth/login`) must enforce authentication AND granular permission checks via `Depends(require_permission("<module>:<action>"))`.
- Every router module lives in `<package>/router.py`, paired 1:1 with `<package>/service.py` holding the business logic. Routers stay thin.
- **When adding or changing an endpoint**, the same commit/PR must update `docs/03-api-reference.md`.

---

## 9. Validation & Troubleshooting Script Sandboxing

- All inbound API payloads, Excel/CSV branch seed rows, and LLM JSON responses are validated via Pydantic v2.
- **Troubleshooting Script Execution Guardrails (`diagnostics/executor.py`):**
  - Diagnostic scripts run in isolated subprocesses with a strict wall-clock timeout (`DIAGNOSTIC_TIMEOUT_SEC`, default `60s`), restricted environment variables (no DB passwords or app secret keys leaked into child script `os.environ`), and validated arguments (IP/hostname/circuit format validation to prevent shell command injection — always use `asyncio.create_subprocess_exec` with an argument list, **never** `shell=True`).

---

## 10. Error Handling

- All errors returned from the REST API use a structured problem-detail JSON shape produced from a single global FastAPI exception handler in `common/exceptions.py` — never expose raw Python stack traces in HTTP responses.
- Domain exceptions (`EntityNotFoundError`, `DuplicateResourceError`, `InvalidStateTransitionError`, `PermissionDeniedError`, `DiagnosticExecutionError`, `LLMInferenceError`, `EmailDeliveryError`) live in `common/exceptions.py`.
- If `vLLM` (`10.100.109.9:8002`) is temporarily unreachable or times out, the agent must catch `LLMInferenceError`, log a timeline warning on the ticket, and schedule a retry or flag the ticket `NEEDS_HUMAN_REVIEW` — never drop an inbound branch or ISP email on the floor.

---

## 11. Security, Authentication & Permission-Based RBAC

- **Granular Permission Matrix:** Access control is permission-based (`resource:action`), not hardcoded role names. The Super Admin (`is_super_admin = True`) bypasses permission checks and can create/manage users, roles, and assign individual permissions (`tickets:view`, `tickets:edit_status`, `tickets:pause_ai`, `diagnostics:trigger_manual`, `emails:send_manual_reply`, `branches:import_sheet`, `users:edit_permissions`, etc.).
- **No Secrets in Logs:** `common/logging.py` automatically scrubs Bearer tokens, passwords, secret keys, and sensitive credentials from all log lines.
- **Audit Trail:** Every manual or AI-driven action on a ticket (`status_changed`, `diagnostic_triggered`, `email_sent`, `ai_paused`, `user_permissions_updated`) is recorded in `ticket_events` / audit logs with actor identity and UTC timestamp.

---

## 12. Logging

- Structured logging via `common/logging.py` only.
- Include `ticket_id` / `ticket_number` and `branch_code` in log context wherever applicable so engineers can trace a ticket's full journey across email ingestion $\rightarrow$ `vLLM` classification $\rightarrow$ diagnostic script $\rightarrow$ ISP escalation.

---

## 13. Timestamps & Timezones

- Persist every timestamp as timezone-aware UTC (`datetime` with `tzinfo=timezone.utc`, Postgres `timestamptz`).
- Return ISO-8601 UTC strings from the API; the React frontend renders timestamps in the user's or branch's local timezone (`Africa/Cairo` by default).

---

## 14. Configuration & Client Conventions

- All configuration lives in `app/common/config.py` via `pydantic-settings` (`Settings` class cached via `@lru_cache`). Do not scatter raw `os.getenv()` calls across domain packages.
- The `vLLM` client (`agent/vllm_client.py`) uses a shared, connection-pooled `httpx.AsyncClient` initialized and closed cleanly in the FastAPI lifespan — never instantiate a new `httpx.AsyncClient` per request.

---

## 15. Async & Concurrency

- FastAPI routes, the `vLLM` client, the diagnostic subprocess executor, and the background scheduler are `async` throughout.
- Any blocking I/O (such as synchronous `imaplib`/`smtplib` or Excel parsing with `openpyxl`/`pandas`) must run in a thread executor (`asyncio.to_thread`) so it never blocks the main FastAPI event loop or WebSocket broadcasts.
- Use Redis distributed locks (`common/cache.py`) when polling emails or running diagnostic scripts for a ticket/branch so multiple workers never execute duplicate diagnostics or send duplicate ISP escalations simultaneously.

---

## 16. Performance & Caching

- Redis (`common/cache.py`) caches frequently read, rarely mutated lookups (e.g., user permission sets, branch/ISP lookup tables) with explicit cache invalidation on mutation.
- Redis outage degrades gracefully to direct PostgreSQL reads for cache lookups (fail-open for read caches, fail-safe for email loop guards).

---

## 17. Dead Code & Module Boundary Enforcement

- Remove unused imports, unused private functions, and dead code immediately.
- Every commit must pass `ruff check`, `mypy`, and `pytest` cleanly.

---

## 18. Code Style

- Run before every commit:

  ```bash
  cd backend
  ruff format <the files this change touched>
  ruff check <the files this change touched>
  mypy app/
  pytest
  ```

- `ruff.toml` at the repo root pins `line-length = 100` and `target-version = "py312"`.
- `backend/mypy.ini` sets `explicit_package_bases = True` and `mypy_path = .`. Do not remove it.
- Type hints are mandatory on every function signature in `backend/app/`.
- Naming: `PascalCase` for classes, `snake_case` for functions/variables/modules, `UPPER_SNAKE_CASE` for constants.
- No wildcard imports (`from module import *`).

---

## 19. Build, Run & Multi-Environment Deployment

```bash
# Local development (Backend :8000 + Frontend :5173)
./run.sh dev

# Automated tests
./run.sh test

# Deploy to DEV environment on 10.100.109.9 (isolated containers: it-net-*-dev, port 8085)
./deploy.sh --env dev

# Deploy to PROD environment on 10.100.109.9 (isolated containers: it-net-*-prod, port 8084)
./deploy.sh --env prod

# Check status or logs for a specific environment on 10.100.109.9
./deploy.sh --env dev --status
./deploy.sh --env prod --logs
```

---

## 20. Check Before Building

Before implementing any new requirement:

1. Read `docs/01-project-overview.md` for the architecture and environment baseline.
2. Read `docs/02-database-schema.md` if the task touches SQLAlchemy models or Alembic migrations.
3. Read `docs/03-api-reference.md` if the task adds or modifies REST endpoints or WebSockets.
4. Read `docs/04-security-and-rbac.md` if the task touches permissions, auth, or script sandboxing.
5. Read `docs/05-deployment-dev-prod.md` if the task touches Docker, `deploy.sh`, or environment variables.
6. Grep the codebase for existing modules covering the requirement before creating new ones.

---

## 21. Post-Task Documentation Updates

**Every task — feature, bug fix, refactor, schema change, deployment tweak — ends with a documentation update.** No exceptions.

"The code runs" is not "the task is done". The task is done when the docs match reality.

### What to update, always

1. **Project overview (`docs/01-project-overview.md`).** New module, architectural component, or configuration variable.
2. **Database schema (`docs/02-database-schema.md`).** New Alembic migration, table, or column.
3. **API reference (`docs/03-api-reference.md`).** New, changed, or removed REST endpoint or WebSocket event.
4. **Security & RBAC (`docs/04-security-and-rbac.md`).** New granular permission, role rule, or script sandboxing rule.
5. **Deployment guide (`docs/05-deployment-dev-prod.md`).** Any change to `deploy.sh`, `docker-compose.yml`, ports, container names, or `.env` templates.
6. **Documentation index (`docs/README.md`).** New `docs/*.md` file → add a link under the appropriate section.
7. **Walkthrough (`docs/walkthroughs/YYYY-MM-DD_<slug>.md`).** Required for every non-trivial task (§3). Update `docs/walkthroughs/README.md`.

### Docs-update verification

Before committing:

```bash
git status docs/     # expect changes matching the task
git diff docs/       # quick review of the doc edits
```

---

## Quick Reference — Mandatory Actions Per Task

| Task Type | Plan & Check | Migration | Validation | Error Handling | Security / RBAC | Logging Check | Commit | Walkthrough | Docs Update |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| New domain feature / endpoint | ✅ | If it needs state | ✅ | ✅ | ✅ (`require_permission`) | ✅ | ✅ | ✅ Create | ✅ `03-api-reference.md` + `02-database-schema.md` |
| Diagnostic script / runner change | ✅ | If schema-related | ✅ (strict I/O) | ✅ (timeout) | ✅ (no `shell=True`) | ✅ | ✅ | ✅ Create | ✅ `01-project-overview.md` + `04-security-and-rbac.md` |
| Email engine / AI agent workflow | ✅ | If schema-related | ✅ (Guided JSON) | ✅ (loop guard) | ✅ (thread isolation) | ✅ | ✅ | ✅ Create | ✅ `01-project-overview.md` |
| New RBAC permission / role rule | ✅ | If seeded | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ Update | ✅ `04-security-and-rbac.md` |
| Deployment / Docker / Env change | ✅ | — | — | — | ✅ (no secrets committed) | — | ✅ | ✅ Update | ✅ `05-deployment-dev-prod.md` + `.env*.example` |
| Bug fix / Refactor | ✅ | If related | If related | If related | If related | If related | ✅ | ✅ Update | ✅ Whichever doc was affected |
