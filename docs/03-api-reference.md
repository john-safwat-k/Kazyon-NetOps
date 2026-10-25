# 03 — API & WebSocket Reference

## Health & System Status

### `GET /api/health`
- **Auth:** Public (used by Docker healthcheck and `deploy.sh`)
- **Response (`200 OK`):** Service status, environment slug (`dev` / `prod`), version, and `vLLM` model metadata.

> `GET /api/v1/system/vllm-status` was removed (it had no authentication). Use `POST /api/v1/settings/test-vllm`.

---

## Executive & SLA Dashboard (`/api/v1/dashboard`)

### `GET /api/v1/dashboard/summary`
- **Auth:** `require_permission("tickets:view")`
- **Query Params:** `range` (`24h` | `7d` | `30d`, default `7d`)
- **Response (`200 OK`):** `DashboardSummaryResponse` containing the 5 live KPI counts (`open`, `review`, `welcome`, `followup`, `repl`), health services bar, 4 chart series (`by_isp`, `mttr_by_isp`, `by_type`, `by_region`), and urgent `watchlist` rows.

---

## Ticketing, Kanban Board & 360° Detail (`/api/v1/tickets`)

### `GET /api/v1/tickets`
- **Auth:** `require_permission("tickets:view")`
- **Query Params:** `search`, `isp`, `region`, `priority`, `trigger`, `failure_type`, `ai_paused_only`
- **Response (`200 OK`):** `list[KanbanTicketCardDto]` mapped to the 8 Kanban columns (`col: 0..7`).

### `POST /api/v1/tickets`
- **Auth:** `require_permission("tickets:edit_status")`
- **Body:** `TicketCreateManualRequest` (`branch_code`, `priority`, `site_contact_phone`, `trigger_source`, `description`, `run_diagnostics`)
- **Response (`201 Created`):** `KanbanTicketCardDto`

### `GET /api/v1/tickets/{ticket_identifier}`
- **Auth:** `require_permission("tickets:view")`
- **Response (`200 OK`):** `TicketDetail360Response` (full 360° ticket view including SLA timer, Branch & ISP metadata, Gemma 4 Vision verdict, chronological `events`, `diagnostic_runs`, `branch_emails`, and `isp_emails`).

### `PATCH /api/v1/tickets/{ticket_identifier}`
- **Auth:** `require_permission("tickets:edit_status")`
- **Body:** `TicketStatusUpdateRequest` (`status`, `priority`, `ai_automation_enabled`, `isp_reference_number`, `site_contact_phone`, `kanban_col`)
- **Response (`200 OK`):** `TicketDetail360Response`

### `POST /api/v1/tickets/{ticket_identifier}/notes`
- **Auth:** `require_permission("tickets:view")`
- **Body:** `{"note": "..."}`
- **Response (`200 OK`):** `TicketDetail360Response`

### `POST /api/v1/tickets/{ticket_identifier}/rerun-diagnostics`
- **Auth:** `require_permission("diagnostics:trigger_manual")`
- **Response (`200 OK`):** Executes immediate Dual-Ping + 4G Hub Traceroute for the ticket's branch and returns updated `TicketDetail360Response`.

### `POST /api/v1/tickets/{ticket_identifier}/force-followup`
- **Auth:** `require_permission("emails:force_isp_followup")`
- **Response (`200 OK`):** Sends an immediate follow-up chaser email on the ISP thread and resets the 4–6h SLA timer.

### `POST /api/v1/tickets/{ticket_identifier}/reply`
- **Auth:** `require_permission("emails:send_manual_reply")`
- **Body:** `{"thread_type": "BRANCH" | "ISP", "body_text": "...", "subject": "..."}`
- **Response (`200 OK`):** `TicketDetail360Response`

### `POST /api/v1/tickets/{ticket_identifier}/escalate`
- **Auth:** `require_permission("tickets:edit_status")`
- **Body:** `{"target_email": "noc-oncall@kazyon.com", "reason": "OTHER", "note": "..."}`
- **Response (`200 OK`):** Transitions ticket to `NEEDS_HUMAN_REVIEW`, pauses AI automation, emails the full incident report, and returns `TicketDetail360Response`.

