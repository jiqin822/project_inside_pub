"""Interaction API module."""
from fastapi import APIRouter
from . import websocket, pokes

router = APIRouter()

router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
router.include_router(pokes.router, prefix="/pokes", tags=["pokes"])
