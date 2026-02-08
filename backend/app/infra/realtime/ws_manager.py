"""WebSocket session manager."""
from typing import Dict, Set
from fastapi import WebSocket
import json


class WebSocketSessionManager:
    """WebSocket session manager implementation."""

    def __init__(self):
        # Map session_id -> set of (websocket, user_id) tuples
        self.sessions: Dict[str, Set[tuple[WebSocket, str]]] = {}
        # Map user_id -> set of session_ids
        self.user_sessions: Dict[str, Set[str]] = {}

    async def connect(self, session_id: str, user_id: str, websocket: WebSocket, already_accepted: bool = False) -> None:
        """Connect a WebSocket session.
        
        Args:
            session_id: Unique session identifier
            user_id: User ID associated with this connection
            websocket: WebSocket connection
            already_accepted: If True, assumes websocket.accept() was already called
        """
        if not already_accepted:
            await websocket.accept()
        if session_id not in self.sessions:
            self.sessions[session_id] = set()
        self.sessions[session_id].add((websocket, user_id))
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = set()
        self.user_sessions[user_id].add(session_id)

    async def disconnect(self, session_id: str, user_id: str, websocket: WebSocket) -> None:
        """Disconnect a WebSocket session."""
        if session_id in self.sessions:
            self.sessions[session_id].discard((websocket, user_id))
            if not self.sessions[session_id]:
                del self.sessions[session_id]
        if user_id in self.user_sessions:
            self.user_sessions[user_id].discard(session_id)
            if not self.user_sessions[user_id]:
                del self.user_sessions[user_id]

    async def send_to_session(self, session_id: str, message: dict) -> None:
        """Send message to all connections for a session."""
        if session_id not in self.sessions:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ [WEBSOCKET] Session {session_id} not found, cannot send message: {message.get('type', 'unknown')}")
            return

        disconnected = []
        for websocket, user_id in self.sessions[session_id].copy():
            try:
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"📤 [WEBSOCKET] Sending message to session {session_id}, user {user_id}: {message.get('type', 'unknown')}")
                await websocket.send_json(message)
            except (RuntimeError, ConnectionError) as e:
                # Connection closed errors (e.g., ConnectionClosedError from websockets library)
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️ [WEBSOCKET] Connection closed for session {session_id}, user {user_id}: {e}")
                disconnected.append((session_id, user_id, websocket))
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"❌ [WEBSOCKET] Failed to send message to session {session_id}: {e}")
                disconnected.append((session_id, user_id, websocket))

        # Clean up disconnected sessions
        for sid, uid, ws in disconnected:
            try:
                await self.disconnect(sid, uid, ws)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"⚠️ [WEBSOCKET] Error during disconnect cleanup: {e}")

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send message to all sessions for a user."""
        import logging
        logger = logging.getLogger(__name__)
        
        if user_id not in self.user_sessions:
            logger.warning(f"⚠️ [WEBSOCKET] User {user_id} has no active sessions, cannot send message: {message.get('type', 'unknown')}")
            logger.debug(f"   Active users: {list(self.user_sessions.keys())}")
            return

        logger.info(f"🔵 [WEBSOCKET] Sending message to user {user_id}, sessions: {list(self.user_sessions[user_id])}")
        for session_id in self.user_sessions[user_id].copy():
            await self.send_to_session(session_id, message)


# Global instance
ws_manager = WebSocketSessionManager()
