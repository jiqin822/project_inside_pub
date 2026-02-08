"""
Seed the demo Rivera family: 3 users — Priya and Marcus are partners (parents),
Sam is their child. One FAMILY relationship, Love Map data, Connection Market
items/transactions, and completed quests. Run after migrations and seed_love_map_prompts.

Usage (from repo root):
  cd backend && .venv/bin/python scripts/seed_demo_family.py

Or activate venv first:
  cd backend && source .venv/bin/activate && python scripts/seed_demo_family.py
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import date, datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from /etc/project_inside/backend.env if it exists (for remote deployments)
# This must happen before importing app.settings or app.infra.db.base
ENV_FILE = "/etc/project_inside/backend.env"
if os.path.exists(ENV_FILE):
    print(f"Loading environment from {ENV_FILE}...")
    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            # Parse KEY=VALUE (handle values with = signs)
            if "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes if present
                value = value.strip('"').strip("'")
                os.environ[key.strip()] = value

# Check SQLAlchemy version before importing (catches venv issues early)
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError as e:
    print("ERROR: Cannot import async_sessionmaker from sqlalchemy.ext.asyncio")
    print(f"  Details: {e}")
    print("\nThis script requires SQLAlchemy 2.0+ and must be run with the virtual environment Python.")
    print("\nUsage:")
    print("  cd backend")
    print("  .venv/bin/python scripts/seed_demo_family.py")
    print("\nOr activate venv first:")
    print("  cd backend")
    print("  source .venv/bin/activate")
    print("  python scripts/seed_demo_family.py")
    sys.exit(1)

from sqlalchemy import select, update
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
from app.infra.db.models.love_map import (
    MapPromptModel,
    UserSpecModel,
    RelationshipMapProgressModel,
)
from app.infra.db.models.market import (
    EconomySettingsModel,
    WalletModel,
    MarketItemModel,
    TransactionModel,
    TransactionCategory,
    TransactionStatus,
    market_item_relationships,
)
from app.infra.db.models.onboarding import OnboardingProgressModel
from app.infra.security.password import get_password_hash
from app.domain.common.types import generate_id

# ---------------------------------------------------------------------------
# Demo family config (see docs/FAMILY_DEMO_USER_STORY.md)
# ---------------------------------------------------------------------------
DEMO_PASSWORD = "DemoFamily2025!"

USERS = [
    {
        "email": "marcus.rivera@demo.inside.app",
        "display_name": "Marcus Rivera",
        "pronouns": "he/him",
        "birthday": date(1986, 5, 15),
        "occupation": "Software Engineer",
        "personality_type": {"type": "INTJ", "values": {"ei": 20, "sn": 70, "tf": 55, "jp": 75}},
        "communication_style": 0.65,
        "goals": ["More quality time with Sam", "Keep date nights with Priya", "Run a half-marathon"],
        "personal_description": "I’m a software engineer and dad. I need some quiet time to recharge—running or a good book does it. I’m not great at talking about feelings but I try to show up for my family by doing stuff: fixing things, making coffee, being there.",
        "hobbies": ["Running", "Reading sci-fi", "Bike rides", "Fixing things around the house", "Hiking"],
    },
    {
        "email": "priya.rivera@demo.inside.app",
        "display_name": "Priya Rivera",
        "pronouns": "she/her",
        "birthday": date(1988, 8, 22),
        "occupation": "UX Designer (part-time)",
        "personality_type": {"type": "ENFJ", "values": {"ei": 75, "sn": 45, "tf": 80, "jp": 60}},
        "communication_style": 0.35,
        "goals": ["Family game nights", "Garden more", "Less screen time for everyone"],
        "personal_description": "I do UX design part-time and the rest of the time I’m mostly thinking about my people. I love when we’re all in the same room and actually talking. Also trying to grow herbs on our balcony—mixed results so far.",
        "hobbies": ["Gardening", "Baking", "Podcasts", "Family movie nights", "Planning trips"],
    },
    {
        "email": "sam.rivera@demo.inside.app",
        "display_name": "Sam Rivera",
        "pronouns": "they/them",
        "birthday": date(2014, 11, 3),
        "occupation": "Student",
        "personality_type": {"type": "INFP", "values": {"ei": 30, "sn": 55, "tf": 85, "jp": 40}},
        "communication_style": 0.25,
        "goals": ["Get better at robotics", "Read 20 books this year", "Learn to bake with Mom"],
        "personal_description": "I’m in 5th grade. I like drawing and building stuff and our dog Bean is the best. I get tired after school so I need quiet sometimes. I like it when we do things together and nobody’s on their phone.",
        "hobbies": ["Drawing", "Minecraft", "LEGO", "Reading fantasy", "Playing with Bean"],
    },
]

# Love Map answers by prompt index (order: tier 1–5, category order from seed_love_map_prompts)
# Index: 0 comfort food, 1 relax, 2 childhood memory, 3 vacation, 4 hobby, 5 dream, 6 perfect day, 7 goal year,
#        8 stress, 9 fear, 10 comfort when stressed, 11 life event, 12 values, 13 achievement, 14 feel loved, 15 love language, 16 regret
LOVE_MAP_ANSWERS = {
    "marcus": [
        "Strong coffee and a good pastry",
        "Running or reading sci-fi alone",
        "Building a tree fort with my dad",
        "Anywhere with mountains and trails",
        "Running, reading, fixing things",
        "Run a marathon and see Sam graduate",
        "Morning run, quiet work, dinner with family, then a movie",
        "Ship a side project and coach robotics well",
        "Last-minute changes and disorganization",
        "Letting down my family",
        "Space and then a practical fix—tea or taking over a chore",
        "Getting married and having Sam",
        "Honesty, reliability, growth",
        "Getting my engineering degree",
        "When Priya tells me she's proud of me and when Sam wants to hang out",
        "Acts of service and quality time",
        "Not traveling more before we had Sam",
    ],
    "priya": [
        "Chai and something sweet she baked",
        "Gardening or a podcast with a blanket",
        "Family trips to the beach",
        "Beach towns and cozy cabins",
        "Gardening, baking, planning trips",
        "A small B&B or design studio one day",
        "Sleep in, garden, family movie night, good food",
        "Consistent family rituals and a bigger garden",
        "Conflict and feeling unheard",
        "Losing someone I love",
        "Talking it through and a long hug",
        "Becoming a mom",
        "Connection, kindness, creativity",
        "Designing an app that helped real users",
        "Words of affirmation and quality time",
        "Words of affirmation and gifts",
        "Not speaking up more in my twenties",
    ],
    "sam": [
        "Mac and cheese or Mom's cookies",
        "Drawing or playing with Bean",
        "The first time we got Bean",
        "Somewhere with a beach and animals",
        "Drawing, Minecraft, LEGO, reading",
        "Be an artist or work with animals",
        "Build LEGO with Dad, bake with Mom, read, play with Bean",
        "Get better at robotics and read 20 books",
        "When people are mad or things change too fast",
        "Something bad happening to Bean or my parents",
        "Quiet time and someone saying it's gonna be okay",
        "When we got Bean",
        "Being kind and being creative",
        "Winning the art contest at school",
        "When Mom and Dad do stuff with me without phones",
        "Quality time and when people remember what I like",
        "I don't really have one yet",
    ],
}

ECONOMY = [
    {"key": "marcus", "currency_name": "High Fives", "currency_symbol": "✋"},
    {"key": "priya", "currency_name": "Heart Tokens", "currency_symbol": "💗"},
    {"key": "sam", "currency_name": "Stars", "currency_symbol": "⭐"},
]


DEMO_EMAILS = [u["email"] for u in USERS]


async def run_seed(session: AsyncSession, *, skip_exists_check: bool = False) -> dict | None:
    """Seed the demo family into the given session. Caller must commit.
    Returns dict with user_ids, relationship_id if seeded; None if skipped (user already exists).
    When skip_exists_check=True, skips the existence check (for tests after cleanup)."""
    if not skip_exists_check:
        for u in USERS:
            r = await session.execute(select(UserModel).where(UserModel.email == u["email"]))
            if r.scalar_one_or_none():
                return None

    # Naive UTC so asyncpg TIMESTAMP WITHOUT TIME ZONE columns accept it
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user_ids = []
    key_by_id = {}

    # 1. Create users
    for i, u in enumerate(USERS):
        uid = generate_id()
        user_ids.append(uid)
        key_by_id[uid] = ["marcus", "priya", "sam"][i]
        model = UserModel(
            id=uid,
            email=u["email"],
            password_hash=get_password_hash(DEMO_PASSWORD),
            display_name=u["display_name"],
            pronouns=u.get("pronouns"),
            birthday=u.get("birthday"),
            occupation=u.get("occupation"),
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
        session.add(model)
    await session.flush()
    marcus_id, priya_id, sam_id = user_ids
    key_by_id[marcus_id], key_by_id[priya_id], key_by_id[sam_id] = "marcus", "priya", "sam"

    # 2. Relationships: COUPLE (Marcus–Priya partners), FAMILY (Marcus–Sam, Priya–Sam parent–child)
    rel_couple_id = generate_id()
    rel_marcus_sam_id = generate_id()
    rel_priya_sam_id = generate_id()
    for rel_id, rel_type, member_ids in [
        (rel_couple_id, RelationshipType.COUPLE, [marcus_id, priya_id]),
        (rel_marcus_sam_id, RelationshipType.FAMILY, [marcus_id, sam_id]),
        (rel_priya_sam_id, RelationshipType.FAMILY, [priya_id, sam_id]),
    ]:
        session.add(
            RelationshipModel(
                id=rel_id,
                type=rel_type,
                status=RelationshipStatus.ACTIVE,
                created_by_user_id=marcus_id,
                created_at=now,
                updated_at=now,
            )
        )
    await session.flush()  # persist relationships before inserting members (FK)
    for rel_id, _rel_type, member_ids in [
        (rel_couple_id, RelationshipType.COUPLE, [marcus_id, priya_id]),
        (rel_marcus_sam_id, RelationshipType.FAMILY, [marcus_id, sam_id]),
        (rel_priya_sam_id, RelationshipType.FAMILY, [priya_id, sam_id]),
    ]:
        for j, uid in enumerate(member_ids):
            await session.execute(
                relationship_members.insert().values(
                    relationship_id=rel_id,
                    user_id=uid,
                    role=MemberRole.OWNER if j == 0 else MemberRole.MEMBER,
                    member_status=MemberStatus.ACCEPTED,
                    added_at=now,
                )
            )
    await session.flush()

    # 3. Love Map: get prompts (order by tier, category)
    prompts_result = await session.execute(
        select(MapPromptModel)
        .where(MapPromptModel.is_active == True)
        .order_by(MapPromptModel.difficulty_tier, MapPromptModel.category)
    )
    prompts = prompts_result.scalars().all()
    for uid in user_ids:
        key = key_by_id[uid]
        answers = LOVE_MAP_ANSWERS[key]
        for idx, prompt in enumerate(prompts):
            if idx >= len(answers):
                break
            spec = UserSpecModel(
                id=generate_id(),
                user_id=uid,
                prompt_id=prompt.id,
                answer_text=answers[idx],
                last_updated=now,
            )
            session.add(spec)
    # Map progress: each person has progress learning the other two
    for observer_id in user_ids:
        for subject_id in user_ids:
            if observer_id == subject_id:
                continue
            session.add(
                RelationshipMapProgressModel(
                    id=generate_id(),
                    observer_id=observer_id,
                    subject_id=subject_id,
                    level_tier=min(2, 1 + (len(prompts) // 5)),
                    current_xp=40 + len(prompts) * 2,
                    stars={"tier_1": 3, "tier_2": 1},
                    created_at=now,
                    updated_at=now,
                )
            )

    # 4. Economy settings + wallets
    for i, uid in enumerate(user_ids):
        e = ECONOMY[i]
        session.add(
            EconomySettingsModel(
                user_id=uid,
                currency_name=e["currency_name"],
                currency_symbol=e["currency_symbol"],
                created_at=now,
                updated_at=now,
            )
        )
    # Wallets: each pair (issuer, holder)
    wallet_ids = {}
    for issuer_id in user_ids:
        for holder_id in user_ids:
            if issuer_id == holder_id:
                continue
            wid = generate_id()
            session.add(
                WalletModel(
                    id=wid,
                    issuer_id=issuer_id,
                    holder_id=holder_id,
                    balance=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            wallet_ids[(issuer_id, holder_id)] = wid
    await session.flush()

    # 5. Market items (SPEND + EARN) linked to the appropriate relationship(s)
    # Each item: (key, issuer_id, title, desc, cost, icon, cat, rel_ids)
    items = [
        ("priya", priya_id, "New lego car", "New lego car for 1000 hearts", 1000, "🚗", TransactionCategory.SPEND, [rel_priya_sam_id]),
        ("priya", priya_id, "Favorite meatball pasta", "Favorite meatball pasta for 100 hearts", 100, "🍝", TransactionCategory.SPEND, [rel_priya_sam_id]),
        ("priya", priya_id, "Help fertilize garden", "Bounty: Help fertilize garden for 100 hearts", 100, "🌱", TransactionCategory.EARN, [rel_couple_id]),
        ("priya", priya_id, "Romantic date night", "Romantic date night for 200 hearts", 200, "💕", TransactionCategory.SPEND, [rel_couple_id]),
        ("marcus", marcus_id, "Breakfast in bed", "Breakfast in bed for 150 high fives", 150, "🛏️", TransactionCategory.SPEND, [rel_couple_id]),
        ("marcus", marcus_id, "Game night", "Game night for 100 high fives", 100, "🎲", TransactionCategory.SPEND, [rel_couple_id]),
        ("marcus", marcus_id, "Homework help for 1 hour", "Homework help for 1 hour for 50 high fives", 50, "📚", TransactionCategory.SPEND, [rel_marcus_sam_id]),
        ("marcus", marcus_id, "Bike with me", "Bounty: Bike with me for 100 high fives", 100, "🚴", TransactionCategory.EARN, [rel_marcus_sam_id]),
        ("sam", sam_id, "Draw you a picture", "Sam draws a picture for you", 10, "🎨", TransactionCategory.SPEND, [rel_priya_sam_id, rel_marcus_sam_id]),
        ("sam", sam_id, "Play a board game with me", "One board game together", 20, "🎲", TransactionCategory.EARN, [rel_priya_sam_id, rel_marcus_sam_id]),
    ]

    item_id_by_title = {}
    for _key, issuer_id, title, desc, cost, icon, cat, _rel_ids in items:
        item_id = generate_id()
        session.add(
            MarketItemModel(
                id=item_id,
                issuer_id=issuer_id,
                title=title,
                description=desc,
                cost=cost,
                icon=icon,
                category=cat,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        item_id_by_title[(issuer_id, title)] = item_id
    await session.flush()
    for _key, issuer_id, title, _desc, _cost, _icon, _cat, rel_ids in items:
        iid = item_id_by_title[(issuer_id, title)]
        for r_id in rel_ids:
            await session.execute(
                market_item_relationships.insert().values(
                    market_item_id=iid,
                    relationship_id=r_id,
                )
            )

    # 6. Transactions: SPEND (purchased/redeemed) and EARN (accepted -> approved)
    wallet_sam_priya = wallet_ids[(sam_id, priya_id)]
    item_draw = item_id_by_title[(sam_id, "Draw you a picture")]
    session.add(
        TransactionModel(
            id=generate_id(),
            wallet_id=wallet_sam_priya,
            market_item_id=item_draw,
            category=TransactionCategory.SPEND,
            amount=10,
            status=TransactionStatus.REDEEMED,
            tx_metadata={"title": "Draw you a picture", "icon": "🎨"},
            created_at=now,
            completed_at=now,
        )
    )
    wallet_sam_marcus = wallet_ids[(sam_id, marcus_id)]
    item_board = item_id_by_title[(sam_id, "Play a board game with me")]
    session.add(
        TransactionModel(
            id=generate_id(),
            wallet_id=wallet_sam_marcus,
            market_item_id=item_board,
            category=TransactionCategory.EARN,
            amount=20,
            status=TransactionStatus.APPROVED,
            tx_metadata={"title": "Play a board game with me", "icon": "🎲"},
            created_at=now,
            completed_at=now,
        )
    )
    for (issuer_id, holder_id), wid in wallet_ids.items():
        balance = 0
        if (sam_id, marcus_id) == (issuer_id, holder_id):
            balance += 20
        if balance > 0:
            await session.execute(
                update(WalletModel)
                .where(WalletModel.id == wid)
                .values(balance=balance, updated_at=now)
            )

    # 7. Onboarding completed for all
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

    return {
        "user_ids": user_ids,
        "relationship_id": rel_couple_id,
        "relationship_ids": [rel_couple_id, rel_marcus_sam_id, rel_priya_sam_id],
    }


async def seed_demo_family():
    """CLI entrypoint: open session, run_seed, commit, print."""
    async with AsyncSessionLocal() as session:
        result = await run_seed(session, skip_exists_check=False)
        if result is None:
            print("❌ A demo user already exists. Run cleanup_demo_family.py first.")
            return
        await session.commit()
        print("\n✅ Demo family seeded successfully.")
        print(f"   Relationship IDs: 1 COUPLE (partners) + 2 FAMILY (parent–child): {result['relationship_ids']}")
        print(f"   User IDs: {result['user_ids']}")
        print("   See docs/FAMILY_DEMO_CREDENTIALS.md for login details.")


if __name__ == "__main__":
    asyncio.run(seed_demo_family())
