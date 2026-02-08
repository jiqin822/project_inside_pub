"""Admin API module."""
from fastapi import APIRouter
from . import auth, users, relationships, consent

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(relationships.router, prefix="/relationships", tags=["relationships"])
router.include_router(consent.router, prefix="/consent", tags=["consent"])
