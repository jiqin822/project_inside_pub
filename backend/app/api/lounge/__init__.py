"""Lounge API: group chat rooms with Kai agent."""
from fastapi import APIRouter

from app.api.lounge import routes_lounge

router = APIRouter()
router.include_router(routes_lounge.router)
