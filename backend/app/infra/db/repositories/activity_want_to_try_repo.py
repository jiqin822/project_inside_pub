"""Activity want-to-try and mutual match repository."""
from datetime import datetime
from typing import Optional, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.infra.db.models.compass import (
    ActivityWantToTryModel,
    ActivityMutualMatchModel,
    DiscoverFeedItemModel,
)
from app.domain.common.types import generate_id


class ActivityWantToTryRepository:
    """Want-to-try and mutual match records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_want_to_try(
        self,
        user_id: str,
        relationship_id: str,
        discover_feed_item_id: str,
    ) -> ActivityWantToTryModel:
        """Record that user wants to try this discover feed item."""
        record_id = generate_id()
        model = ActivityWantToTryModel(
            id=record_id,
            user_id=user_id,
            relationship_id=relationship_id,
            discover_feed_item_id=discover_feed_item_id,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_other_want_to_try_for_feed_item(
        self,
        discover_feed_item_id: str,
        exclude_user_id: str,
    ) -> Optional[ActivityWantToTryModel]:
        """Get another user's want-to-try for the same feed item (for mutual match)."""
        result = await self.session.execute(
            select(ActivityWantToTryModel).where(
                and_(
                    ActivityWantToTryModel.discover_feed_item_id == discover_feed_item_id,
                    ActivityWantToTryModel.user_id != exclude_user_id,
                )
            ).order_by(ActivityWantToTryModel.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def create_mutual_match(
        self,
        relationship_id: str,
        discover_feed_item_id: str,
        user_a_id: str,
        user_b_id: str,
    ) -> ActivityMutualMatchModel:
        """Create a mutual match record (both users want to try)."""
        match_id = generate_id()
        model = ActivityMutualMatchModel(
            id=match_id,
            relationship_id=relationship_id,
            discover_feed_item_id=discover_feed_item_id,
            user_a_id=user_a_id,
            user_b_id=user_b_id,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def get_mutual_match_by_id(self, match_id: str) -> Optional[ActivityMutualMatchModel]:
        """Get mutual match by id."""
        result = await self.session.execute(
            select(ActivityMutualMatchModel).where(ActivityMutualMatchModel.id == match_id)
        )
        return result.scalar_one_or_none()

    async def list_pending_mutual_matches_for_user(
        self,
        user_id: str,
        relationship_id: Optional[str] = None,
    ) -> List[ActivityMutualMatchModel]:
        """List mutual matches where user has not yet responded (pending)."""
        q = (
            select(ActivityMutualMatchModel)
            .where(
                or_(
                    ActivityMutualMatchModel.user_a_id == user_id,
                    ActivityMutualMatchModel.user_b_id == user_id,
                )
            )
            .where(
                or_(
                    and_(
                        ActivityMutualMatchModel.user_a_id == user_id,
                        ActivityMutualMatchModel.user_a_response == "pending",
                    ),
                    and_(
                        ActivityMutualMatchModel.user_b_id == user_id,
                        ActivityMutualMatchModel.user_b_response == "pending",
                    ),
                )
            )
            .order_by(ActivityMutualMatchModel.created_at.desc())
        )
        if relationship_id:
            q = q.where(ActivityMutualMatchModel.relationship_id == relationship_id)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def respond_to_mutual_match(
        self,
        match_id: str,
        user_id: str,
        response: str,  # "accept" | "decline"
    ) -> Optional[ActivityMutualMatchModel]:
        """Set user's response on a mutual match. Returns updated model or None if not found/not pending."""
        match = await self.get_mutual_match_by_id(match_id)
        if not match:
            return None
        if match.user_a_id == user_id:
            if match.user_a_response != "pending":
                return match
            match.user_a_response = response
        elif match.user_b_id == user_id:
            if match.user_b_response != "pending":
                return match
            match.user_b_response = response
        else:
            return None
        if response == "decline":
            match.resolved_at = datetime.utcnow()
        elif match.user_a_response in ("accept", "decline") and match.user_b_response in ("accept", "decline"):
            if match.user_a_response == "accept" and match.user_b_response == "accept":
                match.resolved_at = datetime.utcnow()
            else:
                match.resolved_at = datetime.utcnow()
        self.session.add(match)
        await self.session.commit()
        await self.session.refresh(match)
        return match

    async def both_accepted(self, match: ActivityMutualMatchModel) -> bool:
        """Return True if both users have accepted."""
        return (
            getattr(match, "user_a_response", None) == "accept"
            and getattr(match, "user_b_response", None) == "accept"
        )
