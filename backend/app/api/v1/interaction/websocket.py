"""WebSocket endpoints."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional
import json
import uuid

from app.infra.realtime.websocket import ws_manager
from app.infra.security.jwt import decode_token

router = APIRouter()


async def get_user_from_token(token: Optional[str]) -> Optional[str]:
    """Extract user ID from token."""
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return payload.get("sub")


@router.websocket("/session")
async def websocket_session(websocket: WebSocket, token: Optional[str] = Query(None)):
    """WebSocket session endpoint."""
    user_id = await get_user_from_token(token)
    if not user_id:
        await websocket.close(code=1008, reason="Authentication required")
        return

    session_id = str(uuid.uuid4())
    await ws_manager.connect(user_id, session_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # Echo back or process message
            message = json.loads(data)
            await websocket.send_json({"type": "ack", "message": message})
    except WebSocketDisconnect:
        await ws_manager.disconnect(session_id)
