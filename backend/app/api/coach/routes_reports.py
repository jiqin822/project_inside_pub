"""Session report routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.coach.models import SessionReport
from app.infra.db.repositories.session_repo import SessionReportRepositoryImpl

router = APIRouter()


class ReportResponse(BaseModel):
    """Report response model."""
    sid: str
    summary: str
    moments: list[dict]
    action_items: list[dict]


@router.get("/{session_id}/report", response_model=ReportResponse)
async def get_report(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get session report."""
    report_repo = SessionReportRepositoryImpl(db)
    report = await report_repo.get_by_session_id(session_id)

    if not report:
        # Return default pending report
        return ReportResponse(
            sid=session_id,
            summary="Session report pending",
            moments=[],
            action_items=[],
        )

    return ReportResponse(
        sid=report.session_id,
        summary=report.summary,
        moments=report.moments,
        action_items=report.action_items,
    )