### `POST /api/v1/tickets/{ticket_identifier}/override-vision`
- **Auth:** `require_permission("tickets:edit_status")`
- **Body:** `{"cables_plugged": true, "summary": "..."}`
- **Response (`200 OK`):** `TicketDetail360Response`

---

## Replication Dashboard Monitor (`/api/v1/replication`)

### `GET /api/v1/replication/reports`
- **Auth:** `require_permission("replication:view")`
- **Response (`200 OK`):** List of ingested `Replication Dashboard - <Date>` reports and their store breakdown rows.

### `POST /api/v1/replication/parse`
- **Auth:** `require_permission("replication:upload")`
- **Body:** `{"subject": "...", "html_content": "...", "dry_run": true}`
- **Response (`200 OK`):** Parses the HTML table for `Not Updated` stores and either previews (`dry_run=true`) or creates `AWAITING_REGIONAL_IT` tickets (`dry_run=false`).

---

## Human Review & Escalations (`/api/v1/escalations`)

### `GET /api/v1/escalations`
- **Auth:** `require_permission("tickets:view")`
- **Response (`200 OK`):** `list[EscalationItemDto]` (`QUOTA_CONSUMED`, `MSAN_MIGRATION`, `INTERNAL_BOX_CABLE`, `UNRECOGNIZED_EMAIL`, `MAX_RETRIES`, `LOOP_GUARD_TRIPPED`, `LLM_UNAVAILABLE`, `DIAGNOSTICS_UNAVAILABLE`, `INGEST_FAILED`).
- Emails with no ticket are listed when they are `UNRECOGNIZED`, or when they are inbound `HUMAN_ESCALATION` rows labelled `LLM_UNAVAILABLE` (vLLM failed on every retry cycle) or `INGEST_FAILED` (the agent crashed while processing them). Their `reason` is that label.

### `POST /api/v1/escalations/convert-email/{email_id}`
- **Auth:** `require_permission("tickets:edit_status")`
- **Response (`200 OK`):** Converts an unmatched `UNRECOGNIZED` email from the Human Review Queue into a tracked `Ticket` (`status="NEEDS_HUMAN_REVIEW"`, `trigger_source="UNKNOWN_ESCALATION"`).

---

## Mailbox & Email Triage (`/api/v1/emails`)

### `GET /api/v1/emails`
- **Auth:** `require_permission("emails:view")`
- **Response (`200 OK`):** Inbound and outbound service account email log with Gemma 4 JSON classifications, thread type (`BRANCH` / `ISP` / `HUMAN_ESCALATION`), `In-Reply-To` correlation, and raw RFC-5322 headers.

### `GET /api/v1/emails/loop-status`
- **Auth:** `require_permission("emails:view")`
- **Response (`200 OK`):** Live telemetry for the background Email Agent Harness Loop and SLA Chaser worker (`background_loop_running`, `global_ai_kill_switch`, `poll_interval_sec`, `last_poll_at`, `seconds_since_last_poll`, `poll_count`, `inbound_count`, `outbound_count`, `open_isp_threads_count`, `awaiting_branch_threads_count`).

- `smtp_listener` (added): `{ enabled, running, host, port, allowed_clients, messages_accepted, messages_rejected, connections_refused, last_received_at, last_error }`. It is `{ "enabled": false, "running": false }` while the listener is off.

### `POST /api/v1/emails/poll-now`
- **Auth:** `require_permission("emails:view")`
- **Response (`200 OK`):** Immediately polls the local `.eml` dropbox (`data/imports/inbox/`) and the vLLM retry queue (`LLM_RETRY_QUEUE_DIR`; only emails whose `LLM_RETRY_BACKOFF_SEC` backoff has passed). It ingests new messages through the autonomous workflow and runs the 2h Welcome SLA & 4–6h ISP follow-up chaser cycle. A message whose ingest crashes is stored as `INGEST_FAILED` and reported to the human engineer instead of being dropped.

