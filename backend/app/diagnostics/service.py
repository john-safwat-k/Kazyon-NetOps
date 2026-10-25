"""Service layer for Network Diagnostics (`DiagnosticRun` persistence, sandbox runs, and settings)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.common.audit import record_audit_event
from app.diagnostics.base import (
    DiagnosticCheckPillDto,
    DiagnosticRunResponse,
    DiagnosticStepDetailDto,
    DiagnosticSuiteBranchItem,
    DiagnosticSuiteIspSummary,
    DiagnosticSuiteRegionSummary,
    DiagnosticSuiteReportResponse,
    DiagnosticSuiteRunRequest,
    DualPingTracerouteRequest,
)
from app.diagnostics.executor import (
    build_detailed_diagnosis_meta,
    execute_dual_ping_and_traceroute,
)
from app.directory.seeder import derive_branch_ips
from app.directory.service import get_branch_by_code
from app.ticketing.models import DiagnosticRun, SystemSettings, Ticket, TicketEvent

logger = logging.getLogger("it_net.diagnostics.service")


def _to_run_response(
    run: DiagnosticRun,
    *,
    branch_label: Optional[str] = None,
    isp_name: Optional[str] = None,
    meaning: Optional[str] = None,
) -> DiagnosticRunResponse:
    metrics = dict(run.metrics_json or {})
    check_mode = str(metrics.get("check_mode") or "FULL").upper()

    checks: list[DiagnosticCheckPillDto] = []
    if check_mode in {"FULL", "PING_IP1", "TRACEROUTE"} and run.ip_1_up is not None:
        checks.append(DiagnosticCheckPillDto(label="IP1", state="up" if run.ip_1_up else "down"))
    if check_mode == "FULL" and run.ip_1_up is False:
        checks.append(DiagnosticCheckPillDto(label="IP2", state="skip"))
    elif check_mode in {"FULL", "PING_IP2"} and run.ip_2_up is not None:
        checks.append(DiagnosticCheckPillDto(label="IP2", state="up" if run.ip_2_up else "down"))
    if run.four_g_hub_detected:
        checks.append(DiagnosticCheckPillDto(label="4G", state="hub"))

    resolved_meaning = meaning or (
        run.summary.split(" — ", 1)[1] if " — " in run.summary else run.summary
    )
    resolved_isp = isp_name or str(metrics.get("isp_name") or "NOOR")
    ip_1_str = str(metrics.get("ip_1") or "10.0.0.1")
    ip_2_str = str(metrics.get("ip_2") or "10.0.0.2")

    raw_steps = metrics.get("steps")
    if isinstance(raw_steps, list) and raw_steps:
        steps = [DiagnosticStepDetailDto(**s) for s in raw_steps if isinstance(s, dict)]
        diagnosis_title = str(metrics.get("diagnosis_title") or "")
        root_cause = str(metrics.get("root_cause") or "")
        responsible_team = str(metrics.get("responsible_team") or "")
        ai_workflow_action = str(metrics.get("ai_workflow_action") or "")
        operator_action = str(metrics.get("operator_action") or "")
    else:
        meta = build_detailed_diagnosis_meta(
            diagnosis_code=run.diagnosis_code or "PASS",
            check_mode=check_mode,
            isp_name=resolved_isp,
            ip_1=ip_1_str,
            ip_2=ip_2_str,
            ip_1_up=run.ip_1_up,
            ip_2_up=run.ip_2_up,
            four_g_hub_detected=bool(run.four_g_hub_detected),
            detected_hub_ip=run.detected_hub_ip,
            configured_hub_ip=run.detected_hub_ip or "",
        )
        steps = [DiagnosticStepDetailDto(**s) for s in meta["steps"]]
        diagnosis_title = str(meta["diagnosis_title"])
        root_cause = str(meta["root_cause"])
        responsible_team = str(meta["responsible_team"])
        ai_workflow_action = str(meta["ai_workflow_action"])
        operator_action = str(meta["operator_action"])

    return DiagnosticRunResponse(
        id=run.id,
        ticket_id=run.ticket_id,
        branch_code=run.branch_code,
        branch_label=branch_label or run.branch_code,
        isp_name=resolved_isp,
        trigger_source=run.trigger_source,
        ip_1_up=run.ip_1_up,
        ip_2_up=run.ip_2_up,
        four_g_hub_detected=run.four_g_hub_detected,
        detected_hub_ip=run.detected_hub_ip,
        result_status=run.result_status,
        diagnosis_code=run.diagnosis_code,
        diagnosis_title=diagnosis_title,
        meaning=resolved_meaning,
        root_cause=root_cause,
        responsible_team=responsible_team,
        ai_workflow_action=ai_workflow_action,
        operator_action=operator_action,
        summary=run.summary,
        checks=checks,
        steps=steps,
        metrics_json=metrics,
        raw_output=run.raw_output,
        duration_ms=run.duration_ms,
        executed_at=run.executed_at.isoformat(),
    )


async def run_and_persist_diagnostics(
    db: Session,
    request: DualPingTracerouteRequest,
    *,
    actor_name: str = "AI_AGENT",
) -> DiagnosticRunResponse:
    """Run the dual-ping + 4G hub traceroute check, persist `DiagnosticRun`, and optionally log to a ticket."""
    branch = get_branch_by_code(db, request.branch_code)
    derived_ip1, derived_ip2 = derive_branch_ips(request.branch_code)

    ip_1 = (request.ip_1 or "").strip() or (branch.ip_1 if branch else derived_ip1)
    ip_2 = (request.ip_2 or "").strip() or (branch.ip_2 if branch else derived_ip2)
    isp_name = (request.isp_name or "").strip() or (branch.isp_name if branch else "NOOR")
    hub_ip = (request.four_g_hub_ip or "").strip() or (branch.four_g_hub_ip if branch else None)
    branch_name = branch.name if branch else request.branch_code
    region = branch.region if branch and branch.region else "Cairo"
    branch_label = f"{branch_name} · {region}"

    saved = db.execute(
        select(SystemSettings).where(SystemSettings.config_key == "global").limit(1)
    ).scalar_one_or_none()
    saved_ping_count = saved.ping_count if saved is not None else 4
    saved_max_hops = saved.traceroute_max_hops if saved is not None else 15
    saved_timeout_sec = saved.diagnostic_timeout_sec if saved is not None else None

    exec_result = await execute_dual_ping_and_traceroute(
        branch_code=request.branch_code,
        branch_name=branch_name,
        ip_1=ip_1,
        ip_2=ip_2,
        isp_name=isp_name,
        four_g_hub_ip=hub_ip,
        check_mode=request.resolved_check_mode(),
        simulate_scenario=request.simulate_scenario,
        ping_count=request.ping_count or saved_ping_count,
        traceroute_max_hops=request.traceroute_max_hops or saved_max_hops,
        timeout_sec=request.timeout_sec or saved_timeout_sec,
        verify_local_loop=request.trigger_source == "FINAL_VERIFICATION",
    )

    run = DiagnosticRun(
        ticket_id=request.ticket_id,
        branch_code=request.branch_code,
        trigger_source=request.trigger_source,
        ip_1_up=exec_result["ip_1_up"],
        ip_2_up=exec_result["ip_2_up"],
        four_g_hub_detected=exec_result["four_g_hub_detected"],
        detected_hub_ip=exec_result["detected_hub_ip"],
        result_status=exec_result["result_status"],
        diagnosis_code=exec_result["diagnosis_code"],
        summary=exec_result["summary"],
        metrics_json=exec_result["metrics_json"],
        raw_output=exec_result["raw_output"],
        duration_ms=exec_result["duration_ms"],
    )
    db.add(run)

    if request.ticket_id is not None:
        ticket = db.get(Ticket, request.ticket_id)
        if ticket is not None:
            if exec_result["diagnosis_code"] != "PASS":
                ticket.connection_failure_type = exec_result["diagnosis_code"]
            evt = TicketEvent(
                ticket_id=ticket.id,
                actor_type="ENGINEER" if request.trigger_source == "MANUAL" else "AI_AGENT",
                actor_name=actor_name,
                event_type="diagnostic_triggered",
                summary=f"Diagnostics ({request.trigger_source}): {exec_result['diagnosis_code']}",
                details_json={
                    "ip_1_up": exec_result["ip_1_up"],
                    "ip_2_up": exec_result["ip_2_up"],
                    "four_g_hub_detected": exec_result["four_g_hub_detected"],
                    "diagnosis_code": exec_result["diagnosis_code"],
                },
            )
            db.add(evt)

    db.commit()
    db.refresh(run)
    return _to_run_response(
        run,
        branch_label=branch_label,
        isp_name=exec_result["isp_name"],
        meaning=exec_result["meaning"],
    )


def list_recent_diagnostic_runs(
    db: Session,
    *,
    ticket_id: Optional[int] = None,
    branch_code: Optional[str] = None,
    limit: int = 20,
) -> list[DiagnosticRunResponse]:
    """List recent diagnostic executions (for a specific ticket or the Diagnostics Sandbox)."""
    stmt = select(DiagnosticRun)
    if ticket_id is not None:
        stmt = stmt.where(DiagnosticRun.ticket_id == ticket_id)
    if branch_code:
        stmt = stmt.where(DiagnosticRun.branch_code == branch_code.strip())
    rows = db.execute(stmt.order_by(DiagnosticRun.id.desc()).limit(limit)).scalars().all()
    return [_to_run_response(r) for r in rows]


def get_sandbox_catalog(db: Session) -> dict[str, Any]:
    """Return real branches from the directory, 3G/4G hub IP mappings, and recent sandbox runs for Page 9."""
    from app.directory.models import Branch

    def _branch_item(b: Branch) -> dict[str, Any]:
        return {
            "code": b.branch_code,
            "name": b.name,
            "region": b.region or "Cairo",
            "label": f"{b.name} · {b.region or 'Cairo'}",
            "ip1": b.ip_1,
            "ip2": b.ip_2,
            "ip_1": b.ip_1,
            "ip_2": b.ip_2,
            "isp": b.isp_name,
            "hub": b.four_g_hub_ip or "—",
            "ll_circuit_id": b.ll_circuit_id or "—",
            "backup_circuit_id": b.backup_circuit_id or "—",
            "regional_it_email": b.regional_it_email or "CITSupport@kazyon.com",
            "default_result": "PASS",
        }

    featured_codes = ["1173", "2009", "1201", "1366", "1254", "1088", "1005"]
    quick_branches: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for code in featured_codes:
        b = get_branch_by_code(db, code)
        if b is not None:
            seen_codes.add(b.branch_code)
            quick_branches.append(_branch_item(b))

    all_branches = (
        db.execute(
            select(Branch)
            .where(Branch.is_active.is_(True))
            .order_by(Branch.branch_code.asc())
            .limit(2000)
        )
        .scalars()
        .all()
    )
    for b in all_branches:
        if b.branch_code in seen_codes:
            continue
        seen_codes.add(b.branch_code)
        quick_branches.append(_branch_item(b))

    recent = list_recent_diagnostic_runs(db, limit=10)
    recent_dtos: list[dict[str, Any]] = []
    for r in recent:
        tone = (
            "good"
            if r.result_status == "PASS"
            else ("critical" if r.result_status == "FAIL" else "warning")
        )
        recent_dtos.append(
            {
                "id": r.id,
                "branch_code": r.branch_code,
                "when": r.executed_at[11:16] if len(r.executed_at) >= 16 else r.executed_at,
                "diagnosis_code": r.diagnosis_code or r.result_status,
                "tone": tone,
            }
        )
    return {
        "branches": quick_branches,
        "quick_branches": quick_branches,
        "hub_ips": {
            "ORANGE": "10.247.8.1",
            "WE": "172.16.70.33 · 172.17.20.33",
            "NOOR": "No traceroute (LAN rule)",
        },
        "hub_mappings": [
            {"isp": "ORANGE", "hubs": "10.247.8.1"},
            {"isp": "WE", "hubs": "172.16.70.33 · 172.17.20.33"},
            {"isp": "NOOR", "hubs": "No traceroute (LAN rule)"},
        ],
        "recent_runs": recent_dtos,
    }


async def run_full_branch_diagnostic_suite(
    db: Session,
    request: DiagnosticSuiteRunRequest,
    *,
    actor_username: str = "admin",
) -> DiagnosticSuiteReportResponse:
    """Execute the full Dual-Ping + 4G Hub Traceroute test suite across all matching branches."""
    from app.directory.models import Branch

    start_ns = time.perf_counter_ns()
    stmt = select(Branch).where(Branch.is_active.is_(True))

    if request.isp_name and request.isp_name.upper() != "ALL":
        stmt = stmt.where(Branch.isp_name == request.isp_name.strip().upper())
    if request.region and request.region != "All":
        stmt = stmt.where(Branch.region == request.region.strip())
    if request.search and request.search.strip():
        q = f"%{request.search.strip()}%"
        stmt = stmt.where(
            or_(
                Branch.branch_code.ilike(q),
                Branch.name.ilike(q),
                Branch.ip_1.ilike(q),
                Branch.ip_2.ilike(q),
            )
        )

    branches = (
        db.execute(stmt.order_by(Branch.branch_code.asc()).limit(request.limit)).scalars().all()
    )

    items: list[DiagnosticSuiteBranchItem] = []
    pass_count = 0
    full_outage_count = 0
    four_g_count = 0
    lan_switch_count = 0

    isp_stats: dict[str, dict[str, int]] = {}
    region_stats: dict[str, dict[str, int]] = {}

    is_live_icmp = request.simulate_scenario == "LIVE_ICMP"
    sem = asyncio.Semaphore(64)
    suite_ping_count = 1 if is_live_icmp else request.ping_count
    suite_timeout_sec = 2 if is_live_icmp else None

    async def _run_one(b: Branch) -> tuple[Branch, dict[str, Any]]:
        fb_ip1, fb_ip2 = derive_branch_ips(b.branch_code)
        async with sem:
            try:
                r = await execute_dual_ping_and_traceroute(
                    branch_code=b.branch_code,
                    branch_name=b.name,
                    ip_1=b.ip_1 or fb_ip1,
                    ip_2=b.ip_2 or fb_ip2,
                    isp_name=b.isp_name,
                    four_g_hub_ip=b.four_g_hub_ip,
                    check_mode="FULL",
                    simulate_scenario=request.simulate_scenario,
                    ping_count=suite_ping_count,
                    traceroute_max_hops=request.traceroute_max_hops,
                    timeout_sec=suite_timeout_sec,
                    use_live_subprocess=is_live_icmp,
                    simulate_delay=False,
                )
            except Exception:
                r = await execute_dual_ping_and_traceroute(
                    branch_code=b.branch_code,
                    branch_name=b.name,
                    ip_1=fb_ip1,
                    ip_2=fb_ip2,
                    isp_name=b.isp_name,
                    four_g_hub_ip=b.four_g_hub_ip,
                    check_mode="FULL",
                    simulate_scenario=request.simulate_scenario,
                    ping_count=suite_ping_count,
                    traceroute_max_hops=request.traceroute_max_hops,
                    timeout_sec=suite_timeout_sec,
                    use_live_subprocess=is_live_icmp,
                    simulate_delay=False,
                )
            return b, r

    results_pairs = await asyncio.gather(*(_run_one(b) for b in branches))

    for b, res in results_pairs:
        d_code = str(res["diagnosis_code"])
        isp_key = str(res["isp_name"] or b.isp_name or "NOOR")
        reg_key = str(b.region or "Cairo")

        if isp_key not in isp_stats:
            isp_stats[isp_key] = {
                "total": 0,
                "pass": 0,
                "full_outage": 0,
                "four_g": 0,
                "lan_switch": 0,
            }
        if reg_key not in region_stats:
            region_stats[reg_key] = {
                "total": 0,
                "pass": 0,
                "full_outage": 0,
                "four_g": 0,
                "lan_switch": 0,
            }

        isp_stats[isp_key]["total"] += 1
        region_stats[reg_key]["total"] += 1

        if d_code == "PASS":
            pass_count += 1
            isp_stats[isp_key]["pass"] += 1
            region_stats[reg_key]["pass"] += 1
        elif d_code == "FULL_OUTAGE":
            full_outage_count += 1
            isp_stats[isp_key]["full_outage"] += 1
            region_stats[reg_key]["full_outage"] += 1
        elif d_code == "LOCAL_LOOP_DOWN_ON_4G":
            four_g_count += 1
            isp_stats[isp_key]["four_g"] += 1
            region_stats[reg_key]["four_g"] += 1
        else:
            lan_switch_count += 1
            isp_stats[isp_key]["lan_switch"] += 1
            region_stats[reg_key]["lan_switch"] += 1

        items.append(
            DiagnosticSuiteBranchItem(
                branch_code=b.branch_code,
                branch_name=b.name,
                region=reg_key,
                isp_name=isp_key,
                ip_1=b.ip_1,
                ip_2=b.ip_2,
                four_g_hub_ip=b.four_g_hub_ip,
                ll_circuit_id=b.ll_circuit_id,
                backup_circuit_id=b.backup_circuit_id,
                regional_it_email=b.regional_it_email,
                ip_1_up=bool(res["ip_1_up"]),
                ip_2_up=res["ip_2_up"],
                ip_2_skipped=res["ip_1_up"] is False,
                four_g_hub_detected=bool(res["four_g_hub_detected"]),
                detected_hub_ip=res["detected_hub_ip"],
                result_status=str(res["result_status"]),
                diagnosis_code=d_code,
                diagnosis_title=str(res["diagnosis_title"]),
                meaning=str(res["meaning"]),
                root_cause=str(res["root_cause"]),
                responsible_team=str(res["responsible_team"]),
                ai_workflow_action=str(res["ai_workflow_action"]),
                operator_action=str(res["operator_action"]),
                checks=[DiagnosticCheckPillDto(**c) for c in res["checks"]],
                steps=[DiagnosticStepDetailDto(**s) for s in res["steps"]],
                raw_output=str(res["raw_output"]),
                duration_ms=int(res["duration_ms"]),
            )
        )

    total_branches = len(items)
    health_pct = round((pass_count / total_branches) * 100.0, 1) if total_branches > 0 else 100.0
    duration_ms = max(25, int((time.perf_counter_ns() - start_ns) / 1_000_000))
    now_dt = datetime.now(timezone.utc)
    suite_id = f"SUITE-{now_dt.strftime('%Y%m%d-%H%M%S')}"

    by_isp = [
        DiagnosticSuiteIspSummary(
            isp_name=k,
            total=v["total"],
            pass_count=v["pass"],
            full_outage_count=v["full_outage"],
            four_g_count=v["four_g"],
            lan_switch_count=v["lan_switch"],
            health_pct=round((v["pass"] / v["total"]) * 100.0, 1) if v["total"] > 0 else 100.0,
        )
        for k, v in sorted(isp_stats.items(), key=lambda x: -x[1]["total"])
    ]

    by_region = [
        DiagnosticSuiteRegionSummary(
            region=k,
            total=v["total"],
            pass_count=v["pass"],
            full_outage_count=v["full_outage"],
            four_g_count=v["four_g"],
            lan_switch_count=v["lan_switch"],
            health_pct=round((v["pass"] / v["total"]) * 100.0, 1) if v["total"] > 0 else 100.0,
        )
        for k, v in sorted(region_stats.items(), key=lambda x: -x[1]["total"])
    ]

    record_audit_event(
        db,
        action="diagnostics.suite_executed",
        actor_username=actor_username,
        resource_type="diagnostics",
        resource_id=suite_id,
        summary=(
            f"Executed full diagnostic test suite {suite_id} across {total_branches} branches "
            f"(PASS={pass_count}, FULL_OUTAGE={full_outage_count}, "
            f"4G_BACKUP={four_g_count}, LAN_SWITCH={lan_switch_count})"
        ),
        details={
            "suite_id": suite_id,
            "scenario_mode": request.simulate_scenario,
            "total_branches": total_branches,
            "pass_count": pass_count,
            "full_outage_count": full_outage_count,
            "four_g_count": four_g_count,
            "lan_switch_count": lan_switch_count,
            "duration_ms": duration_ms,
        },
        commit=True,
    )

    return DiagnosticSuiteReportResponse(
        suite_id=suite_id,
        executed_at=now_dt.isoformat(),
        duration_ms=duration_ms,
        scenario_mode=request.simulate_scenario,
        total_branches=total_branches,
        pass_count=pass_count,
        full_outage_count=full_outage_count,
        four_g_count=four_g_count,
        lan_switch_count=lan_switch_count,
        health_pct=health_pct,
        by_isp=by_isp,
        by_region=by_region,
        items=items,
    )
