# 01 — Project Overview & Architecture

## 1. System Purpose
The **IT Network Support AI Agent & Ticketing Harness** automates end-to-end branch network troubleshooting and ISP escalation:
- Receives branch incident emails and maps the reporting branch.
- Runs pluggable network diagnostic scripts (`DiagnosticInput` $\rightarrow$ `DiagnosticOutput`).
- Escalates confirmed network issues to the branch's ISP via email.
- Periodically chases the ISP for status updates (`next_followup_at`).
- Re-verifies branch connectivity when the ISP claims resolution and confirms with the branch.
- Tracks all tickets on a Jira-style Kanban board with full visibility into timeline events, diagnostic outputs, and separated Branch/ISP email threads.

## 2. Technology Stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2
- **AI Engine:** `google/gemma-4-26B-A4B-it` (`NVFP4`) on `vLLM` at `http://10.100.109.9:8002`
- **Database:** PostgreSQL 16 (`dev` and `prod` containers) / SQLite (local tests)
- **Cache & Coordination:** Redis 7
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS

## 3. Frozen Contracts (`backend/app/common/contracts.py`)
1. `DiagnosticInput` & `DiagnosticOutput` (`DiagnosticStatus`: `PASS`, `FAIL`, `DEGRADED`, `ERROR`)
2. `EmailEnvelope`
3. `BranchEmailAnalysis` & `IspResponseAnalysis` (Guided JSON schemas for `vLLM`)
4. `TicketStatus` & `TicketPriority`
