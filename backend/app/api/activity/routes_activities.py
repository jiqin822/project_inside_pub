"""Activity API: invite, respond, planned, complete, log-interaction, memory-upload, scrapbook."""
from datetime import datetime
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List

from app.api.deps import get_current_user, get_db, get_llm_service
from app.domain.admin.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.relationship import relationship_members
from app.infra.db.repositories.event_repo import EventRepository
from app.infra.db.repositories.activity_invite_repo import ActivityInviteRepository
from app.infra.db.repositories.planned_activity_repo import PlannedActivityRepository
from app.infra.db.repositories.activity_template_repo import ActivityTemplateRepository
from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
from app.services.notification_service import deliver_notification
from app.domain.activity.services import (
    generate_scrapbook_layout as generate_scrapbook_layout_service,
    generate_scrapbook_options as generate_scrapbook_options_service,
    generate_scrapbook_html as generate_scrapbook_html_service,
    make_sticker_generator,
)
from app.settings import settings
from app.services.llm_service import LLMService

router = APIRouter()


async def _ensure_member(db: AsyncSession, relationship_id: str, user_id: str) -> None:
    result = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id == relationship_id,
        )
    )
    member_ids = [row[0] for row in result.all()]
    if user_id not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this relationship",
        )


class LogInteractionRequest(BaseModel):
    relationship_id: str
    suggestion_id: str
    action: str  # viewed | invite_sent | dismissed | completed


@router.post("/log-interaction")
async def log_interaction(
    request: LogInteractionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log user interaction with an activity suggestion (viewed, invite_sent, dismissed, completed)."""
    if request.action not in ("viewed", "invite_sent", "dismissed", "completed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
    await _ensure_member(db, request.relationship_id, current_user.id)
    event_repo = EventRepository(db)
    await event_repo.append(
        type="activity_suggestion_interaction",
        actor_user_id=current_user.id,
        relationship_id=request.relationship_id,
        payload={
            "suggestion_id": request.suggestion_id,
            "action": request.action,
        },
        source="activity",
    )
    return {"ok": True}


class InviteRequest(BaseModel):
    relationship_id: str
    activity_template_id: str
    invitee_user_id: str
    card_snapshot: Optional[dict] = None  # full ActivityCard-like JSON for UI (title, description, tags, etc.)


@router.post("/invite")
async def send_invite(
    request: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an activity invite and notify the invitee."""
    await _ensure_member(db, request.relationship_id, current_user.id)
    member_result = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id == request.relationship_id,
        )
    )
    member_ids = [row[0] for row in member_result.all()]
    if request.invitee_user_id not in member_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invitee is not in this relationship")
    if request.invitee_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot invite yourself")

    template_repo = ActivityTemplateRepository(db)
    template = await template_repo.get(request.activity_template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Activity template not found: {request.activity_template_id}. "
                "Use an activity_template_id from the current suggestions or recommendations. "
                "If you just loaded suggestions, refresh the Game Room and try again."
            ),
        )
    activity_title = template.title

    invite_repo = ActivityInviteRepository(db)
    invite = await invite_repo.create(
        relationship_id=request.relationship_id,
        activity_template_id=request.activity_template_id,
        from_user_id=current_user.id,
        to_user_id=request.invitee_user_id,
        card_snapshot=request.card_snapshot,
    )

    sender_name = current_user.display_name or "Someone"
    await deliver_notification(
        db,
        request.invitee_user_id,
        "activity_invite",
        "Activity invite",
        f"{sender_name} invited you to: {activity_title}",
        extra_payload={"invite_id": invite.id, "activity_title": activity_title},
    )

    event_repo = EventRepository(db)
    await event_repo.append(
        type="activity_invite_sent",
        actor_user_id=current_user.id,
        relationship_id=request.relationship_id,
        payload={
            "invite_id": invite.id,
            "activity_template_id": request.activity_template_id,
            "invitee_user_id": request.invitee_user_id,
        },
        source="activity",
    )
    return {"invite_id": invite.id}


