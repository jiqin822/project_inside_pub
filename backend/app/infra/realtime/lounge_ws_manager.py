"""WebSocket manager for lounge chat group rooms: room_id -> set of (websocket, user_id)."""
import logging
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


LOUNGE_ROOM_UPDATES_CHANNEL = "lounge:room_updates"


class LoungeRoomWsManager:
    """Room-scoped WebSocket manager for lounge. Key: room_id -> set of (websocket, user_id)."""

    def __init__(self) -> None:
        self.rooms: Dict[str, Set[tuple[WebSocket, str]]] = {}

    async def connect(
        self, room_id: str, user_id: str, websocket: WebSocket, already_accepted: bool = False
    ) -> None:
        """Add a connection to a room. Call websocket.accept() if not already accepted."""
        if not already_accepted:
            await websocket.accept()
        if room_id not in self.rooms:
            self.rooms[room_id] = set()
        self.rooms[room_id].add((websocket, user_id))

    async def disconnect(self, room_id: str, user_id: str, websocket: WebSocket) -> None:
        """Remove a connection from a room."""
        if room_id in self.rooms:
            self.rooms[room_id].discard((websocket, user_id))
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def send_to_user_in_room(self, room_id: str, user_id: str, message: dict) -> None:
        """Send message to a specific user's connection(s) in the room. Best-effort."""
        if room_id not in self.rooms:
            return
        disconnected = []
        for websocket, uid in self.rooms[room_id].copy():
            if uid != user_id:
                continue
            try:
                await websocket.send_json(message)
            except (RuntimeError, ConnectionError) as e:
                logger.warning("Lounge WS connection closed for room %s user %s: %s", room_id, uid, e)
                disconnected.append((room_id, uid, websocket))
            except Exception as e:
                logger.exception("Lounge WS send failed for room %s user %s: %s", room_id, uid, e)
                disconnected.append((room_id, uid, websocket))
        for rid, uid, ws in disconnected:
            try:
                await self.disconnect(rid, uid, ws)
            except Exception as e:
                logger.warning("Lounge WS disconnect cleanup: %s", e)

    async def broadcast_local(self, room_id: str, message: dict) -> None:
        """Send message to all connections in this instance only. Used by broadcast and by Redis subscriber."""
        if room_id not in self.rooms:
            return
        disconnected = []
        for websocket, uid in self.rooms[room_id].copy():
            try:
                await websocket.send_json(message)
            except (RuntimeError, ConnectionError) as e:
                logger.warning("Lounge WS connection closed for room %s user %s: %s", room_id, uid, e)
                disconnected.append((room_id, uid, websocket))
            except Exception as e:
                logger.exception("Lounge WS send failed for room %s user %s: %s", room_id, uid, e)
                disconnected.append((room_id, uid, websocket))
        for rid, uid, ws in disconnected:
            try:
                await self.disconnect(rid, uid, ws)
            except Exception as e:
                logger.warning("Lounge WS disconnect cleanup: %s", e)

    async def broadcast(self, room_id: str, message: dict) -> None:
        """Publish to Redis; every instance (including this one) receives and forwards via broadcast_local."""
        try:
            from app.infra.messaging.redis_bus import redis_bus
            await redis_bus.publish(LOUNGE_ROOM_UPDATES_CHANNEL, {"room_id": room_id, "message": message})
        except Exception as e:
            logger.warning("Lounge WS Redis publish failed: %s", e)
            await self.broadcast_local(room_id, message)


lounge_ws_manager = LoungeRoomWsManager()
