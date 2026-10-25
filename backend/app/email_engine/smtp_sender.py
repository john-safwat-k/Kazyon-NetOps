"""Outbound Email Formatter & Dispatcher with strict Branch vs ISP thread separation (BRD §3.2 & FR-6.1)."""

from __future__ import annotations

import asyncio
import email.utils
import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, cast
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from app.common.config import get_settings
from app.common.crypto import decrypt_secret
from app.common.exceptions import EmailDeliveryError
from app.directory.models import Branch, NetworkProvider
from app.directory.seeder import REGIONAL_IT_DEFAULTS
from app.email_engine.loop_guard import check_and_increment_outbound_allowance
from app.email_engine.parser import extract_branch_sap_code
from app.ticketing.models import SystemSettings, Ticket, TicketEmail, TicketEvent

logger = logging.getLogger("it_net.email_engine.smtp_sender")

_CANONICAL_ISP_DEFAULTS: dict[str, str] = {
    "NOOR": "noc@noor.net",
    "ORANGE": "ccc-eg@orange.com",
    "WE": "psupport@te.eg",
}


def resolve_branch_regional_it_cc(
    branch: Optional[Branch],
    db: Optional[Session] = None,
) -> list[str]:
    """Resolve the branch's Regional IT email (`branch.regional_it_email`, falling back to
    `REGIONAL_IT_DEFAULTS` by region or `CITSupport@kazyon.com`) so every email sent to a
    branch CCs its Regional IT mailbox."""
    if branch is not None:
        reg_mail = (branch.regional_it_email or "").strip()
        if not reg_mail:
            reg_mail = REGIONAL_IT_DEFAULTS.get(branch.region or "Cairo", "CITSupport@kazyon.com")
        return [reg_mail] if reg_mail else ["CITSupport@kazyon.com"]
    return ["CITSupport@kazyon.com"]


def resolve_isp_recipients(
    branch: Branch,
    db: Optional[Session] = None,
) -> tuple[list[str], list[str]]:
    """Resolve the active ISP `To` and `CC` email lists for a branch, prioritizing any ISP card
    overrides saved in `NetworkProvider` on Page 10 (`Branches & ISP Directory -> ISPs - 3`)."""
    isp = (branch.isp_name or "NOOR").upper()
    canonical_default = _CANONICAL_ISP_DEFAULTS.get(isp, "noc@noor.net")
    branch_mail = (branch.isp_contact_mail or "").strip()

    sess = db or object_session(branch)
    provider: Optional[NetworkProvider] = None
    if sess is not None:
        if branch.isp_id:
            provider = sess.get(NetworkProvider, branch.isp_id)
        if provider is None:
            provider = sess.execute(
                select(NetworkProvider).where(func.upper(NetworkProvider.name) == isp).limit(1)
            ).scalar_one_or_none()

    if provider is not None:
        prov_mail = (provider.support_email or "").strip()
        if prov_mail and (not branch_mail or branch_mail == canonical_default):
            to_addr = prov_mail
        else:
            to_addr = branch_mail or prov_mail or canonical_default
        cc_list = (
            [c.strip() for c in (provider.cc_emails or []) if c.strip()]
            if provider.cc_emails is not None and len(provider.cc_emails) > 0
            else ["ITInfrastructure@kazyon.com"]
        )
        return [to_addr], cc_list

    return [branch_mail or canonical_default], ["ITInfrastructure@kazyon.com"]


