"""FastAPI router for `/api/v1/diagnostics` (Page 9 Network Diagnostics Sandbox & manual checks)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.auth.models import User
from app.common.database import get_db
from app.diagnostics.base import (
    DiagnosticRunResponse,
    DiagnosticSuiteReportResponse,
    DiagnosticSuiteRunRequest,
    DualPingTracerouteRequest,
)
from app.diagnostics.service import (
    get_sandbox_catalog,
    list_recent_diagnostic_runs,
    run_and_persist_diagnostics,
    run_full_branch_diagnostic_suite,
)
from app.observability.event_bus import event_bus

diagnostics_router = APIRouter(prefix="/api/v1/diagnostics", tags=["Network Diagnostics"])


@diagnostics_router.get("/sandbox-catalog")
async def get_sandbox_catalog_endpoint(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("diagnostics:view_logs")),
) -> dict[str, Any]:
    """Return featured branches, 3G/4G hub IP mappings, and recent sandbox runs."""
    return get_sandbox_catalog(db)


@diagnostics_router.get("/runs", response_model=list[DiagnosticRunResponse])
async def list_diagnostic_runs_endpoint(
    ticket_id: Optional[int] = Query(default=None),
    branch_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    _user: User = Depends(require_permission("diagnostics:view_logs")),
) -> list[DiagnosticRunResponse]:
    """List recent diagnostic script executions."""
    return list_recent_diagnostic_runs(
        db, ticket_id=ticket_id, branch_code=branch_code, limit=limit
    )


@diagnostics_router.post("/run", response_model=DiagnosticRunResponse)
async def execute_diagnostics_endpoint(
    payload: DualPingTracerouteRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("diagnostics:trigger_manual")),
) -> DiagnosticRunResponse:
    """Execute Dual-Ping (`IP1`/`IP2`) + `ORANGE`/`WE` 4G Hub Traceroute check."""
    res = await run_and_persist_diagnostics(db, payload, actor_name=actor.display_name)
    await event_bus.broadcast(
        "diagnostic.completed",
        {
            "run_id": res.id,
            "ticket_id": res.ticket_id,
            "branch_code": res.branch_code,
            "diagnosis_code": res.diagnosis_code,
            "result_status": res.result_status,
        },
    )
    return res


@diagnostics_router.post("/run-suite", response_model=DiagnosticSuiteReportResponse)
async def execute_diagnostic_suite_endpoint(
    payload: DiagnosticSuiteRunRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("diagnostics:trigger_manual")),
) -> DiagnosticSuiteReportResponse:
    """Execute the Full Fleet Diagnostic Test Suite across all matching directory branches and generate a report."""
    report = await run_full_branch_diagnostic_suite(db, payload, actor_username=actor.username)
    await event_bus.broadcast(
        "diagnostic.suite_completed",
        {
            "suite_id": report.suite_id,
            "total_branches": report.total_branches,
            "pass_count": report.pass_count,
            "full_outage_count": report.full_outage_count,
            "four_g_count": report.four_g_count,
            "lan_switch_count": report.lan_switch_count,
            "health_pct": report.health_pct,
        },
    )
    return report
