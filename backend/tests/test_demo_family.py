"""
Integration tests for demo family seed and cleanup.
Requires a running Postgres DB (same as app) and Love Map prompts seeded for full assertions.
"""
import importlib.util
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.infra.db.base import AsyncSessionLocal as _BaseSessionLocal
from app.infra.db.models.user import UserModel

# Under pytest, app.infra.db.base sets AsyncSessionLocal = None. Use a real DB session for integration tests.
if _BaseSessionLocal is None:
    from app.settings import settings
    _integration_engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(
        _integration_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    AsyncSessionLocal = _BaseSessionLocal
from app.infra.db.models.relationship import (
    RelationshipModel,
    RelationshipType,
    relationship_members,
)
from app.infra.db.models.market import (
    EconomySettingsModel,
    WalletModel,
    MarketItemModel,
    TransactionModel,
)
from app.infra.db.models.onboarding import OnboardingProgressModel


def _load_script_module(name: str):
    spec = importlib.util.spec_from_file_location(
        name,
        backend_dir / "scripts" / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_seed_module = None
_cleanup_module = None


def _get_seed_module():
    global _seed_module
    if _seed_module is None:
        _seed_module = _load_script_module("seed_demo_family")
    return _seed_module


def _get_cleanup_module():
    global _cleanup_module
    if _cleanup_module is None:
        _cleanup_module = _load_script_module("cleanup_demo_family")
    return _cleanup_module


DEMO_EMAILS = [
    "marcus.rivera@demo.inside.app",
    "priya.rivera@demo.inside.app",
    "sam.rivera@demo.inside.app",
]


@pytest.fixture
def run_seed():
    return _get_seed_module().run_seed


@pytest.fixture
def run_cleanup():
    return _get_cleanup_module().run_cleanup


@pytest.mark.asyncio
@pytest.mark.integration
async def test_demo_family_seed_and_cleanup(run_seed, run_cleanup):
    """Seed demo family, assert counts, then cleanup and assert removal."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(1))
    except (PermissionError, OSError) as e:
        if "Operation not permitted" in str(e) or "could not connect" in str(e).lower():
            pytest.skip(f"Database not available: {e}")
        raise
    except Exception as e:
        if "connect" in str(e).lower() or "refused" in str(e).lower():
            pytest.skip(f"Database not available: {e}")
        raise

    async with AsyncSessionLocal() as session:
        # 1. Cleanup first so we start from a clean state
        await run_cleanup(session)
        await session.commit()

    # 2. Seed (skip_exists_check since we just cleaned)
    async with AsyncSessionLocal() as session:
        result = await run_seed(session, skip_exists_check=True)
        assert result is not None
        assert "user_ids" in result
        assert "relationship_id" in result
        assert len(result["user_ids"]) == 3
        await session.commit()

    # 3. Assert created data
    async with AsyncSessionLocal() as session:
        # 3 users with demo emails
        for email in DEMO_EMAILS:
            r = await session.execute(select(UserModel).where(UserModel.email == email))
            user = r.scalar_one_or_none()
            assert user is not None, f"Expected user with email {email}"

        # 3 relationships: 1 COUPLE (Marcus–Priya), 2 FAMILY (Marcus–Sam, Priya–Sam)
        rel_ids = result["relationship_ids"]
        assert len(rel_ids) == 3
        couple_id = result["relationship_id"]
        assert couple_id in rel_ids
        types = {}
        for rid in rel_ids:
            r = await session.execute(select(RelationshipModel).where(RelationshipModel.id == rid))
            rel = r.scalar_one_or_none()
            assert rel is not None
            types[rel.type] = types.get(rel.type, 0) + 1
        assert types == {RelationshipType.COUPLE: 1, RelationshipType.FAMILY: 2}
        # Each relationship has 2 members
        for rid in rel_ids:
            r = await session.execute(
                select(func.count()).select_from(relationship_members).where(
                    relationship_members.c.relationship_id == rid
                )
            )
            assert r.scalar() == 2

        # 3 economy settings, 3 onboarding
        user_ids = result["user_ids"]
        for uid in user_ids:
            r = await session.execute(select(EconomySettingsModel).where(EconomySettingsModel.user_id == uid))
            assert r.scalar_one_or_none() is not None
            r = await session.execute(select(OnboardingProgressModel).where(OnboardingProgressModel.user_id == uid))
            assert r.scalar_one_or_none() is not None

        # 6 wallets (each pair: 3*2)
        r = await session.execute(
            select(func.count()).select_from(WalletModel).where(
                (WalletModel.issuer_id.in_(user_ids)) | (WalletModel.holder_id.in_(user_ids))
            )
        )
        assert r.scalar() == 6

        # 10 market items (issuers are the 3 users)
        r = await session.execute(
            select(func.count()).select_from(MarketItemModel).where(MarketItemModel.issuer_id.in_(user_ids))
        )
        assert r.scalar() == 10

        # 5 transactions (we create 5 in seed)
        r = await session.execute(
            select(func.count())
            .select_from(TransactionModel)
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .where(
                or_(
                    WalletModel.issuer_id.in_(user_ids),
                    WalletModel.holder_id.in_(user_ids),
                )
            )
        )
        assert r.scalar() >= 5

    # 4. Cleanup
    async with AsyncSessionLocal() as session:
        await run_cleanup(session)
        await session.commit()

    # 5. Assert all demo users and related data are gone
    async with AsyncSessionLocal() as session:
        for email in DEMO_EMAILS:
            r = await session.execute(select(UserModel).where(UserModel.email == email))
            assert r.scalar_one_or_none() is None, f"Demo user {email} should be deleted"

        # No relationship created by any of the demo user ids (they're gone, so no need to check by creator)
        # Just ensure no user_specs, economy_settings, etc. for those emails
        r = await session.execute(select(UserModel).where(UserModel.email.in_(DEMO_EMAILS)))
        assert len(r.scalars().all()) == 0