### `POST /api/v1/emails/trigger`
- **Auth:** `require_permission("emails:view")`
- **Body:** `{"scenario": "BRANCH_INCIDENT" | "CABLE_UNPLUGGED_PHOTO" | "REGIONAL_IT_CABLE_FIXED" | "ISP_WELCOME" | "ISP_CONTACT_UNREACHABLE" | "REGIONAL_IT_NEW_PHONE" | "ISP_RESOLVED" | "ISP_RESOLVED_STILL_DOWN" | "ISP_QUOTA_BLOCKER" | "REPLICATION_REPORT" | "CUSTOM", "branch_code": "2009", "ticket_number": "NET-...", "in_reply_to": "<...>", "diagnostic_scenario": "AUTO"}`
- **Response (`200 OK`):** Constructs an RFC-5322 `.eml` with full thread headers (`Message-ID`, `In-Reply-To`, `References`), correlates to the existing ticket/branch, runs Gemma 4 classification + Dual-Ping/Traceroute diagnostics, dispatches autonomous outbound replies (`BRANCH` / `ISP` / `HUMAN_ESCALATION`), and returns the full execution trace (`outbound_emails`, `actions_taken`, `correlation_method`, `ticket_status`). Each `outbound_emails` item includes `blocked_by_loop_guard` (`true` when the anti-storm guard stopped the send).

### `POST /api/v1/emails/{email_id}/reclassify`
- **Auth:** `require_permission("emails:view")`
- **Response (`200 OK`):** Re-runs Gemma 4 26B classification on an existing `TicketEmail` record.

### `GET /api/v1/emails/info-samples`
- **Auth:** `require_permission("emails:view")`
- **Response (`200 OK`):** Lists the `.eml` files in `Info/` for one-click simulation in the console.

### `POST /api/v1/emails/simulate-eml`
- **Auth:** `require_permission("emails:view")`
- **Params / Multipart:** Either `file` (`.eml` upload) or `sample_filename` query parameter.
- **Response (`200 OK`):** Parses and triages the `.eml` through the full autonomous workflow.

---

## Network Diagnostics Sandbox (`/api/v1/diagnostics`)

### `GET /api/v1/diagnostics/sandbox-catalog`
- **Auth:** `require_permission("diagnostics:view_logs")`
- **Response (`200 OK`):** Featured branches, 3G/4G hub IP mappings (`ORANGE`: `10.247.8.1`, `WE`: `172.16.70.33, 172.17.20.33`, `NOOR`: no traceroute), and recent sandbox runs.

### `GET /api/v1/diagnostics/runs`
- **Auth:** `require_permission("diagnostics:view_logs")`
- **Response (`200 OK`):** `list[DiagnosticRunResponse]`

### `POST /api/v1/diagnostics/run`
- **Auth:** `require_permission("diagnostics:trigger_manual")`
- **Body:** `DualPingTracerouteRequest` (`branch_code`, `ip_1`, `ip_2`, `isp_name`, `mode`, `simulate_scenario`, `timeout_sec`, `ping_count`, `traceroute_max_hops`)
- **Response (`200 OK`):** `DiagnosticRunResponse` (`PASS`, `FULL_OUTAGE`, `LOCAL_LOOP_DOWN_ON_4G`, `INTERNAL_LAN_SWITCH`) with step-by-step decision tree cards (`steps`), `diagnosis_title`, `root_cause`, `responsible_team`, `ai_workflow_action`, and `operator_action`.

### `POST /api/v1/diagnostics/run-suite`
- **Auth:** `require_permission("diagnostics:trigger_manual")`
- **Body:** `DiagnosticSuiteRunRequest` (`isp_name`, `region`, `search`, `simulate_scenario`, `ping_count`, `traceroute_max_hops`, `limit`)
- **Response (`200 OK`):** `DiagnosticSuiteReportResponse` executing the full Dual-Ping (`IP 1` + `IP 2`) + `ORANGE`/`WE` 4G Hub Traceroute suite across all matching directory branches and returning fleet KPIs (`pass_count`, `full_outage_count`, `four_g_count`, `lan_switch_count`, `health_pct`), per-ISP summaries (`by_isp`), per-Region summaries (`by_region`), and branch-by-branch detailed results (`items`).

---

## Branches & ISP Directory (`/api/v1/branches`, `/api/v1/isps`)

### `GET /api/v1/branches`
- **Auth:** `require_permission("branches:view")`
- **Query Params:** `search`, `region`, `isp_name`, `is_active`, `limit`, `offset`
- **Response (`200 OK`):** `BranchListResponse` (1,150 stores, region counts, ISP counts).

