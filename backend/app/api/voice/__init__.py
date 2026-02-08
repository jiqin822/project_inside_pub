"""Voice API module."""
from fastapi import APIRouter
from . import routes_voice

router = APIRouter()

router.include_router(routes_voice.router, prefix="/voice", tags=["voice"])
