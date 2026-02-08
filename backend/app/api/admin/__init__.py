"""Admin API routes."""
from fastapi import APIRouter

from app.api.admin import (
    routes_auth,
    routes_config,
    routes_users,
    routes_relationships,
    routes_history,
    routes_onboarding,
    routes_contacts,
    routes_consent,
    routes_devices,
)

router = APIRouter()

router.include_router(routes_auth.router, prefix="/auth", tags=["auth"])
router.include_router(routes_config.router, tags=["config"])
router.include_router(routes_users.router, prefix="/users", tags=["users"])
router.include_router(routes_relationships.router, prefix="/relationships", tags=["relationships"])
router.include_router(routes_history.router, prefix="/history", tags=["history"])
router.include_router(routes_onboarding.router, prefix="/onboarding", tags=["onboarding"])
router.include_router(routes_contacts.router, prefix="/contacts", tags=["contacts"])
router.include_router(routes_consent.router, prefix="/relationships", tags=["consent"])
router.include_router(routes_devices.router, prefix="/devices", tags=["devices"])