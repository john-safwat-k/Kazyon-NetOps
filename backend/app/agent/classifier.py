"""Guided-JSON Multimodal Vision & Universal Email Triage Classifier (`Gemma 4 26B A4B` + Deterministic Rules)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.agent.prompts import (
    BRANCH_EMAIL_ANALYSIS_PROMPT,
    ISP_RESPONSE_ANALYSIS_PROMPT,
    ROUTER_PHOTO_VISION_PROMPT,
)
from app.agent.vllm_client import VllmCallOptions, guided_json
from app.common.contracts import (
    BranchEmailAnalysis,
    EmailEnvelope,
    EscalationReason,
    IspResponseAnalysis,
    RouterPhotoVisionAnalysis,
    UniversalEmailTriageResult,
)
from app.common.exceptions import LLMInferenceError
from app.email_engine.parser import (
    extract_branch_sap_code,
    extract_circuit_id_hint,
    extract_isp_reference_number,
    extract_site_phone,
    extract_ticket_number_tag,
    format_thread_replies_for_prompt,
    parse_replication_dashboard_html,
    read_attachment_image_bytes,
    split_email_thread_replies,
    strip_reply_quotes,
)

logger = logging.getLogger("it_net.agent.classifier")


async def inspect_router_photo(
    *,
    branch_code: str,
    image_bytes_list: Optional[list[bytes]] = None,
    image_filenames: Optional[list[str]] = None,
    email_body_hint: str = "",
    llm_options: Optional[VllmCallOptions] = None,
) -> Optional[RouterPhotoVisionAnalysis]:
    """Inspect attached branch router photo(s) via Gemma 4 26B A4B vision (`guided_json`).

    Returns `None` when no image bytes are present (no vision verdict; proceed directly to diagnostics).
    """
    if not image_bytes_list:
        return None

    fresh_hint = strip_reply_quotes(email_body_hint)[:500]
    thread_replies = split_email_thread_replies(email_body_hint)
    formatted_thread = format_thread_replies_for_prompt(thread_replies, max_chars=2500)
    messages = [
        {"role": "system", "content": ROUTER_PHOTO_VISION_PROMPT},
        {
            "role": "user",
            "content": (
                f"Branch SAP Code: {branch_code}\n"
                f"Filenames: {image_filenames or []}\n"
                f"Email body context: {fresh_hint}\n"
                f"Full Thread Replies ({len(thread_replies)}):\n{formatted_thread}"
            ),
        },
    ]
    return await guided_json(
        messages,
        RouterPhotoVisionAnalysis,
        images=image_bytes_list,
        options=llm_options,
    )


def _is_regex_certain_isp_closure(subj_lower: str, fresh_lower: str) -> bool:
    combined = f"{subj_lower}\n{fresh_lower}"
    return any(
        phrase in combined
        for phrase in (
            "ticket closure",
            "link has been restored",
            "line restored",
            "problem has been solved",
            "working fine now",
            "0% packet loss",
            "case is closed",
        )
    )


async def classify_inbound_email(
    envelope: EmailEnvelope,
    *,
    confidence_threshold_pct: int = 80,
    correlated_branch_code: Optional[str] = None,
    correlated_thread_type: Optional[str] = None,
    correlated_isp_name: Optional[str] = None,
    thread_history: Optional[list[dict[str, Any]]] = None,
    llm_options: Optional[VllmCallOptions] = None,
) -> UniversalEmailTriageResult:
    """Two-stage inbound email classifier that reads the full email thread and every reply:
    Stage 1 (Deterministic): sender party routing, Replication Dashboard HTML, entity extraction (`branch_code`, `isp_ref`, `circuit_hint`, `phone`, `ticket_tag`) across all thread replies and prior DB messages.
    Stage 2 (vLLM Guided JSON): `IspResponseAnalysis` for ISP mail and `BranchEmailAnalysis` for branch/other mail, passing both `Fresh Body` and `Thread Replies` / `Full Thread Body`.
    """
    sender_lower = envelope.sender.lower()
    subj_lower = envelope.subject.lower()
    fresh_body = strip_reply_quotes(envelope.body_text)
    fresh_lower = fresh_body.lower()
    combined_fresh_lower = f"{subj_lower}\n{fresh_lower}"

    thread_replies = split_email_thread_replies(envelope.body_text)
    formatted_thread = format_thread_replies_for_prompt(
        thread_replies,
        prior_db_emails=thread_history,
        max_chars=6000,
    )
    prior_history_text = "\n".join(
        f"{m.get('subject', '')}\n{m.get('body_text', '')}"
        for m in reversed(thread_history or [])
    )

    branch_code = (
        extract_branch_sap_code(
            envelope.subject,
            fresh_body,
            preferred_branch_code=correlated_branch_code,
        )
        or extract_branch_sap_code(
            envelope.subject,
            envelope.body_text,
            preferred_branch_code=correlated_branch_code,
        )
        or (
            extract_branch_sap_code(
                envelope.subject,
                prior_history_text,
                preferred_branch_code=correlated_branch_code,
            )
            if prior_history_text
            else None
        )
        or correlated_branch_code
    )
    isp_ref = (
        extract_isp_reference_number(envelope.subject, fresh_body)
        or extract_isp_reference_number(envelope.subject, envelope.body_text)
        or (
            extract_isp_reference_number(envelope.subject, prior_history_text)
            if prior_history_text
            else None
        )
    )
    phone = (
        extract_site_phone(fresh_body)
        or extract_site_phone(envelope.body_text)
        or (extract_site_phone(prior_history_text) if prior_history_text else None)
    )
    ticket_tag = extract_ticket_number_tag(envelope.subject, envelope.body_text) or (
        extract_ticket_number_tag(envelope.subject, prior_history_text)
        if prior_history_text
        else None
    )
    circuit_hint = extract_circuit_id_hint(envelope.subject, envelope.body_text) or (
        extract_circuit_id_hint(envelope.subject, prior_history_text)
        if prior_history_text
        else None
    )
    thread_meta: dict[str, Any] = {
        "thread_reply_count": len(thread_replies),
        "thread_replies": thread_replies,
        "prior_db_email_count": len(thread_history or []),
    }

    # 1. Stage 1 Deterministic Trigger: Replication Dashboard Email (D2 high-precision rule)
    if "replication dashboard" in subj_lower or (
        envelope.body_html and "not updated" in envelope.body_html.lower()
    ):
        rows = parse_replication_dashboard_html(envelope.body_html or envelope.body_text)
        not_upd = sum(1 for r in rows if r.get("status") == "Not Updated")
        return UniversalEmailTriageResult(
            trigger_type="REPLICATION_REPORT",
            classification_label="REPLICATION_REPORT",
            intent="REPLICATION_REPORT",
            confidence=0.99,
            next_action="NOTIFY_REGIONAL_IT",
            summary=f"Replication Dashboard parsed ({len(rows)} rows, {not_upd} Not Updated).",
            raw_analysis={
                "intent": "REPLICATION_REPORT",
                "rows": len(rows),
                "not_updated": not_upd,
                "next_action": "NOTIFY_REGIONAL_IT",
                **thread_meta,
            },
        )

    # Determine if sender/subject belongs to an ISP thread (NOOR / ORANGE / WE)
    is_isp_sender = (
        any(
            tok in sender_lower
            for tok in (
                "noor.net",
                "orange.com",
                "te.eg",
                "psupport",
                "noc@",
                "ccc-eg",
                "corporatesupport",
            )
        )
        and "billing@" not in sender_lower
    )
    is_isp_subject = any(
        tok in subj_lower
        for tok in (
            "noor noc",
            "##re-",
            "quo1-",
            "ticket initiation",
            "ticket closure",
            "ticket update",
            "case no",
        )
    ) and not any(
        reg_tok in sender_lower
        for reg_tok in ("gitsupport", "citsupport", "bitsupport", "newoct", "assiut", "store")
    )

    is_isp_thread_reply = (
        correlated_thread_type == "ISP"
        or "[role:isp]" in combined_fresh_lower
        or "[isp]" in subj_lower
        or envelope.raw_headers.get("X-Kz-Thread", "").upper() == "ISP"
    )

    if is_isp_sender or is_isp_subject or is_isp_thread_reply:
        isp_name: Optional[str] = None
        if "noor" in sender_lower or "noor" in subj_lower:
            isp_name = "NOOR"
        elif (
            "orange" in sender_lower
            or "quo1-" in subj_lower
            or (circuit_hint or "").startswith("QUO1-")
        ):
            isp_name = "ORANGE"
        elif "te.eg" in sender_lower or "psupport" in sender_lower or "##re-" in subj_lower:
            isp_name = "WE"
        elif correlated_isp_name:
            isp_name = correlated_isp_name

        try:
            isp_analysis = await guided_json(
                [
                    {"role": "system", "content": ISP_RESPONSE_ANALYSIS_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"From: {envelope.sender}\n"
                            f"Subject: {envelope.subject}\n"
                            f"Fresh Body:\n{fresh_body[:1600]}\n\n"
                            f"Thread Replies ({len(thread_replies)} in email, {len(thread_history or [])} prior DB messages):\n{formatted_thread}\n\n"
                            f"Full Thread Body:\n{envelope.body_text[:4000]}"
                        ),
                    },
                ],
                IspResponseAnalysis,
                options=llm_options,
            )
        except LLMInferenceError:
            # Per D2: header/[NET-XXXX] match combined with regex-certain ISP closure can act deterministically
            has_header_or_tag_match = bool(
                envelope.in_reply_to or envelope.references or ticket_tag or correlated_branch_code
            )
            if has_header_or_tag_match and _is_regex_certain_isp_closure(subj_lower, fresh_lower):
                return UniversalEmailTriageResult(
                    trigger_type="ISP_REPLY",
                    classification_label="ISP_CLOSURE",
                    branch_code=branch_code,
                    isp_name=isp_name,
                    isp_reference_number=isp_ref,
                    intent="ISP_RESOLVED",
                    confidence=0.98,
                    next_action="FINAL_VERIFICATION",
                    summary="Deterministic regex-certain ISP closure on correlated thread.",
                    raw_analysis={
                        "intent": "ISP_RESOLVED",
                        "deterministic_d2_fallback": True,
                        "branch_code": branch_code,
                        "isp": isp_name,
                        "isp_ref": isp_ref,
                        "ticket_tag": ticket_tag,
                        "confidence": 0.98,
                        **thread_meta,
                    },
                )
            raise

        resolved_isp_ref = isp_ref or isp_analysis.isp_ticket_number
        conf = float(isp_analysis.confidence)

        if int(round(conf * 100)) < confidence_threshold_pct:
            return UniversalEmailTriageResult(
                trigger_type="UNRECOGNIZED",
                classification_label="UNRECOGNIZED",
                branch_code=branch_code,
                isp_name=isp_name,
                isp_reference_number=resolved_isp_ref,
                intent="UNKNOWN",
                confidence=conf,
                next_action="HUMAN_REVIEW",
                summary=f"Low confidence ISP email ({conf:.2f} < {confidence_threshold_pct / 100:.2f}); routed to Human Review.",
                raw_analysis={
                    **isp_analysis.model_dump(),
                    "branch_code": branch_code,
                    "isp": isp_name,
                    "isp_ref": resolved_isp_ref,
                    "ticket_tag": ticket_tag,
                    **thread_meta,
                },
            )

        if isp_analysis.intent == "SPECIAL_BLOCKER":
            esc_reason = isp_analysis.special_blocker_reason or (
                EscalationReason.QUOTA_CONSUMED.value
                if "quota" in combined_fresh_lower
                else (
                    EscalationReason.MSAN_MIGRATION.value
                    if "msan" in combined_fresh_lower
                    else (
                        EscalationReason.INTERNAL_BOX_CABLE.value
                        if "cable" in combined_fresh_lower
                        else EscalationReason.OTHER.value
                    )
                )
            )
            return UniversalEmailTriageResult(
                trigger_type="ISP_REPLY",
                classification_label="ISP_BLOCKER",
                branch_code=branch_code,
                isp_name=isp_name,
                isp_reference_number=resolved_isp_ref,
                intent="SPECIAL_BLOCKER",
                confidence=conf,
                next_action="HUMAN_REVIEW",
                summary=isp_analysis.summary,
                raw_analysis={
                    **isp_analysis.model_dump(),
                    "escalation_reason": esc_reason,
                    "branch_code": branch_code,
                    "isp": isp_name,
                    "isp_ref": resolved_isp_ref,
                    "ticket_tag": ticket_tag,
                    **thread_meta,
                },
            )

        if isp_analysis.intent == "SITE_CONTACT_UNREACHABLE":
            return UniversalEmailTriageResult(
                trigger_type="ISP_REPLY",
                classification_label="ISP_BLOCKER",
                branch_code=branch_code,
                isp_name=isp_name,
                isp_reference_number=resolved_isp_ref,
                intent="SITE_CONTACT_UNREACHABLE",
                confidence=conf,
                next_action="ASK_REGIONAL_IT_FOR_PHONE",
                summary=isp_analysis.summary,
                raw_analysis={
                    **isp_analysis.model_dump(),
                    "branch_code": branch_code,
                    "isp": isp_name,
                    "isp_ref": resolved_isp_ref,
                    "ticket_tag": ticket_tag,
                    **thread_meta,
                },
            )

        if isp_analysis.intent == "BRANCH_ACTION_BLOCKER":
            return UniversalEmailTriageResult(
                trigger_type="ISP_REPLY",
                classification_label="ISP_BLOCKER",
                branch_code=branch_code,
                isp_name=isp_name,
                isp_reference_number=resolved_isp_ref,
                intent="BRANCH_ACTION_BLOCKER",
                confidence=conf,
                next_action="RELAY_ACTION_TO_BRANCH",
                summary=isp_analysis.summary,
                raw_analysis={
                    **isp_analysis.model_dump(),
                    "branch_code": branch_code,
                    "isp": isp_name,
                    "isp_ref": resolved_isp_ref,
                    "ticket_tag": ticket_tag,
                    **thread_meta,
                },
            )

        if isp_analysis.intent == "RESOLUTION_CLAIM":
            return UniversalEmailTriageResult(
                trigger_type="ISP_REPLY",
                classification_label="ISP_CLOSURE",
                branch_code=branch_code,
                isp_name=isp_name,
                isp_reference_number=resolved_isp_ref,
                intent="ISP_RESOLVED",
                confidence=conf,
                next_action="FINAL_VERIFICATION",
                summary=isp_analysis.summary,
                raw_analysis={
                    **isp_analysis.model_dump(),
                    "branch_code": branch_code,
                    "isp": isp_name,
                    "isp_ref": resolved_isp_ref,
                    "ticket_tag": ticket_tag,
                    **thread_meta,
                },
            )

        if isp_analysis.intent == "AUTO_ACK":
            return UniversalEmailTriageResult(
                trigger_type="ISP_REPLY",
                classification_label="ISP_AUTO_ACK",
                branch_code=branch_code,
                isp_name=isp_name,
                isp_reference_number=resolved_isp_ref,
                intent="AUTO_ACK",
                confidence=conf,
                next_action="LOG_ONLY",
                summary=isp_analysis.summary,
                raw_analysis={
                    **isp_analysis.model_dump(),
                    "branch_code": branch_code,
                    "isp": isp_name,
                    "isp_ref": resolved_isp_ref,
                    "ticket_tag": ticket_tag,
                    **thread_meta,
                },
            )

        if isp_analysis.intent == "ISP_WELCOME":
            return UniversalEmailTriageResult(
                trigger_type="ISP_REPLY",
                classification_label="ISP_WELCOME",
                branch_code=branch_code,
                isp_name=isp_name,
                isp_reference_number=resolved_isp_ref,
                intent="ISP_WELCOME",
                confidence=conf,
                next_action="START_4_6H_LOOP",
                summary=isp_analysis.summary,
                raw_analysis={
                    **isp_analysis.model_dump(),
                    "branch_code": branch_code,
                    "isp": isp_name,
                    "isp_ref": resolved_isp_ref,
                    "ticket_tag": ticket_tag,
                    **thread_meta,
                },
            )

        return UniversalEmailTriageResult(
            trigger_type="ISP_REPLY",
            classification_label="ISP_WELCOME",
            branch_code=branch_code,
            isp_name=isp_name,
            isp_reference_number=resolved_isp_ref,
            intent="INVESTIGATING_UPDATE",
            confidence=conf,
            next_action="CONTINUE_4_6H_LOOP",
            summary=isp_analysis.summary,
            raw_analysis={
                **isp_analysis.model_dump(),
                "branch_code": branch_code,
                "isp": isp_name,
                "isp_ref": resolved_isp_ref,
                "ticket_tag": ticket_tag,
                **thread_meta,
            },
        )

    # 3. Stage 2 LLM Classification for Branch / Regional IT or Unknown Email
    image_bytes = read_attachment_image_bytes(envelope.attachments)
    branch_analysis = await guided_json(
        [
            {"role": "system", "content": BRANCH_EMAIL_ANALYSIS_PROMPT},
            {
                "role": "user",
                "content": (
                    f"From: {envelope.sender}\n"
                    f"Subject: {envelope.subject}\n"
                    f"Attachments: {[a.get('filename') for a in envelope.attachments]}\n"
                    f"Fresh Body:\n{fresh_body[:1600]}\n\n"
                    f"Thread Replies ({len(thread_replies)} in email, {len(thread_history or [])} prior DB messages):\n{formatted_thread}\n\n"
                    f"Full Thread Body:\n{envelope.body_text[:4000]}"
                ),
            },
        ],
        BranchEmailAnalysis,
        options=llm_options,
    )

    conf = float(branch_analysis.confidence)
    resolved_branch = branch_code or (
        branch_analysis.branch_identifier
        if branch_analysis.branch_identifier
        and len(branch_analysis.branch_identifier.strip()) == 4
        and branch_analysis.branch_identifier.strip().isdigit()
        else None
    )
    resolved_phone = phone or branch_analysis.site_contact_phone
    has_photo = bool(image_bytes) or bool(envelope.attachments) or branch_analysis.has_router_photo

    if (
        not branch_analysis.is_network_issue
        or int(round(conf * 100)) < confidence_threshold_pct
        or (resolved_branch is None and ticket_tag is None)
    ):
        return UniversalEmailTriageResult(
            trigger_type="UNRECOGNIZED",
            classification_label="UNRECOGNIZED",
            branch_code=resolved_branch,
            site_contact_phone=resolved_phone,
            intent="UNKNOWN",
            confidence=conf,
            next_action="HUMAN_REVIEW",
            summary=f"Unrecognized or low-confidence email '{envelope.subject}' from {envelope.sender} (confidence {conf:.2f}).",
            raw_analysis={
                **branch_analysis.model_dump(),
                "branch_code": resolved_branch,
                "ticket_tag": ticket_tag,
                "next_action": "HUMAN_REVIEW",
                **thread_meta,
            },
        )

    is_contact_update = resolved_phone is not None and any(
        k in combined_fresh_lower
        for k in (
            "active phone",
            "new phone",
            "cannot reach site contact",
            "shift manager",
            "updated site contact",
            "relay to the isp",
            "relay to isp",
        )
    )

    intent_val = (
        "BRANCH_RESOLUTION_CONFIRMED"
        if branch_analysis.is_resolution_confirmation
        else (
            "BRANCH_CONTACT_UPDATE"
            if is_contact_update and not bool(envelope.attachments)
            else "BRANCH_INCIDENT"
        )
    )
    next_act = (
        "CLOSE_TICKET"
        if intent_val == "BRANCH_RESOLUTION_CONFIRMED"
        else (
            "RELAY_CONTACT_TO_ISP"
            if intent_val == "BRANCH_CONTACT_UPDATE"
            else ("VISION_CHECK" if has_photo else "RUN_DIAGNOSTICS")
        )
    )

    return UniversalEmailTriageResult(
        trigger_type="BRANCH_INCIDENT",
        classification_label="INCIDENT_REPORT",
        branch_code=resolved_branch,
        site_contact_phone=resolved_phone,
        intent=intent_val,
        confidence=conf,
        next_action=next_act,
        summary=branch_analysis.reported_symptoms
        or f"Branch {resolved_branch or ticket_tag} communication ({intent_val}).",
        raw_analysis={
            **branch_analysis.model_dump(),
            "intent": intent_val,
            "branch_code": resolved_branch,
            "ticket_tag": ticket_tag,
            "site_contact_phone": resolved_phone,
            "has_router_photo": has_photo,
            "next_action": next_act,
            **thread_meta,
        },
    )
