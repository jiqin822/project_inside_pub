"""Market database models."""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Text, Index, Table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

from app.infra.db.base import Base

# Junction table for market items and relationships (many-to-many)
# Note: Import RelationshipModel lazily to avoid circular imports
market_item_relationships = Table(
    'market_item_relationships',
    Base.metadata,
    Column('market_item_id', String, ForeignKey('market_items.id', ondelete='CASCADE'), primary_key=True),
    Column('relationship_id', String, ForeignKey('relationships.id', ondelete='CASCADE'), primary_key=True),
    Index('ix_market_item_relationships_market_item_id', 'market_item_id'),
    Index('ix_market_item_relationships_relationship_id', 'relationship_id'),
)


class TransactionCategory(str, Enum):
    """Transaction category enum."""
    SPEND = "SPEND"  # Reward/Product - costs currency
    EARN = "EARN"    # Bounty/Service - earns currency


class TransactionStatus(str, Enum):
    """Transaction status enum."""
    # Spend flow
    PURCHASED = "PURCHASED"  # Item purchased, waiting to redeem
    REDEEMED = "REDEEMED"    # Item redeemed/consumed
    
    # Earn flow
    ACCEPTED = "ACCEPTED"           # Task accepted by holder
    PENDING_APPROVAL = "PENDING_APPROVAL"  # Submitted for review
    APPROVED = "APPROVED"           # Approved by issuer, balance updated
    CANCELED = "CANCELED"           # Canceled by either party


class EconomySettingsModel(Base):
    """Economy settings model - stores currency configuration for a user."""
    
    __tablename__ = "economy_settings"
    
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    currency_name = Column(String, nullable=False)
    currency_symbol = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("UserModel", backref="economy_settings")
    
    def to_entity(self):
        """Convert to domain entity."""
        from app.domain.market.models import EconomySettings
        return EconomySettings(
            user_id=self.user_id,
            currency_name=self.currency_name,
            currency_symbol=self.currency_symbol,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
    
    @classmethod
    def from_entity(cls, entity):
        """Create from domain entity."""
        return cls(
            user_id=entity.user_id,
            currency_name=entity.currency_name,
            currency_symbol=entity.currency_symbol,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class WalletModel(Base):
    """Wallet model - tracks balance a participant holds in an issuer's economy."""
    
    __tablename__ = "wallets"
    
    id = Column(String, primary_key=True)
    issuer_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    holder_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    balance = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    issuer = relationship("UserModel", foreign_keys=[issuer_id], backref="issued_wallets")
    holder = relationship("UserModel", foreign_keys=[holder_id], backref="held_wallets")
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('issuer_id', 'holder_id', name='uq_wallet_issuer_holder'),
        CheckConstraint('balance >= 0', name='ck_wallet_balance_non_negative'),
        Index('ix_wallets_issuer_id', 'issuer_id'),
        Index('ix_wallets_holder_id', 'holder_id'),
    )
    
    def to_entity(self):
        """Convert to domain entity."""
        from app.domain.market.models import Wallet
        return Wallet(
            id=self.id,
            issuer_id=self.issuer_id,
            holder_id=self.holder_id,
            balance=self.balance,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
    
    @classmethod
    def from_entity(cls, entity):
        """Create from domain entity."""
        return cls(
            id=entity.id,
            issuer_id=entity.issuer_id,
            holder_id=entity.holder_id,
            balance=entity.balance,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class MarketItemModel(Base):
    """Market item model - templates for items available in an issuer's store."""
    
    __tablename__ = "market_items"
    
    id = Column(String, primary_key=True)
    issuer_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    cost = Column(Integer, nullable=False)
    icon = Column(String, nullable=True)  # Emoji or icon ID
    category = Column(PG_ENUM(TransactionCategory, name="transaction_category"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    issuer = relationship("UserModel", backref="market_items")
    # Many-to-many relationship with relationships (which loved ones can see this item)
    visible_to_relationships = relationship(
        "RelationshipModel",
        secondary=market_item_relationships,
        backref="market_items"
    )
    
    # Constraints and indexes
    __table_args__ = (
        CheckConstraint('cost > 0', name='ck_market_item_cost_positive'),
        Index('ix_market_items_issuer_id', 'issuer_id'),
        Index('ix_market_items_is_active', 'is_active'),
    )
    
    def to_entity(self):
        """Convert to domain entity."""
        from app.domain.market.models import MarketItem
        # Get relationship IDs from the many-to-many relationship
        visible_to_relationship_ids = [rel.id for rel in self.visible_to_relationships] if self.visible_to_relationships else None
        return MarketItem(
            id=self.id,
            issuer_id=self.issuer_id,
            title=self.title,
            description=self.description,
            cost=self.cost,
            icon=self.icon,
            category=self.category,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
            visible_to_relationship_ids=visible_to_relationship_ids if visible_to_relationship_ids else None,
        )
    
    @classmethod
    def from_entity(cls, entity):
        """Create from domain entity."""
        return cls(
            id=entity.id,
            issuer_id=entity.issuer_id,
            title=entity.title,
            description=entity.description,
            cost=entity.cost,
            icon=entity.icon,
            category=entity.category,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )


class TransactionModel(Base):
    """Transaction model - instances of items being purchased, completed, or transferred."""
    
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True)
    wallet_id = Column(String, ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False)
    market_item_id = Column(String, ForeignKey("market_items.id", ondelete="SET NULL"), nullable=True)
    category = Column(PG_ENUM(TransactionCategory, name="transaction_category"), nullable=False)
    amount = Column(Integer, nullable=False)  # The value processed
    status = Column(PG_ENUM(TransactionStatus, name="transaction_status"), nullable=False)
    tx_metadata = Column(JSONB, nullable=True)  # Snapshot of item title/icon at time of tx
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    wallet = relationship("WalletModel", backref="transactions")
    market_item = relationship("MarketItemModel", backref="transactions")
    
    # Constraints and indexes
    __table_args__ = (
        CheckConstraint('amount > 0', name='ck_transaction_amount_positive'),
        Index('ix_transactions_wallet_id', 'wallet_id'),
        Index('ix_transactions_market_item_id', 'market_item_id'),
        Index('ix_transactions_status', 'status'),
        Index('ix_transactions_created_at', 'created_at'),
    )
    
    def to_entity(self):
        """Convert to domain entity."""
        from app.domain.market.models import Transaction
        return Transaction(
            id=self.id,
            wallet_id=self.wallet_id,
            market_item_id=self.market_item_id,
            category=self.category,
            amount=self.amount,
            status=self.status,
            metadata=self.tx_metadata,
            created_at=self.created_at,
            completed_at=self.completed_at,
        )
    
    @classmethod
    def from_entity(cls, entity):
        """Create from domain entity."""
        return cls(
            id=entity.id,
            wallet_id=entity.wallet_id,
            market_item_id=entity.market_item_id,
            category=entity.category,
            amount=entity.amount,
            status=entity.status,
            tx_metadata=entity.metadata,
            created_at=entity.created_at,
            completed_at=entity.completed_at,
        )