### `GET /api/v1/branches/derive-ips/{branch_code}`
- **Auth:** `require_permission("branches:view")`
- **Response (`200 OK`):** `{"branch_code": "2009", "ip_1": "10.20.9.1", "ip_2": "10.20.9.2"}`

### `GET /api/v1/branches/by-code/{branch_code}`
- **Auth:** `require_permission("branches:view")`
- **Response (`200 OK`):** `BranchResponse`

### `POST /api/v1/branches`, `PATCH /api/v1/branches/{branch_id}`, & `DELETE /api/v1/branches/{branch_id}`
- **Auth:** `require_permission("branches:create")` / `require_permission("branches:edit")` / `require_permission("branches:delete")`
- **Response:** `BranchResponse` (`204 No Content` on delete)

### `POST /api/v1/branches/seed-excel`
- **Auth:** `require_permission("branches:import_sheet")`
- **Query Params:** `dry_run` (`true` | `false`), `replace_existing` (`true` | `false`, default `false`)
- **Multipart Form (optional):** `file` (`.csv`, `.xlsx`, or `.xls`). Supports header-mapped columns (`SAP Code`, `Branch Name`, `ISP`, `L.L Circuit ID`, `3G / Backup ID`, `IP 1 (Router)`, `IP 2 (Switch)`, `Region`, `Regional IT Email`) as well as positional Columns A–K. If `file` is omitted, seeds from `Info/Copy of All store ISP (2).xlsx`.
- **Response (`200 OK`):** `SeedResultSummary` (with `preview_rows`, `created_count`, `updated_count`, `unchanged_count`, `deleted_count`, `by_isp`, `by_region`, and `warnings`).

### `GET /api/v1/branches/template`
- **Auth:** `require_permission("branches:view")`
- **Query Params:** `format` (`csv` | `xlsx`, default `csv`)
- **Response (`200 OK`):** Downloadable CSV or Excel branch upload template with sample rows for `NOOR`, `ORANGE`, and `WE`.

### `GET /api/v1/branches/export`
- **Auth:** `require_permission("branches:view")`
- **Query Params:** `format` (`csv` | `xlsx`, default `csv`), `search`, `region`, `isp_name`, `is_active`
- **Response (`200 OK`):** Downloadable CSV or Excel sheet containing all matching branches.

### `GET /api/v1/isps` & `PUT /api/v1/isps/{isp_id_or_name}`
- **Auth:** `require_permission("branches:view")` / `require_permission("isps:manage")`
- **Response (`200 OK`):** `list[IspResponse]` / `IspResponse`

---

## AI Agent, Mailbox & SLA Settings (`/api/v1/settings`)

These are the settings the agent actually runs with:
- Outbound mail uses the SMTP host, port, security mode, sender address (`mailbox_account`), "send real email" switch (`smtp_enabled`) and per-ticket email limit.
- vLLM calls use the endpoint, temperature and max tokens.
- Diagnostics use the timeout, ping count and traceroute max hops whenever a request does not set them.
- Only the optional SMTP login (`SMTP_USERNAME` / `SMTP_PASSWORD`) stays in the environment.

### `GET /api/v1/settings`
- **Auth:** `require_permission("settings:read")`
- **Response (`200 OK`):** `SystemSettingsDto`. It includes `smtp_security` (`starttls` | `ssl` | `none`), `smtp_enabled`, and `smtp_credentials_configured` (`true` when the environment login is set; the values are never returned).

### `PUT /api/v1/settings`
- **Auth:** `require_permission("settings:update")`
- **Request:** `SystemSettingsUpdateRequest`. All fields are optional, and omitted fields keep their value.
- **Validation:** out-of-range values give `422`. For example: port outside 1–65535, `smtp_security` not one of the three modes, a `vllm_endpoint` that is not `http(s)://`, `diagnostic_timeout_sec` outside 2–60, or temperature outside 0–2.
- **Response (`200 OK`):** `SystemSettingsDto`. The change is recorded in `audit_logs` (`settings.updated`) with the list of changed fields.

