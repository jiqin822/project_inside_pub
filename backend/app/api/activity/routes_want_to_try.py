"""Want-to-try and mutual match API."""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.relationship import relationship_members
from app.infra.db.repositories.discover_feed_repo import DiscoverFeedRepository
from app.infra.db.repositories.activity_want_to_try_repo import ActivityWantToTryRepository
from app.infra.db.repositories.planned_activity_repo import PlannedActivityRepository
from app.infra.db.repositories.user_repo import UserRepositoryImpl
from app.services.notification_service import deliver_notification

logger = logging.getLogger(__name__)

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


def _user_display_name(user) -> str:
    if not user:
        return "Someone"
    name = getattr(user, "display_name", None) or (getattr(user, "email", "") or "").split("@")[0]
    if name and len(name) > 0:
        return name
    return "Someone"


class WantToTryRequest(BaseModel):
    relationship_id: str
    discover_feed_item_id: str


class WantToTryResponse(BaseModel):
    ok: bool
    mutual_match_id: Optional[str] = None  # set when mutual match created


@router.post("", response_model=WantToTryResponse)
async def want_to_try(
    request: WantToTryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record that the current user wants to try this activity. If the other user (recommended invitee/generator) already wanted it, creates a mutual match and notifies both."""
    await _ensure_member(db, request.relationship_id, current_user.id)

    discover_repo = DiscoverFeedRepository(db)
    feed_item = await discover_repo.get_by_id(request.discover_feed_item_id)
    if not feed_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discover feed item not found",
        )
    if feed_item.relationship_id != request.relationship_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Feed item not in this relationship")

    want_repo = ActivityWantToTryRepository(db)
    await want_repo.create_want_to_try(
        user_id=current_user.id,
        relationship_id=request.relationship_id,
        discover_feed_item_id=request.discover_feed_item_id,
    )

    other = await want_repo.get_other_want_to_try_for_feed_item(
        discover_feed_item_id=request.discover_feed_item_id,
        exclude_user_id=current_user.id,
    )
    mutual_match_id = None
    if other:
        user_a_id = other.user_id
        user_b_id = current_user.id
        match = await want_repo.create_mutual_match(
            relationship_id=request.relationship_id,
            discover_feed_item_id=request.discover_feed_item_id,
            user_a_id=user_a_id,
            user_b_id=user_b_id,
        )
        mutual_match_id = match.id

        activity_title = "This activity"
        if feed_item.card_snapshot and isinstance(feed_item.card_snapshot, dict):
            activity_title = (feed_item.card_snapshot.get("title") or activity_title).strip()

        user_repo = UserRepositoryImpl(db)
        current_name = _user_display_name(await user_repo.get_by_id(current_user.id))
        other_user = await user_repo.get_by_id(other.user_id)
        other_name = _user_display_name(other_user)

        msg_to_other = f'You and {current_name} both want to try "{activity_title}". Accept to plan it?'
        msg_to_me = f'You and {other_name} both want to try "{activity_title}". Accept to plan it?'
        await deliver_notification(
            db,
            other.user_id,
            "activity",
            "You both want to try!",
            msg_to_other,
            extra_payload={
                "mutual_match_id": match.id,
                "activity_title": activity_title,
                "discover_feed_item_id": request.discover_feed_item_id,
            },
        )
        await deliver_notification(
            db,
            current_user.id,
            "activity",
            "You both want to try!",
            msg_to_me,
            extra_payload={
                "mutual_match_id": match.id,
                "activity_title": activity_title,
                "discover_feed_item_id": request.discover_feed_item_id,
            },
        )

    return WantToTryResponse(ok=True, mutual_match_id=mutual_match_id)


class MutualMatchRespondRequest(BaseModel):
    accept: bool  # True = accept, False = decline


@router.post("/mutual-match/{mutual_match_id}/respond")
async def respond_to_mutual_match(
    mutual_match_id: str,
    request: MutualMatchRespondRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept or decline a mutual match. If both accept, a planned activity is created and both are notified."""
    want_repo = ActivityWantToTryRepository(db)
    match = await want_repo.get_mutual_match_by_id(mutual_match_id)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mutual match not found")
    if current_user.id not in (match.user_a_id, match.user_b_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your mutual match")

    response = "accept" if request.accept else "decline"
    updated = await want_repo.respond_to_mutual_match(match_id=mutual_match_id, user_id=current_user.id, response=response)
    if not updated:
        return {"ok": False, "message": "Already responded"}

    if request.accept and await want_repo.both_accepted(updated):
        discover_repo = DiscoverFeedRepository(db)
        feed_item = await discover_repo.get_by_id(updated.discover_feed_item_id)
        if feed_item:
            planned_repo = PlannedActivityRepository(db)
            card_snapshot = feed_item.card_snapshot if isinstance(feed_item.card_snapshot, dict) else None
            await planned_repo.create(
                relationship_id=feed_item.relationship_id,
                activity_template_id=feed_item.activity_template_id,
                initiator_user_id=updated.user_a_id,
                invitee_user_id=updated.user_b_id,
                invite_id=None,
                card_snapshot=card_snapshot,
            )
            activity_title = (card_snapshot.get("title") or "Activity") if card_snapshot else "Activity"
            for uid in (updated.user_a_id, updated.user_b_id):
                await deliver_notification(
                    db,
                    uid,
                    "activity_planned",
                    "Activity planned",
                    f'You both accepted: "{activity_title}" is now planned.',
                    extra_payload={"activity_title": activity_title},
                )

    return {"ok": True, "response": response}


@router.get("/mutual-matches")
async def list_mutual_matches(
    relationship_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List pending mutual matches for the current user (where they have not yet accepted/declined)."""
    want_repo = ActivityWantToTryRepository(db)
    matches = await want_repo.list_pending_mutual_matches_for_user(
        user_id=current_user.id,
        relationship_id=relationship_id,
    )
    discover_repo = DiscoverFeedRepository(db)
    out = []
    for m in matches:
        feed_item = await discover_repo.get_by_id(m.discover_feed_item_id)
        title = None
        card_snapshot = None
        if feed_item:
            title = (feed_item.card_snapshot or {}).get("title") if isinstance(feed_item.card_snapshot, dict) else None
            card_snapshot = feed_item.card_snapshot
        other_id = m.user_b_id if m.user_a_id == current_user.id else m.user_a_id
        out.append({
            "id": m.id,
            "relationship_id": m.relationship_id,
            "discover_feed_item_id": m.discover_feed_item_id,
            "activity_title": title,
            "card_snapshot": card_snapshot,
            "other_user_id": other_id,
            "created_at": m.created_at.isoformat() + "Z" if m.created_at else None,
        })
    return out
