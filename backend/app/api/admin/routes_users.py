"""User routes."""
import re
from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.infra.db.repositories.user_repo import UserRepositoryImpl
from app.infra.db.repositories.voice_repo import VoiceRepository
from app.infra.db.models.relationship import relationship_members

router = APIRouter()


class UserMeResponse(BaseModel):
    """User me response model."""
    id: str
    email: str
    display_name: str | None
    pronouns: str | None = None
    personality_type: dict | None = None  # MBTI data: {"type": "INTJ", "values": {"ei": 25, "sn": 75, "tf": 50, "jp": 50}} or {"type": "Prefer not to say"}
    communication_style: str | None = None
    goals: list[str] | None = None
    personal_description: str | None = None
    hobbies: list[str] | None = None
    birthday: str | None = None  # ISO date YYYY-MM-DD
    occupation: str | None = None
    privacy_tier: str | None = None
    profile_picture_url: str | None = None
    voice_profile_id: str | None = None  # Set when user has completed voice enrollment
    voice_print_data: str | None = None  # Base64-encoded WAV for Live Coach identification


class UpdateProfileRequest(BaseModel):
    """Update profile request."""
    display_name: Optional[str] = None
    pronouns: Optional[str] = None
    personality_type: Optional[dict] = None  # MBTI data: {"type": "INTJ", "values": {"ei": 25, "sn": 75, "tf": 50, "jp": 50}} or {"type": "Prefer not to say"}
    communication_style: Optional[str] = None
    goals: Optional[list[str]] = None
    personal_description: Optional[str] = None
    hobbies: Optional[list[str]] = None
    birthday: Optional[str] = None  # ISO date YYYY-MM-DD
    occupation: Optional[str] = None
    privacy_tier: Optional[str] = None
    profile_picture_url: Optional[str] = None  # Base64 data URL or image URL


class UserInfoResponse(BaseModel):
    """User info response model (for relationship members)."""
    id: str
    email: str
    display_name: str | None
    profile_picture_url: str | None = None
    voice_profile_id: str | None = None


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user."""
    user_repo = UserRepositoryImpl(db)
    voice_repo = VoiceRepository(db)
    user = await user_repo.get_by_id(current_user.id)

    voice_profile_id: str | None = None
    voice_print_data: str | None = None
    voice_profile = await voice_repo.get_profile(current_user.id)
    if voice_profile:
        voice_profile_id = voice_profile.id
        voice_print_data = getattr(voice_profile, "voice_sample_base64", None)

    if not user:
        return UserMeResponse(
            id=current_user.id,
            email=current_user.email,
            display_name=current_user.display_name,
            voice_profile_id=voice_profile_id,
            voice_print_data=voice_print_data,
        )

    # Map communication_style float to string
    comm_style = None
    if user.communication_style is not None:
        if user.communication_style < 0.33:
            comm_style = "GENTLE"
        elif user.communication_style > 0.67:
            comm_style = "DIRECT"
        else:
            comm_style = "BALANCED"

    birthday_str = None
    if getattr(user, "birthday", None) is not None:
        b = getattr(user, "birthday")
        birthday_str = b.isoformat() if hasattr(b, "isoformat") else str(b)
    response = UserMeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        pronouns=user.pronouns,
        personality_type=getattr(user, "personality_type", None),
        communication_style=comm_style,
        goals=user.goals if user.goals else None,
        personal_description=getattr(user, "personal_description", None),
        hobbies=user.hobbies if getattr(user, "hobbies", None) else None,
        birthday=birthday_str,
        occupation=getattr(user, "occupation", None),
        privacy_tier=user.privacy_tier,
        profile_picture_url=getattr(user, "profile_picture_url", None),
        voice_profile_id=voice_profile_id,
        voice_print_data=voice_print_data,
    )
    return response


@router.patch("/me", response_model=UserMeResponse)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile."""
    user_repo = UserRepositoryImpl(db)
    voice_repo = VoiceRepository(db)

    # Map communication_style string to float
    comm_style_float = None
    if request.communication_style:
        if request.communication_style == "GENTLE":
            comm_style_float = 0.0
        elif request.communication_style == "DIRECT":
            comm_style_float = 1.0
        elif request.communication_style == "BALANCED":
            comm_style_float = 0.5
    
    birthday_date = None
    if request.birthday is not None:
        try:
            birthday_date = date_type.fromisoformat(request.birthday)
        except (ValueError, TypeError):
            pass
    user = await user_repo.update_profile_fields(
        user_id=current_user.id,
        display_name=request.display_name,
        pronouns=request.pronouns,
        personality_type=request.personality_type,
        communication_style=comm_style_float,
        goals=request.goals,
        personal_description=request.personal_description,
        hobbies=request.hobbies,
        birthday=birthday_date,
        occupation=request.occupation,
        privacy_tier=request.privacy_tier,
        profile_picture_url=request.profile_picture_url,
    )
    
    # Map back for response
    comm_style = None
    if user.communication_style is not None:
        if user.communication_style < 0.33:
            comm_style = "GENTLE"
        elif user.communication_style > 0.67:
            comm_style = "DIRECT"
        else:
            comm_style = "BALANCED"

    voice_profile_id = None
    voice_print_data = None
    voice_profile = await voice_repo.get_profile(current_user.id)
    if voice_profile:
        voice_profile_id = voice_profile.id
        voice_print_data = getattr(voice_profile, "voice_sample_base64", None)

    birthday_str = None
    if getattr(user, "birthday", None) is not None:
        b = getattr(user, "birthday")
        birthday_str = b.isoformat() if hasattr(b, "isoformat") else str(b)
    return UserMeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        pronouns=user.pronouns,
        personality_type=getattr(user, 'personality_type', None),
        communication_style=comm_style,
        goals=user.goals if user.goals else None,
        personal_description=getattr(user, "personal_description", None),
        hobbies=user.hobbies if getattr(user, "hobbies", None) else None,
        birthday=birthday_str,
        occupation=getattr(user, "occupation", None),
        privacy_tier=user.privacy_tier,
        profile_picture_url=getattr(user, 'profile_picture_url', None),
        voice_profile_id=voice_profile_id,
        voice_print_data=voice_print_data,
    )


