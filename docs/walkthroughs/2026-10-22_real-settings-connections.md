# Walkthrough — Real Connection Tests on Page 12, and the Agent Using the Saved Settings

**Date:** 2026-10-22
**Task slug:** `real-settings-connections`

---

## Summary

An audit of Page 12 (AI Agent, Mailbox & SLA Settings) found that its connection test was fake:
- The backend always returned `{"status": "ok", "label": "IMAP ✓ · SMTP ✓"}`, even for a host that does not exist.
- The page showed ✓ even when the request failed.
- The vLLM card's `412 ms` was hardcoded text.

Most of the settings saved on the page were also never used. The SMTP sender, the vLLM client, diagnostics and the loop guard all read `.env` instead.

The system uses SMTP only, so this change:
1. Replaces the fake test with a real SMTP session test and a real vLLM test.
2. Makes the agent run with the saved settings.
3. Supports an unauthenticated internal relay as well as an authenticated server.
4. Adds an explicit "Send real email" switch, which is off by default.

## Files changed

**`email_engine/`**
- `smtp_sender.py`:
  - New `SmtpTransportConfig`, built from `system_settings` plus the optional environment login.
  - `_open_smtp_session` does connect → EHLO → STARTTLS/SSL → login. It raises an error naming the step that failed.
  - New `test_smtp_connection_sync` runs that session, then `MAIL FROM` + `RSET`, and sends nothing.
  - Sending uses the saved host, port, mode and sender address, skips sending while `smtp_enabled` is off, and takes the loop-guard limit from the saved settings.
- `imap_poller.py`: removed the fake `_test_imap_smtp_sync` / `test_mailbox_connectivity`.

**`agent/`**
- `vllm_client.py`:
  - One connection pool per endpoint (`get_vllm_http_client(base_url)`).
  - `VllmCallOptions` (endpoint, temperature, max tokens).
  - `normalize_vllm_base_url`.
  - `probe_vllm_endpoint`, which replaces `check_vllm_health`.
- `classifier.py`: `classify_inbound_email` and `inspect_router_photo` take `llm_options`.
- `workflow.py`: new `vllm_call_options(settings_row)`, passed to every LLM call.

**`diagnostics/`**
- `base.py`: `ping_count` and `traceroute_max_hops` are now optional.
- `service.py`: values a request leaves unset come from the saved timeout, ping count and max hops.

**`ticketing/`**
- `models.py`: `SystemSettings.smtp_security` and `smtp_enabled`.
- `schemas.py`:
  - `SystemSettingsUpdateRequest` (validated).
  - `SmtpConnectionTestRequest/Result`, `VllmConnectionTestRequest/Result`.
  - `SystemSettingsDto` gains `smtp_security`, `smtp_enabled`, `smtp_credentials_configured`.
- `service.py`: typed `update_system_settings` (the audit entry lists changed fields), `test_smtp_settings`, `test_vllm_settings`, and vLLM seed values taken from the environment.
- `router.py`: `PUT /settings` takes the typed request. `POST /settings/test-smtp` and `POST /settings/test-vllm` replace `test-connection`.

**`common/`**
- `config.py`: removed `smtp_host`, `smtp_port`, `smtp_use_tls` and `smtp_from_address` (now on Page 12).

**`main.py`**
- Removed the unauthenticated `GET /api/v1/system/vllm-status`.
- The dev SQLite bootstrap adds the two new columns.

**`alembic/`**
- `0004_smtp_security_and_enable.py` (new).

**`frontend/`**
- `lib/api.ts`: new types and `testSmtp` / `testVllm`.
- `views/SettingsView.tsx`, Outbound email (SMTP) card:
  - "Send real email" switch.
  - Sender address, host and port fields.
  - Security mode select, which follows the standard port.
  - Read-only login status.
  - Real test with a pass/fail badge and the server reply.
  - Removed the IMAP fields and the dummy password field.
- `views/SettingsView.tsx`, vLLM card: real test with latency and model check.

**`tests/`**
- `test_settings_connections.py` (new, 26 tests). It uses an in-process SMTP server and a mocked vLLM transport.

**Config and docs**
- `.env.example`, `.env.dev.example`, `.env.prod.example`
- `docs/01`–`05`, this walkthrough and the index.
- `.claude/launch.json` (local preview config).

## Contract changes

None of the four frozen contracts changed.

## API / WebSocket changes

All documented in `docs/03-api-reference.md`:
- **Added:** `POST /api/v1/settings/test-smtp`, `POST /api/v1/settings/test-vllm`.
- **Removed:**
  - `POST /api/v1/settings/test-connection` (always returned OK).
  - `GET /api/v1/system/vllm-status` (no authentication; not used by the UI).
- **Changed:**
  - `PUT /api/v1/settings` now validates its body and returns `422` for invalid values.
  - `SystemSettingsDto` has three new fields.

## Schema changes

`0004_smtp_security_and_enable` adds:
- `system_settings.smtp_security` (`VARCHAR(16)`, server default `starttls`)
- `system_settings.smtp_enabled` (`BOOLEAN`, server default `false`)

It is additive with server defaults, so it is zero-downtime safe.

## Security & RBAC impact

- Both tests require `settings:read`.
- The SMTP login stays in the environment. It is never stored in the database or returned; only a `smtp_credentials_configured` boolean is exposed.
- Removed one unauthenticated endpoint.
- Real sending is off by default, so a fresh or `dev` install cannot email ISPs by accident.

## Configuration

- **No longer read:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_FROM_ADDRESS`. They are removed from the templates; existing `.env` files can drop them.
- **Still used:** `SMTP_USERNAME` / `SMTP_PASSWORD` (optional).
- **Seed values only:** `VLLM_BASE_URL`, `VLLM_TEMPERATURE` and `VLLM_MAX_TOKENS` set the first `system_settings` row. After that, Page 12 is the source of truth.

## Verification

- `pytest`: 209 passed. `ruff check` and `mypy app/` pass. `npm run build` passes.
- Manual check in the running dev app (`run.sh dev`):
  - Saved `smtp.office365.com:587` STARTTLS with no login failed at **Sender refused**: `530 5.7.57 Client not authenticated to send mail`.
  - A local relay on `127.0.0.1:2525` with security None passed.
  - "Test vLLM" passed in 186 ms, with `google/gemma-4-26B-A4B-it` served at `10.100.109.9:8002`.
  - The test values were not saved.

## Known limitations / follow-ups

- *(Resolved by [`2026-10-22_inbound-smtp-listener.md`](2026-10-22_inbound-smtp-listener.md): the agent now has its own SMTP listener.)* **Inbound mail is still open.** With SMTP only, the agent reads mail only from the `.eml` dropbox (`data/imports/inbox/`) and the vLLM retry queue. The IMAP poller code remains, but it is unused while `IMAP_*` is empty. How branch and ISP mail reaches the agent is still to be decided.
- **The Dashboard health bar** ("vLLM … Healthy", "IMAP / SMTP Mailbox … Healthy") looks hardcoded and was not changed here.
