"""Tests for Market module."""
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator, JSON

from app.domain.common.types import generate_id
from app.domain.market.models import (
    EconomySettings,
    Wallet,
    MarketItem,
    Transaction,
    TransactionCategory,
    TransactionStatus,
)
from app.domain.market.services import MarketService
from app.infra.db.repositories.market_repo import MarketRepositoryImpl
from app.infra.db.base import Base


# Type adapter for JSONB -> JSON in SQLite
class JSONBType(TypeDecorator):
    """Type adapter that uses JSON for SQLite and JSONB for PostgreSQL."""
    impl = JSONB
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'sqlite':
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSONB())


# Test database setup
@pytest.fixture
async def db_session():
    """Create a test database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create a minimal users table for foreign keys (using JSON instead of JSONB for SQLite)
    from sqlalchemy import Table, MetaData, UniqueConstraint, CheckConstraint
    metadata = MetaData()
    
    # Create users table with JSON instead of JSONB for SQLite compatibility
    users_table = Table(
        'users',
        metadata,
        Column('id', String, primary_key=True),
        Column('email', String, unique=True, nullable=False),
        Column('password_hash', String, nullable=False),
        Column('display_name', String, nullable=True),
        Column('pronouns', String, nullable=True),
        Column('communication_style', Float, nullable=True),
        Column('goals', JSON, nullable=True),  # Use JSON instead of JSONB for SQLite
        Column('privacy_tier', String, nullable=True),
        Column('profile_picture_url', String, nullable=True),
        Column('is_active', Boolean, default=True, nullable=False),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
    )
    
    # Create market tables with JSON instead of JSONB for SQLite
    # Note: We need to create these manually to replace JSONB with JSON
    economy_settings_table = Table(
        'economy_settings',
        metadata,
        Column('user_id', String, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        Column('currency_name', String, nullable=False),
        Column('currency_symbol', String, nullable=False),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
    )
    
    wallets_table = Table(
        'wallets',
        metadata,
        Column('id', String, primary_key=True),
        Column('issuer_id', String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        Column('holder_id', String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        Column('balance', Integer, default=0, nullable=False),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
        # Constraints
        UniqueConstraint('issuer_id', 'holder_id', name='uq_wallet_issuer_holder'),
    )
    
    # Create enum types for SQLite (SQLite doesn't support native enums, so we use String)
    market_items_table = Table(
        'market_items',
        metadata,
        Column('id', String, primary_key=True),
        Column('issuer_id', String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        Column('title', String, nullable=False),
        Column('description', Text, nullable=True),
        Column('cost', Integer, nullable=False),
        Column('icon', String, nullable=True),
        Column('category', String, nullable=False),  # Use String instead of ENUM for SQLite
        Column('is_active', Boolean, default=True, nullable=False),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
    )
    
    transactions_table = Table(
        'transactions',
        metadata,
        Column('id', String, primary_key=True),
        Column('wallet_id', String, ForeignKey('wallets.id', ondelete='CASCADE'), nullable=False),
        Column('market_item_id', String, ForeignKey('market_items.id', ondelete='SET NULL'), nullable=True),
        Column('category', String, nullable=False),  # Use String instead of ENUM for SQLite
        Column('amount', Integer, nullable=False),
        Column('status', String, nullable=False),  # Use String instead of ENUM for SQLite
        Column('tx_metadata', JSON, nullable=True),  # Use JSON instead of JSONB for SQLite
        Column('created_at', DateTime, nullable=False),
        Column('completed_at', DateTime, nullable=True),
    )

    # Required for MarketItem.visible_to_relationships (repo refresh loads this)
    relationships_table = Table(
        'relationships',
        metadata,
        Column('id', String, primary_key=True),
        Column('type', String, nullable=False),
        Column('status', String, nullable=False),
        Column('created_by_user_id', String, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        Column('created_at', DateTime, nullable=False),
        Column('updated_at', DateTime, nullable=False),
    )
    market_item_relationships_table = Table(
        'market_item_relationships',
        metadata,
        Column('market_item_id', String, ForeignKey('market_items.id', ondelete='CASCADE'), primary_key=True),
        Column('relationship_id', String, ForeignKey('relationships.id', ondelete='CASCADE'), primary_key=True),
    )
    
    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(metadata.create_all)
    
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def sample_users(db_session: AsyncSession):
    """Create sample users in the database."""
    from datetime import datetime
    user_ids = {
        "issuer": generate_id(),
        "holder": generate_id(),
    }
    
    # Insert minimal user records for foreign key constraints
    from sqlalchemy import text
    for user_id in user_ids.values():
        await db_session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, is_active, created_at, updated_at)
                VALUES (:id, :email, :hash, :active, :created, :updated)
            """),
            {
                "id": user_id,
                "email": f"{user_id}@test.com",
                "hash": "dummy_hash",
                "active": True,
                "created": datetime.utcnow(),
                "updated": datetime.utcnow(),
            }
        )
    await db_session.commit()
    
    return user_ids


