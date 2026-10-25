"""Inbound SMTP listener: the company mail server forwards branch / ISP mail straight to the agent.

Receive-only and deliberately small (RFC 5321 subset: EHLO/HELO, MAIL, RCPT, DATA, RSET, NOOP,
QUIT). No AUTH and no STARTTLS: it is meant for one trusted internal mail server, so access is
limited by client IP (`SMTP_LISTENER_ALLOWED_CLIENTS`) and by recipient
(`SMTP_LISTENER_ALLOWED_RECIPIENTS`, default the Page 12 sender address).

A message is written durably to the inbound dropbox (`data/imports/inbox/`) *before* `250` is
returned, then the poller is woken. Ingestion therefore keeps Message-ID dedup, the vLLM retry
queue and the `INGEST_FAILED` safety net; this module never touches ticket logic.

Lines in DATA must end in CRLF. A message containing a bare LF or CR is rejected, and only
`CRLF . CRLF` ends DATA, which closes the SMTP-smuggling hole.
"""

from __future__ import annotations

import asyncio
import email.utils
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ipaddress import IPv4Network, IPv6Network, ip_address
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select

from app.common.config import get_settings
from app.common.database import SessionLocal
from app.email_engine.imap_poller import inbound_dropbox_dir
from app.ticketing.models import SystemSettings

logger = logging.getLogger("it_net.email_engine.smtp_listener")

_COMMAND_TIMEOUT_SEC = 300.0
_DATA_TIMEOUT_SEC = 600.0
_MAX_COMMAND_LINE = 2048
_MAX_RECIPIENTS = 50
_MAX_CONNECTIONS = 20
_ADDRESS_RE = re.compile(r"^\s*<([^<>]*)>(.*)$")

RecipientResolver = Callable[[], Awaitable[set[str]]]


@dataclass
class ListenerStats:
    running: bool = False
    host: str = ""
    port: int = 0
    allowed_clients: list[str] = field(default_factory=list)
    messages_accepted: int = 0
    messages_rejected: int = 0
    connections_refused: int = 0
    last_received_at: Optional[datetime] = None
    last_error: Optional[str] = None


