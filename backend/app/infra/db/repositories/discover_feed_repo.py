"""Discover feed and dismissals repository."""
from datetime import datetime
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_

from app.infra.db.models.compass import DiscoverFeedItemModel, DiscoverDismissalModel
from app.domain.common.types import generate_id


class DiscoverFeedRepository:
    """Discover feed items and dismissals."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_feed_item(
        self,
        relationship_id: str,
        activity_template_id: str,
        generated_by_user_id: str,
        recommended_invitee_user_id: str,
        card_snapshot: Optional[dict] = None,
    ) -> DiscoverFeedItemModel:
        """Insert a discover feed item (card shown to both generator and recommended invitee)."""
        item_id = generate_id()
        model = DiscoverFeedItemModel(
            id=item_id,
            relationship_id=relationship_id,
            activity_template_id=activity_template_id,
            card_snapshot=card_snapshot,
            generated_by_user_id=generated_by_user_id,
            recommended_invitee_user_id=recommended_invitee_user_id,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def list_feed_for_user(
        self,
        user_id: str,
        relationship_id: str,
        limit: int = 50,
    ) -> List[DiscoverFeedItemModel]:
        """
        List discover feed items for the user: relationship_id matches and user is either
        generated_by_user_id or recommended_invitee_user_id. Exclude items the user has dismissed.
        Dedupe by activity_template_id (keep newest row per activity).
        """
        # Subquery: feed item ids this user has dismissed
        dismissed_ids = (
            select(DiscoverDismissalModel.discover_feed_item_id).where(
                and_(
                    DiscoverDismissalModel.user_id == user_id,
                    DiscoverDismissalModel.relationship_id == relationship_id,
                )
            )
        )
        # All feed items for this relationship where user is generator or invitee, not dismissed
        base = (
            select(DiscoverFeedItemModel)
            .where(
                and_(
                    DiscoverFeedItemModel.relationship_id == relationship_id,
                    or_(
                        DiscoverFeedItemModel.generated_by_user_id == user_id,
                        DiscoverFeedItemModel.recommended_invitee_user_id == user_id,
                    ),
                    ~DiscoverFeedItemModel.id.in_(dismissed_ids),
                )
            )
            .order_by(DiscoverFeedItemModel.created_at.desc())
        )
        result = await self.session.execute(base)
        rows = list(result.scalars().all())
        # Dedupe by activity_template_id: keep first (newest) occurrence
        seen = set()
        deduped = []
        for r in rows:
            if r.activity_template_id not in seen:
                seen.add(r.activity_template_id)
                deduped.append(r)
            if len(deduped) >= limit:
                break
        return deduped

    async def dismiss(self, user_id: str, relationship_id: str, discover_feed_item_id: str) -> None:
        """Record that the user dismissed this feed item."""
        result = await self.session.execute(
            select(DiscoverFeedItemModel).where(
                and_(
                    DiscoverFeedItemModel.id == discover_feed_item_id,
                    DiscoverFeedItemModel.relationship_id == relationship_id,
                    or_(
                        DiscoverFeedItemModel.generated_by_user_id == user_id,
                        DiscoverFeedItemModel.recommended_invitee_user_id == user_id,
                    ),
                )
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            return
        dismissal_id = generate_id()
        model = DiscoverDismissalModel(
            id=dismissal_id,
            user_id=user_id,
            relationship_id=relationship_id,
            discover_feed_item_id=discover_feed_item_id,
        )
        self.session.add(model)
        await self.session.commit()

    async def get_by_id(self, discover_feed_item_id: str) -> Optional[DiscoverFeedItemModel]:
        """Get a single discover feed item by id."""
        result = await self.session.execute(
            select(DiscoverFeedItemModel).where(DiscoverFeedItemModel.id == discover_feed_item_id)
        )
        return result.scalar_one_or_none()
