"""Love Map repository implementation."""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.domain.love_map.models import (
    MapPrompt,
    UserSpec,
    RelationshipMapProgress,
)
from app.domain.love_map.repositories import (
    MapPromptRepository,
    UserSpecRepository,
    RelationshipMapProgressRepository,
)
from app.infra.db.models.love_map import (
    MapPromptModel,
    UserSpecModel,
    RelationshipMapProgressModel,
)
from app.domain.common.types import generate_id


class MapPromptRepositoryImpl(MapPromptRepository):
    """Map prompt repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, prompt_id: str) -> Optional[MapPrompt]:
        """Get prompt by ID."""
        result = await self.session.execute(
            select(MapPromptModel).where(MapPromptModel.id == prompt_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return MapPrompt(
            id=model.id,
            category=model.category,
            difficulty_tier=model.difficulty_tier,
            question_template=model.question_template,
            input_prompt=model.input_prompt,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_all_active(self) -> List[MapPrompt]:
        """Get all active prompts."""
        result = await self.session.execute(
            select(MapPromptModel).where(MapPromptModel.is_active == True)
        )
        models = result.scalars().all()
        return [
            MapPrompt(
                id=m.id,
                category=m.category,
                difficulty_tier=m.difficulty_tier,
                question_template=m.question_template,
                input_prompt=m.input_prompt,
                is_active=m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]

    async def get_by_tier(self, tier: int) -> List[MapPrompt]:
        """Get prompts by difficulty tier."""
        result = await self.session.execute(
            select(MapPromptModel).where(
                and_(MapPromptModel.difficulty_tier == tier, MapPromptModel.is_active == True)
            )
        )
        models = result.scalars().all()
        return [
            MapPrompt(
                id=m.id,
                category=m.category,
                difficulty_tier=m.difficulty_tier,
                question_template=m.question_template,
                input_prompt=m.input_prompt,
                is_active=m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]

    async def get_unanswered_by_user(self, user_id: str) -> List[MapPrompt]:
        """Get prompts that user hasn't answered yet."""
        # Subquery to get answered prompt IDs
        answered_subquery = select(UserSpecModel.prompt_id).where(
            UserSpecModel.user_id == user_id
        )
        
        # Get all active prompts that are not in answered list
        result = await self.session.execute(
            select(MapPromptModel).where(
                and_(
                    MapPromptModel.is_active == True,
                    ~MapPromptModel.id.in_(answered_subquery)
                )
            )
        )
        models = result.scalars().all()
        return [
            MapPrompt(
                id=m.id,
                category=m.category,
                difficulty_tier=m.difficulty_tier,
                question_template=m.question_template,
                input_prompt=m.input_prompt,
                is_active=m.is_active,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]


class UserSpecRepositoryImpl(UserSpecRepository):
    """User spec repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_update(self, spec: UserSpec) -> UserSpec:
        """Create or update a user spec."""
        # Check if spec already exists
        existing = await self.get_by_user_and_prompt(spec.user_id, spec.prompt_id)
        
        if existing:
            # Update existing
            from datetime import datetime
            from sqlalchemy import update
            await self.session.execute(
                update(UserSpecModel)
                .where(UserSpecModel.id == existing.id)
                .values(
                    answer_text=spec.answer_text,
                    last_updated=datetime.utcnow(),
                )
            )
            await self.session.commit()
            return await self.get_by_id(existing.id)
        else:
            # Create new
            model = UserSpecModel(
                id=spec.id if hasattr(spec, 'id') and spec.id else generate_id(),
                user_id=spec.user_id,
                prompt_id=spec.prompt_id,
                answer_text=spec.answer_text,
                last_updated=spec.last_updated,
            )
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)
            return UserSpec(
                id=model.id,
                user_id=model.user_id,
                prompt_id=model.prompt_id,
                answer_text=model.answer_text,
                last_updated=model.last_updated,
                embedding=None,
            )

    async def get_by_id(self, spec_id: str) -> Optional[UserSpec]:
        """Get spec by ID."""
        result = await self.session.execute(
            select(UserSpecModel).where(UserSpecModel.id == spec_id)
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return UserSpec(
            id=model.id,
            user_id=model.user_id,
            prompt_id=model.prompt_id,
            answer_text=model.answer_text,
            last_updated=model.last_updated,
            embedding=None,  # TODO: Add embedding support if needed
        )

    async def get_by_user_and_prompt(self, user_id: str, prompt_id: str) -> Optional[UserSpec]:
        """Get spec by user and prompt."""
        result = await self.session.execute(
            select(UserSpecModel).where(
                and_(
                    UserSpecModel.user_id == user_id,
                    UserSpecModel.prompt_id == prompt_id
                )
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return UserSpec(
            id=model.id,
            user_id=model.user_id,
            prompt_id=model.prompt_id,
            answer_text=model.answer_text,
            last_updated=model.last_updated,
            embedding=None,
        )

    async def get_by_user(self, user_id: str) -> List[UserSpec]:
        """Get all specs for a user."""
        result = await self.session.execute(
            select(UserSpecModel).where(UserSpecModel.user_id == user_id)
        )
        models = result.scalars().all()
        return [
            UserSpec(
                id=m.id,
                user_id=m.user_id,
                prompt_id=m.prompt_id,
                answer_text=m.answer_text,
                last_updated=m.last_updated,
                embedding=None,
            )
            for m in models
        ]

    async def get_by_user_and_tier(self, user_id: str, tier: int) -> List[UserSpec]:
        """Get specs for a user by difficulty tier."""
        result = await self.session.execute(
            select(UserSpecModel)
            .join(MapPromptModel, UserSpecModel.prompt_id == MapPromptModel.id)
            .where(
                and_(
                    UserSpecModel.user_id == user_id,
                    MapPromptModel.difficulty_tier == tier
                )
            )
        )
        models = result.scalars().all()
        return [
            UserSpec(
                id=m.id,
                user_id=m.user_id,
                prompt_id=m.prompt_id,
                answer_text=m.answer_text,
                last_updated=m.last_updated,
                embedding=None,
            )
            for m in models
        ]

    async def count_by_user_and_tier(self, user_id: str, tier: int) -> int:
        """Count specs for a user by tier."""
        result = await self.session.execute(
            select(func.count(UserSpecModel.id))
            .join(MapPromptModel, UserSpecModel.prompt_id == MapPromptModel.id)
            .where(
                and_(
                    UserSpecModel.user_id == user_id,
                    MapPromptModel.difficulty_tier == tier
                )
            )
        )
        return result.scalar() or 0


class RelationshipMapProgressRepositoryImpl(RelationshipMapProgressRepository):
    """Relationship map progress repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_update(self, progress: RelationshipMapProgress) -> RelationshipMapProgress:
        """Create or update progress."""
        existing = await self.get_by_observer_and_subject(
            progress.observer_id, progress.subject_id
        )
        
        if existing:
            # Update existing
            from datetime import datetime
            from sqlalchemy import update
            await self.session.execute(
                update(RelationshipMapProgressModel)
                .where(RelationshipMapProgressModel.id == existing.id)
                .values(
                    level_tier=progress.level_tier,
                    current_xp=progress.current_xp,
                    stars=progress.stars,
                    updated_at=datetime.utcnow(),
                )
            )
            await self.session.commit()
            return await self.get_by_observer_and_subject(progress.observer_id, progress.subject_id)
        else:
            # Create new
            model = RelationshipMapProgressModel(
                id=progress.id if hasattr(progress, 'id') and progress.id else generate_id(),
                observer_id=progress.observer_id,
                subject_id=progress.subject_id,
                level_tier=progress.level_tier,
                current_xp=progress.current_xp,
                stars=progress.stars,
            )
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)
            return RelationshipMapProgress(
                id=model.id,
                observer_id=model.observer_id,
                subject_id=model.subject_id,
                level_tier=model.level_tier,
                current_xp=model.current_xp,
                stars=model.stars or {},
                created_at=model.created_at,
                updated_at=model.updated_at,
            )

    async def get_by_observer_and_subject(
        self, observer_id: str, subject_id: str
    ) -> Optional[RelationshipMapProgress]:
        """Get progress by observer and subject."""
        result = await self.session.execute(
            select(RelationshipMapProgressModel).where(
                and_(
                    RelationshipMapProgressModel.observer_id == observer_id,
                    RelationshipMapProgressModel.subject_id == subject_id
                )
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return RelationshipMapProgress(
            id=model.id,
            observer_id=model.observer_id,
            subject_id=model.subject_id,
            level_tier=model.level_tier,
            current_xp=model.current_xp,
            stars=model.stars or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def update_xp(self, observer_id: str, subject_id: str, xp_delta: int) -> RelationshipMapProgress:
        """Update XP for a relationship map."""
        progress = await self.get_by_observer_and_subject(observer_id, subject_id)
        if not progress:
            # Create new progress record
            from datetime import datetime
            progress = RelationshipMapProgress(
                id=generate_id(),
                observer_id=observer_id,
                subject_id=subject_id,
                level_tier=1,
                current_xp=xp_delta,
                stars={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        else:
            progress.current_xp += xp_delta
        return await self.create_or_update(progress)

    async def update_stars(
        self, observer_id: str, subject_id: str, tier: int, stars: int
    ) -> RelationshipMapProgress:
        """Update star rating for a tier."""
        progress = await self.get_by_observer_and_subject(observer_id, subject_id)
        if not progress:
            from datetime import datetime
            progress = RelationshipMapProgress(
                id=generate_id(),
                observer_id=observer_id,
                subject_id=subject_id,
                level_tier=1,
                current_xp=0,
                stars={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        
        if not progress.stars:
            progress.stars = {}
        progress.stars[f'tier_{tier}'] = stars
        return await self.create_or_update(progress)

    async def unlock_level(
        self, observer_id: str, subject_id: str, level_tier: int
    ) -> RelationshipMapProgress:
        """Unlock a level tier."""
        progress = await self.get_by_observer_and_subject(observer_id, subject_id)
        if not progress:
            from datetime import datetime
            progress = RelationshipMapProgress(
                id=generate_id(),
                observer_id=observer_id,
                subject_id=subject_id,
                level_tier=level_tier,
                current_xp=0,
                stars={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        else:
            progress.level_tier = max(progress.level_tier, level_tier)
        return await self.create_or_update(progress)
