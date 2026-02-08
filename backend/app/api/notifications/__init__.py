"""Notifications API."""
from fastapi import APIRouter

from app.api.notifications import routes_notifications

router = APIRouter()

router.include_router(routes_notifications.router, prefix="/notifications", tags=["notifications"])
