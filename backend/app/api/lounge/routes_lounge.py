"""Lounge REST API: rooms, invite, messages (with vet), private, context, events, room WebSocket."""
import base64
import dataclasses
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_llm_service
from app.domain.admin.models import User
from app.domain.lounge.kai_agent import (
    KaiAgentService,
    detect_lounge_intention,
    generate_activity_recommendations,
    generate_repair_vouchers,
    extract_chat_from_screenshots,
    understand_screenshot_conversation,
    analyze_screenshot_messages_for_revisions_and_guidance,
    analyze_screenshot_communication_and_suggest,
)
from app.infra.db.models.lounge import LoungeMessageModel, LoungeRoomModel
from app.infra.db.models.user import UserModel
from app.infra.db.repositories.lounge_repo import LoungeRepository
from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
from app.infra.realtime.lounge_ws_manager import lounge_ws_manager
from app.infra.security.jwt import decode_token
from app.services.notification_service import deliver_notification
from app.settings import settings
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

router = APIRouter()

# Pending guidance per (room_id, for_user_id). Delivered on get_room when recipient has no WebSocket connection.
_pending_guidance: dict[tuple[str, str], dict] = {}


async def _get_user_id_from_token(token: str) -> Optional[str]:
    """Extract user ID from JWT token (for WebSocket). Returns None if invalid."""
    payload = decode_token(token)
    if not payload:
        return None
    if payload.get("type") != "access":
        return None
    return payload.get("sub")


# ---- Request/Response models ----
class CreateRoomRequest(BaseModel):
    title: Optional[str] = None
    conversation_goal: Optional[str] = None


class InviteRequest(BaseModel):
    user_id: str


class SendMessageRequest(BaseModel):
    content: str
    force_send: bool = False
    debug: bool = False


class VetRequest(BaseModel):
    draft: str


class PrivateMessageRequest(BaseModel):
    content: str


# Allowed image types and max size (5MB) for screenshot analysis (align with activity memory upload)
SCREENSHOT_UPLOAD_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
SCREENSHOT_UPLOAD_MAX_BYTES = 5 * 1024 * 1024


