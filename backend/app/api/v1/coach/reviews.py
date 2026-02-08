"""Review job endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.domain.admin.entities import User
from app.domain.coach.services import ReviewJobService, AnalysisEngine
from app.domain.coach.repositories import ReviewJobRepository, ActivityRepository
from app.infra.db.repositories import ReviewJobRepositoryImpl, ActivityRepositoryImpl
from app.infra.vendors.llm import MockLLMAdapter

router = APIRouter()


class CreateReviewJobRequest(BaseModel):
    """Create review job request."""

    relationship_id: str
    job_type: str


class ReviewJobResponse(BaseModel):
    """Review job response."""

    id: str
    relationship_id: str
    job_type: str
    status: str
    result: dict | None = None
    error: str | None = None


@router.post("", response_model=ReviewJobResponse, status_code=status.HTTP_201_CREATED)
async def create_review_job(
    request: CreateReviewJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new review job."""
    job_repo: ReviewJobRepository = ReviewJobRepositoryImpl(db)
    activity_repo: ActivityRepository = ActivityRepositoryImpl(db)
    analysis_engine = AnalysisEngine(llm_adapter=MockLLMAdapter())
    review_service = ReviewJobService(job_repo, activity_repo, analysis_engine)

    job = await review_service.create_review_job(
        relationship_id=request.relationship_id, job_type=request.job_type
    )

    return ReviewJobResponse(
        id=job.id,
        relationship_id=job.relationship_id,
        job_type=job.job_type,
        status=job.status,
        result=job.result,
        error=job.error,
    )


@router.get("/{job_id}", response_model=ReviewJobResponse)
async def get_review_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get review job by ID."""
    job_repo: ReviewJobRepository = ReviewJobRepositoryImpl(db)
    activity_repo: ActivityRepository = ActivityRepositoryImpl(db)
    analysis_engine = AnalysisEngine(llm_adapter=MockLLMAdapter())
    review_service = ReviewJobService(job_repo, activity_repo, analysis_engine)

    job = await review_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return ReviewJobResponse(
        id=job.id,
        relationship_id=job.relationship_id,
        job_type=job.job_type,
        status=job.status,
        result=job.result,
        error=job.error,
    )
