"""WebSocket session manager."""
from typing import Dict, Set
from fastapi import WebSocket
import json

from app.domain.interaction.services import WebSocketSessionManager as WSManagerProtocol


class WebSocketSessionManager:
    """WebSocket session manager implementation."""

    def __init__(self):
        # Map user_id -> set of session_ids
        self.user_sessions: Dict[str, Set[str]] = {}
        # Map session_id -> (websocket, user_id)
        self.sessions: Dict[str, tuple[WebSocket, str]] = {}

    async def connect(self, user_id: str, session_id: str, websocket: WebSocket) -> None:
        """Connect a WebSocket session."""
        await websocket.accept()
        self.sessions[session_id] = (websocket, user_id)
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = set()
        self.user_sessions[user_id].add(session_id)

    async def disconnect(self, session_id: str) -> None:
        """Disconnect a WebSocket session."""
        if session_id in self.sessions:
            _, user_id = self.sessions[session_id]
            del self.sessions[session_id]
            if user_id in self.user_sessions:
                self.user_sessions[user_id].discard(session_id)
                if not self.user_sessions[user_id]:
                    del self.user_sessions[user_id]

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send message to user's active sessions."""
        if user_id not in self.user_sessions:
            return

        disconnected = []
        for session_id in self.user_sessions[user_id]:
            if session_id in self.sessions:
                websocket, _ = self.sessions[session_id]
                try:
                    await websocket.send_json(message)
                except Exception:
                    disconnected.append(session_id)

        # Clean up disconnected sessions
        for session_id in disconnected:
            await self.disconnect(session_id)

    async def send_to_session(self, session_id: str, message: dict) -> None:
        """Send message to specific session."""
        if session_id in self.sessions:
            websocket, _ = self.sessions[session_id]
            try:
                await websocket.send_json(message)
            except Exception:
                await self.disconnect(session_id)


# Global instance
ws_manager = WebSocketSessionManager()
