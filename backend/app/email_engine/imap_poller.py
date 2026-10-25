"""Inbound Mailbox Poller (IMAP4 SSL + local `.eml` dropbox) with Message-ID deduplication (CLAUDE.md §1 & §15)."""

from __future__ import annotations

import asyncio
import email
import hashlib
import imaplib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from app.common.config import get_settings
from app.common.crypto import decrypt_secret
from app.email_engine.parser import parse_eml_bytes
from app.ticketing.models import SystemSettings

logger = logging.getLogger("it_net.email_engine.imap_poller")

ImapStage = Literal["config", "connect", "auth", "select", "done"]


@dataclass(frozen=True)
class ImapTransportConfig:
    """Inbound IMAP settings loaded from Page 12 (`system_settings`) with fallback to `.env`."""

    host: str
    port: int
    use_ssl: bool
    folder: str
    username: str = field(default="", repr=False)
    password: str = field(default="", repr=False)

    @property
    def credentials_configured(self) -> bool:
        return bool(self.username and self.password)


def imap_transport_config_from_row(row: Optional[SystemSettings]) -> ImapTransportConfig:
    """Build IMAP transport config from a saved Page 12 `SystemSettings` row plus `.env` fallback."""
    settings = get_settings()
    row_host = (row.imap_host if row is not None else "").strip()
    row_user = (row.imap_username if row is not None else "").strip()
    row_pass = decrypt_secret(row.imap_password_encrypted if row is not None else "")
    return ImapTransportConfig(
        host=row_host or settings.imap_host.strip(),
        port=(row.imap_port if row is not None and row.imap_port else settings.imap_port),
        use_ssl=bool(row.imap_use_ssl) if row is not None else settings.imap_use_ssl,
        folder=(
            (row.imap_folder if row is not None else "") or settings.imap_folder or "INBOX"
        ).strip(),
        username=row_user or settings.imap_username,
        password=row_pass or settings.imap_password,
    )


def test_imap_connection_sync(
    cfg: ImapTransportConfig, timeout_sec: float = 10.0
) -> dict[str, Any]:
    """Open a real IMAP session (connect, login, select folder, count messages) without altering Seen flags."""
    started = time.perf_counter()
    result: dict[str, Any] = {
        "ok": False,
        "host": cfg.host,
        "port": cfg.port,
        "use_ssl": cfg.use_ssl,
        "folder": cfg.folder,
        "authenticated": False,
        "credentials_configured": cfg.credentials_configured,
        "stage": "config",
        "messages_in_folder": None,
        "unseen_in_folder": None,
        "error": None,
    }
    if not cfg.host:
        result["error"] = "IMAP host is empty."
    elif not cfg.credentials_configured:
        result["stage"] = "auth"
        result["error"] = "IMAP username or App Password is not configured."
    else:
        conn: Optional[imaplib.IMAP4] = None
        try:
            try:
                conn = (
                    imaplib.IMAP4_SSL(cfg.host, cfg.port, timeout=timeout_sec)
                    if cfg.use_ssl
                    else imaplib.IMAP4(cfg.host, cfg.port, timeout=timeout_sec)
                )
            except Exception as exc:
                result.update(stage="connect", error=f"{type(exc).__name__}: {exc}")
                result["latency_ms"] = int((time.perf_counter() - started) * 1000)
                return result

            try:
                conn.login(cfg.username, cfg.password)
                result["authenticated"] = True
            except Exception as exc:
                result.update(stage="auth", error=f"{type(exc).__name__}: {exc}")
                result["latency_ms"] = int((time.perf_counter() - started) * 1000)
                return result

            try:
                status_sel, sel_data = conn.select(cfg.folder, readonly=True)
                if status_sel != "OK":
                    result.update(
                        stage="select",
                        error=f"Folder '{cfg.folder}' could not be selected ({status_sel})",
                    )
                    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
                    return result
                total_msgs = 0
                if sel_data and sel_data[0]:
                    try:
                        total_msgs = int(sel_data[0].decode("ascii", errors="ignore").strip())
                    except ValueError:
                        total_msgs = 0
                unseen_count = 0
                st_unseen, unseen_data = conn.search(None, "UNSEEN")
                if st_unseen == "OK" and unseen_data and unseen_data[0]:
                    unseen_count = len(unseen_data[0].split())
                result.update(
                    ok=True,
                    stage="done",
                    messages_in_folder=total_msgs,
                    unseen_in_folder=unseen_count,
                )
            except Exception as exc:
                result.update(stage="select", error=f"{type(exc).__name__}: {exc}")
        finally:
            if conn is not None:
                try:
                    conn.logout()
                except Exception:
                    pass
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return result


_ingested_imap_mids: set[str] = set()


