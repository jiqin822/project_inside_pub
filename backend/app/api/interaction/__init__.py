"""Interaction API routes."""
from fastapi import APIRouter

from app.api.interaction import routes_pokes, routes_ws

router = APIRouter()

router.include_router(routes_pokes.router, prefix="/interaction", tags=["pokes"])
router.include_router(routes_ws.router, prefix="/interaction", tags=["websocket"])
