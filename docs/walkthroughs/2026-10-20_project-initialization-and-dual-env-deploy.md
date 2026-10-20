# Walkthrough: Project Initialization & Dual-Environment Deployment Setup

- **Date:** 2026-10-20
- **Summary:** Initialized the IT Network Support AI Agent & Ticketing Harness repository following the architectural standards established in `CLAUDE.md`. Set up the layered FastAPI backend (`common`, `auth`, `directory`, `ticketing`, `email_engine`, `diagnostics`, `agent`, `observability`), initial Alembic migration (`0001_initial_baseline`), React + Vite + Tailwind CSS frontend shell, and dual-environment (`dev` and `prod`) Docker Compose + `deploy.sh` deployment scripts targeting `10.100.109.9`.
- **Files Changed:**
  - Root: `CLAUDE.md`, `README.md`, `Dockerfile`, `docker-compose.yml`, `deploy.sh`, `run.sh`, `ruff.toml`, `.gitignore`, `.dockerignore`, `.env.example`, `.env.dev.example`, `.env.prod.example`
  - Backend: `backend/requirements.txt`, `backend/mypy.ini`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial_baseline.py`, `backend/scripts/entrypoint.sh`, `backend/scripts/healthcheck.py`, `backend/app/main.py`, `backend/app/common/*`, `backend/app/auth/*`, `backend/app/directory/*`, `backend/app/ticketing/*`, `backend/app/agent/vllm_client.py`, `backend/tests/test_health_and_contracts.py`
  - Frontend: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tailwind.config.js`, `frontend/src/App.tsx`, `frontend/src/main.tsx`
- **Contract Changes:** Established baseline frozen contracts in `backend/app/common/contracts.py` (`DiagnosticInput`, `DiagnosticOutput`, `EmailEnvelope`, `BranchEmailAnalysis`, `IspResponseAnalysis`, `TicketStatus`, `TicketPriority`).
- **Schema Changes:** Created `0001_initial_baseline.py` defining `users`, `network_providers`, `branches`, `tickets`, `diagnostic_runs`, `ticket_emails`, and `ticket_events`.