def _fetch_unseen_imap_messages_sync(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
    folder: str = "INBOX",
    max_messages: int = 25,
) -> list[tuple[str, bytes]]:
    """Synchronous `imaplib` reader executed inside `asyncio.to_thread` so it never blocks the event loop."""
    if not (host and username and password):
        return []

    fetched: list[tuple[str, bytes]] = []
    conn: Optional[imaplib.IMAP4] = None
    try:
        conn = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
        conn.login(username, password)
        status_sel, sel_data = conn.select(folder)
        if status_sel != "OK":
            return []

        is_gmail_host = "gmail.com" in host.lower()
        msg_nums: list[str] = []
        if (
            is_gmail_host
            and sel_data
            and sel_data[0]
            and sel_data[0].decode("ascii", errors="ignore").strip().isdigit()
        ):
            # Inspect only the newest 15 messages at the top of the Gmail folder using BODY.PEEK
            # so historical unread emails are never touched and even opened test emails are caught.
            total_msgs = int(sel_data[0].decode("ascii", errors="ignore").strip())
            if total_msgs <= 0:
                return []
            start_seq = max(1, total_msgs - 14)
            msg_nums = [str(i) for i in range(start_seq, total_msgs + 1)]
        else:
            status_search, data = conn.search(None, "UNSEEN")
            if status_search != "OK" or not data or not data[0]:
                return []
            msg_nums = [n.decode("ascii", errors="ignore") for n in data[0].split()[-max_messages:]]

        for num in msg_nums:
            # Peek at headers first without marking the message as \Seen in the user's mailbox
            st_hdr, hdr_data = conn.fetch(
                num,
                "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID DATE SUBJECT FROM IN-REPLY-TO REFERENCES)])",
            )
            if st_hdr == "OK" and hdr_data:
                raw_hdr_bytes = b"".join(
                    p[1]
                    for p in hdr_data
                    if isinstance(p, tuple) and len(p) >= 2 and isinstance(p[1], bytes)
                )
                raw_hdr_str = raw_hdr_bytes.decode("utf-8", errors="ignore")
                raw_hdr = raw_hdr_str.lower()
                hdr_msg = email.message_from_string(raw_hdr_str)
                peek_mid = (hdr_msg.get("Message-ID") or "").strip().lower()
                if peek_mid and peek_mid in _ingested_imap_mids:
                    continue
                has_reply_header = bool(
                    (hdr_msg.get("In-Reply-To") or "").strip()
                    or (hdr_msg.get("References") or "").strip()
                )
                if (
                    is_gmail_host
                    and not has_reply_header
                    and not any(
                        kw in raw_hdr
                        for kw in (
                            "store",
                            "branch",
                            "kazyon",
                            "net-",
                            "noc",
                            "router",
                            "offline",
                            "down",
                            "replication",
                            "ticket",
                            "case",
                            "circuit",
                            "quo1",
                            "noor",
                            "orange",
                            "te.eg",
                        )
                    )
                ):
                    # Leave unrelated personal emails untouched and UNSEEN in Gmail
                    continue

            st, msg_data = conn.fetch(num, "(BODY.PEEK[])" if is_gmail_host else "(RFC822)")
            if st != "OK" or not msg_data:
                continue
            for part in msg_data:
                if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
                    raw_bytes = part[1]
                    env = parse_eml_bytes(raw_bytes)
                    if env.message_id:
                        _ingested_imap_mids.add(env.message_id.lower())
                    fname = f"imap_{num}_{env.message_id.strip('<>')[:24]}.eml"
                    fetched.append((fname, raw_bytes))
        return fetched
    except Exception as exc:
        logger.warning("IMAP poll skipped/failed for %s@%s:%s — %s", username, host, port, exc)
        return []
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass


_IMPORTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "imports"


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

    IMAP has already marked the message Seen, so this queue is the only way it is read again.
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


async def poll_inbound_mailbox_raw(
    *,
    imap_host: Optional[str] = None,
    imap_port: Optional[int] = None,
    imap_config: Optional[ImapTransportConfig] = None,
) -> list[tuple[str, bytes]]:
    """Fetch new raw `(filename, eml_bytes)` from IMAP (if configured), the local dropbox, and the
    vLLM retry queue (emails whose backoff has elapsed)."""
    settings = get_settings()
    if imap_config is not None:
        host = imap_config.host
        port = imap_config.port
        username = imap_config.username
        password = imap_config.password
        use_ssl = imap_config.use_ssl
        folder = imap_config.folder
    else:
        host = imap_host or settings.imap_host
        port = imap_port or settings.imap_port
        username = settings.imap_username
        password = settings.imap_password
        use_ssl = settings.imap_use_ssl
        folder = settings.imap_folder

    imap_items: list[tuple[str, bytes]] = []
    if host and username and password:
        imap_items = await asyncio.to_thread(
            _fetch_unseen_imap_messages_sync,
            host=host,
            port=port,
            username=username,
            password=password,
            use_ssl=use_ssl,
            folder=folder,
        )

    dropbox_items = await asyncio.to_thread(_consume_local_dropbox_eml_files_sync)
    retry_items = await asyncio.to_thread(
        _consume_llm_retry_queue_sync, float(settings.llm_retry_backoff_sec)
    )
    return [*imap_items, *dropbox_items, *retry_items]
