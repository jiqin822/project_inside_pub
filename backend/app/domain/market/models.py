"""Market domain models."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum


class TransactionCategory(str, Enum):
    """Transaction category enum."""
    SPEND = "SPEND"
    EARN = "EARN"


class TransactionStatus(str, Enum):
    """Transaction status enum."""
    PURCHASED = "PURCHASED"
    REDEEMED = "REDEEMED"
    ACCEPTED = "ACCEPTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    CANCELED = "CANCELED"


@dataclass
class EconomySettings:
    """Economy settings domain model."""
    user_id: str
    currency_name: str
    currency_symbol: str
    created_at: datetime
    updated_at: datetime


@dataclass
class Wallet:
    """Wallet domain model."""
    id: str
    issuer_id: str
    holder_id: str
    balance: int
    created_at: datetime
    updated_at: datetime


@dataclass
class MarketItem:
    """Market item domain model."""
    id: str
    issuer_id: str
    title: str
    description: Optional[str]
    cost: int
    icon: Optional[str]
    category: TransactionCategory
    is_active: bool
    created_at: datetime
    updated_at: datetime
    visible_to_relationship_ids: Optional[list[str]] = None  # List of relationship IDs that can see this item. If None, available to all. Issuer can always see their own items.


@dataclass
class Transaction:
    """Transaction domain model."""
    id: str
    wallet_id: str
    market_item_id: Optional[str]
    category: TransactionCategory
    amount: int
    status: TransactionStatus
    metadata: Optional[dict]  # Note: This is tx_metadata in the database model
    created_at: datetime
    completed_at: Optional[datetime]
