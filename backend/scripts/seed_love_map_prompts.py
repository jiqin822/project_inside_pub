"""Seed script for Love Map prompts."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.infra.db.base import (
    normalize_async_pg_url,
    async_pg_url_without_sslmode,
    async_pg_connect_args,
)
from app.infra.db.models.love_map import MapPromptModel
from app.settings import settings
from app.domain.common.types import generate_id
from datetime import datetime


# Sample prompts organized by tier and category
PROMPTS = [
    # Tier 1: Basics
    {
        "category": "Basics",
        "difficulty_tier": 1,
        "question_template": "What is [NAME]'s favorite comfort food?",
        "input_prompt": "What is your favorite comfort food?",
    },
    {
        "category": "Basics",
        "difficulty_tier": 1,
        "question_template": "What is [NAME]'s favorite way to relax?",
        "input_prompt": "What is your favorite way to relax?",
    },
    {
        "category": "Basics",
        "difficulty_tier": 1,
        "question_template": "What is [NAME]'s favorite childhood memory?",
        "input_prompt": "What is your favorite childhood memory?",
    },
    {
        "category": "Basics",
        "difficulty_tier": 1,
        "question_template": "What is [NAME]'s favorite vacation destination?",
        "input_prompt": "What is your favorite vacation destination?",
    },
    {
        "category": "Basics",
        "difficulty_tier": 1,
        "question_template": "What is [NAME]'s favorite hobby?",
        "input_prompt": "What is your favorite hobby?",
    },
    
    # Tier 2: Dreams & Goals
    {
        "category": "Dreams",
        "difficulty_tier": 2,
        "question_template": "What is [NAME]'s biggest dream?",
        "input_prompt": "What is your biggest dream?",
    },
    {
        "category": "Dreams",
        "difficulty_tier": 2,
        "question_template": "What is [NAME]'s ideal way to spend a perfect day?",
        "input_prompt": "What is your ideal way to spend a perfect day?",
    },
    {
        "category": "Dreams",
        "difficulty_tier": 2,
        "question_template": "What is [NAME]'s biggest goal for the next year?",
        "input_prompt": "What is your biggest goal for the next year?",
    },
    
    # Tier 3: Stress & Fears
    {
        "category": "Stress",
        "difficulty_tier": 3,
        "question_template": "What causes [NAME] the most stress?",
        "input_prompt": "What causes you the most stress?",
    },
    {
        "category": "Stress",
        "difficulty_tier": 3,
        "question_template": "What is [NAME]'s biggest fear?",
        "input_prompt": "What is your biggest fear?",
    },
    {
        "category": "Stress",
        "difficulty_tier": 3,
        "question_template": "How does [NAME] prefer to be comforted when stressed?",
        "input_prompt": "How do you prefer to be comforted when stressed?",
    },
    
    # Tier 4: History & Values
    {
        "category": "History",
        "difficulty_tier": 4,
        "question_template": "What is [NAME]'s most significant life event?",
        "input_prompt": "What is your most significant life event?",
    },
    {
        "category": "History",
        "difficulty_tier": 4,
        "question_template": "What values are most important to [NAME]?",
        "input_prompt": "What values are most important to you?",
    },
    {
        "category": "History",
        "difficulty_tier": 4,
        "question_template": "What is [NAME]'s proudest achievement?",
        "input_prompt": "What is your proudest achievement?",
    },
    
    # Tier 5: Deep/Intimate
    {
        "category": "Intimacy",
        "difficulty_tier": 5,
        "question_template": "What makes [NAME] feel most loved?",
        "input_prompt": "What makes you feel most loved?",
    },
    {
        "category": "Intimacy",
        "difficulty_tier": 5,
        "question_template": "What is [NAME]'s love language?",
        "input_prompt": "What is your love language?",
    },
    {
        "category": "Intimacy",
        "difficulty_tier": 5,
        "question_template": "What is [NAME]'s deepest regret?",
        "input_prompt": "What is your deepest regret?",
    },
]


async def seed_prompts():
    """Seed map prompts into the database."""
    url = normalize_async_pg_url(settings.database_url)
    engine = create_async_engine(
        async_pg_url_without_sslmode(url),
        connect_args=async_pg_connect_args(url),
        echo=False,
    )
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as session:
        # Check if prompts already exist
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(MapPromptModel.id)))
        count = result.scalar()
        
        if count > 0:
            print(f"Found {count} existing prompts. Skipping seed.")
            return
        
        # Insert prompts
        now = datetime.utcnow()
        for prompt_data in PROMPTS:
            prompt = MapPromptModel(
                id=generate_id(),
                category=prompt_data["category"],
                difficulty_tier=prompt_data["difficulty_tier"],
                question_template=prompt_data["question_template"],
                input_prompt=prompt_data["input_prompt"],
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(prompt)
        
        await session.commit()
        print(f"Successfully seeded {len(PROMPTS)} map prompts.")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_prompts())
