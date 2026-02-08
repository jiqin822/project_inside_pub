"""Coach API routes."""
from fastapi import APIRouter

from app.api.coach import routes_sessions, routes_reports, routes_activities, routes_analyze_turn

router = APIRouter()

router.include_router(routes_sessions.router, prefix="/sessions", tags=["sessions"])
router.include_router(routes_reports.router, prefix="/sessions", tags=["reports"])
router.include_router(routes_activities.router, prefix="/activities", tags=["activities"])
router.include_router(routes_analyze_turn.router, tags=["live-coach"])