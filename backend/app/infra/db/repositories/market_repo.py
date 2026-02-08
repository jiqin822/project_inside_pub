"""Market repository implementation."""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from sqlalchemy.orm import selectinload

from app.domain.market.models import (
    EconomySettings,
    Wallet,
    MarketItem,
    Transaction,
    TransactionCategory,
    TransactionStatus,
)
from app.infra.db.models.market import (
    EconomySettingsModel,
    WalletModel,
    MarketItemModel,
    TransactionModel,
)


class MarketRepository:
    """Market repository interface."""
    
    # Economy Settings
    async def get_economy_settings(self, user_id: str) -> Optional[EconomySettings]:
        """Get economy settings for a user."""
        raise NotImplementedError
    
    async def create_or_update_economy_settings(self, settings: EconomySettings) -> EconomySettings:
        """Create or update economy settings."""
        raise NotImplementedError
    
    # Wallets
    async def get_wallet(self, issuer_id: str, holder_id: str) -> Optional[Wallet]:
        """Get wallet for issuer/holder pair."""
        raise NotImplementedError
    
    async def create_wallet(self, wallet: Wallet) -> Wallet:
        """Create a new wallet."""
        raise NotImplementedError
    
    async def update_wallet_balance(self, wallet_id: str, new_balance: int) -> Wallet:
        """Update wallet balance (with locking)."""
        raise NotImplementedError
    
    async def get_wallets_by_holder(self, holder_id: str) -> List[Wallet]:
        """Get all wallets for a holder."""
        raise NotImplementedError
    
    # Market Items
    async def create_market_item(self, item: MarketItem, relationship_ids: Optional[List[str]] = None) -> MarketItem:
        """Create a market item with optional relationship associations."""
        raise NotImplementedError
    
    async def get_market_item(self, item_id: str) -> Optional[MarketItem]:
        """Get market item by ID."""
        raise NotImplementedError
    
    async def get_market_items_by_issuer(
        self, 
        issuer_id: str, 
        active_only: bool = True,
        relationship_id: Optional[str] = None
    ) -> List[MarketItem]:
        """Get market items for an issuer, optionally filtered by relationship."""
        raise NotImplementedError
    
    async def update_market_item(self, item: MarketItem) -> MarketItem:
        """Update market item."""
        raise NotImplementedError
    
    async def delete_market_item(self, item_id: str) -> bool:
        """Soft delete market item."""
        raise NotImplementedError
    
    # Transactions
    async def create_transaction(self, transaction: Transaction) -> Transaction:
        """Create a transaction."""
        raise NotImplementedError
    
    async def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        raise NotImplementedError
    
    async def get_transactions_by_wallet(self, wallet_id: str) -> List[Transaction]:
        """Get all transactions for a wallet."""
        raise NotImplementedError
    
    async def get_transactions_by_holder(self, holder_id: str) -> List[Transaction]:
        """Get all transactions for a holder (across all wallets)."""
        raise NotImplementedError
    
    async def get_transactions_by_issuer(self, issuer_id: str, status: Optional[TransactionStatus] = None) -> List[Transaction]:
        """Get all transactions for an issuer (across all wallets), optionally filtered by status."""
        raise NotImplementedError
    
    async def update_transaction_status(self, transaction_id: str, status: TransactionStatus, completed_at: Optional[datetime] = None) -> Transaction:
        """Update transaction status."""
        raise NotImplementedError