class RespondRequest(BaseModel):
    accept: bool


@router.post("/invite/{invite_id}/respond")
async def respond_to_invite(
    invite_id: str,
    request: RespondRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept or decline an activity invite. Only the invitee can respond."""
    invite_repo = ActivityInviteRepository(db)
    invite = await invite_repo.get_by_id(invite_id)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.to_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the invitee can respond")
    if invite.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite already responded")

    status_value = "accepted" if request.accept else "declined"
    now = datetime.utcnow()
    await invite_repo.update_status(invite_id, status_value, responded_at=now)

    template_repo = ActivityTemplateRepository(db)
    template = await template_repo.get(invite.activity_template_id)
    activity_title = template.title if template else "Activity"

    event_repo = EventRepository(db)
    await event_repo.append(
        type="activity_invite_accepted" if request.accept else "activity_invite_declined",
        actor_user_id=current_user.id,
        relationship_id=invite.relationship_id,
        payload={"invite_id": invite_id, "accept": request.accept},
        source="activity",
    )

    if request.accept:
        planned_repo = PlannedActivityRepository(db)
        card_snapshot = getattr(invite, "card_snapshot", None)
        planned = await planned_repo.create(
            relationship_id=invite.relationship_id,
            activity_template_id=invite.activity_template_id,
            initiator_user_id=invite.from_user_id,
            invitee_user_id=current_user.id,
            invite_id=invite_id,
            card_snapshot=card_snapshot,
        )
        responder_name = current_user.display_name or "Someone"
        await deliver_notification(
            db,
            invite.from_user_id,
            "activity_invite",
            "Activity accepted",
            f"{responder_name} accepted: {activity_title}",
            extra_payload={"planned_id": planned.id},
        )
        return {"ok": True, "planned_id": planned.id}
    # Declined: notify the sender
    responder_name = current_user.display_name or "Someone"
    await deliver_notification(
        db,
        invite.from_user_id,
        "activity_invite",
        "Activity declined",
        f"{responder_name} declined: {activity_title}",
    )
    return {"ok": True}


class PlannedItemResponse(BaseModel):
    id: str
    relationship_id: str
    activity_template_id: str
    activity_title: str
    initiator_user_id: str
    invitee_user_id: str
    status: str
    agreed_at: str
    completed_at: Optional[str]
    notes_text: Optional[str]
    memory_urls: Optional[List[str]]
    activity_card: Optional[dict] = None  # full ActivityCard-like JSON for UI (from card_snapshot)


class HistoryItemResponse(BaseModel):
    id: str
    relationship_id: str
    activity_template_id: str
    activity_title: str
    started_at: str
    completed_at: Optional[str]
    notes_text: Optional[str]
    rating: Optional[float]
    outcome_tags: Optional[List[str]]
    memory_urls: Optional[List[str]]


@router.get("/history", response_model=List[HistoryItemResponse])
async def list_activity_history(
    relationship_id: str = Query(..., description="Relationship ID"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List dyad activity history (completed activities) for Archived Logs / Past Memories."""
    await _ensure_member(db, relationship_id, current_user.id)
    dyad_repo = DyadActivityHistoryRepository(db)
    template_repo = ActivityTemplateRepository(db)
    records = await dyad_repo.list_by_relationship(relationship_id, limit=limit)
    out = []
    for r in records:
        template = await template_repo.get(r.activity_template_id)
        title = template.title if template else r.activity_template_id
        # outcome_tags may be stored as list or dict (e.g. {"feeling": "loved"}); response expects list
        ot = r.outcome_tags
        if isinstance(ot, dict) and ot:
            outcome_tags_list = [f"{k}:{v}" for k, v in ot.items() if v is not None]
        elif isinstance(ot, list):
            outcome_tags_list = [str(x) for x in ot]
        else:
            outcome_tags_list = None
        out.append(
            HistoryItemResponse(
                id=r.id,
                relationship_id=r.relationship_id,
                activity_template_id=r.activity_template_id,
                activity_title=title,
                started_at=r.started_at.isoformat() + "Z" if r.started_at else "",
                completed_at=r.completed_at.isoformat() + "Z" if r.completed_at else None,
                notes_text=r.notes_text,
                rating=r.rating,
                outcome_tags=outcome_tags_list,
                memory_urls=r.memory_urls,
            )
        )
    return out


class HistoryAllItemResponse(BaseModel):
    item_type: str  # "completed" | "declined"
    id: str
    relationship_id: str
    activity_template_id: str
    activity_title: str
    date: str  # iso date for sorting/display
    notes_text: Optional[str] = None
    memory_urls: Optional[List[str]] = None
    # for declined: invite_id
    invite_id: Optional[str] = None


@router.get("/history/all", response_model=List[HistoryAllItemResponse])
async def list_activity_history_all(
    relationship_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all activity history for the current user: completed activities and declined invites, unified and sorted by date."""
    dyad_repo = DyadActivityHistoryRepository(db)
    invite_repo = ActivityInviteRepository(db)
    template_repo = ActivityTemplateRepository(db)
    out: List[HistoryAllItemResponse] = []
    # Completed: from dyad_activity_history for relationships the user is in
    if relationship_id:
        await _ensure_member(db, relationship_id, current_user.id)
        records = await dyad_repo.list_by_relationship(relationship_id, limit=limit * 2)
        for r in records:
            if r.actor_user_id != current_user.id:
                continue
            template = await template_repo.get(r.activity_template_id)
            title = template.title if template else r.activity_template_id
            date_str = r.completed_at.isoformat() + "Z" if r.completed_at else (r.started_at.isoformat() + "Z" if r.started_at else "")
            out.append(
                HistoryAllItemResponse(
                    item_type="completed",
                    id=r.id,
                    relationship_id=r.relationship_id,
                    activity_template_id=r.activity_template_id,
                    activity_title=title,
                    date=date_str,
                    notes_text=r.notes_text,
                    memory_urls=r.memory_urls,
                    invite_id=None,
                )
            )
    else:
        # No relationship filter: get all dyad history where user is actor (we'd need list_by_user on dyad_repo)
        # For simplicity, require relationship_id for /history/all
        pass
    # Declined: invites to current user that were declined
    declined = await invite_repo.get_declined_for_user(current_user.id, limit=limit)
    for inv in declined:
        if relationship_id and inv.relationship_id != relationship_id:
            continue
        template = await template_repo.get(inv.activity_template_id)
        title = template.title if template else inv.activity_template_id
        date_str = inv.responded_at.isoformat() + "Z" if inv.responded_at else (inv.created_at.isoformat() + "Z" if inv.created_at else "")
        out.append(
            HistoryAllItemResponse(
                item_type="declined",
                id=inv.id,
                relationship_id=inv.relationship_id,
                activity_template_id=inv.activity_template_id,
                activity_title=title,
                date=date_str,
                notes_text=None,
                memory_urls=None,
                invite_id=inv.id,
            )
        )
    # Sort by date descending
    out.sort(key=lambda x: x.date, reverse=True)
    return out[:limit]


class MemoryContributionResponse(BaseModel):
    actor_user_id: str
    actor_name: Optional[str] = None
    notes_text: Optional[str] = None
    memory_entries: Optional[List[dict]] = None  # [{ "url", "caption" }]
    feeling: Optional[str] = None


class MemoryItemResponse(BaseModel):
    id: str  # planned_id or first record id
    relationship_id: str
    activity_template_id: str
    activity_title: str
    completed_at: str
    contributions: List[MemoryContributionResponse]
    scrapbook_layout: Optional[dict] = None  # AI-generated layout when saved


@router.get("/memories", response_model=List[MemoryItemResponse])
async def list_memories(
    relationship_id: str = Query(..., description="Relationship ID"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List completed activities for the relationship with aggregated notes and memory entries from all participants (for Memories tab).
    By default, each memory/scrapbook entry is visible to all participants in the relationship; only relationship members can call this endpoint."""
    await _ensure_member(db, relationship_id, current_user.id)
    dyad_repo = DyadActivityHistoryRepository(db)
    template_repo = ActivityTemplateRepository(db)
    planned_repo = PlannedActivityRepository(db)
    from app.infra.db.repositories.user_repo import UserRepositoryImpl
    user_repo = UserRepositoryImpl(db)
    records = await dyad_repo.list_by_relationship(relationship_id, limit=limit * 5)
    # Group by planned_id (or by record id when planned_id is null)
    groups: dict = {}
    for r in records:
        key = r.planned_id if r.planned_id else r.id
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    out = []
    for key, rows in groups.items():
        r0 = rows[0]
        template = await template_repo.get(r0.activity_template_id)
        title = template.title if template else r0.activity_template_id
        completed_at = r0.completed_at.isoformat() + "Z" if r0.completed_at else (r0.started_at.isoformat() + "Z" if r0.started_at else "")
        contributions = []
        for r in rows:
            actor = await user_repo.get_by_id(r.actor_user_id)
            actor_name = (actor.display_name or (actor.email.split("@")[0] if actor and actor.email else "Someone")) if actor else "Someone"
            feeling = None
            if isinstance(r.outcome_tags, dict) and r.outcome_tags:
                feeling = r.outcome_tags.get("feeling")
            contributions.append(
                MemoryContributionResponse(
                    actor_user_id=r.actor_user_id,
                    actor_name=actor_name,
                    notes_text=r.notes_text,
                    memory_entries=r.memory_entries,
                    feeling=feeling,
                )
            )
        scrapbook_layout = None
        planned = await planned_repo.get_by_id(key)
        if planned and getattr(planned, "scrapbook_layout", None):
            scrapbook_layout = planned.scrapbook_layout
        elif not planned and getattr(r0, "scrapbook_layout", None):
            scrapbook_layout = r0.scrapbook_layout
        out.append(
            MemoryItemResponse(
                id=key,
                relationship_id=r0.relationship_id,
                activity_template_id=r0.activity_template_id,
                activity_title=title,
                completed_at=completed_at,
                contributions=contributions,
                scrapbook_layout=scrapbook_layout,
            )
        )
    out.sort(key=lambda x: x.completed_at, reverse=True)
    return out[:limit]


@router.get("/planned", response_model=List[PlannedItemResponse])
async def list_planned(
    relationship_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List planned activities for the current user (initiator or invitee)."""
    planned_repo = PlannedActivityRepository(db)
    template_repo = ActivityTemplateRepository(db)
    items = await planned_repo.list_by_user(current_user.id, relationship_id=relationship_id)
    out = []
    for p in items:
        template = await template_repo.get(p.activity_template_id)
        title = template.title if template else p.activity_template_id
        card_snapshot = getattr(p, "card_snapshot", None)
        out.append(
            PlannedItemResponse(
                id=p.id,
                relationship_id=p.relationship_id,
                activity_template_id=p.activity_template_id,
                activity_title=title,
                initiator_user_id=p.initiator_user_id,
                invitee_user_id=p.invitee_user_id,
                status=p.status,
                agreed_at=p.agreed_at.isoformat() + "Z" if p.agreed_at else "",
                completed_at=p.completed_at.isoformat() + "Z" if p.completed_at else None,
                notes_text=p.notes_text,
                memory_urls=p.memory_urls,
                activity_card=card_snapshot,
            )
        )
    return out


class MemoryEntryItem(BaseModel):
    url: str
    caption: Optional[str] = None


class CompleteRequest(BaseModel):
    notes: Optional[str] = None
    memory_urls: Optional[List[str]] = None
    memory_entries: Optional[List[MemoryEntryItem]] = None
    feeling: Optional[str] = None


class LogMemoryRequest(BaseModel):
    relationship_id: str
    activity_title: str
    notes: Optional[str] = None
    memory_urls: Optional[List[str]] = None
    memory_entries: Optional[List[MemoryEntryItem]] = None
    feeling: Optional[str] = None


def _urls_from_memory_entries(entries: Optional[List[MemoryEntryItem]]) -> Optional[List[str]]:
    if not entries:
        return None
    return [e.url for e in entries]


class ScrapbookGenerateRequest(BaseModel):
    activity_title: str
    note: str
    feeling: Optional[str] = None
    image_count: int
    limit: Optional[int] = 3  # 1 = single style (e.g. Palette), 3 = multiple options
    activity_template_id: Optional[str] = None  # for HTML scrapbook: look up template for description, vibe_tags, etc.
    include_debug: Optional[bool] = False  # when true, return prompt and response for scrapbook debug modal
    disable_sticker_generation: Optional[bool] = False  # when true, do not generate or inject AI sticker images (user preference)


@router.post("/scrapbook/generate")
async def scrapbook_generate(
    request: ScrapbookGenerateRequest,
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Generate a scrapbook layout (themeColor, headline, narrative, stickers, imageCaptions) via LLM service."""
    layout = await generate_scrapbook_layout_service(
        gemini_api_key=settings.gemini_api_key,
        activity_title=request.activity_title,
        note=request.note,
        feeling=request.feeling,
        image_count=max(0, request.image_count),
        llm_service=llm_service,
    )
    return layout


@router.post("/scrapbook/generate-options")
async def scrapbook_generate_options(
    request: ScrapbookGenerateRequest,
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Generate 1 or 3 scrapbook layout options (element-based) via LLM service. limit=1 for Palette (single style + Cancel)."""
    limit = max(1, min(3, request.limit or 3))
    options = await generate_scrapbook_options_service(
        activity_title=request.activity_title,
        note=request.note,
        feeling=request.feeling,
        image_count=max(0, request.image_count),
        limit=limit,
        layout_generator=llm_service.generate_text,
    )
    return {"options": options}


@router.post("/scrapbook/generate-html")
async def scrapbook_generate_html(
    request: ScrapbookGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Generate a single scrapbook layout as raw HTML via LLM service (Palette / inside-app parity). Uses activity template when provided for description, vibe_tags, duration, location."""
    description = None
    vibe_tags = None
    duration_min = None
    recommended_location = None
    if request.activity_template_id:
        template_repo = ActivityTemplateRepository(db)
        template = await template_repo.get(request.activity_template_id)
        if template:
            enriched = _enrich_invite_with_template(template, None, template.title)
            description = enriched.get("description") or None
            vibe_tags = enriched.get("vibe_tags") or None
            duration_min = enriched.get("duration_min")
            recommended_location = enriched.get("recommended_location")
    def layout_generator(prompt: str, model: Optional[str] = None) -> Optional[str]:
        return llm_service.generate_text(prompt, model=model)

    result = await generate_scrapbook_html_service(
        activity_title=request.activity_title,
        note=request.note,
        feeling=request.feeling,
        image_count=max(0, request.image_count),
        description=description,
        vibe_tags=vibe_tags,
        duration_min=duration_min,
        recommended_location=recommended_location,
        include_debug=bool(request.include_debug),
        disable_sticker_generation=bool(request.disable_sticker_generation),
        sticker_generator=make_sticker_generator(llm_service.generate_image),
        layout_generator=layout_generator,
    )
    return result


class ScrapbookGenerateStickerRequest(BaseModel):
    prompt: str


@router.post("/scrapbook/generate-sticker")
async def scrapbook_generate_sticker(
    request: ScrapbookGenerateStickerRequest,
    current_user: User = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service),
):
    """Generate a single scrapbook sticker image (OpenAI or Gemini per LLM service). Returns base64 for inlining."""
    sticker_gen = make_sticker_generator(llm_service.generate_image)
    b64 = sticker_gen(request.prompt.strip(), (100, 100))
    if b64 is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sticker generation failed or no image API key configured",
        )
    return {"b64": b64}


class ScrapbookSaveRequest(BaseModel):
    layout: dict  # ScrapbookLayout: themeColor, secondaryColor, narrative, headline, stickers, imageCaptions, style


@router.post("/planned/{planned_id}/scrapbook")
async def save_scrapbook(
    planned_id: str,
    request: ScrapbookSaveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save AI-generated scrapbook layout for a completed planned activity; notify all participants.
    The scrapbook is visible to all participants in the planned activity by default.
    Accepts either a planned_activity id or a memory (dyad history) id; if the id is a history
    record id and it has a planned_id, we resolve to the planned activity."""
    planned_repo = PlannedActivityRepository(db)
    planned = await planned_repo.get_by_id(planned_id)
    if not planned:
        # Frontend may send the memory list id, which can be a dyad history id when grouped by record
        from app.infra.db.repositories.dyad_activity_repo import DyadActivityHistoryRepository
        dyad_repo = DyadActivityHistoryRepository(db)
        history_record = await dyad_repo.get_by_id(planned_id)
        if history_record and history_record.planned_id:
            planned_id = history_record.planned_id
            planned = await planned_repo.get_by_id(planned_id)
        if not planned:
            if history_record and not history_record.planned_id:
                # Standalone memory: save scrapbook to the dyad history record
                await _ensure_member(db, history_record.relationship_id, current_user.id)
                await dyad_repo.update_scrapbook_layout(planned_id, request.layout)
                return {"ok": True}
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planned activity not found")
    participant_ids = {str(planned.initiator_user_id), str(planned.invitee_user_id)}
    current_id = str(current_user.id)
    if current_id not in participant_ids:
        # Fallback: allow if user is a member of the planned activity's relationship (handles id format mismatch)
        result = await db.execute(
            select(relationship_members.c.user_id).where(
                relationship_members.c.relationship_id == planned.relationship_id,
            )
        )
        member_ids = {str(row[0]) for row in result.all()}
        if current_id not in member_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")
    await planned_repo.update_scrapbook_layout(planned_id, request.layout)
    title = "Scrapbook saved"
    message = "Your shared memory has a new scrapbook layout."
    # Notify only other participants; do not notify the user who performed the save
    for user_id in (planned.initiator_user_id, planned.invitee_user_id):
        if str(user_id) == current_id:
            continue
        await deliver_notification(
            db,
            user_id,
            "scrapbook",
            title,
            message,
            extra_payload={"planned_id": planned_id},
        )
    return {"ok": True}


@router.post("/planned/{planned_id}/complete")
async def complete_planned(
    planned_id: str,
    request: CompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a planned activity as completed and append to dyad history. Second participant can also submit (adds their notes/photos).
    The resulting memory/scrapbook entry is visible to all participants in the relationship by default."""
    planned_repo = PlannedActivityRepository(db)
    planned = await planned_repo.get_by_id(planned_id)
    if not planned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planned activity not found")
    if current_user.id not in (planned.initiator_user_id, planned.invitee_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")

    now = datetime.utcnow()
    memory_urls = request.memory_urls
    memory_entries_raw = None
    if request.memory_entries:
        memory_entries_raw = [{"url": e.url, "caption": e.caption} for e in request.memory_entries]
        if not memory_urls:
            memory_urls = _urls_from_memory_entries(request.memory_entries)

    if planned.status == "planned":
        await planned_repo.update_completion(
            planned_id,
            completed_at=now,
            notes_text=request.notes,
            memory_urls=memory_urls,
        )

    dyad_repo = DyadActivityHistoryRepository(db)
    outcome_tags = {"feeling": request.feeling} if request.feeling else None
    await dyad_repo.append(
        relationship_id=planned.relationship_id,
        activity_template_id=planned.activity_template_id,
        actor_user_id=current_user.id,
        started_at=planned.agreed_at,
        completed_at=now,
        notes_text=request.notes,
        memory_urls=memory_urls,
        memory_entries=memory_entries_raw,
        planned_id=planned_id,
        outcome_tags=outcome_tags,
    )

    event_repo = EventRepository(db)
    mem_count = len(memory_urls or []) if memory_urls else (len(request.memory_entries or []) if request.memory_entries else 0)
    await event_repo.append(
        type="activity_completed",
        actor_user_id=current_user.id,
        relationship_id=planned.relationship_id,
        payload={
            "planned_id": planned_id,
            "activity_template_id": planned.activity_template_id,
            "has_notes": bool(request.notes),
            "memory_count": mem_count,
        },
        source="activity",
    )
    return {"ok": True}


@router.post("/memory/log")
async def log_memory(
    request: LogMemoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log a standalone memory entry (not tied to a planned activity)."""
    await _ensure_member(db, request.relationship_id, current_user.id)
    title = (request.activity_title or "").strip() or "Memory"

    template_repo = ActivityTemplateRepository(db)
    template_id = f"memory-log-{uuid.uuid4().hex[:12]}"
    await template_repo.create(
        activity_id=template_id,
        title=title,
        relationship_types=["partner"],
        vibe_tags=["memory"],
        constraints={"duration_min": 0, "location": "any"},
        steps_markdown_template="",
        personalization_slots={"source": "memory_log"},
        is_active=False,
    )

    memory_urls = request.memory_urls
    memory_entries_raw = None
    if request.memory_entries:
        memory_entries_raw = [{"url": e.url, "caption": e.caption} for e in request.memory_entries]
        if not memory_urls:
            memory_urls = _urls_from_memory_entries(request.memory_entries)

    now = datetime.utcnow()
    dyad_repo = DyadActivityHistoryRepository(db)
    outcome_tags = {"feeling": request.feeling} if request.feeling else None
    await dyad_repo.append(
        relationship_id=request.relationship_id,
        activity_template_id=template_id,
        actor_user_id=current_user.id,
        started_at=now,
        completed_at=now,
        notes_text=request.notes,
        memory_urls=memory_urls,
        memory_entries=memory_entries_raw,
        planned_id=None,
        outcome_tags=outcome_tags,
    )
    return {"ok": True, "activity_template_id": template_id}


def _enrich_invite_with_template(template, inv, title):
    """Add full activity card fields from template for frontend card layout."""
    if not template:
        return {
            "description": "",
            "duration_min": 30,
            "vibe_tags": [],
            "recommended_location": None,
        }
    constraints = getattr(template, "constraints", None) or {}
    if isinstance(constraints, dict):
        duration_min = constraints.get("duration_min") if constraints else None
        recommended_location = (constraints.get("location") or "").strip() or None
    else:
        duration_min = 30
        recommended_location = None
    slots = getattr(template, "personalization_slots", None) or {}
    if isinstance(slots, dict) and not recommended_location and slots.get("recommended_location"):
        recommended_location = str(slots["recommended_location"]).strip() or None
    vibe_tags = getattr(template, "vibe_tags", None)
    if not isinstance(vibe_tags, list):
        vibe_tags = []
    description = (getattr(template, "steps_markdown_template") or "").strip() or ""
    return {
        "description": description[:500] if description else "",
        "duration_min": int(duration_min) if duration_min is not None else 30,
        "vibe_tags": vibe_tags[:10],
        "recommended_location": recommended_location,
    }


@router.get("/invites/pending")
async def list_pending_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pending activity invites for the current user (for Accept/Decline UI)."""
    invite_repo = ActivityInviteRepository(db)
    template_repo = ActivityTemplateRepository(db)
    from app.infra.db.repositories.user_repo import UserRepositoryImpl
    user_repo = UserRepositoryImpl(db)
    invites = await invite_repo.get_pending_for_user(current_user.id)
    out = []
    for inv in invites:
        template = await template_repo.get(inv.activity_template_id)
        title = template.title if template else inv.activity_template_id
        extra = _enrich_invite_with_template(template, inv, title)
        from_user = await user_repo.get_by_id(inv.from_user_id)
        from_name = (from_user.display_name or (from_user.email.split("@")[0] if from_user and from_user.email else "Someone")) if from_user else "Someone"
        out.append({
            "invite_id": inv.id,
            "relationship_id": inv.relationship_id,
            "activity_template_id": inv.activity_template_id,
            "activity_title": title,
            "from_user_id": inv.from_user_id,
            "from_user_name": from_name,
            "created_at": inv.created_at.isoformat() + "Z" if inv.created_at else None,
            **extra,
        })
    return out


@router.get("/invites/sent")
async def list_sent_invites(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List activity invites sent by the current user that are still pending (for Planned tab)."""
    invite_repo = ActivityInviteRepository(db)
    template_repo = ActivityTemplateRepository(db)
    from app.infra.db.repositories.user_repo import UserRepositoryImpl
    user_repo = UserRepositoryImpl(db)
    invites = await invite_repo.get_sent_for_user(current_user.id)
    out = []
    for inv in invites:
        template = await template_repo.get(inv.activity_template_id)
        title = template.title if template else inv.activity_template_id
        extra = _enrich_invite_with_template(template, inv, title)
        to_user = await user_repo.get_by_id(inv.to_user_id)
        to_name = (to_user.display_name or (to_user.email.split("@")[0] if to_user and to_user.email else "Someone")) if to_user else "Someone"
        out.append({
            "item_type": "sent_pending",
            "invite_id": inv.id,
            "relationship_id": inv.relationship_id,
            "activity_template_id": inv.activity_template_id,
            "activity_title": title,
            "to_user_id": inv.to_user_id,
            "to_user_name": to_name,
            "created_at": inv.created_at.isoformat() + "Z" if inv.created_at else None,
            **extra,
        })
    return out


# Allowed image types and max size (5MB) for memory uploads (include HEIC/HEIF for iOS)
MEMORY_UPLOAD_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
MEMORY_UPLOAD_MAX_BYTES = 5 * 1024 * 1024


@router.post("/memory-upload")
async def memory_upload(
    planned_id: Optional[str] = Query(None, description="Planned activity ID"),
    relationship_id: Optional[str] = Query(None, description="Relationship ID for standalone memory"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a memory image for a planned or standalone memory."""
    if not planned_id and not relationship_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="planned_id or relationship_id required")
    if planned_id:
        planned_repo = PlannedActivityRepository(db)
        planned = await planned_repo.get_by_id(planned_id)
        if not planned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planned activity not found")
        if current_user.id not in (planned.initiator_user_id, planned.invitee_user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant")
    else:
        await _ensure_member(db, relationship_id, current_user.id)

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    if ext not in MEMORY_UPLOAD_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allowed types: {', '.join(MEMORY_UPLOAD_ALLOWED_EXTENSIONS)}",
        )
    content = await file.read()
    if len(content) > MEMORY_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large (max 5MB)")

    storage_dir = Path("storage/activity_memories")
    storage_dir.mkdir(parents=True, exist_ok=True)
    owner_key = planned_id or relationship_id or "memory"
    name = f"{owner_key}_{uuid.uuid4().hex[:12]}{ext}"
    path = storage_dir / name
    path.write_bytes(content)
    relative_url = f"storage/activity_memories/{name}"
    return {"url": relative_url}
