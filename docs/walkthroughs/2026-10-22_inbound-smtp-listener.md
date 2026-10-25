# Walkthrough — Inbound SMTP Listener (Mail Server → Agent)

**Date:** 2026-10-22
**Task slug:** `inbound-smtp-listener`

---

## Summary

The system uses SMTP only, with no IMAP mailbox, so until now the agent could only receive mail through `.eml` files dropped into `data/imports/inbox/`. This change adds a small built-in SMTP listener so the company mail server can forward branch and ISP mail straight to the agent.

The listener only does transport:
1. It accepts a message from an allowed IP, addressed to an allowed recipient.
2. It writes the message durably into the existing inbound dropbox before answering `250`.
3. It wakes the poller.

Ingestion is unchanged, so forwarded mail gets Message-ID dedup, the vLLM retry queue and the `INGEST_FAILED` safety net like any other mail.

The listener is hand-written on `asyncio` streams (about 300 lines, receive-only RFC 5321 subset), so no new dependency was added. It is off by default.

## Files changed

**`email_engine/`**
- `smtp_listener.py` (new):
  - `InboundSmtpListener`: EHLO/HELO, MAIL, RCPT, DATA, RSET, NOOP, QUIT. `STARTTLS` and `AUTH` return `502`.
  - Client-IP allowlist (`554` on connect) and recipient allowlist (`550`).
  - Limits on size (`SIZE` / `552`), recipients, connections and time.
  - Strict CRLF DATA (`550 5.6.0`; SMTP-smuggling safe), dot-unstuffing.
  - Durable write (fsync, then rename), plus `Received:` / `X-Kz-Envelope-*` headers.
  - `start_inbound_smtp_listener` / `stop_inbound_smtp_listener` / `get_listener_status`. A bind failure is reported in the status and does not crash the app.
- `imap_poller.py`: new shared `inbound_dropbox_dir()`; the poller and the listener use the same folder.

**`agent/`**
- `scheduler.py`:
  - `request_immediate_poll()`: the poll loop now waits on an event with the poll interval as timeout, so a received message is ingested at once.
  - `get_email_loop_status` includes `smtp_listener`.

**`common/`**
- `config.py`: `SMTP_LISTENER_*` settings. When the listener is enabled, startup fails if the allowed-clients list is empty or invalid, or is `0.0.0.0/0` in production.

**`main.py`**
- The lifespan starts and stops the listener, with the poller wake-up as callback.

**`frontend/`**
- `lib/api.ts`: `SmtpListenerStatusDTO`.
- `views/SettingsView.tsx`: new read-only **Inbound email (SMTP listener)** card on Page 12. It shows Off / Listening / Not running, allowed clients, counts, the last message and any error, and has a Refresh button.

**Deploy**
- `docker-compose.yml` publishes `${SMTP_LISTENER_PUBLISH_PORT}:${SMTP_LISTENER_PORT}`.
- `deploy.sh` pins `SMTP_LISTENER_PUBLISH_PORT` (`dev` 2525, `prod` 2524).
- `.env.example`, `.env.dev.example`, `.env.prod.example` have the new keys.

**`tests/`**
- `test_smtp_listener.py` (new, 17 tests), driven by `smtplib` and raw sockets:
  - accepted mail is stored and wakes the poller
  - IP refusal and recipient refusal
  - oversize mail
  - command order
  - the smuggling attempt
  - listener → poller → ticket end to end
  - disabled by default, port already in use, status, recipient default, config validation

**Docs**
- `docs/01`, `03`, `04`, `05`, this walkthrough and the index.

## Contract changes

None. Forwarded mail is parsed into the same `EmailEnvelope` by the existing poller.

## API / WebSocket changes

- `GET /api/v1/emails/loop-status` adds `smtp_listener`.
- New non-HTTP interface: the SMTP listener, documented in `docs/03-api-reference.md` with its reply codes.

## Schema changes

None.

## Security & RBAC impact

A new unauthenticated network port that can lead to tickets and ISP escalations. Mitigations:
- off by default
- client-IP allowlist, enforced at connect; invalid or empty lists, and "everyone" in production, are refused at startup
- recipient allowlist
- size, recipient, connection and time limits
- strict CRLF against SMTP smuggling
- the host firewall should also restrict the port

Forwarded mail is still untrusted input: it goes through the classifier and the state machine like any other email. No new permissions; the status is visible under the existing `emails:view` / settings pages.

## Configuration

| Key | Default | Purpose |
| :--- | :--- | :--- |
| `SMTP_LISTENER_ENABLED` | `false` | Turn the listener on |
| `SMTP_LISTENER_HOST` / `SMTP_LISTENER_PORT` | `0.0.0.0` / `2525` | Bind address and port inside the container |
| `SMTP_LISTENER_PUBLISH_PORT` | `2525` (`dev`) / `2524` (`prod`) | Host port published by docker-compose (pinned by `deploy.sh`) |
| `SMTP_LISTENER_ALLOWED_CLIENTS` | `127.0.0.1/32` | IPs/CIDRs of the forwarding mail server |
| `SMTP_LISTENER_ALLOWED_RECIPIENTS` | empty = Page 12 sender address | Accepted `RCPT TO` addresses |
| `SMTP_LISTENER_MAX_MESSAGE_MB` | `25` | Message size limit |
| `SMTP_LISTENER_HOSTNAME` | `netops-agent.kazyon.local` | Name used in the greeting and the `Received:` header |

## Verification

- `pytest`: 226 passed. `ruff check` and `mypy app/` pass. `npm run build` passes.
- In the running dev app, `loop-status` reports `smtp_listener: {enabled: false, running: false}`, and the Page 12 card shows **Off** with setup instructions.
- The listening state was exercised by the tests: real `smtplib` client → listener → dropbox → poller → ticket.

## Known limitations / follow-ups

- **No TLS or AUTH.** It is meant for a single internal mail server on a trusted network. Add STARTTLS if forwarding ever crosses an untrusted network.
- **One listener per container.** The app runs one uvicorn process. If it ever runs several workers, only the first binds the port; the others report it in their status.
- **Not yet tried with the real mail server.** The Exchange / mail-server routing and the firewall rule on `10.100.109.9` still need to be set up by the mail admin (see `docs/05-deployment-dev-prod.md`).
