"""Inbound `.eml` dropbox poller (populated by Inbound SMTP Listener or manual `.eml` drops) and vLLM retry queue."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.common.config import get_settings

logger = logging.getLogger("it_net.email_engine.imap_poller")

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


async def poll_inbound_mailbox_raw(**_unused: Any) -> list[tuple[str, bytes]]:
    """Fetch new raw `(filename, eml_bytes)` from the local `.eml` dropbox (inbound SMTP listener)
    and the vLLM retry queue (emails whose backoff has elapsed)."""
    settings = get_settings()
    dropbox_items = await asyncio.to_thread(_consume_local_dropbox_eml_files_sync)
    retry_items = await asyncio.to_thread(
        _consume_llm_retry_queue_sync, float(settings.llm_retry_backoff_sec)
    )
    return [*dropbox_items, *retry_items]