@pytest.fixture
async def market_service(db_session: AsyncSession):
    """Create a market service instance."""
    repo = MarketRepositoryImpl(db_session)
    return MarketService(repo, db_session)


class TestEconomySettings:
    """Tests for economy settings."""
    
    async def test_create_economy_settings(self, market_service: MarketService, sample_users: dict):
        """Test creating economy settings."""
        settings = await market_service.create_or_update_economy_settings(
            user_id=sample_users["issuer"],
            currency_name="Love Tokens",
            currency_symbol="🪙",
        )
        
        assert settings.user_id == sample_users["issuer"]
        assert settings.currency_name == "Love Tokens"
        assert settings.currency_symbol == "🪙"
    
    async def test_get_economy_settings(self, market_service: MarketService, sample_users: dict):
        """Test getting economy settings."""
        # Create settings
        await market_service.create_or_update_economy_settings(
            user_id=sample_users["issuer"],
            currency_name="Hugs",
            currency_symbol="❤️",
        )
        
        # Get settings
        settings = await market_service.get_economy_settings(sample_users["issuer"])
        assert settings is not None
        assert settings.currency_name == "Hugs"
        assert settings.currency_symbol == "❤️"
    
    async def test_update_economy_settings(self, market_service: MarketService, sample_users: dict):
        """Test updating economy settings."""
        # Create initial settings
        await market_service.create_or_update_economy_settings(
            user_id=sample_users["issuer"],
            currency_name="Love Tokens",
            currency_symbol="🪙",
        )
        
        # Update settings
        settings = await market_service.create_or_update_economy_settings(
            user_id=sample_users["issuer"],
            currency_name="Hugs",
            currency_symbol="❤️",
        )
        
        assert settings.currency_name == "Hugs"
        assert settings.currency_symbol == "❤️"


class TestWallets:
    """Tests for wallets."""
    
    async def test_get_or_create_wallet(self, market_service: MarketService, sample_users: dict):
        """Test getting or creating a wallet."""
        wallet = await market_service.get_or_create_wallet(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        assert wallet.issuer_id == sample_users["issuer"]
        assert wallet.holder_id == sample_users["holder"]
        assert wallet.balance == 0
    
    async def test_get_wallet_balance(self, market_service: MarketService, sample_users: dict):
        """Test getting wallet balance."""
        # Create wallet
        await market_service.get_or_create_wallet(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        balance = await market_service.get_wallet_balance(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        assert balance == 0


class TestMarketItems:
    """Tests for market items."""
    
    async def test_create_market_item_spend(self, market_service: MarketService, sample_users: dict):
        """Test creating a SPEND market item."""
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Back Massage",
            description="A relaxing back massage",
            cost=500,
            icon="💆",
            category=TransactionCategory.SPEND,
        )
        
        assert item.issuer_id == sample_users["issuer"]
        assert item.title == "Back Massage"
        assert item.cost == 500
        assert item.category == TransactionCategory.SPEND
        assert item.is_active is True
    
    async def test_create_market_item_earn(self, market_service: MarketService, sample_users: dict):
        """Test creating an EARN market item."""
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Wash Dishes",
            description="Clean the dishes",
            cost=150,
            icon="🧼",
            category=TransactionCategory.EARN,
        )
        
        assert item.category == TransactionCategory.EARN
        assert item.cost == 150
    
    async def test_get_market_items(self, market_service: MarketService, sample_users: dict):
        """Test getting market items for an issuer."""
        # Create items
        await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Item 1",
            description=None,
            cost=100,
            icon=None,
            category=TransactionCategory.SPEND,
        )
        await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Item 2",
            description=None,
            cost=200,
            icon=None,
            category=TransactionCategory.EARN,
        )
        
        items = await market_service.get_market_items(sample_users["issuer"])
        assert len(items) == 2
    
    async def test_delete_market_item(self, market_service: MarketService, sample_users: dict):
        """Test deleting a market item."""
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Test Item",
            description=None,
            cost=100,
            icon=None,
            category=TransactionCategory.SPEND,
        )
        
        await market_service.delete_market_item(item.id, sample_users["issuer"])
        
        items = await market_service.get_market_items(sample_users["issuer"], active_only=True)
        assert len(items) == 0


