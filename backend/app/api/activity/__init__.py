"""Activity API: invites, planned, history, memories, recommendations, vouchers, discover, want-to-try."""
from fastapi import APIRouter

from app.api.activity import routes_activities, routes_recommendations, routes_vouchers, routes_discover, routes_want_to_try

router = APIRouter()

router.include_router(routes_activities.router, tags=["activity"])
router.include_router(routes_recommendations.router, prefix="/recommendations", tags=["activity-recommendations"])
router.include_router(routes_vouchers.router, prefix="/vouchers", tags=["activity-vouchers"])
router.include_router(routes_discover.router, prefix="/discover", tags=["activity-discover"])
router.include_router(routes_want_to_try.router, prefix="/want-to-try", tags=["activity-want-to-try"])
