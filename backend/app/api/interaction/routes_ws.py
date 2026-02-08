"""WebSocket routes."""
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.infra.realtime.ws_manager import ws_manager
from app.domain.coach.analyzers.realtime_engine import RealtimeCoachingEngine
from app.domain.coach.services import SessionRepository, SessionService
from app.domain.admin.services import RelationshipRepository
from app.infra.db.repositories.session_repo import SessionRepositoryImpl, NudgeEventRepositoryImpl
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
from app.infra.messaging.redis_bus import redis_bus
from app.settings import settings
from app.infra.security.jwt import decode_token

router = APIRouter()

realtime_engine = RealtimeCoachingEngine()


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    token: str | None = None,
):
    """WebSocket endpoint for user notifications (emoji pokes, etc.)."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Accept the WebSocket connection first (required before closing)
        logger.info("🔵 [WEBSOCKET] Attempting to accept connection...")
        await websocket.accept()
        logger.info("✅ [WEBSOCKET] Connection accepted")
    except Exception as e:
        logger.error(f"❌ [WEBSOCKET] Failed to accept connection: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=f"Server error: {str(e)}")
        except:
            pass
        return
    
    # Get token from query params if not provided
    if not token:
        query_params = dict(websocket.query_params)
        token = query_params.get("token")
    
    if not token:
        logger.warning("⚠️ [WEBSOCKET] Connection rejected: No token provided")
        try:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        except:
            pass
        return
    
    logger.info(f"🔵 [WEBSOCKET] Connection attempt with token: {token[:20]}...")
    user_id = await get_user_from_token(token)
    if not user_id:
        logger.warning(f"⚠️ [WEBSOCKET] Connection rejected: Invalid token (decode failed or wrong type)")
        try:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        except:
            pass
        return
    
    logger.info(f"✅ [WEBSOCKET] Connection accepted for user: {user_id}")
    
    # Connect WebSocket using a user-specific session ID
    # Pass already_accepted=True since we already called websocket.accept() above
    session_id = f"user_{user_id}"
    await ws_manager.connect(session_id, user_id, websocket, already_accepted=True)
    
    try:
        # Send connection confirmation
        try:
            await websocket.send_json({
                "type": "connection.established",
                "user_id": user_id,
            })
        except (WebSocketDisconnect, RuntimeError, ConnectionError) as e:
            # Connection was closed before we could send confirmation
            logger.warning(f"⚠️ [WEBSOCKET] Connection closed before confirmation could be sent: {e}")
            await ws_manager.disconnect(session_id, user_id, websocket)
            return
        
        # Keep connection alive and listen for messages
        while True:
            # Wait for any message (ping/pong or actual messages)
            try:
                data = await websocket.receive_text()
                # Handle ping messages
                if data == "ping":
                    try:
                        await websocket.send_text("pong")
                    except (WebSocketDisconnect, RuntimeError, ConnectionError):
                        # Connection closed while sending pong
                        break
            except WebSocketDisconnect:
                break
            except (RuntimeError, ConnectionError) as e:
                # Handle other connection errors (e.g., ConnectionClosedError from websockets library)
                logger.warning(f"⚠️ [WEBSOCKET] Connection error during receive: {e}")
                break
    except WebSocketDisconnect:
        pass
    except (RuntimeError, ConnectionError) as e:
        logger.warning(f"⚠️ [WEBSOCKET] Connection error: {e}")
    finally:
        try:
            await ws_manager.disconnect(session_id, user_id, websocket)
        except Exception as e:
            logger.warning(f"⚠️ [WEBSOCKET] Error during disconnect cleanup: {e}")


async def get_user_from_token(token: str) -> str | None:
    """Extract user ID from WebSocket token."""
    import logging
    logger = logging.getLogger(__name__)
    
    payload = decode_token(token)
    if not payload:
        logger.warning("Token decode failed - invalid token or expired")
        return None
    
    token_type = payload.get("type")
    if token_type != "access":
        logger.warning(f"Token type mismatch: expected 'access', got '{token_type}'")
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Token payload missing 'sub' field")
        return None
    
    return user_id


@router.websocket("/sessions/{session_id}/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str | None = None,
):
    """WebSocket endpoint for session real-time coaching."""
    # Get user from token (passed as query param or header)
    if not token:
        # Try to get from query params
        query_params = dict(websocket.query_params)
        token = query_params.get("token")

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = await get_user_from_token(token)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify session exists and user is participant
    # We need a DB session, but WebSocket doesn't support Depends
    # So we'll create a temporary session
    from app.infra.db.base import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        session_repo: SessionRepository = SessionRepositoryImpl(db)
        relationship_repo: RelationshipRepository = RelationshipRepositoryImpl(db)
        session_service = SessionService(session_repo, relationship_repo)

        try:
            session = await session_service.get_session(session_id)
            # Only allow WebSocket connections for ACTIVE sessions
            if session.status != "ACTIVE":
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            participants = await session_service.get_session_participants(session_id)
            if user_id not in participants:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        except Exception as e:
            # Send error message before closing
            try:
                await websocket.send_json({
                    "type": "server.error",
                    "sid": session_id,
                    "payload": {"code": "BAD_REQUEST", "message": str(e)},
                })
            except:
                pass
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Connect WebSocket
        await ws_manager.connect(session_id, user_id, websocket)

        # Send initial session state
        await ws_manager.send_to_session(
            session_id,
            {
                "type": "server.session_state",
                "sid": session_id,
                "payload": {
                    "sid": session_id,
                    "participants": participants,
                },
            },
        )

        # Get nudge event repo for storing nudges
        nudge_repo = NudgeEventRepositoryImpl(db)

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()

                # Validate message structure
                if data.get("type") != "client.feature_frame":
                    await websocket.send_json({
                        "type": "server.error",
                        "sid": session_id,
                        "payload": {"code": "BAD_REQUEST", "message": "Invalid message type"},
                    })
                    continue

                if data.get("sid") != session_id:
                    await websocket.send_json({
                        "type": "server.error",
                        "sid": session_id,
                        "payload": {"code": "BAD_REQUEST", "message": "Session ID mismatch"},
                    })
                    continue

                payload = data.get("payload", {})
                timestamp_ms = payload.get("timestamp_ms", 0)
                speaking_rate = payload.get("speaking_rate", 0.0)
                overlap_ratio = payload.get("overlap_ratio", 0.0)

                # Store feature frame if enabled
                if settings.store_frames:
                    from app.infra.db.models.session import SessionFeatureFrameModel
                    from app.domain.common.types import generate_id
                    frame_model = SessionFeatureFrameModel(
                        id=generate_id(),
                        session_id=session_id,
                        user_id=user_id,
                        timestamp_ms=timestamp_ms,
                        speaking_rate=speaking_rate,
                        overlap_ratio=overlap_ratio,
                    )
                    db.add(frame_model)
                    await db.commit()

                # Check rate limit (max 1 nudge per 10 seconds per (sid, user_id))
                rate_limit_key = f"nudge_rl:{session_id}:{user_id}"
                await redis_bus.connect()
                count = await redis_bus.increment_rate_limit(
                    rate_limit_key, settings.nudge_rate_limit_seconds
                )

                if count > 1:
                    # Rate limited, skip nudge
                    continue

                # Analyze feature frame
                nudge = realtime_engine.analyze_feature_frame(speaking_rate, overlap_ratio)

                if nudge:
                    # Store nudge event
                    from app.domain.coach.models import NudgeEvent
                    nudge_event_obj = NudgeEvent.create(
                        session_id=session_id,
                        user_id=user_id,
                        nudge_type=nudge["nudge_type"],
                        payload=nudge,
                    )
                    nudge_event = {
                        "id": nudge_event_obj.id,
                        "session_id": session_id,
                        "user_id": user_id,
                        "nudge_type": nudge["nudge_type"],
                        "payload": nudge,
                    }
                    await nudge_repo.create(nudge_event)

                    # Send nudge to session
                    await ws_manager.send_to_session(
                        session_id,
                        {
                            "type": "server.nudge",
                            "sid": session_id,
                            "payload": nudge,
                        },
                    )

        except WebSocketDisconnect:
            await ws_manager.disconnect(session_id, user_id, websocket)
        except Exception as e:
            await ws_manager.disconnect(session_id, user_id, websocket)
            raise
