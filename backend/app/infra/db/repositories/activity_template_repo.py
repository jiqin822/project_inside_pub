"""Activity template repository."""
from typing import Optional, List, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.infra.db.models.compass import ActivityTemplateModel


class ActivityTemplateRepository:
    """Activity template repository."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_active(
        self,
        relationship_types: Optional[List[str]] = None,
        vibe_tags: Optional[List[str]] = None,
        age_min: Optional[int] = None,
        age_max: Optional[int] = None,
        limit: int = 100,
    ) -> List[ActivityTemplateModel]:
        """List active templates with optional filters.
        relationship_types: e.g. ['partner'], ['child'] - template must include at least one.
        vibe_tags: template must include at least one of these (if provided).
        age_min/age_max: for child/family - filter by age_range JSONB.
        """
        q = (
            select(ActivityTemplateModel)
            .where(ActivityTemplateModel.is_active.is_(True))
            .order_by(ActivityTemplateModel.title)
            .limit(limit * 2)
        )
        result = await self.session.execute(q)
        templates = list(result.scalars().all())
        if relationship_types:
            types_set = set(relationship_types)
            templates = [
                t for t in templates
                if t.relationship_types and (set(t.relationship_types) & types_set)
            ]
        if vibe_tags:
            tags_set = set(vibe_tags)
            templates = [
                t for t in templates
                if t.vibe_tags and (set(t.vibe_tags) & tags_set)
            ]
        if age_min is not None or age_max is not None:
            def age_ok(t: ActivityTemplateModel) -> bool:
                ar = t.age_range
                if ar is None:
                    return True
                t_min = ar.get("min")
                t_max = ar.get("max")
                if age_min is not None and t_max is not None and age_min > t_max:
                    return False
                if age_max is not None and t_min is not None and age_max < t_min:
                    return False
                return True
            templates = [t for t in templates if age_ok(t)]
        return templates[:limit]

    async def get(self, activity_id: str) -> Optional[ActivityTemplateModel]:
        """Get a template by ID."""
        result = await self.session.execute(
            select(ActivityTemplateModel).where(
                ActivityTemplateModel.activity_id == activity_id
            )
        )
        return result.scalars().first()

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
    ) -> ActivityTemplateModel:
        """Create a template (e.g. from LLM-generated activity)."""
        model = ActivityTemplateModel(
            activity_id=activity_id,
            title=title,
            relationship_types=relationship_types or ["partner"],
            vibe_tags=vibe_tags or ["fun"],
            constraints=constraints or {},
            steps_markdown_template=steps_markdown_template or "",
            personalization_slots=personalization_slots or {},
            is_active=is_active,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model