def format_isp_escalation_email(
    branch: Branch,
    *,
    site_contact_phone: Optional[str] = None,
    db: Optional[Session] = None,
) -> tuple[str, str, list[str], list[str], str]:
    """Build exact provider-specific escalation `(subject, body, to_list, cc_list, template_code)` per BRD §3.2."""
    isp = (branch.isp_name or "NOOR").upper()
    sap = branch.branch_code
    clean_phone = (site_contact_phone or "").strip()
    phone = clean_phone if clean_phone else "will be shared shortly"
    ll_id = branch.ll_circuit_id or f"LL-{sap}"
    g3_id = branch.backup_circuit_id or f"3G-{sap}"
    to_list, cc = resolve_isp_recipients(branch, db=db)

    if isp == "ORANGE":
        subject = f"store {sap} # {ll_id}"
        body = (
            "Dear NOC\n"
            f"kindly check L.L and 4G connection store {sap}\n"
            f"{sap}\n"
            f"{ll_id}\n"
            f"{g3_id}\n"
            f"site contact : {phone}"
        )
        return subject, body, to_list, cc, "ORANGE_ESCALATION"

    if isp == "WE":
        subject = f"Kazyon #E33209 #{ll_id} #{g3_id} #{sap}"
        body = (
            "Dear support\n"
            "kindly check LL & 4G connection\n"
            f"LL order number : {ll_id}\n"
            f"4G order number : {g3_id}\n"
            f"site contact : {phone}\n"
            "site work from 9 AM to 12 AM\n"
            "power working fine at site"
        )
        return subject, body, to_list, cc, "WE_ESCALATION"

    # Default: NOOR
    subject = f"store {sap}"
    body = f"Dear NOC\nKindly check connection store {sap}\nsite contact : {phone}"
    return subject, body, to_list, cc, "NOOR_ESCALATION"


SmtpSecurity = Literal["starttls", "ssl", "none"]
SmtpStage = Literal["config", "connect", "ehlo", "tls", "auth", "sender", "done"]


@dataclass(frozen=True)
class SmtpTransportConfig:
    """Outbound SMTP settings: host, port, mode, sender, and optional encrypted login from Page 12
    (`system_settings`), with fallback to `SMTP_USERNAME` / `SMTP_PASSWORD` in `.env`."""

    host: str
    port: int
    security: SmtpSecurity
    enabled: bool
    from_address: str
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)
    test_redirect_email: str = ""

    @property
    def credentials_configured(self) -> bool:
        return bool(self.username and self.password)


class _SmtpStageError(Exception):
    def __init__(self, stage: SmtpStage, exc: Exception) -> None:
        if isinstance(exc, smtplib.SMTPResponseException):
            reply = exc.smtp_error
            text = reply.decode("utf-8", errors="replace") if isinstance(reply, bytes) else reply
            message = f"{exc.smtp_code} {' '.join(str(text).split())}"
        else:
            message = f"{type(exc).__name__}: {exc}"
        super().__init__(message)
        self.stage = stage


def smtp_transport_config_from_row(row: Optional[SystemSettings]) -> SmtpTransportConfig:
    """Build the transport from a saved Page 12 settings row plus `.env` fallback."""
    settings = get_settings()
    security = (row.smtp_security if row is not None else "starttls") or "starttls"
    row_user = (row.smtp_username or "").strip() if row is not None else ""
    row_pass = decrypt_secret(row.smtp_password_encrypted or "") if row is not None else ""
    row_redirect = (row.test_redirect_email or "").strip() if row is not None else ""
    return SmtpTransportConfig(
        host=(row.smtp_host if row is not None else "").strip(),
        port=row.smtp_port if row is not None else 587,
        security=cast(SmtpSecurity, security),
        enabled=bool(row.smtp_enabled) if row is not None else False,
        from_address=(row.mailbox_account if row is not None else "") or "noc@kazyon.com",
        username=row_user or settings.smtp_username,
        password=row_pass or settings.smtp_password,
        test_redirect_email=row_redirect,
    )


def load_smtp_transport_config(db: Session) -> SmtpTransportConfig:
    row = db.execute(
        select(SystemSettings).where(SystemSettings.config_key == "global").limit(1)
    ).scalar_one_or_none()
    return smtp_transport_config_from_row(row)


