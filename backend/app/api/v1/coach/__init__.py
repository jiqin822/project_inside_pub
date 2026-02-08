"""Coach API module."""
from fastapi import APIRouter
from . import activities, reviews

router = APIRouter()

router.include_router(activities.router, prefix="/activities", tags=["activities"])
router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
