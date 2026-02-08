"""Insider Compass repository protocols (for dependency injection)."""
from typing import Optional, List, Protocol
from datetime import datetime


class EventRepositoryProtocol(Protocol):
    """Event repository protocol."""

    async def append(
        self,
        type: str,
        actor_user_id: str,
        payload: dict,
        source: str,
        relationship_id: Optional[str] = None,
        privacy_scope: str = "private",
    ):
        ...

    async def list_by_actor(
        self,
        actor_user_id: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List:
        ...

    async def list_by_relationship(
        self,
        relationship_id: str,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List:
        ...


class MemoryRepositoryProtocol(Protocol):
    """Memory repository protocol."""

    async def create(
        self,
        owner_user_id: str,
        memory_type: str,
        canonical_key: str,
        value_json: dict,
        relationship_id: Optional[str] = None,
        visibility: str = "private",
        confidence: float = 0.5,
        status: str = "hypothesis",
        evidence_event_ids: Optional[list] = None,
    ):
        ...

    async def get(self, memory_id: str):
        ...

    async def list_by_owner(
        self,
        owner_user_id: str,
        relationship_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List:
        ...

    async def update_status(self, memory_id: str, status: str) -> bool:
        ...

    async def update_visibility(self, memory_id: str, visibility: str) -> bool:
        ...


class PersonPortraitRepositoryProtocol(Protocol):
    """Person portrait repository protocol."""

    async def upsert(
        self,
        owner_user_id: str,
        portrait_text: Optional[str] = None,
        portrait_facets_json: Optional[dict] = None,
        relationship_id: Optional[str] = None,
        visibility: str = "private",
        evidence_event_ids: Optional[list] = None,
        confidence: float = 0.5,
    ):
        ...

    async def get_by_owner(
        self,
        owner_user_id: str,
        relationship_id: Optional[str] = None,
    ):
        ...


class DyadPortraitRepositoryProtocol(Protocol):
    """Dyad portrait repository protocol."""

    async def upsert(
        self,
        relationship_id: str,
        portrait_text: Optional[str] = None,
        facets_json: Optional[dict] = None,
        evidence_event_ids: Optional[list] = None,
        confidence: float = 0.5,
    ):
        ...

    async def get_by_relationship(self, relationship_id: str):
        ...


class LoopRepositoryProtocol(Protocol):
    """Relationship loop repository protocol."""

    async def create(
        self,
        relationship_id: str,
        name: str,
        trigger_signals_json: Optional[dict] = None,
        meanings_json: Optional[dict] = None,
        patterns_by_person_json: Optional[dict] = None,
        heat_signature_json: Optional[dict] = None,
        repair_attempts_json: Optional[dict] = None,
        recommended_interruptions_json: Optional[dict] = None,
        confidence: float = 0.5,
        status: str = "hypothesis",
        evidence_event_ids: Optional[list] = None,
    ):
        ...

    async def get(self, loop_id: str):
        ...

    async def list_by_relationship(
        self,
        relationship_id: str,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List:
        ...

    async def update_status(self, loop_id: str, status: str) -> bool:
        ...


class ActivityTemplateRepositoryProtocol(Protocol):
    """Activity template repository protocol."""

    async def list_active(
        self,
        relationship_types: Optional[List[str]] = None,
        vibe_tags: Optional[List[str]] = None,
        age_min: Optional[int] = None,
        age_max: Optional[int] = None,
        limit: int = 100,
    ) -> List:
        ...

    async def get(self, activity_id: str):
        ...

    async def create(
        self,
        activity_id: str,
        title: str,
        *,
        relationship_types: Optional[List[str]] = None,
        vibe_tags: Optional[List[str]] = None,
        constraints: Optional[dict] = None,
        steps_markdown_template: Optional[str] = None,
        personalization_slots: Optional[dict] = None,
        is_active: bool = True,
    ):
        ...


class DyadActivityHistoryRepositoryProtocol(Protocol):
    """Dyad activity history repository protocol."""

    async def append(
        self,
        relationship_id: str,
        activity_template_id: str,
        actor_user_id: str,
        started_at: datetime,
        completed_at: Optional[datetime] = None,
        rating: Optional[float] = None,
        outcome_tags: Optional[list] = None,
    ):
        ...

    async def list_by_relationship(
        self,
        relationship_id: str,
        limit: int = 100,
    ) -> List:
        ...
