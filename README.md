# IT Network Support AI Agent & Ticketing Harness

Autonomous network operations agent and Jira-style ticketing platform that:
1. **Ingests Branch Emails:** Monitors incoming branch network incident emails and resolves the reporting branch & circuit.
2. **Executes Network Diagnostics:** Runs sandboxed troubleshooting scripts (`DiagnosticInput` $\rightarrow$ `DiagnosticOutput`).
3. **Escalates to Network Providers (ISPs):** Maps confirmed outages to the branch's ISP and sends structured escalation emails.
4. **Proactively Chases ISPs:** Periodically polls/chases the ISP on open tickets until an update or fix is reported.
5. **Verifies & Confirms with Branch:** Re-runs diagnostics when the ISP claims resolution, and emails the branch to confirm restoration.
6. **Jira-Style Ticketing & RBAC Web UI:** Tracks every ticket status, timeline update, diagnostic test result, and request/response email thread behind a granular permission-based authentication system.

---

## Tech Stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic
- **AI Engine:** Self-hosted `google/gemma-4-26B-A4B-it` (`NVFP4`) on `vLLM` (`http://10.100.109.9:8002`)
- **Database & Cache:** PostgreSQL 16 + Redis 7
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS

---

## Dual-Environment Deployment on `10.100.109.9` (`dev` & `prod`)

Both `dev` and `prod` run on `10.100.109.9` in completely isolated containers, networks, and volumes:

| Resource | DEV (`./deploy.sh --env dev`) | PROD (`./deploy.sh --env prod`) |
| :--- | :--- | :--- |
| **Remote Directory** | `~/it-network-support-agent-dev` | `~/it-network-support-agent-prod` |
| **Compose Project** | `it-net-support-dev` | `it-net-support-prod` |
| **App Container** | `it-net-agent-dev` (`:8085`) | `it-net-agent-prod` (`:8084`) |
| **Postgres Container** | `it-net-postgres-dev` (`:5435`) | `it-net-postgres-prod` (`:5434`) |
| **Redis Container** | `it-net-redis-dev` (`:6385`) | `it-net-redis-prod` (`:6384`) |
| **Volumes** | `it-net-pgdata-dev`, `it-net-redisdata-dev` | `it-net-pgdata-prod`, `it-net-redisdata-prod` |

### Quick Commands
```bash
# Local Development (Backend :8000 + Frontend :5173)
./run.sh dev

# Run Tests & Linters
./run.sh test
./run.sh lint

# Deploy to DEV on 10.100.109.9
./deploy.sh --env dev

# Deploy to PROD on 10.100.109.9
./deploy.sh --env prod
```
