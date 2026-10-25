# 05 — Multi-Environment Deployment Guide (`dev` & `prod` on `10.100.109.9`)

## 1. Environment Isolation Matrix
Both `dev` and `prod` environments run side-by-side on `10.100.109.9` using isolated Docker Compose project names, container names, bridge networks, volumes, and host ports:

| Setting | DEV (`--env dev`) | PROD (`--env prod`) |
| :--- | :--- | :--- |
| **Remote Path** | `~/it-network-support-agent-dev` | `~/it-network-support-agent-prod` |
| **Compose Project (`-p`)** | `it-net-support-dev` | `it-net-support-prod` |
| **App Container** | `it-net-agent-dev` | `it-net-agent-prod` |
| **Postgres Container** | `it-net-postgres-dev` | `it-net-postgres-prod` |
| **Redis Container** | `it-net-redis-dev` | `it-net-redis-prod` |
| **Docker Network** | `it-net-network-dev` | `it-net-network-prod` |
| **Docker Volumes** | `it-net-pgdata-dev`, `it-net-redisdata-dev` | `it-net-pgdata-prod`, `it-net-redisdata-prod` |
| **Web / API Host Port** | `8085` | `8084` |
| **Postgres Host Port** | `5435` | `5434` |
| **Redis Host Port** | `6385` | `6384` |
| **vLLM Endpoint** | `http://10.100.109.9:8002` | `http://10.100.109.9:8002` |
| **Linux Capability (`cap_add`)** | `NET_RAW` (live `ping` & `traceroute`) | `NET_RAW` (live `ping` & `traceroute`) |
| **Attachments Volume** | `./data/attachments:/app/data/attachments` | `./data/attachments:/app/data/attachments` |
| **Diagnostic Mode** | `DIAGNOSTIC_MODE=live` | `DIAGNOSTIC_MODE=live` (enforced at startup) |
| **Inbound SMTP Listener Host Port** | `2525` (`SMTP_LISTENER_PUBLISH_PORT`) | `2524` (`SMTP_LISTENER_PUBLISH_PORT`) |
| **vLLM Retry Queue** | `LLM_RETRY_QUEUE_DIR=/app/data/imports/llm_retry`, `LLM_RETRY_BACKOFF_SEC=300` | `LLM_RETRY_QUEUE_DIR=/app/data/imports/llm_retry`, `LLM_RETRY_BACKOFF_SEC=300` |

The retry queue lives under the `./data:/app/data` bind mount, so emails waiting for vLLM survive a container restart or redeploy.

**Inbound IMAP & Outbound SMTP (Gmail Testing or Kazyon Exchange) are configured on Page 12.**
- You can switch between **Gmail Testing (`imap.gmail.com:993` SSL + `smtp.gmail.com:587` STARTTLS)** and **Kazyon Exchange (`mail.kazyon.com`)** directly on Page 12 (**AI & SLA Settings**) using the **Mail Provider Quick Presets** bar.
- To test with **Gmail**:
  1. Generate a 16-character **Google App Password** in your Google Account (`Security → 2-Step Verification → App passwords`).
  2. On Page 12, click **Use Gmail for Testing (`imap.gmail.com`)**.
  3. Enter your Gmail address in **IMAP Username** and your 16-character App Password in **IMAP Password**, then click **Copy Gmail login to Outbound SMTP →** (which also sets **Safe Test Redirect Email** to your Gmail address so real ISPs are never emailed).
  4. Click **Save all changes**, then verify connectivity with **Test IMAP connection**, **Test SMTP connection**, and **Send live test email to Inbox**.
- Migration `0005_gmail_and_redirect` runs automatically in `deploy.sh` (`alembic upgrade head`).

**Receiving branch / ISP mail (inbound SMTP listener).** The company mail server forwards mail for the agent's address to the agent over SMTP.
1. In the environment's `.env`:
   - Set `SMTP_LISTENER_ENABLED=true`.
   - Set `SMTP_LISTENER_ALLOWED_CLIENTS` to the mail server's IP (comma-separate several).
   - Optionally set `SMTP_LISTENER_ALLOWED_RECIPIENTS` (default: the Page 12 sender address).
   - `deploy.sh` pins `SMTP_LISTENER_PUBLISH_PORT` to 2525 (`dev`) or 2524 (`prod`).
2. Open the published port on `10.100.109.9` for the mail server's IP only (host firewall).
3. On the mail server, route mail for the agent's address to `10.100.109.9:2524` (`prod`) or `:2525` (`dev`). On Exchange this is a send connector or transport rule; plain SMTP, no TLS, no authentication.
4. Redeploy. Page 12 → **Inbound email (SMTP listener)** should show **Listening**. Send a test mail and check that "Messages … accepted" goes up and a ticket appears.
5. If "connections refused" goes up instead, the agent sees a different source IP than expected (check the agent logs for `refused client`). Docker normally keeps the client IP for traffic arriving from other hosts.

## 2. Deployment Commands
```bash
# Deploy DEV stack
./deploy.sh --env dev

# Deploy PROD stack
./deploy.sh --env prod

# Inspect container status
./deploy.sh --env dev --status
./deploy.sh --env prod --status

# Stream live logs
./deploy.sh --env dev --logs
./deploy.sh --env prod --logs
```
