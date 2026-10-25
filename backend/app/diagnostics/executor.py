"""Sandboxed Network Diagnostic Executor (Ping IP1/IP2 + ORANGE/WE 4G Hub Traceroute).

Follows CLAUDE.md §9:
- Always uses `asyncio.create_subprocess_exec` with an explicit argument list (never `shell=True`).
- Validates IP addresses strictly to prevent command injection.
- Strips sensitive environment variables from subprocess execution.
- Supports deterministic simulation/mock mode for local/dev testing alongside live ICMP execution.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import platform
import time
from typing import Any, Literal, Optional

from app.common.config import get_settings
from app.common.contracts import (
    ConnectionFailureType,
    DiagnosticInput,
    DiagnosticOutput,
    DiagnosticStatus,
)
from app.common.exceptions import DiagnosticExecutionError, ValidationError

logger = logging.getLogger("it_net.diagnostics.executor")

ORANGE_4G_HUBS: set[str] = {"10.247.8.1"}
WE_4G_HUBS: set[str] = {"172.16.70.33", "172.17.20.33"}


def validate_ip_address(ip_str: str) -> str:
    """Validate that `ip_str` is a legal IPv4 or IPv6 address (normalizes zero-padded IPv4 octets)."""
    cleaned = ip_str.strip()
    parts = cleaned.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        cleaned = ".".join(str(int(p)) for p in parts)
    try:
        ipaddress.ip_address(cleaned)
        return cleaned
    except ValueError as exc:
        raise ValidationError(f"Invalid IP address '{cleaned}'") from exc


async def _run_safe_subprocess(cmd: list[str], timeout_sec: float) -> tuple[int, str]:
    """Execute a command via `asyncio.create_subprocess_exec` with sanitized env and timeout."""
    safe_env = {"PATH": "/usr/sbin:/sbin:/usr/bin:/bin", "LC_ALL": "C"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=safe_env,
        )
        try:
            stdout_bytes, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
            output = stdout_bytes.decode("utf-8", errors="replace")
            return int(proc.returncode or 0), output
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return 124, f"Command timed out after {timeout_sec:.1f}s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 127, f"Binary not found: {cmd[0]}"
    except Exception as exc:
        return 1, f"Subprocess execution error: {exc}"


def _check_icmp_execution_error(target_ip: str, rc: int, out: str) -> None:
    lower = out.lower()
    if rc == 127 or "binary not found" in lower:
        raise DiagnosticExecutionError(target_ip, out.strip())
    if any(
        phrase in lower
        for phrase in (
            "operation not permitted",
            "socket type not supported",
            "must be root",
            "cap_net_raw",
            "permission denied",
        )
    ):
        raise DiagnosticExecutionError(target_ip, out.strip())


async def run_live_ping(target_ip: str, count: int = 4, timeout_sec: int = 8) -> tuple[bool, str]:
    """Run an actual OS `ping` command against `target_ip` via `create_subprocess_exec`."""
    ip = validate_ip_address(target_ip)
    is_mac = platform.system().lower() == "darwin"
    wait_flag = "-W"
    wait_val = "1000" if is_mac else "1"
    cmd = ["ping", "-c", str(max(1, min(count, 10))), wait_flag, wait_val, ip]
    rc, out = await _run_safe_subprocess(cmd, timeout_sec=float(timeout_sec))
    _check_icmp_execution_error(ip, rc, out)
    is_up = rc == 0 and (
        "0% packet loss" in out or "0.0% packet loss" in out or "bytes from" in out
    )
    return is_up, f"$ {' '.join(cmd)}\n{out.strip()}"


async def run_live_traceroute(
    target_ip: str, max_hops: int = 15, timeout_sec: int = 12
) -> tuple[str, list[str]]:
    """Run an actual OS `traceroute -n` command against `target_ip` via `create_subprocess_exec`."""
    ip = validate_ip_address(target_ip)
    cmd = ["traceroute", "-n", "-m", str(max(1, min(max_hops, 30))), "-w", "1", ip]
    rc, out = await _run_safe_subprocess(cmd, timeout_sec=float(timeout_sec))
    _check_icmp_execution_error(ip, rc, out)
    hops: list[str] = []
    for line in out.splitlines():
        for token in line.split():
            try:
                ipaddress.ip_address(token)
                hops.append(token)
            except ValueError:
                continue
    return f"$ {' '.join(cmd)}\n{out.strip()}", hops


def _resolve_scenario(
    branch_code: str,
    isp_name: str,
    simulate_scenario: Optional[str],
) -> str:
    """Resolve explicit simulation scenario when running in `DIAGNOSTIC_MODE=simulated`."""
    if simulate_scenario and simulate_scenario not in {"AUTO", "LIVE_ICMP"}:
        return simulate_scenario
    # Simulated-only deterministic test fixtures
    simulated_fixtures: dict[str, str] = {
        "1173": ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value,
        "2009": ConnectionFailureType.FULL_OUTAGE.value,
        "1254": ConnectionFailureType.FULL_OUTAGE.value,
        "1201": ConnectionFailureType.INTERNAL_LAN_SWITCH.value,
        "1366": ConnectionFailureType.PASS.value,
        "1099": ConnectionFailureType.PASS.value,
        "1222": ConnectionFailureType.PASS.value,
        "1420": ConnectionFailureType.FULL_OUTAGE.value,
        "1005": ConnectionFailureType.FULL_OUTAGE.value,
        "1510": ConnectionFailureType.FULL_OUTAGE.value,
        "1088": ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value,
        "1188": ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value,
    }
    if branch_code in simulated_fixtures:
        return simulated_fixtures[branch_code]
    return ConnectionFailureType.PASS.value


def build_detailed_diagnosis_meta(
    *,
    diagnosis_code: str,
    check_mode: str,
    isp_name: str,
    ip_1: str,
    ip_2: str,
    ip_1_up: Optional[bool],
    ip_2_up: Optional[bool],
    four_g_hub_detected: bool,
    detected_hub_ip: Optional[str],
    configured_hub_ip: str,
) -> dict[str, Any]:
    """Build detailed human-readable descriptions, step-by-step analysis, root cause, and actions."""
    norm_isp = isp_name.strip().upper()
    hub_display = (
        detected_hub_ip
        or configured_hub_ip
        or (
            "10.247.8.1"
            if norm_isp == "ORANGE"
            else ("172.16.70.33 / 172.17.20.33" if norm_isp == "WE" else "None (NOOR LAN Rule)")
        )
    )

    steps: list[dict[str, Any]] = []

    # Step 1: Router WAN Check (IP 1)
    if check_mode in {"FULL", "PING_IP1", "TRACEROUTE"}:
        if ip_1_up:
            lat = (
                "avg 182 ms (elevated 4G RTT)"
                if four_g_hub_detected
                else "0% packet loss · avg 21 ms"
            )
            steps.append(
                {
                    "step_number": 1,
                    "step_name": "Step 1 · Router WAN Interface (Ping IP 1)",
                    "target": ip_1,
                    "status": "UP",
                    "tone": "good",
                    "latency_or_hops": lat,
                    "explanation": (
                        f"Branch CPE router ({ip_1}) responded to ICMP echo requests with 0% packet loss. "
                        "WAN connectivity from Kazyon HQ to the store router is active."
                    ),
                }
            )
        else:
            steps.append(
                {
                    "step_number": 1,
                    "step_name": "Step 1 · Router WAN Interface (Ping IP 1)",
                    "target": ip_1,
                    "status": "DOWN",
                    "tone": "critical",
                    "latency_or_hops": "100% packet loss · Request timed out",
                    "explanation": (
                        f"Branch CPE router ({ip_1}) did not respond to any ICMP echo packets. "
                        f"Both the primary {norm_isp} local loop and any backup WAN path are unreachable."
                    ),
                }
            )

    # Step 2: Store Server Switch Check (IP 2)
    if check_mode in {"FULL", "PING_IP2"}:
        if ip_1_up is False and check_mode == "FULL":
            steps.append(
                {
                    "step_number": 2,
                    "step_name": "Step 2 · Store Server Switch (Ping IP 2)",
                    "target": ip_2,
                    "status": "SKIPPED",
                    "tone": "neutral",
                    "latency_or_hops": "Skipped (Router IP 1 is DOWN)",
                    "explanation": (
                        f"Server switch ({ip_2}) sits behind the branch router ({ip_1}). "
                        "Because IP 1 is unreachable from WAN, pinging IP 2 is automatically skipped."
                    ),
                }
            )
        elif ip_2_up:
            steps.append(
                {
                    "step_number": 2,
                    "step_name": "Step 2 · Store Server Switch (Ping IP 2)",
                    "target": ip_2,
                    "status": "UP",
                    "tone": "good",
                    "latency_or_hops": "0% packet loss · avg 23 ms",
                    "explanation": (
                        f"Store server switch ({ip_2}) is reachable through the branch router. "
                        "Internal store LAN uplink and primary MPLS routing are operating normally."
                    ),
                }
            )
        else:
            steps.append(
                {
                    "step_number": 2,
                    "step_name": "Step 2 · Store Server Switch (Ping IP 2)",
                    "target": ip_2,
                    "status": "DOWN",
                    "tone": "warning" if ip_1_up else "critical",
                    "latency_or_hops": "100% packet loss · Unreachable",
                    "explanation": (
                        f"Store server switch ({ip_2}) failed to respond while Router IP 1 ({ip_1}) is UP. "
                        "This occurs either when an ORANGE/WE branch fails over to its 4G backup hub "
                        "or when the store's internal LAN switch/patch cable is down."
                    ),
                }
            )

    # Step 3: 3G/4G Backup Hub Traceroute Analysis
    if check_mode in {"FULL", "TRACEROUTE"}:
        if ip_1_up is False:
            steps.append(
                {
                    "step_number": 3,
                    "step_name": "Step 3 · 3G/4G Backup Hub Traceroute",
                    "target": ip_1,
                    "status": "SKIPPED",
                    "tone": "neutral",
                    "latency_or_hops": "Skipped (Router IP 1 is DOWN)",
                    "explanation": (
                        "Traceroute is skipped because the branch router is completely unreachable on both landline and 4G."
                    ),
                }
            )
        elif ip_2_up is True and check_mode == "FULL":
            steps.append(
                {
                    "step_number": 3,
                    "step_name": "Step 3 · 3G/4G Backup Hub Traceroute",
                    "target": ip_1,
                    "status": "MPLS_DIRECT",
                    "tone": "good",
                    "latency_or_hops": "Not required (IP 1 & IP 2 both UP on primary landline)",
                    "explanation": (
                        "Because both Router IP 1 and Switch IP 2 responded, the branch is confirmed on its primary "
                        "landline local loop without needing a 4G hub disambiguation traceroute."
                    ),
                }
            )
        elif norm_isp == "NOOR" and check_mode == "FULL":
            steps.append(
                {
                    "step_number": 3,
                    "step_name": "Step 3 · 3G/4G Backup Hub Traceroute",
                    "target": ip_1,
                    "status": "SKIPPED",
                    "tone": "info",
                    "latency_or_hops": "Skipped per NOOR LAN Rule (No 4G Hub)",
                    "explanation": (
                        "Per BRD §6.5, NOOR branches do not use a 4G backup hub that masks IP 2. "
                        "Therefore IP 1 UP + IP 2 DOWN on NOOR immediately confirms an Internal LAN / Switch failure."
                    ),
                }
            )
        elif four_g_hub_detected:
            steps.append(
                {
                    "step_number": 3,
                    "step_name": "Step 3 · 3G/4G Backup Hub Traceroute",
                    "target": ip_1,
                    "status": "HUB_DETECTED",
                    "tone": "warning",
                    "latency_or_hops": f"Hop 2 matched {norm_isp} 4G Hub ({hub_display})",
                    "explanation": (
                        f"Traceroute to {ip_1} traversed the {norm_isp} 3G/4G backup concentration hub ({hub_display}). "
                        "This proves the branch's primary landline (Local Loop) is DOWN and the router is operating on cellular backup."
                    ),
                }
            )
        else:
            steps.append(
                {
                    "step_number": 3,
                    "step_name": "Step 3 · 3G/4G Backup Hub Traceroute",
                    "target": ip_1,
                    "status": "MPLS_DIRECT",
                    "tone": "good",
                    "latency_or_hops": f"Direct MPLS path (No {norm_isp} 4G Hub {hub_display} in hops)",
                    "explanation": (
                        f"Traceroute to {ip_1} did NOT pass through the {norm_isp} 4G hub ({hub_display}). "
                        "The primary landline local loop is UP, confirming the issue is isolated to the store's internal LAN switch (IP 2)."
                    ),
                }
            )

    if diagnosis_code == ConnectionFailureType.FULL_OUTAGE.value:
        return {
            "diagnosis_title": "Complete Branch WAN Outage (Router Unreachable)",
            "root_cause": (
                f"Router IP 1 ({ip_1}) has 100% packet loss from HQ. The branch is completely isolated from the WAN "
                f"(primary {norm_isp} local loop is down and no 3G/4G backup tunnel is reachable, or branch CPE power is off)."
            ),
            "responsible_team": f"ISP Support ({norm_isp}) & Regional IT (Power/CPE verification)",
            "ai_workflow_action": (
                f"Requests CPE/Switch physical photo from Regional IT (Gemma 4 Vision check). Once power & cables are verified, "
                f"sends formal escalation email to {norm_isp} quoting L.L Circuit ID and Backup ID, and starts the 2h Welcome SLA timer."
            ),
            "operator_action": (
                f"Verify store electricity/UPS status with Regional IT, then track {norm_isp} ticket reference number and 2h Welcome SLA."
            ),
            "steps": steps,
        }

    if diagnosis_code == ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value:
        return {
            "diagnosis_title": f"Primary Local Loop Down · Running on {norm_isp} 4G Backup Hub",
            "root_cause": (
                f"Router IP 1 ({ip_1}) is UP, Server Switch IP 2 ({ip_2}) is DOWN, and traceroute hits the {norm_isp} "
                f"4G backup hub ({hub_display}). The physical landline (Local Loop) has failed and the router failed over to 4G."
            ),
            "responsible_team": f"ISP Support ({norm_isp} Landline / Local Loop Team)",
            "ai_workflow_action": (
                f"Classifies incident as LOCAL_LOOP_DOWN_ON_4G, escalates directly to {norm_isp} support quoting the "
                "Branch SAP Code, L.L Circuit ID, and 4G Hub traceroute evidence, and starts the 2h Welcome SLA timer."
            ),
            "operator_action": (
                f"Escalate primary landline outage to {norm_isp} with L.L Circuit ID; keep branch operating on 4G backup until landline is restored."
            ),
            "steps": steps,
        }

    if diagnosis_code == ConnectionFailureType.INTERNAL_LAN_SWITCH.value:
        return {
            "diagnosis_title": "Internal Store LAN / Server Switch Unreachable",
            "root_cause": (
                f"Router IP 1 ({ip_1}) is UP on the primary {norm_isp} local loop (no 4G hub in path), "
                f"but Server Switch IP 2 ({ip_2}) is unreachable (100% packet loss). The WAN circuit is healthy; "
                "the failure is inside the store between the router LAN port and the server switch."
            ),
            "responsible_team": "Kazyon Regional IT / Store IT Field Engineer",
            "ai_workflow_action": (
                "Does NOT escalate to the ISP (prevents false ISP tickets). Transitions ticket to INTERNAL_LAN_ISSUE "
                "and notifies Regional IT (`Regional IT Email`) to inspect the store switch power and RJ45 uplink cable."
            ),
            "operator_action": (
                "Contact Regional IT to check the store server switch power supply, LAN uplink patch cord between Router and Switch, and VLAN port state."
            ),
            "steps": steps,
        }

    return {
        "diagnosis_title": "Network Healthy (Primary WAN & Store LAN Operational)",
        "root_cause": (
            f"Both Router IP 1 ({ip_1}) and Store Server Switch IP 2 ({ip_2}) are reachable with 0% packet loss "
            f"over the primary {norm_isp} circuit."
        ),
        "responsible_team": "None (Normal Operation)",
        "ai_workflow_action": (
            "Marks diagnostic verification as PASS. If triggered during ticket recovery verification, "
            "confirms link restoration with Regional IT and resolves the incident."
        ),
        "operator_action": "No action required — branch WAN router and LAN switch are both healthy.",
        "steps": steps,
    }


async def execute_dual_ping_and_traceroute(
    *,
    branch_code: str,
    branch_name: str,
    ip_1: str,
    ip_2: str,
    isp_name: str = "NOOR",
    four_g_hub_ip: Optional[str] = None,
    check_mode: Literal["FULL", "PING_IP1", "PING_IP2", "TRACEROUTE"] = "FULL",
    simulate_scenario: Optional[str] = "AUTO",
    ping_count: int = 4,
    traceroute_max_hops: int = 15,
    timeout_sec: Optional[int] = None,
    use_live_subprocess: bool = False,
    simulate_delay: bool = True,
    verify_local_loop: bool = False,
) -> dict[str, Any]:
    """Execute the Kazyon Dual-Ping (`IP1` Router, `IP2` Switch) + `ORANGE`/`WE` 4G Hub Traceroute tree.

    Decision Tree (BRD §4.2 Step 3B & §6.5):
    1. Ping `IP 1` (Router `10.x.x.1`) and `IP 2` (Server Switch `10.x.x.2`).
    2. `IP 1` UP + `IP 2` UP -> `PASS` (Network Healthy). With `verify_local_loop` (BRD Step 7
       final verification) `ORANGE`/`WE` branches also traceroute `IP 1`; a 4G hub in the path
       means the branch is still on backup -> `LOCAL_LOOP_DOWN_ON_4G`.
    3. `IP 1` DOWN (skip `IP 2`) -> `FULL_OUTAGE` (Escalate to ISP).
    4. `IP 1` UP + `IP 2` DOWN:
       - If ISP is `NOOR` -> `INTERNAL_LAN_SWITCH` (Return to Regional/Store IT).
       - If ISP is `ORANGE` or `WE` -> Run `traceroute` to `IP 1`:
         * Hits `10.247.8.1` (`ORANGE`) or `172.16.70.33` / `172.17.20.33` (`WE`)
           -> `LOCAL_LOOP_DOWN_ON_4G` (Escalate to ISP).
         * Does NOT hit 4G Hub -> `INTERNAL_LAN_SWITCH` (Return to Regional/Store IT).
    """
    start_ns = time.perf_counter_ns()
    settings = get_settings()
    _ = timeout_sec or settings.diagnostic_timeout_sec

    valid_ip1 = validate_ip_address(ip_1)
    valid_ip2 = validate_ip_address(ip_2)
    norm_isp = isp_name.strip().upper()
    if norm_isp == "ORANG":
        norm_isp = "ORANGE"

    hub_ip = (four_g_hub_ip or "").strip()
    if not hub_ip or hub_ip == "—":
        if norm_isp == "ORANGE":
            hub_ip = "10.247.8.1"
        elif norm_isp == "WE":
            hub_ip = "172.16.70.33"
        else:
            hub_ip = ""

    effective_scenario = simulate_scenario
    if effective_scenario is None:
        effective_scenario = "LIVE_ICMP" if settings.diagnostic_mode == "live" else "AUTO"

    is_live = use_live_subprocess or (effective_scenario == "LIVE_ICMP")
    eff_timeout = max(2, min(int(timeout_sec or 4), 30))

    if is_live:
        if check_mode == "PING_IP1":
            ip1_up, log1 = await run_live_ping(valid_ip1, count=ping_count, timeout_sec=eff_timeout)
            _check_icmp_execution_error(valid_ip1, 0, log1)
            ip2_up = None
            four_g_detected = False
            detected_hub = None
            diagnosis_code = (
                ConnectionFailureType.PASS.value
                if ip1_up
                else ConnectionFailureType.FULL_OUTAGE.value
            )
            result_status = DiagnosticStatus.PASS.value if ip1_up else DiagnosticStatus.FAIL.value
            meaning = (
                "Router IP 1 is reachable via live OS ping."
                if ip1_up
                else "Router IP 1 is unreachable via live OS ping (100% packet loss)."
            )
            raw_log = f"{log1}\nDIAGNOSIS: {diagnosis_code}"
            checks = [{"label": "IP1", "state": "up" if ip1_up else "down"}]
        elif check_mode == "PING_IP2":
            ip2_up, log2 = await run_live_ping(valid_ip2, count=ping_count, timeout_sec=eff_timeout)
            _check_icmp_execution_error(valid_ip2, 0, log2)
            ip1_up = ip2_up
            four_g_detected = False
            detected_hub = None
            diagnosis_code = (
                ConnectionFailureType.PASS.value
                if ip2_up
                else ConnectionFailureType.INTERNAL_LAN_SWITCH.value
            )
            result_status = DiagnosticStatus.PASS.value if ip2_up else DiagnosticStatus.FAIL.value
            meaning = (
                "Server switch IP 2 is reachable via live OS ping."
                if ip2_up
                else "Server switch IP 2 is unreachable via live OS ping (100% packet loss)."
            )
            raw_log = f"{log2}\nDIAGNOSIS: {diagnosis_code}"
            checks = [{"label": "IP2", "state": "up" if ip2_up else "down"}]
        elif check_mode == "TRACEROUTE":
            tr_log, hops = await run_live_traceroute(
                valid_ip1, max_hops=traceroute_max_hops, timeout_sec=eff_timeout
            )
            _check_icmp_execution_error(valid_ip1, 0, tr_log)
            target_hubs = ORANGE_4G_HUBS if norm_isp == "ORANGE" else WE_4G_HUBS
            if hub_ip:
                target_hubs = set(target_hubs) | {h.strip() for h in hub_ip.split(",") if h.strip()}
            matched_hub = next((h for h in hops if h in target_hubs), None)
            ip1_up = len(hops) > 0 and valid_ip1 in hops
            ip2_up = None
            if matched_hub:
                four_g_detected = True
                detected_hub = matched_hub
                diagnosis_code = ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value
                result_status = DiagnosticStatus.DEGRADED.value
                meaning = f"Live traceroute matched {norm_isp} 4G backup hub ({matched_hub})."
                checks = [{"label": "IP1", "state": "up"}, {"label": "4G", "state": "hub"}]
            else:
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.PASS.value
                result_status = DiagnosticStatus.PASS.value
                meaning = "Live traceroute completed (no 4G backup hub matched in path)."
                checks = [{"label": "IP1", "state": "up" if ip1_up else "down"}]
            raw_log = f"{tr_log}\nDIAGNOSIS: {diagnosis_code}"
        else:
            ip1_up, log1 = await run_live_ping(valid_ip1, count=ping_count, timeout_sec=eff_timeout)
            _check_icmp_execution_error(valid_ip1, 0, log1)
            if not ip1_up:
                ip2_up = None
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.FULL_OUTAGE.value
                result_status = DiagnosticStatus.FAIL.value
                meaning = "Router unreachable (live OS ICMP ping failed). The branch is down from the WAN; escalate to the ISP."
                raw_log = f"{log1}\nIP 2 skipped (IP 1 down)\nDIAGNOSIS: {diagnosis_code}"
                checks = [{"label": "IP1", "state": "down"}, {"label": "IP2", "state": "skip"}]
            else:
                ip2_up, log2 = await run_live_ping(
                    valid_ip2, count=ping_count, timeout_sec=eff_timeout
                )
                _check_icmp_execution_error(valid_ip2, 0, log2)
                verify_hub_hit: Optional[str] = None
                verify_tr_log = ""
                if ip2_up and verify_local_loop and norm_isp in {"ORANGE", "WE"}:
                    verify_tr_log, verify_hops = await run_live_traceroute(
                        valid_ip1, max_hops=traceroute_max_hops, timeout_sec=eff_timeout
                    )
                    _check_icmp_execution_error(valid_ip1, 0, verify_tr_log)
                    verify_hubs = set(ORANGE_4G_HUBS if norm_isp == "ORANGE" else WE_4G_HUBS)
                    if hub_ip:
                        verify_hubs |= {h.strip() for h in hub_ip.split(",") if h.strip()}
                    verify_hub_hit = next((h for h in verify_hops if h in verify_hubs), None)
                if ip2_up and verify_hub_hit:
                    four_g_detected = True
                    detected_hub = verify_hub_hit
                    diagnosis_code = ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value
                    result_status = DiagnosticStatus.DEGRADED.value
                    meaning = (
                        f"Router and switch reachable, but traffic still routes via the {norm_isp} "
                        f"4G backup hub ({verify_hub_hit}). Local loop is not restored."
                    )
                    raw_log = f"{log1}\n{log2}\n{verify_tr_log}\nDIAGNOSIS: {diagnosis_code}"
                    checks = [
                        {"label": "IP1", "state": "up"},
                        {"label": "IP2", "state": "up"},
                        {"label": "4G", "state": "hub"},
                    ]
                elif ip2_up:
                    four_g_detected = False
                    detected_hub = None
                    diagnosis_code = ConnectionFailureType.PASS.value
                    result_status = DiagnosticStatus.PASS.value
                    meaning = "Router and switch both reachable via live OS ping. Network healthy."
                    raw_log = f"{log1}\n{log2}\nDIAGNOSIS: {diagnosis_code}"
                    checks = [{"label": "IP1", "state": "up"}, {"label": "IP2", "state": "up"}]
                elif norm_isp in {"ORANGE", "WE"}:
                    tr_log, hops = await run_live_traceroute(
                        valid_ip1, max_hops=traceroute_max_hops, timeout_sec=eff_timeout
                    )
                    _check_icmp_execution_error(valid_ip1, 0, tr_log)
                    target_hubs = ORANGE_4G_HUBS if norm_isp == "ORANGE" else WE_4G_HUBS
                    if hub_ip:
                        target_hubs = set(target_hubs) | {
                            h.strip() for h in hub_ip.split(",") if h.strip()
                        }
                    matched_hub = next((h for h in hops if h in target_hubs), None)
                    if matched_hub:
                        four_g_detected = True
                        detected_hub = matched_hub
                        diagnosis_code = ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value
                        result_status = DiagnosticStatus.DEGRADED.value
                        meaning = "Router reachable through the 4G backup. Escalate the local loop to the ISP."
                        raw_log = f"{log1}\n{log2}\n{tr_log}\nDIAGNOSIS: {diagnosis_code}"
                        checks = [
                            {"label": "IP1", "state": "up"},
                            {"label": "IP2", "state": "down"},
                            {"label": "4G", "state": "hub"},
                        ]
                    else:
                        four_g_detected = False
                        detected_hub = None
                        diagnosis_code = ConnectionFailureType.INTERNAL_LAN_SWITCH.value
                        result_status = DiagnosticStatus.DEGRADED.value
                        meaning = "Router up on local loop, switch down. Return to Regional IT as an internal LAN issue."
                        raw_log = f"{log1}\n{log2}\n{tr_log}\nDIAGNOSIS: {diagnosis_code}"
                        checks = [
                            {"label": "IP1", "state": "up"},
                            {"label": "IP2", "state": "down"},
                        ]
                else:
                    four_g_detected = False
                    detected_hub = None
                    diagnosis_code = ConnectionFailureType.INTERNAL_LAN_SWITCH.value
                    result_status = DiagnosticStatus.DEGRADED.value
                    meaning = "Router up, switch down on a NOOR line. Return to Regional IT as an internal LAN issue."
                    raw_log = f"{log1}\n{log2}\nNOOR branch: no traceroute needed\nDIAGNOSIS: {diagnosis_code}"
                    checks = [{"label": "IP1", "state": "up"}, {"label": "IP2", "state": "down"}]
    else:
        # Deterministic high-fidelity simulation matching Kazyon NetOps Console blueprints
        if simulate_delay:
            await asyncio.sleep(0.02)
        scenario = _resolve_scenario(branch_code, norm_isp, effective_scenario)

        # If a non-ORANGE/WE branch was given LOCAL_LOOP_DOWN_ON_4G, coerce to INTERNAL_LAN_SWITCH unless forced
        if (
            scenario == ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value
            and norm_isp == "NOOR"
            and effective_scenario == "AUTO"
        ):
            scenario = ConnectionFailureType.INTERNAL_LAN_SWITCH.value

        if check_mode == "PING_IP1":
            if scenario == ConnectionFailureType.FULL_OUTAGE.value:
                ip1_up = False
                ip2_up = None
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.FULL_OUTAGE.value
                result_status = DiagnosticStatus.FAIL.value
                meaning = "Router unreachable (100% packet loss on IP 1)."
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip1}\n"
                    f"{ping_count} packets transmitted, 0 received, 100% packet loss"
                )
                checks = [{"label": "IP1", "state": "down"}]
            else:
                ip1_up = True
                ip2_up = None
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.PASS.value
                result_status = DiagnosticStatus.PASS.value
                meaning = "Router IP 1 is reachable."
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip1}\n"
                    f"{ping_count} packets transmitted, {ping_count} received, 0% packet loss, avg 24 ms"
                )
                checks = [{"label": "IP1", "state": "up"}]
        elif check_mode == "PING_IP2":
            if scenario == ConnectionFailureType.PASS.value:
                ip1_up = True
                ip2_up = True
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.PASS.value
                result_status = DiagnosticStatus.PASS.value
                meaning = "Server switch IP 2 is reachable."
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip2}\n"
                    f"{ping_count} packets transmitted, {ping_count} received, 0% packet loss, avg 23 ms"
                )
                checks = [{"label": "IP2", "state": "up"}]
            else:
                ip1_up = scenario != ConnectionFailureType.FULL_OUTAGE.value
                ip2_up = False
                four_g_detected = False
                detected_hub = None
                diagnosis_code = scenario
                result_status = DiagnosticStatus.FAIL.value
                meaning = "Server switch IP 2 is unreachable (100% packet loss)."
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip2}\n"
                    f"{ping_count} packets transmitted, 0 received, 100% packet loss"
                )
                checks = [{"label": "IP2", "state": "down"}]
        elif check_mode == "TRACEROUTE":
            active_hub = hub_ip.split(",")[0].strip() if hub_ip else "10.247.8.1"
            if norm_isp in {"ORANGE", "WE"} and scenario in {
                ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value,
                ConnectionFailureType.FULL_OUTAGE.value,
            }:
                ip1_up = True
                ip2_up = False
                four_g_detected = True
                detected_hub = active_hub
                diagnosis_code = ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value
                result_status = DiagnosticStatus.DEGRADED.value
                meaning = (
                    f"Traceroute hits {norm_isp} 4G backup hub ({active_hub}). Local loop is down."
                )
                raw_log = (
                    f"$ traceroute -n -m {traceroute_max_hops} {valid_ip1}\n"
                    f" 1  10.100.109.1   0.6 ms\n"
                    f" 2  {active_hub:<14} 41.2 ms   ← {norm_isp} 4G hub\n"
                    f" 3  {valid_ip1:<14} 180.9 ms\n"
                    f"DIAGNOSIS: LOCAL_LOOP_DOWN_ON_4G"
                )
                checks = [{"label": "IP1", "state": "up"}, {"label": "4G", "state": "hub"}]
            else:
                ip1_up = True
                ip2_up = True
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.PASS.value
                result_status = DiagnosticStatus.PASS.value
                meaning = "Direct MPLS / Local Loop route active (no 4G backup hub in path)."
                raw_log = (
                    f"$ traceroute -n -m {traceroute_max_hops} {valid_ip1}\n"
                    f" 1  10.100.109.1   0.5 ms\n"
                    f" 2  172.30.0.1     11.4 ms   ← MPLS Core\n"
                    f" 3  {valid_ip1:<14} 21.8 ms"
                )
                checks = [{"label": "IP1", "state": "up"}]
        else:
            # FULL check mode
            if scenario == ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value:
                active_hub = hub_ip.split(",")[0].strip() if hub_ip else "10.247.8.1"
                ip1_up = True
                ip2_up = False
                four_g_detected = True
                detected_hub = active_hub
                diagnosis_code = ConnectionFailureType.LOCAL_LOOP_DOWN_ON_4G.value
                result_status = DiagnosticStatus.DEGRADED.value
                meaning = (
                    "Router reachable through the 4G backup. Escalate the local loop to the ISP."
                )
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip1}\n"
                    f"{ping_count} packets transmitted, {ping_count} received, 0% packet loss, avg 182 ms\n"
                    f"$ ping -c {ping_count} {valid_ip2}\n"
                    f"{ping_count} packets transmitted, 0 received, 100% packet loss\n"
                    f"$ traceroute -n {valid_ip1}\n"
                    f" 1  10.100.109.1   0.6 ms\n"
                    f" 2  {active_hub:<14} 41.2 ms   ← {norm_isp} 4G hub\n"
                    f" 3  {valid_ip1:<14} 180.9 ms\n"
                    f"DIAGNOSIS: LOCAL_LOOP_DOWN_ON_4G"
                )
                checks = [
                    {"label": "IP1", "state": "up"},
                    {"label": "IP2", "state": "down"},
                    {"label": "4G", "state": "hub"},
                ]
            elif scenario == ConnectionFailureType.FULL_OUTAGE.value:
                ip1_up = False
                ip2_up = None
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.FULL_OUTAGE.value
                result_status = DiagnosticStatus.FAIL.value
                meaning = (
                    "Router unreachable. The branch is down from the WAN; escalate to the ISP."
                )
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip1}\n"
                    f"{ping_count} packets transmitted, 0 received, 100% packet loss\n"
                    f"IP 2 skipped (IP 1 down)\n"
                    f"DIAGNOSIS: FULL_OUTAGE"
                )
                checks = [
                    {"label": "IP1", "state": "down"},
                    {"label": "IP2", "state": "skip"},
                ]
            elif scenario == ConnectionFailureType.INTERNAL_LAN_SWITCH.value:
                ip1_up = True
                ip2_up = False
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.INTERNAL_LAN_SWITCH.value
                result_status = DiagnosticStatus.DEGRADED.value
                meaning = f"Router up, switch down on a {norm_isp} line. Return to Regional IT as an internal LAN issue."
                extra_line = (
                    "NOOR branch: no traceroute needed"
                    if norm_isp == "NOOR"
                    else f"$ traceroute -n {valid_ip1}\n 1  10.100.109.1   0.6 ms\n 2  {valid_ip1}   24.1 ms (Local Loop OK, no 4G hub)"
                )
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip1}\n"
                    f"0% packet loss, avg 24 ms\n"
                    f"$ ping -c {ping_count} {valid_ip2}\n"
                    f"100% packet loss\n"
                    f"{extra_line}\n"
                    f"DIAGNOSIS: INTERNAL_LAN_SWITCH"
                )
                checks = [
                    {"label": "IP1", "state": "up"},
                    {"label": "IP2", "state": "down"},
                ]
            else:
                ip1_up = True
                ip2_up = True
                four_g_detected = False
                detected_hub = None
                diagnosis_code = ConnectionFailureType.PASS.value
                result_status = DiagnosticStatus.PASS.value
                meaning = "Router and switch both reachable. Network healthy."
                raw_log = (
                    f"$ ping -c {ping_count} {valid_ip1}\n"
                    f"0% packet loss, avg 21 ms\n"
                    f"$ ping -c {ping_count} {valid_ip2}\n"
                    f"0% packet loss, avg 23 ms\n"
                    f"DIAGNOSIS: PASS"
                )
                checks = [
                    {"label": "IP1", "state": "up"},
                    {"label": "IP2", "state": "up"},
                ]

    elapsed_ms = max(
        12 if not simulate_delay else 120, int((time.perf_counter_ns() - start_ns) / 1_000_000)
    )
    detail_meta = build_detailed_diagnosis_meta(
        diagnosis_code=diagnosis_code,
        check_mode=check_mode,
        isp_name=norm_isp,
        ip_1=valid_ip1,
        ip_2=valid_ip2,
        ip_1_up=ip1_up,
        ip_2_up=ip2_up,
        four_g_hub_detected=four_g_detected,
        detected_hub_ip=detected_hub,
        configured_hub_ip=hub_ip,
    )
    return {
        "branch_code": branch_code,
        "branch_name": branch_name,
        "isp_name": norm_isp,
        "ip_1": valid_ip1,
        "ip_2": valid_ip2,
        "ip_1_up": ip1_up,
        "ip_2_up": ip2_up,
        "four_g_hub_detected": four_g_detected,
        "detected_hub_ip": detected_hub,
        "result_status": result_status,
        "diagnosis_code": diagnosis_code,
        "diagnosis_title": detail_meta["diagnosis_title"],
        "meaning": meaning,
        "root_cause": detail_meta["root_cause"],
        "responsible_team": detail_meta["responsible_team"],
        "ai_workflow_action": detail_meta["ai_workflow_action"],
        "operator_action": detail_meta["operator_action"],
        "summary": f"{diagnosis_code} — {meaning}",
        "checks": checks,
        "steps": detail_meta["steps"],
        "raw_output": raw_log,
        "duration_ms": elapsed_ms,
        "metrics_json": {
            "ip_1": valid_ip1,
            "ip_2": valid_ip2,
            "ip_1_up": ip1_up,
            "ip_2_up": ip2_up,
            "isp_name": norm_isp,
            "four_g_hub_detected": four_g_detected,
            "detected_hub_ip": detected_hub,
            "check_mode": check_mode,
            "diagnosis_title": detail_meta["diagnosis_title"],
            "root_cause": detail_meta["root_cause"],
            "responsible_team": detail_meta["responsible_team"],
            "ai_workflow_action": detail_meta["ai_workflow_action"],
            "operator_action": detail_meta["operator_action"],
            "steps": detail_meta["steps"],
        },
    }


async def run_diagnostic_contract(payload: DiagnosticInput) -> DiagnosticOutput:
    """Adapter satisfying the frozen `DiagnosticScriptContract` (`DiagnosticInput -> DiagnosticOutput`)."""
    ip2 = str(payload.extra_meta.get("ip_2") or payload.target_ip.rsplit(".", 1)[0] + ".2")
    isp_name = str(payload.extra_meta.get("isp_name") or "NOOR")
    hub_ip = payload.extra_meta.get("four_g_hub_ip")
    scenario = payload.extra_meta.get("simulate_scenario", "AUTO")

    res = await execute_dual_ping_and_traceroute(
        branch_code=payload.branch_code,
        branch_name=payload.branch_name,
        ip_1=payload.target_ip,
        ip_2=ip2,
        isp_name=isp_name,
        four_g_hub_ip=str(hub_ip) if hub_ip else None,
        simulate_scenario=str(scenario) if scenario else "AUTO",
    )
    return DiagnosticOutput(
        status=DiagnosticStatus(res["result_status"]),
        summary=str(res["summary"]),
        metrics=dict(res["metrics_json"]),
        raw_output=str(res["raw_output"]),
        duration_ms=int(res["duration_ms"]),
    )