def _write_eml_durably(directory: Path, raw: bytes) -> Path:
    """Write to a temp name, fsync, then rename so the poller never sees a partial file."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    target = directory / f"smtp_{stamp}_{uuid4().hex[:8]}.eml"
    tmp = target.with_suffix(".tmp")
    with open(tmp, "wb") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(target)
    return target


def _parse_path(arg: str, keyword: str) -> Optional[tuple[str, str]]:
    """Parse `FROM:<addr> params` / `TO:<addr> params` into (address, params)."""
    if not arg.upper().startswith(keyword):
        return None
    match = _ADDRESS_RE.match(arg[len(keyword) :])
    if match is None:
        return None
    return match.group(1).strip(), match.group(2).strip()


class InboundSmtpListener:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        allowed_networks: list[IPv4Network | IPv6Network],
        resolve_recipients: RecipientResolver,
        max_message_bytes: int,
        hostname: str,
        on_message_stored: Optional[Callable[[], None]] = None,
        dropbox_dir: Optional[Path] = None,
    ) -> None:
        self._host = host
        self._port = port
        self._allowed_networks = allowed_networks
        self._resolve_recipients = resolve_recipients
        self._max_bytes = max_message_bytes
        self._hostname = hostname
        self._on_message_stored = on_message_stored
        self._dropbox_dir = dropbox_dir
        self._server: Optional[asyncio.base_events.Server] = None
        self._slots = asyncio.Semaphore(_MAX_CONNECTIONS)
        self.stats = ListenerStats(
            host=host, port=port, allowed_clients=[str(n) for n in allowed_networks]
        )

    @property
    def bound_port(self) -> int:
        if self._server is None or not self._server.sockets:
            return self._port
        return int(self._server.sockets[0].getsockname()[1])

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self._host, self._port, limit=self._max_bytes + 4096
        )
        self.stats.running = True
        self.stats.port = self.bound_port
        logger.info(
            "Inbound SMTP listener on %s:%s (clients: %s)",
            self._host,
            self.stats.port,
            ", ".join(self.stats.allowed_clients) or "none",
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self.stats.running = False

    def _client_allowed(self, peer_ip: str) -> bool:
        try:
            addr = ip_address(peer_ip)
        except ValueError:
            return False
        if addr.version == 6 and addr.ipv4_mapped is not None:  # type: ignore[union-attr]
            addr = addr.ipv4_mapped  # type: ignore[union-attr]
        return any(addr in net for net in self._allowed_networks)

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername") or ("?", 0)
        peer_ip = str(peer[0])

        async def reply(line: str) -> None:
            writer.write(f"{line}\r\n".encode())
            await writer.drain()

        try:
            if not self._client_allowed(peer_ip):
                self.stats.connections_refused += 1
                logger.warning("Inbound SMTP: refused client %s (not in allowed list)", peer_ip)
                await reply("554 5.7.1 Client host rejected: access denied")
                return
            if self._slots.locked():
                await reply("421 4.3.2 Too many connections, try again later")
                return
            async with self._slots:
                await self._session(reader, reply, peer_ip)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError):
            pass
        except Exception as exc:
            self.stats.last_error = f"{type(exc).__name__}: {exc}"
            logger.exception("Inbound SMTP session with %s failed", peer_ip)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _session(
        self,
        reader: asyncio.StreamReader,
        reply: Callable[[str], Awaitable[None]],
        peer_ip: str,
    ) -> None:
        await reply(f"220 {self._hostname} ESMTP Kazyon NetOps agent ready")
        helo: Optional[str] = None
        mail_from: Optional[str] = None
        rcpts: list[str] = []

        while True:
            raw = await asyncio.wait_for(reader.readline(), timeout=_COMMAND_TIMEOUT_SEC)
            if not raw:
                return
            if len(raw) > _MAX_COMMAND_LINE:
                await reply("500 5.5.2 Line too long")
                return
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            verb, _, arg = line.partition(" ")
            verb = verb.upper()

            if verb == "EHLO":
                helo, mail_from, rcpts = arg.strip() or peer_ip, None, []
                await reply(f"250-{self._hostname} Hello [{peer_ip}]")
                await reply(f"250-SIZE {self._max_bytes}")
                await reply("250 8BITMIME")
            elif verb == "HELO":
                helo, mail_from, rcpts = arg.strip() or peer_ip, None, []
                await reply(f"250 {self._hostname}")
            elif verb == "MAIL":
                if helo is None:
                    await reply("503 5.5.1 Send EHLO/HELO first")
                    continue
                parsed = _parse_path(arg, "FROM:")
                if parsed is None:
                    await reply("501 5.5.4 Syntax: MAIL FROM:<address>")
                    continue
                size_match = re.search(r"\bSIZE=(\d+)", parsed[1], re.IGNORECASE)
                if size_match and int(size_match.group(1)) > self._max_bytes:
                    await reply("552 5.3.4 Message size exceeds fixed limit")
                    continue
                mail_from, rcpts = parsed[0], []
                await reply("250 2.1.0 Sender OK")
            elif verb == "RCPT":
                if mail_from is None:
                    await reply("503 5.5.1 Need MAIL before RCPT")
                    continue
                parsed = _parse_path(arg, "TO:")
                if parsed is None:
                    await reply("501 5.5.4 Syntax: RCPT TO:<address>")
                    continue
                if len(rcpts) >= _MAX_RECIPIENTS:
                    await reply("452 4.5.3 Too many recipients")
                    continue
                allowed = await self._resolve_recipients()
                if parsed[0].lower() not in allowed:
                    await reply("550 5.1.1 Recipient not accepted by this agent")
                    continue
                rcpts.append(parsed[0])
                await reply("250 2.1.5 Recipient OK")
            elif verb == "DATA":
                if mail_from is None or not rcpts:
                    await reply("503 5.5.1 Need MAIL and RCPT before DATA")
                    continue
                await reply("354 End data with <CR><LF>.<CR><LF>")
                body, problem = await asyncio.wait_for(
                    self._read_data(reader), timeout=_DATA_TIMEOUT_SEC
                )
                if problem is not None:
                    self.stats.messages_rejected += 1
                    await reply(problem)
                else:
                    await self._store(body, helo or peer_ip, peer_ip, mail_from, rcpts)
                    await reply("250 2.0.0 Message accepted for delivery")
                mail_from, rcpts = None, []
            elif verb == "RSET":
                mail_from, rcpts = None, []
                await reply("250 2.0.0 OK")
            elif verb == "NOOP":
                await reply("250 2.0.0 OK")
            elif verb == "QUIT":
                await reply(f"221 2.0.0 {self._hostname} closing connection")
                return
            elif verb == "VRFY":
                await reply("252 2.1.5 Cannot verify user")
            elif verb in {"STARTTLS", "AUTH", "BDAT", "ETRN", "EXPN"}:
                await reply("502 5.5.1 Command not implemented")
            else:
                await reply("500 5.5.2 Command not recognized")

    async def _read_data(self, reader: asyncio.StreamReader) -> tuple[bytes, Optional[str]]:
        """Read DATA until a CRLF.CRLF line. Returns (message, None) or (b"", error reply)."""
        chunks: list[bytes] = []
        total = 0
        oversize = False
        bad_line_ending = False
        # The terminator only counts after a CRLF-terminated line, so "\n.\r\n" (SMTP smuggling)
        # stays inside the message instead of ending it and starting a forged transaction.
        prev_ended_crlf = True
        while True:
            try:
                line = await reader.readuntil(b"\n")
            except asyncio.LimitOverrunError:
                oversize = True
                await reader.read(self._max_bytes)
                prev_ended_crlf = False
                continue
            if line == b".\r\n" and prev_ended_crlf:
                break
            prev_ended_crlf = line.endswith(b"\r\n")
            if not prev_ended_crlf or b"\r" in line[:-2]:
                bad_line_ending = True
            if line.startswith(b"."):
                line = line[1:]
            total += len(line)
            if total > self._max_bytes:
                oversize = True
            elif not (oversize or bad_line_ending):
                chunks.append(line)
        if oversize:
            return b"", "552 5.3.4 Message size exceeds fixed limit"
        if bad_line_ending:
            return b"", "550 5.6.0 Bare LF or CR in message; lines must end in CRLF"
        return b"".join(chunks), None

    async def _store(
        self, body: bytes, helo: str, peer_ip: str, mail_from: str, rcpts: list[str]
    ) -> None:
        received = (
            f"Received: from {helo} ([{peer_ip}])\r\n"
            f"\tby {self._hostname} (Kazyon NetOps agent) with ESMTP\r\n"
            f"\tfor <{rcpts[0]}>; {email.utils.format_datetime(datetime.now(timezone.utc))}\r\n"
            f"X-Kz-Envelope-From: <{mail_from}>\r\n"
            f"X-Kz-Envelope-To: {', '.join(f'<{r}>' for r in rcpts)}\r\n"
        ).encode()
        path = await asyncio.to_thread(
            _write_eml_durably, self._dropbox_dir or inbound_dropbox_dir(), received + body
        )
        self.stats.messages_accepted += 1
        self.stats.last_received_at = datetime.now(timezone.utc)
        logger.info(
            "Inbound SMTP: accepted %d bytes from %s (envelope %s -> %s) as %s",
            len(body),
            peer_ip,
            mail_from,
            ", ".join(rcpts),
            path.name,
        )
        if self._on_message_stored is not None:
            self._on_message_stored()


_active_listener: Optional[InboundSmtpListener] = None


def set_active_listener(listener: Optional[InboundSmtpListener]) -> None:
    global _active_listener
    _active_listener = listener


def get_listener_status() -> dict[str, Any]:
    """Status for `GET /api/v1/emails/loop-status` and Page 12."""
    if _active_listener is None:
        return {"enabled": False, "running": False}
    st = _active_listener.stats
    return {
        "enabled": True,
        "running": st.running,
        "host": st.host,
        "port": st.port,
        "allowed_clients": st.allowed_clients,
        "messages_accepted": st.messages_accepted,
        "messages_rejected": st.messages_rejected,
        "connections_refused": st.connections_refused,
        "last_received_at": st.last_received_at.isoformat() if st.last_received_at else None,
        "last_error": st.last_error,
    }


def _saved_sender_address_sync() -> set[str]:
    with SessionLocal() as db:
        address = db.execute(
            select(SystemSettings.mailbox_account)
            .where(SystemSettings.config_key == "global")
            .limit(1)
        ).scalar_one_or_none()
    return {address.strip().lower()} if address else set()


async def _configured_recipients() -> set[str]:
    """`SMTP_LISTENER_ALLOWED_RECIPIENTS`, or the Page 12 sender address when that is empty."""
    explicit = get_settings().smtp_listener_recipients()
    if explicit:
        return explicit
    return await asyncio.to_thread(_saved_sender_address_sync)


async def start_inbound_smtp_listener(
    on_message_stored: Optional[Callable[[], None]] = None,
) -> Optional[InboundSmtpListener]:
    """Start the listener when `SMTP_LISTENER_ENABLED` is true (FastAPI lifespan).

    A bind failure is logged and shown in the status, but does not stop the app.
    """
    settings = get_settings()
    if not settings.smtp_listener_enabled:
        set_active_listener(None)
        return None
    listener = InboundSmtpListener(
        host=settings.smtp_listener_host,
        port=settings.smtp_listener_port,
        allowed_networks=settings.smtp_listener_networks(),
        resolve_recipients=_configured_recipients,
        max_message_bytes=settings.smtp_listener_max_message_mb * 1024 * 1024,
        hostname=settings.smtp_listener_hostname,
        on_message_stored=on_message_stored,
    )
    set_active_listener(listener)
    try:
        await listener.start()
    except OSError as exc:
        listener.stats.last_error = f"Cannot listen on port {settings.smtp_listener_port}: {exc}"
        logger.error("Inbound SMTP listener not started: %s", listener.stats.last_error)
    return listener


async def stop_inbound_smtp_listener() -> None:
    if _active_listener is not None:
        await _active_listener.stop()
    set_active_listener(None)
