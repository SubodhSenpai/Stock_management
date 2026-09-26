"""WebSocket endpoint for live updates.

The server sends small "something changed" events carrying only identifiers. Clients
refetch through the REST API, which keeps permission checks in one place and means a
client can never receive data it would not be allowed to request.
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings
from app.core.events import event_bus
from app.core.exceptions import AppError
from app.core.tokens import token_subject

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws")
async def live_updates(websocket: WebSocket) -> None:
    """Authenticate from the session cookie, then stream change events until disconnect."""
    settings = get_settings()
    token = websocket.cookies.get(settings.auth_cookie_name)
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        token_subject(token, "access")
    except AppError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await event_bus.connect(websocket)
    try:
        while True:
            # Incoming messages are ignored; the channel exists to push updates out.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.disconnect(websocket)
