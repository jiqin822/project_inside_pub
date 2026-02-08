"""Market API routes."""
from fastapi import APIRouter

from app.api.market import routes_market

router = APIRouter()

router.include_router(routes_market.router, prefix="/market", tags=["market"])