@router.get("/{user_id}", response_model=UserInfoResponse)
async def get_user_by_id(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user by ID. Only allowed if user is in a relationship with current user."""
    # Allow users to view their own profile
    if user_id == current_user.id:
        user_repo = UserRepositoryImpl(db)
        voice_repo = VoiceRepository(db)
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        voice_profile_id = None
        voice_profile = await voice_repo.get_profile(user_id)
        if voice_profile:
            voice_profile_id = voice_profile.id
        raw = (user.display_name or "").strip() or (user.email.split("@")[0] if user.email else None)
        if raw and re.match(r"^User\s+[a-f0-9]{8}$", raw, re.I):
            raw = (user.email.split("@")[0] if user.email else None) or "Partner"
        display_name = raw
        return UserInfoResponse(
            id=user.id,
            email=user.email,
            display_name=display_name,
            profile_picture_url=getattr(user, 'profile_picture_url', None),
            voice_profile_id=voice_profile_id,
        )
    
    # Check if the requested user is in a relationship with the current user
    # Get all relationships where current user is a member
    current_user_relationships = await db.execute(
        select(relationship_members.c.relationship_id).where(
            relationship_members.c.user_id == current_user.id
        )
    )
    relationship_ids = [row[0] for row in current_user_relationships.all()]
    
    if not relationship_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view users who are in relationships with you"
        )
    
    # Check if the requested user is in any of these relationships
    target_user_in_relationship = await db.execute(
        select(relationship_members.c.user_id).where(
            relationship_members.c.relationship_id.in_(relationship_ids),
            relationship_members.c.user_id == user_id
        )
    )
    
    if not target_user_in_relationship.first():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view users who are in relationships with you"
        )
    
    # User is in a relationship with current user, fetch their details
    user_repo = UserRepositoryImpl(db)
    voice_repo = VoiceRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    voice_profile_id = None
    voice_profile = await voice_repo.get_profile(user_id)
    if voice_profile:
        voice_profile_id = voice_profile.id
    
    # Ensure client always gets a display name: prefer display_name, else email prefix. Never return "User xxxxxxxx" placeholder.
    raw = (user.display_name or "").strip() or (user.email.split("@")[0] if user.email else None)
    if raw and re.match(r"^User\s+[a-f0-9]{8}$", raw, re.I):
        raw = (user.email.split("@")[0] if user.email else None) or "Partner"
    display_name = raw
    return UserInfoResponse(
        id=user.id,
        email=user.email,
        display_name=display_name,
        profile_picture_url=getattr(user, 'profile_picture_url', None),
        voice_profile_id=voice_profile_id,
    )
