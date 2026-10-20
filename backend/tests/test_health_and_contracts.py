"""Baseline tests for application health, contracts, and initial Super Admin bootstrap."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.common.contracts import (
    BranchEmailAnalysis,
    DiagnosticInput,
    DiagnosticOutput,
    DiagnosticStatus,
    TicketPriority,
    TicketStatus,
)
from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert "vllm_base_url" in payload
        assert payload["vllm_model"] == "google/gemma-4-26B-A4B-it"


def test_frozen_contracts_validation() -> None:
    diag_in = DiagnosticInput(
        ticket_number="NET-1001",
        branch_code="BR-001",
        branch_name="Maadi Branch",
        target_ip="10.20.30.1",
        circuit_id="WE-FIBER-9988",
    )
    assert diag_in.connection_type == "FIBER"

    diag_out = DiagnosticOutput(
        status=DiagnosticStatus.FAIL,
        summary="100% packet loss to branch gateway 10.20.30.1",
        metrics={"packet_loss_pct": 100.0},
        raw_output="PING 10.20.30.1: 5 packets transmitted, 0 received",
        duration_ms=5120,
    )
    assert diag_out.status == DiagnosticStatus.FAIL

    analysis = BranchEmailAnalysis(
        is_network_issue=True,
        branch_identifier="BR-001",
        reported_symptoms="Internet and POS down since 10 AM",
        urgency=TicketPriority.HIGH,
        confidence=0.96,
    )
    assert analysis.urgency == TicketPriority.HIGH
    assert TicketStatus.ESCALATED_TO_ISP == "ESCALATED_TO_ISP"
