"""Love Map repository protocols."""
from typing import Protocol, Optional, List
from app.domain.love_map.models import (
    MapPrompt,
    UserSpec,
    RelationshipMapProgress,
)


class MapPromptRepository(Protocol):
    """Repository protocol for map prompts."""

    async def get_by_id(self, prompt_id: str) -> Optional[MapPrompt]:
        """Get prompt by ID."""
        ...

    async def get_all_active(self) -> List[MapPrompt]:
        """Get all active prompts."""
        ...

    async def get_by_tier(self, tier: int) -> List[MapPrompt]:
        """Get prompts by difficulty tier."""
        ...

    async def get_unanswered_by_user(self, user_id: str) -> List[MapPrompt]:
        """Get prompts that user hasn't answered yet."""
        ...


class UserSpecRepository(Protocol):
    """Repository protocol for user specs."""

    async def create_or_update(self, spec: UserSpec) -> UserSpec:
        """Create or update a user spec."""
        ...

    async def get_by_id(self, spec_id: str) -> Optional[UserSpec]:
        """Get spec by ID."""
        ...

    async def get_by_user_and_prompt(self, user_id: str, prompt_id: str) -> Optional[UserSpec]:
        """Get spec by user and prompt."""
        ...

    async def get_by_user(self, user_id: str) -> List[UserSpec]:
        """Get all specs for a user."""
        ...

    async def get_by_user_and_tier(self, user_id: str, tier: int) -> List[UserSpec]:
        """Get specs for a user by difficulty tier."""
        ...

    async def count_by_user_and_tier(self, user_id: str, tier: int) -> int:
        """Count specs for a user by tier."""
        ...


class RelationshipMapProgressRepository(Protocol):
    """Repository protocol for relationship map progress."""

    async def create_or_update(self, progress: RelationshipMapProgress) -> RelationshipMapProgress:
        """Create or update progress."""
        ...

    async def get_by_observer_and_subject(
        self, observer_id: str, subject_id: str
    ) -> Optional[RelationshipMapProgress]:
        """Get progress by observer and subject."""
        ...

    async def update_xp(self, observer_id: str, subject_id: str, xp_delta: int) -> RelationshipMapProgress:
        """Update XP for a relationship map."""
        ...

    async def update_stars(
        self, observer_id: str, subject_id: str, tier: int, stars: int
    ) -> RelationshipMapProgress:
        """Update star rating for a tier."""
        ...

    async def unlock_level(
        self, observer_id: str, subject_id: str, level_tier: int
    ) -> RelationshipMapProgress:
        """Unlock a level tier."""
        ...