def _open_smtp_session(cfg: SmtpTransportConfig, timeout_sec: float) -> smtplib.SMTP:
    """Connect, greet, secure and (when a login is configured) authenticate.

    Raises `_SmtpStageError` naming the step that failed, so the Settings test can say
    exactly what is wrong (DNS/port, TLS, or login).
    """
    try:
        server: smtplib.SMTP = (
            smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=timeout_sec)
            if cfg.security == "ssl"
            else smtplib.SMTP(cfg.host, cfg.port, timeout=timeout_sec)
        )
    except Exception as exc:
        raise _SmtpStageError("connect", exc) from exc
    try:
        try:
            server.ehlo()
        except Exception as exc:
            raise _SmtpStageError("ehlo", exc) from exc
        if cfg.security == "starttls":
            try:
                server.starttls()
                server.ehlo()
            except Exception as exc:
                raise _SmtpStageError("tls", exc) from exc
        if cfg.credentials_configured:
            try:
                server.login(cfg.username, cfg.password)
            except Exception as exc:
                raise _SmtpStageError("auth", exc) from exc
    except _SmtpStageError:
        try:
            server.close()
        except Exception:
            pass
        raise
    return server


def test_smtp_connection_sync(
    cfg: SmtpTransportConfig, timeout_sec: float = 10.0
) -> dict[str, Any]:
    """Open a real SMTP session (connect, EHLO, TLS, login, sender accepted) without sending anything."""
    started = time.perf_counter()
    result: dict[str, Any] = {
        "ok": False,
        "host": cfg.host,
        "port": cfg.port,
        "security": cfg.security,
        "authenticated": False,
        "credentials_configured": cfg.credentials_configured,
        "stage": "config",
        "server_banner": None,
        "error": None,
    }
    if not cfg.host:
        result["error"] = "SMTP host is empty."
    else:
        try:
            server = _open_smtp_session(cfg, timeout_sec)
            try:
                banner = server.ehlo_resp or b""
                result["server_banner"] = (
                    banner.decode("utf-8", errors="replace").splitlines()[0][:200]
                    if banner
                    else None
                )
                # Ask the server to accept our sender, then reset: proves we may send without
                # sending (e.g. Office 365 refuses MAIL FROM until the client has logged in).
                code, reply = server.mail(cfg.from_address)
                if code >= 400:
                    raise _SmtpStageError(
                        "sender",
                        smtplib.SMTPSenderRefused(code, reply, cfg.from_address),
                    )
                server.rset()
            finally:
                try:
                    server.quit()
                except Exception:
                    server.close()
            result.update(ok=True, stage="done", authenticated=cfg.credentials_configured)
        except _SmtpStageError as exc:
            result.update(stage=exc.stage, error=str(exc))
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return result


