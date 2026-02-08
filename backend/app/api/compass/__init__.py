"""Insider Compass API (user profiling: events, dyad insights, confirm/share, insight ingest)."""
from fastapi import APIRouter

from app.api.compass import (
    routes_events,
    routes_insights,
    routes_confirm,
    routes_insight_ingest,
    routes_context,
    routes_things_to_find_out,
)

router = APIRouter()

router.include_router(routes_events.router, prefix="/events", tags=["compass-events"])
router.include_router(routes_insights.router, prefix="/dyads", tags=["compass-insights"])
router.include_router(routes_context.router, prefix="/context", tags=["compass-context"])
router.include_router(routes_insight_ingest.router, prefix="/insights", tags=["compass-insights-ingest"])
router.include_router(routes_things_to_find_out.router, prefix="/things-to-find-out", tags=["compass-things-to-find-out"])
router.include_router(routes_confirm.router, tags=["compass-confirm"])
