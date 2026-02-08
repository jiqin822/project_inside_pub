"""
Seed dev users Bar and Ouyang: 2 users, one COUPLE relationship.
Bar: engineer in California, INFP/INTP (T/F ~50), snowboarding, scuba, singing, guitar.
Ouyang: snowboarding+skiing coach, ESTP, gaming, scuba, free diving, soccer, great at cooking.

Usage (from backend/):
  python scripts/seed_dev_bar_ouyang.py

Requires DATABASE_URL (and migrations + seed_love_map_prompts if you want Love Map).
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import AsyncSessionLocal
from app.infra.db.models.user import UserModel
from app.infra.db.models.relationship import (
    RelationshipModel,
    RelationshipType,
    RelationshipStatus,
    relationship_members,
    MemberStatus,
    MemberRole,
)
from app.infra.db.models.market import EconomySettingsModel, WalletModel
from app.infra.db.models.onboarding import OnboardingProgressModel
from app.infra.security.password import get_password_hash
from app.domain.common.types import generate_id

DEV_PASSWORD = "DevBar2025!"

BAR = {
    "email": "bar@dev.inside.app",
    "display_name": "Bar",
    "pronouns": "she/her",
    "personality_type": {"type": "INFP", "values": {"ei": 35, "sn": 50, "tf": 50, "jp": 45}},
    "communication_style": 0.45,
    "goals": ["Ship side projects", "More powder days", "Get better at guitar"],
    "personal_description": "Engineer in California. I like building things and being outdoors. T/F is almost 50/50 for me—sometimes I lead with logic, sometimes with how it feels.",
    "hobbies": ["Snowboarding", "Scuba diving", "Singing", "Playing guitar"],
}

OUYANG = {
    "email": "ouyang@dev.inside.app",
    "display_name": "Ouyang",
    "pronouns": "he/him",
    "personality_type": {"type": "ESTP", "values": {"ei": 75, "sn": 80, "tf": 35, "jp": 70}},
    "communication_style": 0.7,
    "goals": ["Coach more advanced riders", "Try freediving deeper", "Keep the kitchen the heart of the home"],
    "personal_description": "Snowboarding and skiing coach. I like action, games, and the ocean. I cook a lot and love when people enjoy the food.",
    "hobbies": ["Gaming", "Scuba diving", "Free diving", "Soccer", "Cooking"],
}

USERS = [BAR, OUYANG]


async def run_seed(session: AsyncSession, *, skip_exists_check: bool = False) -> dict | None:
    """Seed Bar and Ouyang + COUPLE relationship. Returns user_ids and relationship_id or None if already exists."""
    if not skip_exists_check:
        for u in USERS:
            r = await session.execute(select(UserModel).where(UserModel.email == u["email"]))
            if r.scalar_one_or_none():
                return None

    now = datetime.utcnow()
    user_ids = []

    # 1. Create users
    for u in USERS:
        uid = generate_id()
        user_ids.append(uid)
        session.add(
            UserModel(
                id=uid,
                email=u["email"],
                password_hash=get_password_hash(DEV_PASSWORD),
                display_name=u["display_name"],
                pronouns=u.get("pronouns"),
                personality_type=u.get("personality_type"),
                communication_style=u.get("communication_style"),
                goals=u.get("goals"),
                personal_description=u.get("personal_description"),
                hobbies=u.get("hobbies"),
                privacy_tier="STANDARD",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
    await session.flush()
    bar_id, ouyang_id = user_ids

    # 2. COUPLE relationship (Bar as creator, both ACCEPTED)
    rel_id = generate_id()
    session.add(
        RelationshipModel(
            id=rel_id,
            type=RelationshipType.COUPLE,
            status=RelationshipStatus.ACTIVE,
            created_by_user_id=bar_id,
            created_at=now,
            updated_at=now,
        )
    )
    await session.flush()
    for j, uid in enumerate(user_ids):
        await session.execute(
            relationship_members.insert().values(
                relationship_id=rel_id,
                user_id=uid,
                role=MemberRole.OWNER if j == 0 else MemberRole.MEMBER,
                member_status=MemberStatus.ACCEPTED,
                added_at=now,
            )
        )

    # 3. Economy settings + wallets (pair)
    session.add(
        EconomySettingsModel(
            user_id=bar_id,
            currency_name="High Fives",
            currency_symbol="✋",
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        EconomySettingsModel(
            user_id=ouyang_id,
            currency_name="Heart Tokens",
            currency_symbol="🫀",
            created_at=now,
            updated_at=now,
        )
    )
    for issuer_id in user_ids:
        for holder_id in user_ids:
            if issuer_id == holder_id:
                continue
            session.add(
                WalletModel(
                    id=generate_id(),
                    issuer_id=issuer_id,
                    holder_id=holder_id,
                    balance=0,
                    created_at=now,
                    updated_at=now,
                )
            )
    await session.flush()

    # 4. Onboarding completed for both
    for uid in user_ids:
        session.add(
            OnboardingProgressModel(
                user_id=uid,
                profile_completed=True,
                voiceprint_completed=False,
                relationships_completed=True,
                consent_completed=True,
                device_setup_completed=True,
                done_completed=True,
                updated_at=now,
            )
        )

    return {"user_ids": user_ids, "relationship_id": rel_id, "bar_id": bar_id, "ouyang_id": ouyang_id}


async def seed_dev_bar_ouyang():
    async with AsyncSessionLocal() as session:
        result = await run_seed(session, skip_exists_check=False)
        if result is None:
            print("❌ Bar or Ouyang already exists. Delete those users first if you want to re-seed.")
            return
        await session.commit()
        print("✅ Bar and Ouyang seeded successfully.")
        print(f"   Bar ID:    {result['bar_id']}")
        print(f"   Ouyang ID: {result['ouyang_id']}")
        print(f"   COUPLE relationship ID: {result['relationship_id']}")
        print(f"   Login: bar@dev.inside.app / ouyang@dev.inside.app  |  Password: {DEV_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed_dev_bar_ouyang())
