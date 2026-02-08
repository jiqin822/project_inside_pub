"""User repository implementation."""
from datetime import date as date_type
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.domain.admin.models import User
from app.domain.admin.services import UserRepository
from app.infra.db.models.user import UserModel


class UserRepositoryImpl(UserRepository):
    """User repository implementation."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user: User) -> User:
        """Create a new user."""
        model = UserModel.from_entity(user)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None

    async def update(self, user: User) -> User:
        """Update user."""
        await self.session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(
                display_name=user.display_name,
                pronouns=getattr(user, "pronouns", None),
                personality_type=getattr(user, "personality_type", None),
                communication_style=getattr(user, "communication_style", None),
                goals=getattr(user, "goals", None),
                personal_description=getattr(user, "personal_description", None),
                hobbies=getattr(user, "hobbies", None),
                birthday=getattr(user, "birthday", None),
                occupation=getattr(user, "occupation", None),
                privacy_tier=getattr(user, "privacy_tier", None),
                profile_picture_url=getattr(user, "profile_picture_url", None),
                is_active=user.is_active,
                updated_at=user.updated_at,
            )
        )
        await self.session.commit()
        return await self.get_by_id(user.id)

    async def update_profile_fields(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        pronouns: Optional[str] = None,
        personality_type: Optional[dict] = None,
        communication_style: Optional[float] = None,
        goals: Optional[list[str]] = None,
        personal_description: Optional[str] = None,
        hobbies: Optional[list[str]] = None,
        birthday: Optional[date_type] = None,
        occupation: Optional[str] = None,
        privacy_tier: Optional[str] = None,
        profile_picture_url: Optional[str] = None,
    ) -> User:
        """Update user profile fields."""
        update_values = {}
        if display_name is not None:
            update_values["display_name"] = display_name
        if pronouns is not None:
            update_values["pronouns"] = pronouns
        if personality_type is not None:
            update_values["personality_type"] = personality_type
        if communication_style is not None:
            update_values["communication_style"] = communication_style
        if goals is not None:
            update_values["goals"] = goals
        if personal_description is not None:
            update_values["personal_description"] = personal_description
        if hobbies is not None:
            update_values["hobbies"] = hobbies
        if birthday is not None:
            update_values["birthday"] = birthday
        if occupation is not None:
            update_values["occupation"] = occupation
        if privacy_tier is not None:
            update_values["privacy_tier"] = privacy_tier
        if profile_picture_url is not None:
            update_values["profile_picture_url"] = profile_picture_url
        
        if update_values:
            from datetime import datetime
            update_values['updated_at'] = datetime.utcnow()
            await self.session.execute(
                update(UserModel)
                .where(UserModel.id == user_id)
                .values(**update_values)
            )
            await self.session.commit()
        
        return await self.get_by_id(user_id)