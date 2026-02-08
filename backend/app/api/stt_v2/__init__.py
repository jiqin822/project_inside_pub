from fastapi import APIRouter

from app.api.stt_v2.routes_stt_v2 import router as stt_v2_router

router = APIRouter()
router.include_router(stt_v2_router, prefix="/stt-v2", tags=["stt-v2"])