class MarketRepositoryImpl(MarketRepository):
    """Market repository implementation."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # Economy Settings
    async def get_economy_settings(self, user_id: str) -> Optional[EconomySettings]:
        """Get economy settings for a user."""
        result = await self.session.execute(
            select(EconomySettingsModel).where(EconomySettingsModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None
    
    async def create_or_update_economy_settings(self, settings: EconomySettings) -> EconomySettings:
        """Create or update economy settings."""
        result = await self.session.execute(
            select(EconomySettingsModel).where(EconomySettingsModel.user_id == settings.user_id)
        )
        model = result.scalar_one_or_none()
        
        if model:
            model.currency_name = settings.currency_name
            model.currency_symbol = settings.currency_symbol
            model.updated_at = settings.updated_at
        else:
            model = EconomySettingsModel.from_entity(settings)
            self.session.add(model)
        
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()
    
    # Wallets
    async def get_wallet(self, issuer_id: str, holder_id: str) -> Optional[Wallet]:
        """Get wallet for issuer/holder pair."""
        result = await self.session.execute(
            select(WalletModel).where(
                and_(
                    WalletModel.issuer_id == issuer_id,
                    WalletModel.holder_id == holder_id
                )
            )
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None
    
    async def get_wallet_for_update(self, issuer_id: str, holder_id: str) -> Optional[WalletModel]:
        """Get wallet with row-level lock for update."""
        result = await self.session.execute(
            select(WalletModel)
            .where(
                and_(
                    WalletModel.issuer_id == issuer_id,
                    WalletModel.holder_id == holder_id
                )
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()
    
    async def create_wallet(self, wallet: Wallet) -> Wallet:
        """Create a new wallet."""
        model = WalletModel.from_entity(wallet)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()
    
    async def update_wallet_balance(self, wallet_id: str, new_balance: int) -> Wallet:
        """Update wallet balance."""
        await self.session.execute(
            update(WalletModel)
            .where(WalletModel.id == wallet_id)
            .values(balance=new_balance)
        )
        await self.session.commit()
        
        result = await self.session.execute(
            select(WalletModel).where(WalletModel.id == wallet_id)
        )
        model = result.scalar_one()
        return model.to_entity()
    
    async def get_wallet_by_id(self, wallet_id: str) -> Optional[Wallet]:
        """Get wallet by ID."""
        result = await self.session.execute(
            select(WalletModel).where(WalletModel.id == wallet_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None
    
    async def get_wallets_by_holder(self, holder_id: str) -> List[Wallet]:
        """Get all wallets for a holder."""
        result = await self.session.execute(
            select(WalletModel).where(WalletModel.holder_id == holder_id)
        )
        models = result.scalars().all()
        return [model.to_entity() for model in models]
    
    # Market Items
    async def create_market_item(self, item: MarketItem, relationship_ids: Optional[List[str]] = None) -> MarketItem:
        """Create a market item with optional relationship associations."""
        model = MarketItemModel.from_entity(item)
        self.session.add(model)
        
        # If relationship_ids are provided, associate the item with those relationships
        if relationship_ids:
            from app.infra.db.models.relationship import RelationshipModel
            from app.infra.db.models.market import market_item_relationships
            
            # Fetch the relationship models
            result = await self.session.execute(
                select(RelationshipModel).where(RelationshipModel.id.in_(relationship_ids))
            )
            relationships = result.scalars().all()
            model.visible_to_relationships = list(relationships)
        
        await self.session.commit()
        await self.session.refresh(model)
        # Eager load relationships for to_entity conversion
        await self.session.refresh(model, ['visible_to_relationships'])
        return model.to_entity()
    
    async def get_market_item(self, item_id: str) -> Optional[MarketItem]:
        """Get market item by ID."""
        from sqlalchemy.orm import selectinload
        result = await self.session.execute(
            select(MarketItemModel)
            .options(selectinload(MarketItemModel.visible_to_relationships))
            .where(MarketItemModel.id == item_id)
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None
    
    async def get_market_items_by_issuer(
        self, 
        issuer_id: str, 
        active_only: bool = True,
        relationship_id: Optional[str] = None,
        viewer_id: Optional[str] = None  # ID of user viewing the market
    ) -> List[MarketItem]:
        """Get market items for an issuer, optionally filtered by relationship.
        
        If relationship_id is provided, only returns items that:
        - Have no visible_to_relationships (available to all), OR
        - Include the specified relationship_id in visible_to_relationships
        
        If viewer_id is provided and equals issuer_id, the issuer can always see their own items
        (no filtering needed - they can see all their own listings).
        """
        from sqlalchemy.orm import selectinload
        from sqlalchemy import or_, exists
        from app.infra.db.models.market import market_item_relationships
        
        query = (
            select(MarketItemModel)
            .options(selectinload(MarketItemModel.visible_to_relationships))
            .where(MarketItemModel.issuer_id == issuer_id)
        )
        if active_only:
            query = query.where(MarketItemModel.is_active == True)
        
        # If viewer is the issuer themselves, they can see all their own items (no filtering)
        # Otherwise, filter by relationship if provided
        if viewer_id and viewer_id == issuer_id:
            # Issuer viewing their own market - show all items (no filtering)
            pass
        elif relationship_id:
            # Items available to all (no relationships) OR items available to this relationship
            subquery = exists().where(
                (market_item_relationships.c.market_item_id == MarketItemModel.id) &
                (market_item_relationships.c.relationship_id == relationship_id)
            )
            query = query.where(
                or_(
                    ~exists().where(
                        market_item_relationships.c.market_item_id == MarketItemModel.id
                    ),  # No relationships = available to all
                    subquery  # Available to this relationship
                )
            ).distinct()
        
        query = query.order_by(MarketItemModel.created_at.desc())
        
        result = await self.session.execute(query)
        models = result.scalars().all()
        return [model.to_entity() for model in models]
    
    async def update_market_item(self, item: MarketItem) -> MarketItem:
        """Update market item."""
        await self.session.execute(
            update(MarketItemModel)
            .where(MarketItemModel.id == item.id)
            .values(
                title=item.title,
                description=item.description,
                cost=item.cost,
                icon=item.icon,
                category=item.category,
                is_active=item.is_active,
                updated_at=item.updated_at,
            )
        )
        await self.session.commit()
        
        result = await self.session.execute(
            select(MarketItemModel).where(MarketItemModel.id == item.id)
        )
        model = result.scalar_one()
        return model.to_entity()
    
    async def delete_market_item(self, item_id: str) -> bool:
        """Soft delete market item."""
        await self.session.execute(
            update(MarketItemModel)
            .where(MarketItemModel.id == item_id)
            .values(is_active=False)
        )
        await self.session.commit()
        return True
    
    # Transactions
    async def create_transaction(self, transaction: Transaction) -> Transaction:
        """Create a transaction."""
        model = TransactionModel.from_entity(transaction)
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model.to_entity()
    
    async def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        result = await self.session.execute(
            select(TransactionModel)
            .where(TransactionModel.id == transaction_id)
            .options(selectinload(TransactionModel.wallet), selectinload(TransactionModel.market_item))
        )
        model = result.scalar_one_or_none()
        return model.to_entity() if model else None
    
    async def get_transactions_by_wallet(self, wallet_id: str) -> List[Transaction]:
        """Get all transactions for a wallet."""
        result = await self.session.execute(
            select(TransactionModel)
            .where(TransactionModel.wallet_id == wallet_id)
            .order_by(TransactionModel.created_at.desc())
        )
        models = result.scalars().all()
        return [model.to_entity() for model in models]
    
    async def get_transactions_by_holder(self, holder_id: str) -> List[Transaction]:
        """Get all transactions for a holder (across all wallets)."""
        result = await self.session.execute(
            select(TransactionModel)
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .where(WalletModel.holder_id == holder_id)
            .order_by(TransactionModel.created_at.desc())
        )
        models = result.scalars().all()
        return [model.to_entity() for model in models]
    
    async def get_transactions_by_issuer(self, issuer_id: str, status: Optional[TransactionStatus] = None) -> List[Transaction]:
        """Get all transactions for an issuer (across all wallets), optionally filtered by status."""
        query = (
            select(TransactionModel)
            .join(WalletModel, TransactionModel.wallet_id == WalletModel.id)
            .where(WalletModel.issuer_id == issuer_id)
        )
        if status:
            query = query.where(TransactionModel.status == status)
        query = query.order_by(TransactionModel.created_at.desc())
        
        result = await self.session.execute(query)
        models = result.scalars().all()
        return [model.to_entity() for model in models]
    
    async def update_transaction_status(self, transaction_id: str, status: TransactionStatus, completed_at: Optional[datetime] = None) -> Transaction:
        """Update transaction status."""
        from datetime import datetime
        update_values = {"status": status}
        if completed_at:
            update_values["completed_at"] = completed_at
        elif status in [TransactionStatus.APPROVED, TransactionStatus.REDEEMED]:
            update_values["completed_at"] = datetime.utcnow()
        
        await self.session.execute(
            update(TransactionModel)
            .where(TransactionModel.id == transaction_id)
            .values(**update_values)
        )
        await self.session.commit()
        
        result = await self.session.execute(
            select(TransactionModel).where(TransactionModel.id == transaction_id)
        )
        model = result.scalar_one()
        return model.to_entity()