class TestSpendFlow:
    """Tests for SPEND workflow (PURCHASE -> REDEEM)."""
    
    async def test_purchase_item_success(self, market_service: MarketService, sample_users: dict):
        """Test successfully purchasing an item."""
        # Create economy settings
        await market_service.create_or_update_economy_settings(
            user_id=sample_users["issuer"],
            currency_name="Love Tokens",
            currency_symbol="🪙",
        )
        
        # Create market item
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Back Massage",
            description=None,
            cost=500,
            icon="💆",
            category=TransactionCategory.SPEND,
        )
        
        # Give holder some balance
        wallet = await market_service.get_or_create_wallet(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        # Manually set balance for testing
        from app.infra.db.repositories.market_repo import MarketRepositoryImpl
        repo = market_service.repo
        if isinstance(repo, MarketRepositoryImpl):
            await repo.update_wallet_balance(wallet.id, 1000)
        
        # Purchase item
        transaction = await market_service.purchase_item(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        assert transaction.status == TransactionStatus.PURCHASED
        assert transaction.amount == 500
        assert transaction.category == TransactionCategory.SPEND
        
        # Check balance decreased
        new_balance = await market_service.get_wallet_balance(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        assert new_balance == 500  # 1000 - 500
    
    async def test_purchase_item_insufficient_balance(self, market_service: MarketService, sample_users: dict):
        """Test purchasing with insufficient balance."""
        # Create market item
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Expensive Item",
            description=None,
            cost=1000,
            icon=None,
            category=TransactionCategory.SPEND,
        )
        
        # Try to purchase (balance is 0)
        with pytest.raises(ValueError, match="Insufficient balance"):
            await market_service.purchase_item(
                item_id=item.id,
                issuer_id=sample_users["issuer"],
                holder_id=sample_users["holder"],
            )
    
    async def test_redeem_item(self, market_service: MarketService, sample_users: dict):
        """Test redeeming a purchased item."""
        # Create and purchase item
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Back Massage",
            description=None,
            cost=500,
            icon="💆",
            category=TransactionCategory.SPEND,
        )
        
        # Give balance and purchase
        wallet = await market_service.get_or_create_wallet(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        from app.infra.db.repositories.market_repo import MarketRepositoryImpl
        repo = market_service.repo
        if isinstance(repo, MarketRepositoryImpl):
            await repo.update_wallet_balance(wallet.id, 1000)
        
        transaction = await market_service.purchase_item(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        # Redeem
        redeemed = await market_service.redeem_item(transaction.id, sample_users["holder"])
        assert redeemed.status == TransactionStatus.REDEEMED
        assert redeemed.completed_at is not None


class TestEarnFlow:
    """Tests for EARN workflow (ACCEPT -> SUBMIT_FOR_REVIEW -> APPROVE)."""
    
    async def test_accept_task(self, market_service: MarketService, sample_users: dict):
        """Test accepting a task."""
        # Create market item
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Wash Dishes",
            description=None,
            cost=150,
            icon="🧼",
            category=TransactionCategory.EARN,
        )
        
        # Accept task
        transaction = await market_service.accept_task(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        assert transaction.status == TransactionStatus.ACCEPTED
        assert transaction.category == TransactionCategory.EARN
        assert transaction.amount == 150
    
    async def test_submit_for_review(self, market_service: MarketService, sample_users: dict):
        """Test submitting task for review."""
        # Create and accept task
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Wash Dishes",
            description=None,
            cost=150,
            icon="🧼",
            category=TransactionCategory.EARN,
        )
        
        transaction = await market_service.accept_task(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        # Submit for review
        submitted = await market_service.submit_for_review(transaction.id, sample_users["holder"])
        assert submitted.status == TransactionStatus.PENDING_APPROVAL
    
    async def test_approve_task(self, market_service: MarketService, sample_users: dict):
        """Test approving a task."""
        # Create, accept, and submit task
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Wash Dishes",
            description=None,
            cost=150,
            icon="🧼",
            category=TransactionCategory.EARN,
        )
        
        transaction = await market_service.accept_task(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        await market_service.submit_for_review(transaction.id, sample_users["holder"])
        
        # Approve
        approved = await market_service.approve_task(transaction.id, sample_users["issuer"])
        assert approved.status == TransactionStatus.APPROVED
        assert approved.completed_at is not None
        
        # Check balance increased
        balance = await market_service.get_wallet_balance(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        assert balance == 150


class TestTransactionCancellation:
    """Tests for transaction cancellation."""
    
    async def test_cancel_transaction_by_holder(self, market_service: MarketService, sample_users: dict):
        """Test canceling a transaction by holder."""
        # Create and accept task
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Wash Dishes",
            description=None,
            cost=150,
            icon="🧼",
            category=TransactionCategory.EARN,
        )
        
        transaction = await market_service.accept_task(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        # Cancel by holder
        canceled = await market_service.cancel_transaction(transaction.id, sample_users["holder"])
        assert canceled.status == TransactionStatus.CANCELED
    
    async def test_cancel_transaction_by_issuer(self, market_service: MarketService, sample_users: dict):
        """Test canceling a transaction by issuer."""
        # Create and accept task
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Wash Dishes",
            description=None,
            cost=150,
            icon="🧼",
            category=TransactionCategory.EARN,
        )
        
        transaction = await market_service.accept_task(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        # Cancel by issuer
        canceled = await market_service.cancel_transaction(transaction.id, sample_users["issuer"])
        assert canceled.status == TransactionStatus.CANCELED
    
    async def test_cannot_cancel_completed_transaction(self, market_service: MarketService, sample_users: dict):
        """Test that completed transactions cannot be canceled."""
        # Create, purchase, and redeem item
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Back Massage",
            description=None,
            cost=500,
            icon="💆",
            category=TransactionCategory.SPEND,
        )
        
        wallet = await market_service.get_or_create_wallet(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        from app.infra.db.repositories.market_repo import MarketRepositoryImpl
        repo = market_service.repo
        if isinstance(repo, MarketRepositoryImpl):
            await repo.update_wallet_balance(wallet.id, 1000)
        
        transaction = await market_service.purchase_item(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        
        await market_service.redeem_item(transaction.id, sample_users["holder"])
        
        # Try to cancel (should fail)
        with pytest.raises(ValueError, match="Cannot cancel"):
            await market_service.cancel_transaction(transaction.id, sample_users["holder"])


class TestConcurrency:
    """Tests for concurrency and locking."""
    
    async def test_concurrent_purchases_prevent_double_spend(self, market_service: MarketService, sample_users: dict):
        """Test that concurrent purchases are handled correctly."""
        # This is a simplified test - in production, you'd use actual async concurrency
        item = await market_service.create_market_item(
            issuer_id=sample_users["issuer"],
            title="Item",
            description=None,
            cost=100,
            icon=None,
            category=TransactionCategory.SPEND,
        )
        
        wallet = await market_service.get_or_create_wallet(
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        from app.infra.db.repositories.market_repo import MarketRepositoryImpl
        repo = market_service.repo
        if isinstance(repo, MarketRepositoryImpl):
            await repo.update_wallet_balance(wallet.id, 150)
        
        # First purchase should succeed
        transaction1 = await market_service.purchase_item(
            item_id=item.id,
            issuer_id=sample_users["issuer"],
            holder_id=sample_users["holder"],
        )
        assert transaction1.status == TransactionStatus.PURCHASED
        
        # Second purchase should fail (insufficient balance)
        with pytest.raises(ValueError, match="Insufficient balance"):
            await market_service.purchase_item(
                item_id=item.id,
                issuer_id=sample_users["issuer"],
                holder_id=sample_users["holder"],
            )
