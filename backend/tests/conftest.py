"""Shared pytest fixtures for IT Network Support AI Agent & Ticketing Harness tests.

Sets `DIAGNOSTIC_MODE=simulated` and `LOOP_GUARD_FAIL_OPEN_FOR_TESTS=true` by default
and installs a deterministic `FakeVllm` `guided_json` responder so unit/integration tests
run offline without a live vLLM server while exercising the full Stage 1 + Stage 2 pipeline.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from app.agent.vllm_client import set_vllm_override
from app.common.config import get_settings
from app.common.contracts import (
    BranchEmailAnalysis,
    IspResponseAnalysis,
    RouterPhotoVisionAnalysis,
    TicketPriority,
)
from app.email_engine.parser import (
    extract_branch_sap_code,
    extract_isp_reference_number,
    extract_site_phone,
)


def default_fake_vllm_responder(
    messages: list[dict[str, Any]],
    schema: type[BaseModel],
    images: list[bytes] | None = None,
) -> BaseModel:
    """Deterministic `FakeVllm` responder for `IspResponseAnalysis`, `BranchEmailAnalysis`, and `RouterPhotoVisionAnalysis`."""
    user_text = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") != "system")
    lower = user_text.lower()

    if schema is RouterPhotoVisionAnalysis:
        fresh_vision_part = user_text.split("\nFull Thread Replies")[0].lower()
        unplugged = any(
            kw in fresh_vision_part
            for kw in (
                "unplugged",
                "loose",
                "disconnected",
                "cable_off",
                "no_cable",
                "power led off",
                "dark power",
            )
        )
        if unplugged:
            return RouterPhotoVisionAnalysis(
                cables_plugged=False,
                power_led_on=False,
                wan_led_on=False,
                confidence=0.93,
                summary="WAN RJ45 cable appears loose/unplugged and power LED is dark.",
            )
        return RouterPhotoVisionAnalysis(
            cables_plugged=True,
            power_led_on=True,
            wan_led_on=False,
            confidence=0.96,
            summary="Power LED solid green; WAN and LAN RJ45 cables firmly seated.",
        )

    subj_match = re.search(r"Subject:\s*(.+)", user_text)
    subj = subj_match.group(1).strip() if subj_match else ""
    body_idx = user_text.find("Fresh Body:\n")
    fresh_body = user_text[body_idx + len("Fresh Body:\n") :] if body_idx != -1 else user_text
    thread_idx = fresh_body.find("\n\nThread Replies")
    if thread_idx != -1:
        thread_context = fresh_body[thread_idx:]
        fresh_body = fresh_body[:thread_idx]
    else:
        thread_context = ""
    combined_lower = f"{subj}\n{fresh_body}".lower()

    isp_ref = extract_isp_reference_number(subj, fresh_body) or extract_isp_reference_number(
        subj, thread_context
    )
    branch_code = extract_branch_sap_code(subj, fresh_body) or extract_branch_sap_code(
        subj, thread_context
    )
    site_phone = extract_site_phone(fresh_body) or extract_site_phone(thread_context)

    if schema is IspResponseAnalysis:
        # 1. Special blockers requiring human review
        if any(k in combined_lower for k in ("quota", "bundle consumed", "exceeded quota")):
            return IspResponseAnalysis(
                intent="SPECIAL_BLOCKER",
                isp_ticket_number=isp_ref,
                special_blocker_reason="QUOTA_CONSUMED",
                confidence=0.95,
                summary=f"ISP reported 4G backup quota consumed for store {branch_code or '—'}.",
            )
        if any(k in combined_lower for k in ("msan", "migration", "cabin")):
            return IspResponseAnalysis(
                intent="SPECIAL_BLOCKER",
                isp_ticket_number=isp_ref,
                special_blocker_reason="MSAN_MIGRATION",
                confidence=0.94,
                summary=f"ISP reported MSAN migration blocker for store {branch_code or '—'}.",
            )
        if any(
            k in combined_lower
            for k in ("internal cable", "from the box", "box to router", "internal wiring")
        ):
            return IspResponseAnalysis(
                intent="SPECIAL_BLOCKER",
                isp_ticket_number=isp_ref,
                special_blocker_reason="INTERNAL_BOX_CABLE",
                confidence=0.94,
                summary=f"ISP reported internal box-to-router cabling issue for store {branch_code or '—'}.",
            )

        # 2. Site contact unreachable
        if any(
            k in combined_lower
            for k in (
                "switched off",
                "not reachable",
                "unreachable",
                "no answer",
                "busy",
                "available site contact",
                "another contact",
                "unreachable/busy",
                "tried to call",
            )
        ):
            return IspResponseAnalysis(
                intent="SITE_CONTACT_UNREACHABLE",
                isp_ticket_number=isp_ref,
                confidence=0.94,
                summary=f"ISP reported site contact phone unreachable for Case #{isp_ref or '—'}.",
            )

        # 3. Branch-side action blocker (restart router / check power / swap SIM)
        if any(
            k in combined_lower
            for k in (
                "check power",
                "restart the router",
                "reboot router",
                "check the router power",
                "kindly check router",
            )
        ) and not any(k in combined_lower for k in ("restored", "solved", "closed", "closure")):
            return IspResponseAnalysis(
                intent="BRANCH_ACTION_BLOCKER",
                isp_ticket_number=isp_ref,
                confidence=0.92,
                summary=f"ISP requested on-site router power/reboot check for store {branch_code or '—'}.",
            )

        # 4. ISP Closure / Resolution
        if any(
            k in combined_lower
            for k in (
                "ticket closure",
                "confirm ticket closure",
                "confirm closure",
                "link is up",
                "link has been restored",
                "working fine now",
                "problem has been solved",
                "solved and",
                "case closed",
                "closing trouble ticket",
                "0% packet loss",
                "operational now",
            )
        ):
            return IspResponseAnalysis(
                intent="RESOLUTION_CLAIM",
                isp_ticket_number=isp_ref,
                confidence=0.95,
                summary=f"ISP reported circuit restored and requested closure verification (Case #{isp_ref or '—'}).",
            )

        # 5. ISP Welcome / Ticket Initiation vs Investigated Update vs Auto Ack
        if any(
            k in combined_lower
            for k in (
                "ticket initiation",
                "opened trouble ticket",
                "registered with ticket number",
                "ref.tt#",
                "request id :##re-",
            )
        ):
            return IspResponseAnalysis(
                intent="ISP_WELCOME",
                isp_ticket_number=isp_ref,
                confidence=0.96,
                summary=f"ISP acknowledged escalation and opened Case #{isp_ref or '—'}.",
            )

        if isp_ref is None and any(
            k in combined_lower for k in ("automated response", "auto-ack", "received your email")
        ):
            return IspResponseAnalysis(
                intent="AUTO_ACK",
                isp_ticket_number=None,
                confidence=0.90,
                summary="ISP sent an automated acknowledgement without a case reference.",
            )

        return IspResponseAnalysis(
            intent="INVESTIGATING_UPDATE",
            isp_ticket_number=isp_ref,
            confidence=0.91,
            summary=f"ISP NOC investigation update on Case #{isp_ref or '—'}.",
        )

    if schema is BranchEmailAnalysis:
        is_res_confirmed = any(
            k in combined_lower
            for k in (
                "working fine now",
                "link is restored",
                "back online",
                "issue resolved",
                "working now",
            )
        ) and not any(k in combined_lower for k in ("still down", "still offline", "not working"))

        has_network_keywords = any(
            k in combined_lower
            for k in (
                "down",
                "offline",
                "outage",
                "router",
                "connection",
                "network",
                "pos",
                "disconnected",
                "cables",
                "reseated",
                "store",
                "branch",
                "kazyon",
                "quo1-",
                "active phone",
                "new phone",
                "site contact",
                "shift manager",
            )
        )
        if branch_code or has_network_keywords or is_res_confirmed:
            return BranchEmailAnalysis(
                is_network_issue=True,
                branch_identifier=branch_code,
                site_contact_phone=site_phone,
                has_router_photo=".jpg" in lower or ".png" in lower or ".jpeg" in lower,
                reported_symptoms=fresh_body[:200]
                or f"Store {branch_code or '—'} connectivity issue",
                urgency=TicketPriority.HIGH,
                is_resolution_confirmation=is_res_confirmed,
                confidence=0.93 if branch_code else 0.86,
            )

        return BranchEmailAnalysis(
            is_network_issue=False,
            branch_identifier=None,
            site_contact_phone=None,
            has_router_photo=False,
            reported_symptoms="Unrelated non-network email",
            urgency=TicketPriority.LOW,
            is_resolution_confirmation=False,
            confidence=0.42,
        )

    raise AssertionError(f"Unexpected schema in FakeVllm: {schema}")


@pytest.fixture(autouse=True)
def configure_test_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[None, None, None]:
    """Configure test environment with simulated diagnostics, fail-open loop guard for tests, and FakeVllm."""
    monkeypatch.setenv("DIAGNOSTIC_MODE", "simulated")
    monkeypatch.setenv("LOOP_GUARD_FAIL_OPEN_FOR_TESTS", "true")
    monkeypatch.setenv("ATTACHMENTS_DIR", str(tmp_path / "attachments"))
    get_settings.cache_clear()
    set_vllm_override(default_fake_vllm_responder)
    try:
        yield
    finally:
        set_vllm_override(None)
        get_settings.cache_clear()