def _send_via_live_smtp_sync(
    *,
    sender: str,
    recipients: list[str],
    cc: list[str],
    subject: str,
    body_text: str,
    raw_headers: dict[str, str],
    transport: SmtpTransportConfig,
) -> bool:
    """Synchronous SMTP delivery helper executed via `asyncio.to_thread`.

    Returns False (nothing sent) while outbound delivery is disabled on Page 12.
    """
    if not (transport.enabled and transport.host):
        return False

    try:
        redirect_addr = (transport.test_redirect_email or "").strip()
        effective_recipients = [redirect_addr] if redirect_addr else recipients
        effective_cc = [] if redirect_addr else cc
        effective_body = body_text
        if redirect_addr:
            banner = (
                "================================================================\n"
                f"[KAZYON SANDBOX REDIRECT — Thread: {raw_headers.get('X-Kz-Thread', 'BRANCH')} | "
                f"Ticket: {raw_headers.get('X-Kz-Ticket', 'GLOBAL')}]\n"
                f"Original To: {', '.join(recipients)}\n"
                f"Original Cc: {', '.join(cc) if cc else 'None'}\n"
                "Tip: Reply directly to this email to role-play as the recipient above.\n"
                "================================================================\n\n"
            )
            effective_body = banner + body_text

        msg = EmailMessage()
        msg["Message-ID"] = raw_headers.get("Message-ID", f"<{uuid4().hex}@kazyon.com>")
        msg["Date"] = raw_headers.get(
            "Date", email.utils.format_datetime(datetime.now(timezone.utc))
        )
        msg["From"] = sender
        msg["To"] = ", ".join(effective_recipients)
        if effective_cc:
            msg["Cc"] = ", ".join(effective_cc)
        if redirect_addr:
            msg["X-Kz-Original-To"] = ", ".join(recipients)
            if cc:
                msg["X-Kz-Original-Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        if raw_headers.get("In-Reply-To"):
            msg["In-Reply-To"] = raw_headers["In-Reply-To"]
        if raw_headers.get("References"):
            msg["References"] = raw_headers["References"]
        msg["X-Kz-Thread"] = raw_headers.get("X-Kz-Thread", "BRANCH")
        msg["Auto-Submitted"] = "no"
        msg.set_content(effective_body)

        all_rcpts = list(dict.fromkeys([*effective_recipients, *effective_cc]))
        server = _open_smtp_session(transport, timeout_sec=15.0)
        try:
            server.send_message(msg, from_addr=sender, to_addrs=all_rcpts)
        finally:
            try:
                server.quit()
            except Exception:
                server.close()
        logger.info("Dispatched live SMTP email to=%s subject=%r", all_rcpts, subject)
        return True
    except _SmtpStageError as exc:
        raise EmailDeliveryError(
            f"{transport.host}:{transport.port} failed at {exc.stage}: {exc}"
        ) from exc
    except Exception as exc:
        raise EmailDeliveryError(f"{transport.host}:{transport.port}: {exc}") from exc


async def dispatch_outbound_email(
    db: Session,
    *,
    ticket: Optional[Ticket],
    thread_type: str,
    recipients: list[str],
    subject: str,
    body_text: str,
    cc: Optional[list[str]] = None,
    branch: Optional[Branch] = None,
    in_reply_to: Optional[str] = None,
    classification_label: str = "OUTBOUND",
    ai_analysis_json: Optional[dict[str, Any]] = None,
) -> TicketEmail:
    """Record and dispatch an outbound email on either the `BRANCH`, `ISP`, or `HUMAN_ESCALATION` thread."""
    transport = load_smtp_transport_config(db)
    ticket_num = ticket.ticket_number if ticket is not None else "GLOBAL"
    # Ticketless mail (e.g. unrecognized-email reports) is limited per inbound message,
    # so one noisy thread cannot exhaust the guard for every other report.
    guard_key = (
        ticket_num
        if ticket is not None
        else f"NO-TICKET:{in_reply_to or ','.join(sorted(recipients))}"
    )
    per_hour_limit = db.execute(
        select(SystemSettings.max_outbound_emails_per_ticket_hour)
        .where(SystemSettings.config_key == "global")
        .limit(1)
    ).scalar_one_or_none()
    allowed = check_and_increment_outbound_allowance(guard_key, max_per_hour=per_hour_limit)

    now = datetime.now(timezone.utc)
    mid = f"<{uuid4().hex[:12]}.kz@kazyon.com>"
    sender = transport.from_address
    cc_list = [addr.strip() for addr in (cc or []) if addr and addr.strip()]

    # Automatically CC the Regional IT email of the branch on any email sent to the branch
    if thread_type == "BRANCH":
        resolved_branch = branch
        if resolved_branch is None and ticket is not None and ticket.branch_id is not None:
            resolved_branch = db.get(Branch, ticket.branch_id)
        if resolved_branch is None:
            sap_hint = extract_branch_sap_code(subject, body_text)
            if sap_hint:
                resolved_branch = db.execute(
                    select(Branch).where(Branch.branch_code == sap_hint).limit(1)
                ).scalar_one_or_none()
        if resolved_branch is not None:
            for reg_cc in resolve_branch_regional_it_cc(resolved_branch, db=db):
                if reg_cc and not any(existing.lower() == reg_cc.lower() for existing in cc_list):
                    cc_list.append(reg_cc)

    # Auto-correlate thread headers (`In-Reply-To` and `References`) from existing emails on this thread
    resolved_in_reply_to = in_reply_to
    references_chain: list[str] = []
    if ticket is not None and ticket.id is not None:
        prior_emails = (
            db.execute(
                select(TicketEmail)
                .where(
                    TicketEmail.ticket_id == ticket.id,
                    TicketEmail.thread_type == thread_type,
                )
                .order_by(TicketEmail.id.asc())
            )
            .scalars()
            .all()
        )
        for p in prior_emails:
            if p.message_id and p.message_id not in references_chain:
                references_chain.append(p.message_id)
        if not resolved_in_reply_to and references_chain:
            resolved_in_reply_to = references_chain[-1]

    # Ensure `[NET-XXXX]` tag is present on BRANCH and HUMAN_ESCALATION threads for deterministic reply matching
    final_subject = subject
    if (
        ticket is not None
        and thread_type in {"BRANCH", "HUMAN_ESCALATION"}
        and ticket.ticket_number not in final_subject
    ):
        final_subject = f"[{ticket.ticket_number}] {final_subject}"

    raw_headers: dict[str, str] = {
        "Message-ID": mid,
        "Date": now.strftime("%a, %d %b %Y %H:%M:%S +0000"),
        "From": sender,
        "To": ", ".join(recipients),
        "Subject": final_subject,
        "X-Kz-Thread": thread_type,
        "X-Kz-Ticket": ticket_num,
        "Auto-Submitted": "no",
    }
    if cc_list:
        raw_headers["Cc"] = ", ".join(cc_list)
    if resolved_in_reply_to:
        raw_headers["In-Reply-To"] = resolved_in_reply_to
    if references_chain:
        raw_headers["References"] = " ".join(references_chain[-8:])

    analysis_payload = dict(
        ai_analysis_json or {"thread": thread_type, "template": classification_label}
    )
    if transport.test_redirect_email:
        analysis_payload["test_redirected_to"] = transport.test_redirect_email
        raw_headers["X-Kz-Redirected-To"] = transport.test_redirect_email

    smtp_delivered = False
    if not allowed:
        analysis_payload["blocked_by_loop_guard"] = True
        analysis_payload["smtp_live_sent"] = False
        if ticket is not None and ticket.id is not None:
            db.add(
                TicketEvent(
                    ticket_id=ticket.id,
                    actor_type="AI_AGENT",
                    actor_name="AI_AGENT",
                    event_type="email_blocked",
                    summary=f"Outbound email blocked by loop guard ({classification_label})",
                    details_json={
                        "detail": f"To {', '.join(recipients)} · Subject: {final_subject}"
                    },
                )
            )
            db.flush()
    else:
        analysis_payload["blocked_by_loop_guard"] = False
        try:
            smtp_delivered = await asyncio.to_thread(
                _send_via_live_smtp_sync,
                sender=sender,
                recipients=recipients,
                cc=cc_list,
                subject=final_subject,
                body_text=body_text,
                raw_headers=raw_headers,
                transport=transport,
            )
        except EmailDeliveryError as exc:
            logger.error("SMTP delivery failed for ticket=%s: %s", ticket_num, exc)
            analysis_payload["smtp_delivery_error"] = exc.message
            if ticket is not None and ticket.id is not None:
                db.add(
                    TicketEvent(
                        ticket_id=ticket.id,
                        actor_type="AI_AGENT",
                        actor_name="AI_AGENT",
                        event_type="email_delivery_failed",
                        summary=f"SMTP delivery failed ({classification_label})",
                        details_json={"detail": exc.message},
                    )
                )
        analysis_payload["smtp_live_sent"] = smtp_delivered
        if not transport.enabled:
            analysis_payload["smtp_delivery_disabled"] = True

    email_row = TicketEmail(
        ticket_id=ticket.id if ticket is not None else None,
        thread_type=thread_type,
        direction="OUTBOUND",
        message_id=mid,
        in_reply_to=resolved_in_reply_to,
        sender=sender,
        recipients=recipients,
        cc=cc_list,
        subject=final_subject,
        body_text=body_text,
        attachments_json=[],
        raw_headers=raw_headers,
        classification_label=classification_label,
        ai_analysis_json=analysis_payload,
        sent_or_received_at=now,
    )
    db.add(email_row)
    db.flush()
    return email_row
