"""Discover feed API: feed list and dismiss."""
import logging
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.relationship import relationship_members
from app.infra.db.repositories.discover_feed_repo import DiscoverFeedRepository

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


@router.get("/feed")
async def get_discover_feed(
    relationship_id: str = Query(..., description="Relationship for which to fetch discover feed"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the Discover feed for the current user and relationship.
    Returns activity cards where the user is either the "generated for" user or the recommended invitee.
    Excludes items the user has dismissed. Deduped by activity_template_id (newest kept).
    """
    await _ensure_member(db, relationship_id, current_user.id)
    repo = DiscoverFeedRepository(db)
    items = await repo.list_feed_for_user(
        user_id=current_user.id,
        relationship_id=relationship_id,
        limit=limit,
    )
    # Return list of activity cards (from card_snapshot, or build minimal from template fields)
    cards: List[dict] = []
    for item in items:
        if item.card_snapshot and isinstance(item.card_snapshot, dict):
            card = dict(item.card_snapshot)
            card["_discover_feed_item_id"] = item.id
            card["id"] = card.get("id") or item.activity_template_id
            # Old feed items may not have debug_source; mark as backend so UI does not show "Client fallback"
            if "debug_source" not in card or card.get("debug_source") is None:
                card["debug_source"] = "backend"
            cards.append(card)
        else:
            cards.append({
                "id": item.activity_template_id,
                "_discover_feed_item_id": item.id,
                "title": "Activity",
                "description": "",
                "vibe_tags": [],
                "relationship_types": [],
                "constraints": {},
                "explanation": None,
                "recommended_invitee": None,
                "recommended_location": None,
                "debug_source": "backend",
            })
    return cards


class DismissRequest(BaseModel):
    relationship_id: str
    discover_feed_item_id: str


@router.post("/dismiss")
async def dismiss_discover_item(
    request: DismissRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record that the current user dismissed this discover feed item (e.g. swipe-left). It will no longer appear in their feed."""
    await _ensure_member(db, request.relationship_id, current_user.id)
    repo = DiscoverFeedRepository(db)
    await repo.dismiss(
        user_id=current_user.id,
        relationship_id=request.relationship_id,
        discover_feed_item_id=request.discover_feed_item_id,
    )
    return {"ok": True}
