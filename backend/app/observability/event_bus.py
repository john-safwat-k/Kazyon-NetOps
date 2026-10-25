"""Real-time WebSocket event bus for Kanban UI, Ticket 360° Detail, and System Health."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("it_net.observability.event_bus")


class TicketEventBus:
    """Manages active WebSocket clients subscribed to `/ws/tickets` and broadcasts JSON events."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)
        logger.debug("WebSocket client connected (active=%d)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        logger.debug("WebSocket client disconnected (active=%d)", len(self._connections))

    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self._connections:
            return
        message = {
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }
        stale: list[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._connections.discard(ws)


event_bus = TicketEventBus()
