"""In-process event bus that pushes change notifications to connected WebSocket clients.

Events carry identifiers only. Clients refetch through the REST API, so authorisation and
response shapes stay in one place. To run several API processes, swap the broadcast for
PostgreSQL LISTEN/NOTIFY; publishers keep calling `publish`.
"""

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the running event loop so sync services can publish into it."""
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def publish(self, event: dict[str, Any]) -> None:
        """Broadcast an event. Safe to call from sync code; never raises into the caller.

        Call this only after the transaction has committed, so clients never refetch
        data that is about to be rolled back.
        """
        if self._loop is None or not self._clients:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(event), self._loop)
        except RuntimeError:
            logger.warning("Event loop unavailable; dropped event %s", event.get("type"))

    async def _broadcast(self, event: dict[str, Any]) -> None:
        for websocket in list(self._clients):
            try:
                await websocket.send_json(event)
            except Exception:
                self.disconnect(websocket)


event_bus = EventBus()