# ---- Helpers ----
async def _ensure_member(repo: LoungeRepository, room_id: str, user_id: str) -> None:
    if not await repo.is_member(room_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this room")


async def _loved_one_user_ids(db: AsyncSession, current_user_id: str) -> set[str]:
    """Return set of user_ids that are in a relationship with current user (loved ones)."""
    rel_repo = RelationshipRepositoryImpl(db)
    relationships = await rel_repo.list_by_user(current_user_id)
    out = set()
    for r in relationships:
        members = await rel_repo.get_members(r.id)
        for m in members:
            if m.user_id != current_user_id:
                out.add(m.user_id)
    return out


async def _resolve_relationship_id_for_room(db: AsyncSession, room_member_ids: list[str]) -> Optional[str]:
    """Resolve a relationship_id whose members exactly match the room's member set (for 2-person rooms). Returns None if no match."""
    if not room_member_ids or len(room_member_ids) != 2:
        return None
    room_set = set(room_member_ids)
    rel_repo = RelationshipRepositoryImpl(db)
    relationships = await rel_repo.list_by_user(room_member_ids[0])
    for r in relationships:
        members = await rel_repo.get_members(r.id)
        rel_member_ids = {m.user_id for m in members}
        if rel_member_ids == room_set:
            return r.id
    return None


async def _loved_ones_with_names(db: AsyncSession, current_user_id: str) -> list[dict]:
    """Return list of {user_id, display_name} for loved ones (for Kai solo reply / invite suggestion)."""
    ids = await _loved_one_user_ids(db, current_user_id)
    out = []
    for uid in ids:
        name = await _get_user_name(db, uid)
        out.append({"user_id": uid, "display_name": name or uid})
    return out


def _message_to_dict(m: LoungeMessageModel, sender_name: Optional[str] = None) -> dict:
    return {
        "id": m.id,
        "room_id": m.room_id,
        "sender_user_id": m.sender_user_id,
        "sender_name": sender_name,
        "content": m.content,
        "visibility": m.visibility,
        "sequence": m.sequence,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def _get_user_preferences_text(repo: LoungeRepository, user_id: str, limit: int = 30) -> str:
    """Format user's stored Kai preferences/feedback for injection into Kai prompts."""
    prefs = await repo.list_preferences_for_user(user_id, limit=limit)
    if not prefs:
        return ""
    parts = []
    for p in reversed(prefs):
        parts.append(f"[{p.kind}]: {p.content}")
    return "; ".join(parts)


async def _get_compass_profile_text(
    db: AsyncSession,
    user_id: str,
    relationship_id: Optional[str] = None,
    context_query: Optional[str] = None,
    llm_service: Optional[Any] = None,
) -> str:
    """Resolve Compass context for Kai. If context_query is set and llm_service provided, returns LLM answer over context; else full profile text. Returns '' on failure."""
    try:
        from app.domain.compass.services import PersonalizationService
        from app.infra.db.repositories.event_repo import EventRepository
        from app.infra.db.repositories.memory_repo import MemoryRepository
        from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
        from app.infra.db.repositories.loop_repo import LoopRepository
        from app.infra.db.repositories.activity_template_repo import ActivityTemplateRepository
        from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
        from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
        from app.infra.db.repositories.unstructured_memory_repo import UnstructuredMemoryRepository
        from app.infra.db.repositories.user_repo import UserRepositoryImpl

        event_repo = EventRepository(db)
        memory_repo = MemoryRepository(db)
        person_portrait_repo = PersonPortraitRepository(db)
        dyad_portrait_repo = DyadPortraitRepository(db)
        loop_repo = LoopRepository(db)
        activity_template_repo = ActivityTemplateRepository(db)
        dyad_activity_repo = DyadActivityHistoryRepository(db)
        context_summary_repo = ContextSummaryRepository(db)
        unstructured_memory_repo = UnstructuredMemoryRepository(db)
        personalization = PersonalizationService(
            event_repo=event_repo,
            memory_repo=memory_repo,
            person_portrait_repo=person_portrait_repo,
            dyad_portrait_repo=dyad_portrait_repo,
            loop_repo=loop_repo,
            activity_template_repo=activity_template_repo,
            dyad_activity_repo=dyad_activity_repo,
            context_summary_repo=context_summary_repo,
            unstructured_memory_repo=unstructured_memory_repo,
        )
        user_repo = UserRepositoryImpl(db)
        user = await user_repo.get_by_id(user_id)
        actor_profile = None
        if user:
            actor_profile = {
                "personal_description": getattr(user, "personal_description", None),
                "hobbies": getattr(user, "hobbies", None),
                "personality_type": getattr(user, "personality_type", None),
            }
        if (context_query or "").strip() and llm_service is not None and hasattr(llm_service, "generate_text"):
            return await personalization.get_context_for_query(
                user_id=user_id,
                question=context_query.strip(),
                relationship_id=relationship_id,
                actor_profile=actor_profile,
                llm_generate_text=llm_service.generate_text,
            )
        return await personalization.get_user_profile_text_for_kai(
            user_id, relationship_id=relationship_id, actor_profile=actor_profile
        )
    except Exception as e:
        logger.debug("Lounge: get_compass_profile_text failed (Kai will run without Compass profile): %s", e)
        return ""


async def _ingest_kai_insight(
    db: AsyncSession,
    user_id: str,
    insight_text: str,
    relationship_id: Optional[str] = None,
) -> None:
    """Store a Kai-generated insight in Compass (unstructured memory). No-op on failure."""
    if not (insight_text or "").strip():
        return
    try:
        from app.domain.compass.services import PersonalizationService
        from app.infra.db.repositories.event_repo import EventRepository
        from app.infra.db.repositories.memory_repo import MemoryRepository
        from app.infra.db.repositories.portrait_repo import PersonPortraitRepository, DyadPortraitRepository
        from app.infra.db.repositories.loop_repo import LoopRepository
        from app.infra.db.repositories.activity_template_repo import ActivityTemplateRepository
        from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
        from app.infra.db.repositories.context_summary_repo import ContextSummaryRepository
        from app.infra.db.repositories.unstructured_memory_repo import UnstructuredMemoryRepository

        event_repo = EventRepository(db)
        memory_repo = MemoryRepository(db)
        person_portrait_repo = PersonPortraitRepository(db)
        dyad_portrait_repo = DyadPortraitRepository(db)
        loop_repo = LoopRepository(db)
        activity_template_repo = ActivityTemplateRepository(db)
        dyad_activity_repo = DyadActivityHistoryRepository(db)
        context_summary_repo = ContextSummaryRepository(db)
        unstructured_memory_repo = UnstructuredMemoryRepository(db)
        personalization = PersonalizationService(
            event_repo=event_repo,
            memory_repo=memory_repo,
            person_portrait_repo=person_portrait_repo,
            dyad_portrait_repo=dyad_portrait_repo,
            loop_repo=loop_repo,
            activity_template_repo=activity_template_repo,
            dyad_activity_repo=dyad_activity_repo,
            context_summary_repo=context_summary_repo,
            unstructured_memory_repo=unstructured_memory_repo,
        )
        await personalization.ingest_kai_insight(
            actor_user_id=user_id,
            insight_text=insight_text.strip()[:5000],
            relationship_id=relationship_id,
            source="kai_insight",
        )
    except Exception as e:
        logger.debug("Lounge: ingest_kai_insight failed: %s", e)


async def _get_user_name(db: AsyncSession, user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return "Kai"
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    u = result.scalar_one_or_none()
    if not u:
        return user_id
    return u.display_name or u.email or user_id


async def _messages_for_kai(
    db: AsyncSession,
    messages: list,
    *,
    extra: Optional[list[dict]] = None,
) -> list[dict]:
    """Build message dicts with sender_label (display name or 'Kai') for LLM context so agent knows who said what."""
    sender_ids = set()
    for m in messages:
        sid = getattr(m, "sender_user_id", None)
        sender_ids.add(sid)
    if extra:
        for d in extra:
            sender_ids.add(d.get("sender_user_id"))
    names = {}
    for uid in sender_ids:
        names[uid] = await _get_user_name(db, uid)
    out = []
    for m in reversed(messages):
        sid = getattr(m, "sender_user_id", None)
        label = names.get(sid) or ("Kai" if sid is None else sid)
        created = getattr(m, "created_at", None)
        out.append({
            "sender_user_id": sid,
            "content": getattr(m, "content", ""),
            "sender_label": label,
            "created_at": created.isoformat() if created else None,
        })
    if extra:
        for d in extra:
            sid = d.get("sender_user_id")
            label = names.get(sid) or ("Kai" if sid is None else sid)
            out.append({
                "sender_user_id": sid,
                "content": d.get("content", ""),
                "sender_label": label,
                "created_at": d.get("created_at"),  # caller may set for "now"
            })
    return out


# ---- Rooms ----
@router.post("/rooms")
async def create_room(
    request: CreateRoomRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a lounge room; current user is owner and first member."""
    repo = LoungeRepository(db)
    room = await repo.create_room(
        owner_user_id=current_user.id,
        title=request.title,
        conversation_goal=request.conversation_goal,
    )
    await repo.add_member(room.id, current_user.id, invited_by_user_id=None)
    await repo.append_event(room.id, "room_created", {"owner_user_id": current_user.id, "title": request.title, "conversation_goal": request.conversation_goal})
    await repo.append_event(room.id, "member_joined", {"user_id": current_user.id})
    await db.commit()
    return {
        "id": room.id,
        "owner_user_id": room.owner_user_id,
        "title": room.title,
        "conversation_goal": room.conversation_goal,
        "created_at": room.created_at.isoformat() if room.created_at else None,
    }


@router.get("/rooms")
async def list_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List lounge rooms where current user is a member."""
    repo = LoungeRepository(db)
    rooms = await repo.list_rooms_for_user(current_user.id)
    out = []
    for r in rooms:
        ctx = await repo.get_or_create_kai_context(r.id)
        summary = (ctx.summary_text or "").strip()
        topic = None
        if summary:
            first_sentence = summary.split(".")[0].strip()
            topic = (first_sentence + ".") if first_sentence else None
            if topic and len(topic) > 100:
                topic = topic[:97] + "..."
        members = await repo.list_members(r.id)
        member_ids = [m.user_id for m in members]
        names = {}
        for uid in member_ids:
            names[uid] = await _get_user_name(db, uid)
        out.append({
            "id": r.id,
            "owner_user_id": r.owner_user_id,
            "title": r.title,
            "conversation_goal": getattr(r, "conversation_goal", None),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "topic": topic,
            "members": [
                {"user_id": m.user_id, "joined_at": m.joined_at.isoformat() if m.joined_at else None, "display_name": names.get(m.user_id) or m.user_id}
                for m in members
            ],
        })
    return out


@router.get("/rooms/{room_id}")
async def get_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get room details, members, and last N public messages. New joiners only see messages from after they joined."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    room = await repo.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    members = await repo.list_members(room_id)
    current_member = next((m for m in members if m.user_id == current_user.id), None)
    after_created_at = current_member.joined_at if current_member else None
    messages = await repo.list_public_messages(room_id, limit=50, after_created_at=after_created_at)
    messages = list(reversed(messages))  # oldest first for display
    member_ids = [m.user_id for m in members]
    names = {}
    for uid in member_ids:
        names[uid] = await _get_user_name(db, uid)
    out = {
        "id": room.id,
        "owner_user_id": room.owner_user_id,
        "title": room.title,
        "conversation_goal": getattr(room, "conversation_goal", None),
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "members": [
            {"user_id": m.user_id, "joined_at": m.joined_at.isoformat() if m.joined_at else None, "display_name": names.get(m.user_id) or m.user_id}
            for m in members
        ],
        "messages": [
            _message_to_dict(m, names.get(m.sender_user_id) if m.sender_user_id else "Kai")
            for m in messages
        ],
    }
    key = (room_id, current_user.id)
    if key in _pending_guidance:
        out["guidance"] = _pending_guidance.pop(key)
    return out


@router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a chat group. Only the owner can delete it."""
    repo = LoungeRepository(db)
    room = await repo.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    if room.owner_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can remove this chat group")
    await repo.delete_room(room_id)
    await db.commit()
    return {"status": "deleted"}


@router.websocket("/rooms/{room_id}/ws")
async def lounge_room_ws(
    websocket: WebSocket,
    room_id: str,
    db: AsyncSession = Depends(get_db),
):
    """WebSocket for a lounge chat group. Client receives lounge_room_update when messages or members change."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required")
        return
    user_id = await _get_user_id_from_token(token)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return
    repo = LoungeRepository(db)
    if not await repo.is_member(room_id, user_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Not a member of this room")
        return
    await lounge_ws_manager.connect(room_id, user_id, websocket)
    try:
        await websocket.send_json({"type": "connection.established", "room_id": room_id})
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    except (RuntimeError, ConnectionError):
        pass
    finally:
        try:
            await lounge_ws_manager.disconnect(room_id, user_id, websocket)
        except Exception as e:
            logger.warning("Lounge WS disconnect cleanup: %s", e)


@router.post("/rooms/{room_id}/invite")
async def invite_to_room(
    room_id: str,
    request: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Invite a loved one (user_id must be in a relationship with current user) to the room."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    loved = await _loved_one_user_ids(db, current_user.id)
    if request.user_id not in loved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only invite loved ones from your relationships")
    if await repo.is_member(room_id, request.user_id):
        return {"status": "already_member"}
    await repo.add_member(room_id, request.user_id, invited_by_user_id=current_user.id)
    await repo.append_event(room_id, "member_joined", {"user_id": request.user_id, "invited_by_user_id": current_user.id})
    room = await repo.get_room(room_id)
    inviter_name = (await _get_user_name(db, current_user.id)) or getattr(current_user, "display_name", None) or "Someone"
    room_title = room.title if room and room.title else f"Chat group {room_id[:8]}"

    # Notify invitee before commit so notification can be created in same session; invite is persisted by notification repo commit or by our commit below
    try:
        await deliver_notification(
            db,
            request.user_id,
            "lounge_invite",
            "Chat group invite",
            f"{inviter_name} added you to \"{room_title}\".",
            extra_payload={"room_id": room_id, "room_title": room_title, "inviter_id": current_user.id, "inviter_name": inviter_name},
        )
        logger.info("Lounge invite notification sent to user %s for room %s", request.user_id, room_id)
    except Exception as e:
        logger.warning("Lounge invite notification failed for user %s: %s", request.user_id, e, exc_info=True)

    # Persist invite (and event) if not already committed by deliver_notification's repo.create()
    try:
        await db.commit()
    except Exception as e:
        logger.warning("Lounge invite commit failed: %s", e)
        await db.rollback()
        raise

    try:
        await lounge_ws_manager.broadcast(room_id, {"type": "lounge_room_update", "room_id": room_id})
    except Exception as e:
        logger.warning("Lounge WS broadcast after invite: %s", e)
    return {"status": "invited"}


# ---- Messages ----
@router.get("/rooms/{room_id}/messages")
async def list_messages(
    room_id: str,
    limit: int = Query(100, ge=1, le=200),
    before_sequence: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List public messages (paginated). New joiners only see messages from after they joined."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    members = await repo.list_members(room_id)
    current_member = next((m for m in members if m.user_id == current_user.id), None)
    after_created_at = current_member.joined_at if current_member else None
    messages = await repo.list_public_messages(
        room_id, limit=limit, before_sequence=before_sequence, after_created_at=after_created_at
    )
    messages = list(reversed(messages))
    member_ids = {m.sender_user_id for m in messages if m.sender_user_id}
    names = {}
    for uid in member_ids:
        names[uid] = await _get_user_name(db, uid)
    return {"messages": [_message_to_dict(m, names.get(m.sender_user_id)) for m in messages]}


@router.post("/rooms/{room_id}/messages/vet")
async def vet_message(
    room_id: str,
    request: VetRequest,
    context_query: Optional[str] = Query(None, description="Optional Compass query for focused context"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Vet a draft message (no persist). Returns allowed and optional suggestion."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    room = await repo.get_room(room_id)
    messages = await repo.list_public_messages(room_id, limit=20)
    msg_dicts = await _messages_for_kai(db, messages)
    ctx = await repo.get_or_create_kai_context(room_id)
    sender_name = await _get_user_name(db, current_user.id) or getattr(current_user, "display_name", None) or current_user.id
    user_preferences_text = await _get_user_preferences_text(repo, current_user.id)
    compass_profile_text = await _get_compass_profile_text(
        db, current_user.id, relationship_id=None, context_query=context_query, llm_service=llm_service
    )
    conversation_goal = getattr(room, "conversation_goal", None) if room else None
    kai = KaiAgentService(llm_service=llm_service, gemini_api_key=settings.gemini_api_key)
    result = kai.vet_message(
        request.draft, msg_dicts, ctx.summary_text,
        sender_name=sender_name,
        user_preferences_text=user_preferences_text or None,
        compass_profile_text=compass_profile_text or None,
        conversation_goal=conversation_goal,
    )
    await repo.append_event(room_id, "message_vetted", {
        "draft_preview": request.draft[:200],
        "allowed": result.allowed,
        "suggestion": result.suggestion,
        "revised_text": result.revised_text,
        "horseman": result.horseman,
    })
    await db.commit()
    return {"vet_ok": result.allowed, "suggestion": result.suggestion, "revised_text": result.revised_text, "horseman": result.horseman}


@router.post("/rooms/{room_id}/messages")
async def send_message(
    room_id: str,
    request: SendMessageRequest,
    context_query: Optional[str] = Query(None, description="Optional Compass query for focused context"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Send a public message. If force_send is false, Kai vets first; if vet says no, return vet_ok: false and suggestion without persisting.
    If vet ok or force_send true, persist message, update Kai context, run guidance, append events.
    """
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    room = await repo.get_room(room_id)
    conversation_goal = getattr(room, "conversation_goal", None) if room else None
    members = await repo.list_members(room_id)
    solo_room = len(members) == 1 and members[0].user_id == current_user.id
    messages = await repo.list_public_messages(room_id, limit=20)
    msg_dicts = await _messages_for_kai(db, messages)
    ctx = await repo.get_or_create_kai_context(room_id)
    kai = KaiAgentService(llm_service=llm_service, gemini_api_key=settings.gemini_api_key)

    user_preferences_text = await _get_user_preferences_text(repo, current_user.id)
    compass_profile_text = await _get_compass_profile_text(
        db, current_user.id, relationship_id=None, context_query=context_query, llm_service=llm_service
    )
    if not request.force_send and not solo_room:
        sender_name = await _get_user_name(db, current_user.id) or getattr(current_user, "display_name", None) or current_user.id
        vet_result = kai.vet_message(
            request.content, msg_dicts, ctx.summary_text,
            sender_name=sender_name,
            user_preferences_text=user_preferences_text or None,
            compass_profile_text=compass_profile_text or None,
            conversation_goal=conversation_goal,
        )
        if not vet_result.allowed:
            await repo.append_event(room_id, "message_vetted", {
                "draft_preview": request.content[:200],
                "allowed": False,
                "suggestion": vet_result.suggestion,
                "revised_text": vet_result.revised_text,
                "horseman": vet_result.horseman,
            })
            await db.commit()
            return {"vet_ok": False, "suggestion": vet_result.suggestion, "revised_text": vet_result.revised_text, "horseman": vet_result.horseman}

    msg = await repo.append_message(room_id, current_user.id, request.content, visibility="public")
    await repo.append_event(room_id, "message_sent", {
        "message_id": msg.id,
        "sender_user_id": current_user.id,
        "content": request.content,
        "visibility": "public",
        "sequence": msg.sequence,
    })

    # Commit and broadcast immediately so other members get lounge_room_update and can refetch without waiting for Kai
    await db.commit()
    try:
        await lounge_ws_manager.broadcast(room_id, {"type": "lounge_room_update", "room_id": room_id})
    except Exception as e:
        logger.warning("Lounge WS broadcast after send_message (early): %s", e)

    # Update Kai context (include new message with sender label for clarity)
    msg_dicts_with_new = await _messages_for_kai(db, messages, extra=[{"sender_user_id": current_user.id, "content": request.content, "created_at": datetime.now(timezone.utc).isoformat()}])
    summary, facts = kai.update_context(msg_dicts_with_new, ctx.summary_text, ctx.extracted_facts)
    await repo.update_kai_context(room_id, summary, facts)
    await repo.append_event(room_id, "kai_context_updated", {"summary_preview": (summary or "")[:200]})
    if summary and (summary or "").strip():
        await _ingest_kai_insight(db, current_user.id, summary, relationship_id=None)

    # Guidance is for other members (the non-sender). Generate per other member and push via WebSocket; sender gets none in HTTP response.
    if not solo_room:
        other_member_ids = [m.user_id for m in members if m.user_id != current_user.id]
        for other_user_id in other_member_ids:
            other_prefs = await _get_user_preferences_text(repo, other_user_id)
            other_compass = await _get_compass_profile_text(
                db, other_user_id, relationship_id=None, context_query=context_query, llm_service=llm_service
            )
            viewer_name = await _get_user_name(db, other_user_id) or other_user_id
            guidance = kai.get_guidance(
                msg_dicts_with_new,
                latest_from_other=request.content,
                kai_summary=summary,
                user_preferences_text=other_prefs or None,
                compass_profile_text=other_compass or None,
                conversation_goal=conversation_goal,
                viewer_display_name=viewer_name,
            )
            if guidance.guidance_type:
                payload = {
                    "guidance_type": guidance.guidance_type,
                    "text": guidance.text,
                    "suggested_phrase": guidance.suggested_phrase,
                    "debug_prompt": getattr(guidance, "debug_prompt", None),
                    "debug_response": getattr(guidance, "debug_response", None),
                }
                await repo.append_event(room_id, "guidance_offered", {"for_user_id": other_user_id, **{k: v for k, v in payload.items() if k != "debug_prompt" and k != "debug_response"}})
                _pending_guidance[(room_id, other_user_id)] = payload
                try:
                    await lounge_ws_manager.send_to_user_in_room(
                        room_id, other_user_id,
                        {"type": "lounge_guidance", "room_id": room_id, "guidance": payload},
                    )
                except Exception as e:
                    logger.warning("Lounge send guidance to user %s failed: %s", other_user_id, e)
    guidance_payload = None  # Sender never gets guidance in HTTP response

    intention_detected = None
    activity_suggestions_payload = None
    activity_suggestions_rationale = None
    voucher_suggestions_payload = None

    # When only one member (current user), Kai replies in the public thread and may suggest inviting a mentioned loved one
    kai_reply_payload = None
    invite_suggestion_payload = None
    if solo_room:
        screenshot_understanding = (ctx.extracted_facts or {}).get("screenshot_understanding")
        screenshot_thread = (ctx.extracted_facts or {}).get("screenshot_extracted_thread")
        if (
            conversation_goal == "analyze_screenshots"
            and screenshot_understanding
            and isinstance(screenshot_thread, list)
            and len(screenshot_thread) > 0
        ):
            analysis_text = analyze_screenshot_communication_and_suggest(
                screenshot_thread,
                str(screenshot_understanding),
                request.content,
                settings.gemini_api_key,
                kai_summary=summary,
                user_preferences_text=user_preferences_text or None,
                conversation_goal=conversation_goal,
                llm_service=llm_service,
            )
            if analysis_text:
                kai_msg = await repo.append_message(room_id, None, analysis_text, visibility="public")
                await repo.append_event(room_id, "message_sent", {
                    "message_id": kai_msg.id,
                    "sender_user_id": None,
                    "content": analysis_text,
                    "visibility": "public",
                    "sequence": kai_msg.sequence,
                })
                kai_reply_payload = {
                    "content": analysis_text,
                    "message": _message_to_dict(kai_msg, "Kai"),
                    "prompt": None,
                    "response": None,
                }
        if kai_reply_payload is None:
            loved_ones = await _loved_ones_with_names(db, current_user.id)
            solo_result = kai.reply_public_solo(
                request.content, msg_dicts_with_new, summary, loved_ones, debug=request.debug,
                user_preferences_text=user_preferences_text or None,
                compass_profile_text=compass_profile_text or None,
                conversation_goal=conversation_goal,
            )
            if solo_result.reply:
                kai_msg = await repo.append_message(room_id, None, solo_result.reply, visibility="public")
                await repo.append_event(room_id, "message_sent", {
                    "message_id": kai_msg.id,
                    "sender_user_id": None,
                    "content": solo_result.reply,
                    "visibility": "public",
                    "sequence": kai_msg.sequence,
                })
                kai_reply_payload = {
                    "content": solo_result.reply,
                    "message": _message_to_dict(kai_msg, "Kai"),
                    "prompt": solo_result.debug_prompt,
                    "response": solo_result.debug_response,
                }
            if solo_result.suggest_invite_display_name:
                suggest_key = (solo_result.suggest_invite_display_name or "").strip().lower()
                for lo in loved_ones:
                    dn = (lo.get("display_name") or "").strip()
                    if suggest_key == dn.lower() or (dn and suggest_key in dn.lower()):
                        invite_suggestion_payload = {
                            "user_id": lo["user_id"],
                            "display_name": dn or lo["user_id"],
                        }
                        break

        # After Kai replied in solo room: detect intention and optionally suggest activities/vouchers
        if kai_reply_payload and kai_reply_payload.get("content"):
            kai_content = (kai_reply_payload.get("content") or "").strip().lower()
            # Build thread including Kai's reply so intention can see "anything to discuss or prepare"
            thread_with_kai = list(msg_dicts_with_new) + [
                {
                    "sender_user_id": None,
                    "content": kai_reply_payload.get("content", ""),
                    "sender_label": "Kai",
                    "created_at": None,
                }
            ]
            intention_detected = detect_lounge_intention(
                thread_with_kai,
                latest_message=request.content,
                kai_summary=summary,
                gemini_api_key=settings.gemini_api_key,
                llm_service=llm_service,
            )
            # When Kai offers "anything to discuss or prepare?", show activity suggestions even if user didn't ask
            if not intention_detected.get("suggest_activities") and (
                "discuss" in kai_content or "prepare" in kai_content or "anything specific" in kai_content
            ):
                intention_detected = {
                    **intention_detected,
                    "suggest_activities": True,
                    "activity_query": intention_detected.get("activity_query") or "something to do together",
                }
            if intention_detected.get("suggest_activities") or intention_detected.get("suggest_vouchers"):
                solo_loved_ones = await _loved_ones_with_names(db, current_user.id)
                member_list = [
                    {"id": current_user.id, "name": (current_user.display_name or getattr(current_user, "email", None) or current_user.id) or "You"}
                ]
                for lo in solo_loved_ones:
                    member_list.append({
                        "id": lo.get("user_id", ""),
                        "name": (lo.get("display_name") or "").strip() or lo.get("user_id", ""),
                    })
                compass_context_text = (compass_profile_text or "").strip() or "Solo lounge; no relationship context."
                if intention_detected.get("suggest_activities"):
                    raw = generate_activity_recommendations(
                        compass_context_text=compass_context_text,
                        member_list=member_list,
                        duration_max_minutes=None,
                        limit=5,
                        gemini_api_key=settings.gemini_api_key,
                        query=intention_detected.get("activity_query"),
                        llm_service=llm_service,
                    )
                    activity_suggestions_payload = (raw or [])[:3]
                    if activity_suggestions_payload:
                        q = (intention_detected.get("activity_query") or "").strip() or "something to do together"
                        activity_suggestions_rationale = f"I'm suggesting these 3 activities because they could help with: {q}. You can try any of them from the Game Room."
                if intention_detected.get("suggest_vouchers"):
                    voucher_suggestions_payload = generate_repair_vouchers(
                        compass_context_text=compass_context_text,
                        member_list=member_list,
                        limit=5,
                        gemini_api_key=settings.gemini_api_key,
                        llm_service=llm_service,
                    )

    # Extract and store user feedback/preferences from this message (public)
    try:
        extracted = kai.extract_user_preferences(request.content, "public")
        for item in extracted:
            kind = item.get("kind")
            content = item.get("content")
            if kind and content:
                await repo.add_preference(
                    current_user.id, content, kind, "public", room_id=room_id
                )
    except Exception as e:
        logger.warning("Lounge send_message: extract_user_preferences failed: %s", e)

    await db.commit()
    try:
        await lounge_ws_manager.broadcast(room_id, {"type": "lounge_room_update", "room_id": room_id})
    except Exception as e:
        logger.warning("Lounge WS broadcast after send_message: %s", e)
    return {
        "vet_ok": True,
        "message": _message_to_dict(msg, current_user.display_name or "Someone"),
        "guidance": guidance_payload,
        "kai_reply": kai_reply_payload,
        "invite_suggestion": invite_suggestion_payload,
        "intention_detected": intention_detected,
        "activity_suggestions": activity_suggestions_payload,
        "activity_suggestions_rationale": activity_suggestions_rationale,
        "voucher_suggestions": voucher_suggestions_payload,
    }


@router.post("/rooms/{room_id}/analyze-screenshots")
async def analyze_screenshots(
    room_id: str,
    files: list[UploadFile] = File(..., description="One or more screenshot images"),
    context_query: Optional[str] = Query(None, description="Optional Compass query for focused context"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Analyze screenshots of a chat: extract the conversation, understand what's going on and who the user is,
    post that understanding and ask the user to confirm or add context. Analysis and next steps happen
    when the user replies (solo rooms only).
    """
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    room = await repo.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one image is required")

    image_base64_list: list[str] = []
    mime_types: list[str] = []
    for f in files:
        ext = Path(f.filename or "").suffix.lower() or ".jpg"
        if ext not in SCREENSHOT_UPLOAD_ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Allowed image types: {', '.join(SCREENSHOT_UPLOAD_ALLOWED_EXTENSIONS)}",
            )
        content = await f.read()
        if len(content) > SCREENSHOT_UPLOAD_MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 5MB)")
        image_base64_list.append(base64.b64encode(content).decode("ascii"))
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp", ".heic": "image/heic", ".heif": "image/heif"}
        mime_types.append(mime_map.get(ext, "image/jpeg"))

    extracted_thread = extract_chat_from_screenshots(
        image_base64_list,
        mime_types=mime_types,
        gemini_api_key=settings.gemini_api_key,
        llm_service=llm_service,
    )
    if not extracted_thread:
        logger.info("Lounge analyze_screenshots: extraction returned no messages (check Kai logs for reason)")
        fallback = "I couldn't extract a clear conversation from these screenshots. Try clearer or more complete images."
        kai_msg = await repo.append_message(room_id, None, fallback, visibility="public")
        await repo.append_event(room_id, "message_sent", {
            "message_id": kai_msg.id,
            "sender_user_id": None,
            "content": fallback,
            "visibility": "public",
            "sequence": kai_msg.sequence,
        })
        await db.commit()
        try:
            await lounge_ws_manager.broadcast(room_id, {"type": "lounge_room_update", "room_id": room_id})
        except Exception as e:
            logger.warning("Lounge WS broadcast after analyze_screenshots: %s", e)
        return {
            "message": _message_to_dict(kai_msg, "Kai"),
            "extracted_thread": [],
            "message_analysis": [],
        }

    understanding = understand_screenshot_conversation(
        extracted_thread,
        gemini_api_key=settings.gemini_api_key,
        llm_service=llm_service,
    )
    parts = []
    if understanding.whats_going_on:
        parts.append(f"What I see: {understanding.whats_going_on}")
    if understanding.participants_description:
        parts.append(f"Participants: {understanding.participants_description}")
    if understanding.likely_user_in_conversation:
        parts.append(f"Who I think you are: {understanding.likely_user_in_conversation}")
    if understanding.questions_if_any:
        parts.append(f"Questions: {understanding.questions_if_any}")
    parts.append(
        "Is this accurate? Please correct or add any context. Once I know, I can analyze the communication and suggest next steps."
    )
    content_to_post = "\n\n".join(parts)

    # Message-by-message analysis: revisions and guidance Kai would suggest
    message_analysis = analyze_screenshot_messages_for_revisions_and_guidance(
        extracted_thread,
        content_to_post,
        understanding.likely_user_in_conversation,
        gemini_api_key=settings.gemini_api_key,
        llm_service=llm_service,
    )
    message_analysis_dicts = [dataclasses.asdict(a) for a in message_analysis]
    has_any_suggestion = any(
        a.suggested_revision or a.guidance_type for a in message_analysis
    )
    if has_any_suggestion:
        parts.insert(-1, "I've also gone through each message and noted where I'd suggest a rephrase or a nudge—see the details below.")
        content_to_post = "\n\n".join(parts)

    ctx = await repo.get_or_create_kai_context(room_id)
    understanding_text = content_to_post
    summary_line = "Screenshot analysis follow-up. " + (understanding.whats_going_on or "")[:200]
    if (understanding.whats_going_on or "") and len(understanding.whats_going_on or "") > 200:
        summary_line += "..."
    merged_facts = dict(ctx.extracted_facts or {})
    merged_facts["screenshot_understanding"] = understanding_text
    merged_facts["screenshot_extracted_thread"] = extracted_thread
    merged_facts["screenshot_messages_analysis"] = message_analysis_dicts
    await repo.update_kai_context(room_id, summary_text=summary_line, extracted_facts=merged_facts)

    kai_msg = await repo.append_message(room_id, None, content_to_post, visibility="public")
    await repo.append_event(room_id, "message_sent", {
        "message_id": kai_msg.id,
        "sender_user_id": None,
        "content": content_to_post,
        "visibility": "public",
        "sequence": kai_msg.sequence,
    })
    await db.commit()
    try:
        await lounge_ws_manager.broadcast(room_id, {"type": "lounge_room_update", "room_id": room_id})
    except Exception as e:
        logger.warning("Lounge WS broadcast after analyze_screenshots: %s", e)
    return {
        "message": _message_to_dict(kai_msg, "Kai"),
        "extracted_thread": extracted_thread,
        "message_analysis": message_analysis_dicts,
    }


# ---- Private ----
@router.post("/rooms/{room_id}/private")
async def send_private(
    room_id: str,
    request: PrivateMessageRequest,
    context_query: Optional[str] = Query(None, description="Optional Compass query for focused context"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Send a private message to Kai; Kai replies. Content not visible to other room members."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    room = await repo.get_room(room_id)
    conversation_goal = getattr(room, "conversation_goal", None) if room else None
    ctx = await repo.get_or_create_kai_context(room_id)
    user_preferences_text = await _get_user_preferences_text(repo, current_user.id)
    compass_profile_text = await _get_compass_profile_text(
        db, current_user.id, relationship_id=None, context_query=context_query, llm_service=llm_service
    )
    kai = KaiAgentService(llm_service=llm_service, gemini_api_key=settings.gemini_api_key)

    user_msg = await repo.append_message(room_id, current_user.id, request.content, visibility="private_to_kai")
    await repo.append_event(room_id, "private_message", {
        "message_id": user_msg.id,
        "sender_user_id": current_user.id,
        "content": request.content,
        "visibility": "private_to_kai",
    })
    await repo.session.flush()

    private_messages = await repo.list_private_messages_for_user(room_id, current_user.id, limit=30)
    recent_private = [
        {"sender_user_id": m.sender_user_id, "sender_label": "User" if m.sender_user_id else "Kai", "content": m.content}
        for m in private_messages
    ]
    public_messages = await repo.list_public_messages(room_id, limit=20)
    recent_public = await _messages_for_kai(db, public_messages)
    logger.info(
        "Lounge send_private: room_id=%s user_id=%s recent_private=%s recent_public=%s",
        room_id, current_user.id, len(recent_private), len(recent_public),
    )

    private_result = kai.reply_private(
        request.content, ctx.summary_text,
        user_preferences_text=user_preferences_text or None,
        compass_profile_text=compass_profile_text or None,
        conversation_goal=conversation_goal,
        recent_private_messages=recent_private,
        recent_public_messages=recent_public,
    )
    reply_text = private_result.reply
    if reply_text and (reply_text or "").strip():
        await _ingest_kai_insight(db, current_user.id, (reply_text or "")[:2000], relationship_id=None)
    kai_reply_payload = None
    if reply_text:
        kai_msg = await repo.append_message(room_id, None, reply_text, visibility="private_to_kai")
        await repo.append_event(room_id, "private_message", {
            "message_id": kai_msg.id,
            "sender_user_id": None,
            "content": reply_text,
            "visibility": "private_to_kai",
        })
        kai_reply_payload = {
            "content": reply_text,
            "message": _message_to_dict(kai_msg, "Kai"),
            "prompt": private_result.debug_prompt,
            "response": private_result.debug_response,
        }
        logger.info("Lounge send_private: kai_reply len=%s", len(reply_text))
    else:
        logger.info("Lounge send_private: kai_reply empty")

    # Extract and store user feedback/preferences from this message (private)
    try:
        extracted = kai.extract_user_preferences(request.content, "private")
        for item in extracted:
            kind = item.get("kind")
            content = item.get("content")
            if kind and content:
                await repo.add_preference(
                    current_user.id, content, kind, "private", room_id=room_id
                )
    except Exception as e:
        logger.warning("Lounge send_private: extract_user_preferences failed: %s", e)

    await db.commit()
    return {
        "user_message": _message_to_dict(user_msg, current_user.display_name or "Someone"),
        "kai_reply": kai_reply_payload,
    }


@router.get("/rooms/{room_id}/private")
async def list_private(
    room_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List private thread (user + Kai) for current user only."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    messages = await repo.list_private_messages_for_user(room_id, current_user.id, limit=limit)
    names = {}
    for m in messages:
        if m.sender_user_id and m.sender_user_id not in names:
            names[m.sender_user_id] = await _get_user_name(db, m.sender_user_id)
    return {"messages": [_message_to_dict(m, names.get(m.sender_user_id) or "Kai") for m in messages]}


# ---- Context ----
@router.get("/rooms/{room_id}/context")
async def get_context(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get Kai's context (summary + extracted facts) for the room."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    ctx = await repo.get_or_create_kai_context(room_id)
    return {
        "summary_text": ctx.summary_text,
        "extracted_facts": ctx.extracted_facts or {},
        "updated_at": ctx.updated_at.isoformat() if ctx.updated_at else None,
    }


# ---- Events (replay) ----
@router.get("/rooms/{room_id}/events")
async def list_events(
    room_id: str,
    limit: int = Query(200, ge=1, le=500),
    from_sequence: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List event log for replay (ordered by sequence)."""
    repo = LoungeRepository(db)
    await _ensure_member(repo, room_id, current_user.id)
    events = await repo.list_events(room_id, limit=limit, from_sequence=from_sequence)
    return {
        "events": [
            {
                "id": e.id,
                "room_id": e.room_id,
                "sequence": e.sequence,
                "event_type": e.event_type,
                "payload": e.payload or {},
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }
