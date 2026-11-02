"""Inbound `.eml` dropbox poller, Exchange EWS Inbox poller, and vLLM retry queue."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import escape as xml_escape

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.config import get_settings
from app.email_engine.smtp_sender import (
    SmtpTransportConfig,
    _is_loopback_host,
    load_smtp_transport_config,
)
from app.ticketing.models import TicketEmail

logger = logging.getLogger("it_net.email_engine.imap_poller")

_IMPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "imports"
_EWS_SEEN_MEM: set[str] = set()


def inbound_dropbox_dir() -> Path:
    """`data/imports/inbox/`: `.eml` files here are ingested on the next poll (SMTP listener, manual drops)."""
    return _IMPORTS_DIR / "inbox"


def _consume_local_dropbox_eml_files_sync() -> list[tuple[str, bytes]]:
    """Check `data/imports/inbox/` for dropped `.eml` files and move processed files to `data/imports/processed/`."""
    inbox_dir = inbound_dropbox_dir()
    processed_dir = _IMPORTS_DIR / "processed"
    if not inbox_dir.exists():
        return []

    results: list[tuple[str, bytes]] = []
    for eml_path in sorted(inbox_dir.glob("*.eml"))[:25]:
        try:
            raw_bytes = eml_path.read_bytes()
            results.append((eml_path.name, raw_bytes))
            processed_dir.mkdir(parents=True, exist_ok=True)
            target = (
                processed_dir / f"{int(datetime.now(timezone.utc).timestamp())}_{eml_path.name}"
            )
            eml_path.replace(target)
        except Exception as exc:
            logger.warning("Failed reading dropbox .eml %s: %s", eml_path.name, exc)
    return results


def _llm_retry_path(message_id: str) -> Path:
    digest = hashlib.sha256(message_id.strip().encode("utf-8")).hexdigest()[:32]
    return Path(get_settings().llm_retry_queue_dir) / f"{digest}.eml"


def enqueue_llm_retry_eml(raw_bytes: bytes, message_id: str) -> Path:
    """Persist a raw inbound email whose triage was deferred because vLLM was unavailable.

    Re-enqueueing the same Message-ID overwrites the file and restarts its backoff.
    """
    target = _llm_retry_path(message_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(raw_bytes)
    tmp.replace(target)
    return target


def _consume_llm_retry_queue_sync(min_age_sec: float) -> list[tuple[str, bytes]]:
    """Return queued emails whose backoff has elapsed, removing them from the queue."""
    queue_dir = Path(get_settings().llm_retry_queue_dir)
    if not queue_dir.exists():
        return []

    now_ts = datetime.now(timezone.utc).timestamp()
    results: list[tuple[str, bytes]] = []
    for eml_path in sorted(queue_dir.glob("*.eml"))[:25]:
        try:
            if now_ts - eml_path.stat().st_mtime < min_age_sec:
                continue
            raw_bytes = eml_path.read_bytes()
            eml_path.unlink()
            results.append((f"llm_retry_{eml_path.name}", raw_bytes))
        except Exception as exc:
            logger.warning("Failed reading LLM retry .eml %s: %s", eml_path.name, exc)
    return results


def _ews_seen_file() -> Path:
    return _IMPORTS_DIR / "ews_seen_ids.txt"


def _load_ews_seen_ids() -> set[str]:
    seen = set(_EWS_SEEN_MEM)
    path = _ews_seen_file()
    if path.exists():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                val = line.strip()
                if val:
                    seen.add(val)
        except Exception:
            pass
    return seen


def _save_ews_seen_ids(seen: set[str]) -> None:
    _EWS_SEEN_MEM.update(seen)
    path = _ews_seen_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        trimmed = sorted(seen)[-2000:]
        path.write_text("\n".join(trimmed) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed persisting ews_seen_ids.txt: %s", exc)


def _poll_ews_inbox_sync(
    cfg: SmtpTransportConfig,
    known_message_ids: set[str],
) -> list[tuple[str, bytes]]:
    """Fetch unread or recent (<24h) un-ingested emails from Exchange EWS (`https://<host>/EWS/Exchange.asmx`)."""
    if not cfg.credentials_configured or _is_loopback_host(cfg.host):
        return []

    ews_url = f"https://{cfg.host.strip()}/EWS/Exchange.asmx"
    soap_find = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
        ' xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"'
        ' xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">'
        '<soap:Header><t:RequestServerVersion Version="Exchange2013" /></soap:Header>'
        "<soap:Body>"
        '<m:FindItem Traversal="Shallow">'
        "<m:ItemShape>"
        "<t:BaseShape>IdOnly</t:BaseShape>"
        "<t:AdditionalProperties>"
        '<t:FieldURI FieldURI="item:Subject" />'
        '<t:FieldURI FieldURI="item:DateTimeReceived" />'
        '<t:FieldURI FieldURI="message:InternetMessageId" />'
        '<t:FieldURI FieldURI="message:IsRead" />'
        '<t:FieldURI FieldURI="message:From" />'
        "</t:AdditionalProperties>"
        "</m:ItemShape>"
        '<m:IndexedPageItemView MaxEntriesReturned="25" Offset="0" BasePoint="Beginning" />'
        "<m:SortOrder>"
        '<t:FieldOrder Order="Descending">'
        '<t:FieldURI FieldURI="item:DateTimeReceived" />'
        "</t:FieldOrder>"
        "</m:SortOrder>"
        "<m:ParentFolderIds>"
        '<t:DistinguishedFolderId Id="inbox" />'
        "</m:ParentFolderIds>"
        "</m:FindItem>"
        "</soap:Body></soap:Envelope>"
    )

    ns = {
        "t": "http://schemas.microsoft.com/exchange/services/2006/types",
        "m": "http://schemas.microsoft.com/exchange/services/2006/messages",
    }
    seen_ids = _load_ews_seen_ids()
    seen_dirty = False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    known_lower = {m.strip().lower() for m in known_message_ids if m}
    results: list[tuple[str, bytes]] = []

    try:
        with httpx.Client(verify=False, timeout=12.0) as client:
            resp = client.post(
                ews_url,
                content=soap_find.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                auth=(cfg.username, cfg.password),
            )
            if resp.status_code != 200 or "<m:ResponseCode>NoError</m:ResponseCode>" not in resp.text:
                return []

            root = ET.fromstring(resp.text)
            messages = list(root.findall(".//t:Items/t:Message", ns))
            # Process oldest to newest so threads ingest in chronological order
            for idx, msg_el in enumerate(reversed(messages)):
                item_id_el = msg_el.find("t:ItemId", ns)
                if item_id_el is None:
                    continue
                item_id = (item_id_el.attrib.get("Id") or "").strip()
                change_key = (item_id_el.attrib.get("ChangeKey") or "").strip()
                if not item_id:
                    continue

                internet_mid = (msg_el.findtext("t:InternetMessageId", default="", namespaces=ns) or "").strip()
                subject = (msg_el.findtext("t:Subject", default="", namespaces=ns) or "").strip()
                is_read_str = (msg_el.findtext("t:IsRead", default="true", namespaces=ns) or "true").strip().lower()
                dt_str = (msg_el.findtext("t:DateTimeReceived", default="", namespaces=ns) or "").strip()
                from_addr = (
                    msg_el.findtext("t:From/t:Mailbox/t:EmailAddress", default="", namespaces=ns) or ""
                ).strip()

                # Check if already durably committed in TicketEmail
                if internet_mid and internet_mid.lower() in known_lower:
                    if item_id not in seen_ids or internet_mid not in seen_ids:
                        seen_ids.add(item_id)
                        seen_ids.add(internet_mid)
                        seen_dirty = True
                    continue

                # Determine whether the email arrived within the last 24h
                is_recent = False
                if dt_str:
                    try:
                        received_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        is_recent = received_dt >= cutoff
                    except Exception:
                        is_recent = False

                # For older (>24h) or Message-ID-less items, consult seen_ids
                if (not is_recent or not internet_mid) and (
                    item_id in seen_ids or (internet_mid and internet_mid in seen_ids)
                ):
                    continue

                # Skip historical already-read emails older than 24h
                if is_read_str == "true" and not is_recent:
                    seen_ids.add(item_id)
                    if internet_mid:
                        seen_ids.add(internet_mid)
                    seen_dirty = True
                    continue

                # Avoid re-ingesting the agent's own outbound messages unless it's a Live SMTP Test
                if (
                    from_addr
                    and from_addr.lower() == cfg.from_address.strip().lower()
                    and "Kazyon Live SMTP Test" not in subject
                ):
                    seen_ids.add(item_id)
                    if internet_mid:
                        seen_ids.add(internet_mid)
                    seen_dirty = True
                    continue

                soap_get = (
                    '<?xml version="1.0" encoding="utf-8"?>'
                    '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
                    ' xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"'
                    ' xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">'
                    '<soap:Header><t:RequestServerVersion Version="Exchange2013" /></soap:Header>'
                    "<soap:Body><m:GetItem>"
                    "<m:ItemShape>"
                    "<t:BaseShape>IdOnly</t:BaseShape>"
                    "<t:IncludeMimeContent>true</t:IncludeMimeContent>"
                    "</m:ItemShape>"
                    f'<m:ItemIds><t:ItemId Id="{xml_escape(item_id)}" /></m:ItemIds>'
                    "</m:GetItem></soap:Body></soap:Envelope>"
                )
                get_resp = client.post(
                    ews_url,
                    content=soap_get.encode("utf-8"),
                    headers={"Content-Type": "text/xml; charset=utf-8"},
                    auth=(cfg.username, cfg.password),
                )
                if get_resp.status_code != 200:
                    continue
                get_root = ET.fromstring(get_resp.text)
                mc_el = get_root.find(".//t:MimeContent", ns)
                if mc_el is None or not mc_el.text:
                    continue
                raw_eml = base64.b64decode(mc_el.text)

                # Mark as read in Exchange if unread
                if is_read_str == "false" and change_key:
                    soap_mark_read = (
                        '<?xml version="1.0" encoding="utf-8"?>'
                        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"'
                        ' xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"'
                        ' xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">'
                        '<soap:Header><t:RequestServerVersion Version="Exchange2013" /></soap:Header>'
                        '<soap:Body><m:UpdateItem ConflictResolution="AlwaysOverwrite"'
                        ' MessageDisposition="SaveOnly">'
                        "<m:ItemChanges><t:ItemChange>"
                        f'<t:ItemId Id="{xml_escape(item_id)}" ChangeKey="{xml_escape(change_key)}" />'
                        "<t:Updates><t:SetItemField>"
                        '<t:FieldURI FieldURI="message:IsRead" />'
                        "<t:Message><t:IsRead>true</t:IsRead></t:Message>"
                        "</t:SetItemField></t:Updates>"
                        "</t:ItemChange></m:ItemChanges>"
                        "</m:UpdateItem></soap:Body></soap:Envelope>"
                    )
                    try:
                        client.post(
                            ews_url,
                            content=soap_mark_read.encode("utf-8"),
                            headers={"Content-Type": "text/xml; charset=utf-8"},
                            auth=(cfg.username, cfg.password),
                        )
                    except Exception:
                        pass

                seen_ids.add(item_id)
                if internet_mid:
                    seen_ids.add(internet_mid)
                seen_dirty = True
                stamp = int(datetime.now(timezone.utc).timestamp())
                results.append((f"ews_{stamp}_{idx}.eml", raw_eml))
                logger.info(
                    "Pulled inbound Exchange EWS email subject=%r from=%s mid=%s",
                    subject,
                    from_addr,
                    internet_mid,
                )
    except Exception as exc:
        logger.warning("Exchange EWS inbox poll failed on %s: %s", cfg.host, exc)

    if seen_dirty:
        _save_ews_seen_ids(seen_ids)
    return results


async def poll_inbound_mailbox_raw(
    db: Optional[Session] = None, **_unused: Any
) -> list[tuple[str, bytes]]:
    """Fetch new raw `(filename, eml_bytes)` from the local `.eml` dropbox, Exchange EWS Inbox,
    and the vLLM retry queue (emails whose backoff has elapsed)."""
    settings = get_settings()
    dropbox_items = await asyncio.to_thread(_consume_local_dropbox_eml_files_sync)
    ews_items: list[tuple[str, bytes]] = []
    if db is not None:
        try:
            cfg = load_smtp_transport_config(db)
            if cfg.credentials_configured and not _is_loopback_host(cfg.host):
                known_mids = {
                    str(m).strip()
                    for m in db.execute(select(TicketEmail.message_id)).scalars().all()
                    if m
                }
                ews_items = await asyncio.to_thread(_poll_ews_inbox_sync, cfg, known_mids)
        except Exception as exc:
            logger.warning("Could not prepare Exchange EWS poll: %s", exc)
    retry_items = await asyncio.to_thread(
        _consume_llm_retry_queue_sync, float(settings.llm_retry_backoff_sec)
    )
    return [*dropbox_items, *ews_items, *retry_items]