### `POST /api/v1/settings/test-smtp`
- **Auth:** `require_permission("settings:read")`
- **Request (optional):** `{ "smtp_host", "smtp_port", "smtp_security" }`. These are unsaved form values; omitted fields use the saved settings.
- **Behaviour:** Opens a real SMTP session: connect, EHLO, STARTTLS or SSL, login (only when the environment login is set), then `MAIL FROM:<sender>` followed by `RSET`. No email is sent.
- **Response (`200 OK`):** `SmtpConnectionTestResult` `{ ok, host, port, security, authenticated, credentials_configured, stage, latency_ms, server_banner, error }`.
  - `stage` is the step that failed: `config` (no host), `connect`, `ehlo`, `tls`, `auth` (login rejected), or `sender` (server refuses our sender, for example Office 365 `530 5.7.57 Client not authenticated`).
  - On success `stage` is `done`.

### `POST /api/v1/settings/test-vllm`
- **Auth:** `require_permission("settings:read")`
- **Request (optional):** `{ "vllm_endpoint" }`. Accepts `http://host:8002` or `http://host:8002/v1`; omitted uses the saved endpoint.
- **Behaviour:** Calls `GET /v1/models`.
- **Response (`200 OK`):** `VllmConnectionTestResult` `{ ok, endpoint, configured_model, model_available, available_models, latency_ms, error }`. `ok` is `true` only if the server answers and serves `DEFAULT_WORKER_MODEL`.

> `POST /api/v1/settings/test-connection` and `POST /api/v1/settings/test-imap` were removed (the system uses SMTP only).

### `POST /api/v1/settings/send-test-email` (`settings:update`)
Sends a live test email through the configured SMTP server (`mail.kazyon.com:587` as `noc@kazyon.com`) into the target inbox so the operator can verify outbound SMTP delivery.
- **Request:** `{"recipient"?: str, "subject"?: str, "body_text"?: str, "branch_code"?: str}`
- **Response:** `{"ok": bool, "recipient": str, "subject": str, "message_id": str, "latency_ms": int, "error": str|null}`

---

## Inbound SMTP Listener (not HTTP)

The agent can receive mail directly over SMTP from the company mail server. See `docs/05-deployment-dev-prod.md` for setup.

- **Address:** `<agent host>:2525` on `dev`, `:2524` on `prod` (container port `SMTP_LISTENER_PORT`, default 2525). Only answers when `SMTP_LISTENER_ENABLED=true`.
- **Commands:** `EHLO`/`HELO`, `MAIL FROM`, `RCPT TO`, `DATA`, `RSET`, `NOOP`, `QUIT`, `VRFY` (`252`). `STARTTLS`, `AUTH`, `BDAT`, `ETRN` and `EXPN` return `502`. EHLO advertises `SIZE` and `8BITMIME`.
- **Replies the mail server may see:**

| Reply | When |
| :--- | :--- |
| `554 5.7.1` | On connect: the client IP is not in `SMTP_LISTENER_ALLOWED_CLIENTS` |
| `421 4.3.2` | More than 20 simultaneous connections |
| `550 5.1.1` | The recipient is not accepted |
| `452 4.5.3` | More than 50 recipients |
| `552 5.3.4` | Message larger than `SMTP_LISTENER_MAX_MESSAGE_MB` (or `SIZE=` announces it) |
| `550 5.6.0` | Bare LF or CR in DATA |
| `503` | Command out of order |
| `250 2.0.0` | Message written to the inbound dropbox; it is ingested on the next poll, which runs immediately |

- **Stored message:** the original message, preceded by a `Received:` header and `X-Kz-Envelope-From` / `X-Kz-Envelope-To`.

---

## Authentication, Users & Roles (`/api/v1/auth`, `/api/v1/users`, `/api/v1/roles`)
- `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/change-password`, `GET /api/v1/auth/permissions`, `GET /api/v1/auth/audit-logs`
- `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{id}`, `PUT /api/v1/users/{id}/permissions`, `POST /api/v1/users/{id}/reset-password`
- `GET /api/v1/roles`, `POST /api/v1/roles`, `PUT /api/v1/roles/{slug}`, `DELETE /api/v1/roles/{slug}`

---

## Real-Time WebSocket Stream (`/ws/tickets`)
- Broadcasts JSON envelopes (`ticket.created`, `ticket.updated`, `diagnostic.completed`, `email.ingested`) to connected console clients.
