from fastapi import APIRouter

from app.api.stt.routes_stt import router as stt_router

router = APIRouter()
router.include_router(stt_router, prefix="/stt", tags=["stt"])
