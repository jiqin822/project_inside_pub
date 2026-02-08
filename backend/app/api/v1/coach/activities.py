"""Activity endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.domain.admin.entities import User
from app.domain.coach.services import ActivityService, AnalysisEngine
from app.domain.coach.repositories import ActivityRepository
from app.infra.db.repositories import ActivityRepositoryImpl
from app.infra.vendors.llm import MockLLMAdapter

router = APIRouter()


class CreateActivityRequest(BaseModel):
    """Create activity request."""

    relationship_id: str
    activity_type: str
    content: str | None = None
    metadata: dict = {}


class ActivityResponse(BaseModel):
    """Activity response."""

    id: str
    relationship_id: str
    activity_type: str
    content: str | None
    metadata: dict


@router.post("", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    request: CreateActivityRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new activity."""
    activity_repo: ActivityRepository = ActivityRepositoryImpl(db)
    analysis_engine = AnalysisEngine(llm_adapter=MockLLMAdapter())
    activity_service = ActivityService(activity_repo, analysis_engine)

    activity = await activity_service.create_activity(
        relationship_id=request.relationship_id,
        activity_type=request.activity_type,
        content=request.content,
        metadata=request.metadata,
    )

    return ActivityResponse(
        id=activity.id,
        relationship_id=activity.relationship_id,
        activity_type=activity.activity_type,
        content=activity.content,
        metadata=activity.metadata,
    )


@router.get("/relationship/{relationship_id}", response_model=list[ActivityResponse])
async def list_activities(
    relationship_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List activities for a relationship."""
    activity_repo: ActivityRepository = ActivityRepositoryImpl(db)
    analysis_engine = AnalysisEngine(llm_adapter=MockLLMAdapter())
    activity_service = ActivityService(activity_repo, analysis_engine)

    activities = await activity_service.list_relationship_activities(relationship_id)
    return [
        ActivityResponse(
            id=a.id,
            relationship_id=a.relationship_id,
            activity_type=a.activity_type,
            content=a.content,
            metadata=a.metadata,
        )
        for a in activities
    ]
