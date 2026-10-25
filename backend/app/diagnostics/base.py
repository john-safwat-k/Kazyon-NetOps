"""Pluggable Network Troubleshooting Script Protocol & Schemas."""

from __future__ import annotations

from typing import Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.common.contracts import DiagnosticInput, DiagnosticOutput


class DiagnosticRunner(Protocol):
    """Protocol for any pluggable network troubleshooting runner."""

    async def run(self, payload: DiagnosticInput) -> DiagnosticOutput: ...


class DualPingTracerouteRequest(BaseModel):
    """Request payload for running the Dual-Ping (`IP1`/`IP2`) + 4G Hub Traceroute check."""

    branch_code: str = Field(default="1173", min_length=1, max_length=64)
    ip_1: Optional[str] = None
    ip_2: Optional[str] = None
    isp_name: Optional[str] = None
    four_g_hub_ip: Optional[str] = None
    check_mode: Literal["FULL", "PING_IP1", "PING_IP2", "TRACEROUTE"] = "FULL"
    mode: Optional[str] = None
    # Unset values fall back to the Page 12 settings (diagnostic timeout, ping count, max hops)
    timeout_sec: Optional[int] = Field(default=None, ge=1, le=300)
    ping_count: Optional[int] = Field(default=None, ge=1, le=20)
    traceroute_max_hops: Optional[int] = Field(default=None, ge=1, le=64)
    simulate_scenario: Optional[
        Literal[
            "LIVE_ICMP",
            "AUTO",
            "PASS",
            "FULL_OUTAGE",
            "LOCAL_LOOP_DOWN_ON_4G",
            "INTERNAL_LAN_SWITCH",
        ]
    ] = None
    ticket_id: Optional[int] = None
    trigger_source: str = "MANUAL"

    def resolved_check_mode(self) -> Literal["FULL", "PING_IP1", "PING_IP2", "TRACEROUTE"]:
        if self.mode:
            upper = self.mode.strip().upper()
            if upper in {"FULL", "PING_IP1", "PING_IP2", "TRACEROUTE"}:
                return upper  # type: ignore[return-value]
        return self.check_mode


class DiagnosticCheckPillDto(BaseModel):
    label: str
    state: Literal["up", "down", "hub", "skip"]


class DiagnosticStepDetailDto(BaseModel):
    step_number: int
    step_name: str
    target: str
    status: Literal["UP", "DOWN", "HUB_DETECTED", "MPLS_DIRECT", "SKIPPED"]
    tone: Literal["good", "warning", "critical", "info", "neutral"]
    latency_or_hops: str
    explanation: str


class DiagnosticRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: Optional[int] = None
    branch_code: Optional[str] = None
    branch_label: Optional[str] = None
    isp_name: Optional[str] = None
    trigger_source: str
    ip_1_up: Optional[bool] = None
    ip_2_up: Optional[bool] = None
    four_g_hub_detected: Optional[bool] = None
    detected_hub_ip: Optional[str] = None
    result_status: str
    diagnosis_code: Optional[str] = None
    diagnosis_title: str = ""
    meaning: str = ""
    root_cause: str = ""
    responsible_team: str = ""
    ai_workflow_action: str = ""
    operator_action: str = ""
    summary: str
    checks: list[DiagnosticCheckPillDto] = Field(default_factory=list)
    steps: list[DiagnosticStepDetailDto] = Field(default_factory=list)
    metrics_json: dict[str, object] = Field(default_factory=dict)
    raw_output: str
    duration_ms: int
    executed_at: str


class DiagnosticSuiteRunRequest(BaseModel):
    """Request payload for running the Full Fleet Diagnostic Test Suite across branches."""

    isp_name: Optional[str] = None
    region: Optional[str] = None
    search: Optional[str] = None
    simulate_scenario: Literal[
        "LIVE_ICMP",
        "AUTO",
        "PASS",
        "FULL_OUTAGE",
        "LOCAL_LOOP_DOWN_ON_4G",
        "INTERNAL_LAN_SWITCH",
    ] = "AUTO"
    ping_count: int = Field(default=4, ge=1, le=20)
    traceroute_max_hops: int = Field(default=15, ge=1, le=64)
    limit: int = Field(default=2000, ge=1, le=5000)


class DiagnosticSuiteIspSummary(BaseModel):
    isp_name: str
    total: int
    pass_count: int
    full_outage_count: int
    four_g_count: int
    lan_switch_count: int
    health_pct: float


class DiagnosticSuiteRegionSummary(BaseModel):
    region: str
    total: int
    pass_count: int
    full_outage_count: int
    four_g_count: int
    lan_switch_count: int
    health_pct: float


class DiagnosticSuiteBranchItem(BaseModel):
    branch_code: str
    branch_name: str
    region: str
    isp_name: str
    ip_1: str
    ip_2: str
    four_g_hub_ip: Optional[str] = None
    ll_circuit_id: Optional[str] = None
    backup_circuit_id: Optional[str] = None
    regional_it_email: Optional[str] = None
    ip_1_up: bool
    ip_2_up: Optional[bool] = None
    ip_2_skipped: bool
    four_g_hub_detected: bool
    detected_hub_ip: Optional[str] = None
    result_status: str
    diagnosis_code: str
    diagnosis_title: str
    meaning: str
    root_cause: str
    responsible_team: str
    ai_workflow_action: str
    operator_action: str
    checks: list[DiagnosticCheckPillDto] = Field(default_factory=list)
    steps: list[DiagnosticStepDetailDto] = Field(default_factory=list)
    raw_output: str
    duration_ms: int


class DiagnosticSuiteReportResponse(BaseModel):
    suite_id: str
    executed_at: str
    duration_ms: int
    scenario_mode: str
    total_branches: int
    pass_count: int
    full_outage_count: int
    four_g_count: int
    lan_switch_count: int
    health_pct: float
    by_isp: list[DiagnosticSuiteIspSummary] = Field(default_factory=list)
    by_region: list[DiagnosticSuiteRegionSummary] = Field(default_factory=list)
    items: list[DiagnosticSuiteBranchItem] = Field(default_factory=list)
