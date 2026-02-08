"""Market domain services."""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.common.types import generate_id
from app.domain.market.models import (
    EconomySettings,
    Wallet,
    MarketItem,
    Transaction,
    TransactionCategory,
    TransactionStatus,
)
from app.infra.db.repositories.market_repo import MarketRepository


class MarketService:
    """Market service for business logic."""
    
    def __init__(self, repo: MarketRepository, db: AsyncSession):
        self.repo = repo
        self.db = db
    
    # Economy Settings
    async def get_economy_settings(self, user_id: str) -> Optional[EconomySettings]:
        """Get economy settings for a user."""
        return await self.repo.get_economy_settings(user_id)
    
    async def create_or_update_economy_settings(
        self,
        user_id: str,
        currency_name: str,
        currency_symbol: str,
    ) -> EconomySettings:
        """Create or update economy settings."""
        now = datetime.utcnow()
        settings = EconomySettings(
            user_id=user_id,
            currency_name=currency_name,
            currency_symbol=currency_symbol,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.create_or_update_economy_settings(settings)
    
    # Wallets
    async def get_or_create_wallet(self, issuer_id: str, holder_id: str) -> Wallet:
        """Get or create wallet for issuer/holder pair."""
        wallet = await self.repo.get_wallet(issuer_id, holder_id)
        if wallet:
            return wallet
        
        # Create new wallet
        now = datetime.utcnow()
        wallet = Wallet(
            id=generate_id(),
            issuer_id=issuer_id,
            holder_id=holder_id,
            balance=0,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.create_wallet(wallet)
    
    async def get_wallet_balance(self, issuer_id: str, holder_id: str) -> int:
        """Get wallet balance."""
        wallet = await self.repo.get_wallet(issuer_id, holder_id)
        return wallet.balance if wallet else 0
    
    # Market Items
    async def create_market_item(
        self,
        issuer_id: str,
        title: str,
        description: Optional[str],
        cost: int,
        icon: Optional[str],
        category: TransactionCategory,
        relationship_ids: Optional[List[str]] = None,
    ) -> MarketItem:
        """Create a market item with optional relationship availability.
        
        Args:
            issuer_id: User creating the item
            title: Item title
            description: Item description
            cost: Item cost/reward
            icon: Item icon
            category: SPEND or EARN
            relationship_ids: List of relationship IDs that can see this item.
                            If None or empty, item is available to all relationships.
                            Note: Issuer can always see their own items regardless of this setting.
        """
        if cost <= 0:
            raise ValueError("Cost must be positive")
        
        now = datetime.utcnow()
        item = MarketItem(
            id=generate_id(),
            issuer_id=issuer_id,
            title=title,
            description=description,
            cost=cost,
            icon=icon,
            category=category,
            is_active=True,
            created_at=now,
            updated_at=now,
            visible_to_relationship_ids=relationship_ids,
        )
        return await self.repo.create_market_item(item, relationship_ids=relationship_ids)
    
    async def get_market_items(
        self, 
        issuer_id: str, 
        active_only: bool = True,
        relationship_id: Optional[str] = None,
        viewer_id: Optional[str] = None
    ) -> List[MarketItem]:
        """Get market items for an issuer, optionally filtered by relationship or viewer.
        
        Args:
            issuer_id: User whose items to fetch
            active_only: Only return active items
            relationship_id: If provided, only return items available to this relationship
            viewer_id: ID of user viewing the market. If equals issuer_id, returns all items (issuer can always see their own)
        """
        return await self.repo.get_market_items_by_issuer(issuer_id, active_only, relationship_id, viewer_id)
    
    async def delete_market_item(self, item_id: str, issuer_id: str) -> bool:
        """Delete a market item (soft delete)."""
        item = await self.repo.get_market_item(item_id)
        if not item:
            raise ValueError("Market item not found")
        if item.issuer_id != issuer_id:
            raise ValueError("Not authorized to delete this item")
        
        return await self.repo.delete_market_item(item_id)
    
    # Transactions - Spend Flow
    async def purchase_item(
        self,
        item_id: str,
        issuer_id: str,
        holder_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Transaction:
        """Purchase an item (Spend flow - PURCHASE)."""
        # Get market item
        item = await self.repo.get_market_item(item_id)
        if not item:
            raise ValueError("Market item not found")
        if item.issuer_id != issuer_id:
            raise ValueError("Item does not belong to this issuer")
        if item.category != TransactionCategory.SPEND:
            raise ValueError("Item is not a SPEND item")
        if not item.is_active:
            raise ValueError("Item is not active")
        
        # Get or create wallet with lock
        from app.infra.db.repositories.market_repo import MarketRepositoryImpl
        if isinstance(self.repo, MarketRepositoryImpl):
            wallet_model = await self.repo.get_wallet_for_update(issuer_id, holder_id)
            if not wallet_model:
                wallet = await self.get_or_create_wallet(issuer_id, holder_id)
                wallet_model = await self.repo.get_wallet_for_update(issuer_id, holder_id)
            else:
                wallet = wallet_model.to_entity()
        else:
            wallet = await self.get_or_create_wallet(issuer_id, holder_id)
            wallet_model = None
        
        # Check balance
        if wallet.balance < item.cost:
            raise ValueError(f"Insufficient balance. Required: {item.cost}, Available: {wallet.balance}")
        
        # Check for duplicate transaction (idempotency)
        if idempotency_key:
            # In a real implementation, you'd check for existing transaction with this key
            pass
        
        # Decrement balance
        new_balance = wallet.balance - item.cost
        if wallet_model:
            wallet_model.balance = new_balance
            wallet_model.updated_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(wallet_model)
            wallet = wallet_model.to_entity()
        else:
            wallet = await self.repo.update_wallet_balance(wallet.id, new_balance)
        
        # Create transaction
        now = datetime.utcnow()
        transaction = Transaction(
            id=generate_id(),
            wallet_id=wallet.id,
            market_item_id=item_id,
            category=TransactionCategory.SPEND,
            amount=item.cost,
            status=TransactionStatus.PURCHASED,
            metadata={
                "title": item.title,
                "icon": item.icon,
                "idempotency_key": idempotency_key,
            },
            created_at=now,
            completed_at=None,
        )
        return await self.repo.create_transaction(transaction)
    
    async def redeem_item(self, transaction_id: str, holder_id: str) -> Transaction:
        """Redeem a purchased item (Spend flow - REDEEM)."""
        transaction = await self.repo.get_transaction(transaction_id)
        if not transaction:
            raise ValueError("Transaction not found")
        
        # Verify holder owns this transaction
        wallet = await self.repo.get_wallet_by_id(transaction.wallet_id)
        if not wallet or wallet.holder_id != holder_id:
            raise ValueError("Not authorized to redeem this transaction")
        
        if transaction.status != TransactionStatus.PURCHASED:
            raise ValueError(f"Cannot redeem transaction with status: {transaction.status}")
        
        # Update status
        return await self.repo.update_transaction_status(
            transaction_id,
            TransactionStatus.REDEEMED,
            datetime.utcnow(),
        )
    
    # Transactions - Earn Flow
    async def accept_task(
        self,
        item_id: str,
        issuer_id: str,
        holder_id: str,
    ) -> Transaction:
        """Accept a task (Earn flow - ACCEPT)."""
        # Get market item
        item = await self.repo.get_market_item(item_id)
        if not item:
            raise ValueError("Market item not found")
        if item.issuer_id != issuer_id:
            raise ValueError("Item does not belong to this issuer")
        if item.category != TransactionCategory.EARN:
            raise ValueError("Item is not an EARN item")
        if not item.is_active:
            raise ValueError("Item is not active")
        
        # Get or create wallet
        wallet = await self.get_or_create_wallet(issuer_id, holder_id)
        
        # Create transaction
        now = datetime.utcnow()
        transaction = Transaction(
            id=generate_id(),
            wallet_id=wallet.id,
            market_item_id=item_id,
            category=TransactionCategory.EARN,
            amount=item.cost,
            status=TransactionStatus.ACCEPTED,
            metadata={
                "title": item.title,
                "icon": item.icon,
            },
            created_at=now,
            completed_at=None,
        )
        return await self.repo.create_transaction(transaction)
    
    async def submit_for_review(self, transaction_id: str, holder_id: str) -> Transaction:
        """Submit task for review (Earn flow - SUBMIT_FOR_REVIEW)."""
        transaction = await self.repo.get_transaction(transaction_id)
        if not transaction:
            raise ValueError("Transaction not found")
        
        # Verify holder owns this transaction
        wallet = await self.repo.get_wallet_by_id(transaction.wallet_id)
        if not wallet or wallet.holder_id != holder_id:
            raise ValueError("Not authorized to submit this transaction")
        
        if transaction.status != TransactionStatus.ACCEPTED:
            raise ValueError(f"Cannot submit transaction with status: {transaction.status}")
        
        # Update status
        return await self.repo.update_transaction_status(
            transaction_id,
            TransactionStatus.PENDING_APPROVAL,
        )
    
    async def approve_task(
        self,
        transaction_id: str,
        issuer_id: str,
    ) -> Transaction:
        """Approve a task (Earn flow - APPROVE)."""
        transaction = await self.repo.get_transaction(transaction_id)
        if not transaction:
            raise ValueError("Transaction not found")
        
        # Get wallet to verify issuer
        wallet = await self.repo.get_wallet_by_id(transaction.wallet_id)
        if not wallet or wallet.issuer_id != issuer_id:
            raise ValueError("Not authorized to approve this transaction")
        
        if transaction.status != TransactionStatus.PENDING_APPROVAL:
            raise ValueError(f"Cannot approve transaction with status: {transaction.status}")
        
        # Get wallet with lock and increment balance
        from app.infra.db.repositories.market_repo import MarketRepositoryImpl
        if isinstance(self.repo, MarketRepositoryImpl):
            wallet_model = await self.repo.get_wallet_for_update(wallet.issuer_id, wallet.holder_id)
            if wallet_model:
                new_balance = wallet_model.balance + transaction.amount
                wallet_model.balance = new_balance
                wallet_model.updated_at = datetime.utcnow()
                await self.db.commit()
                await self.db.refresh(wallet_model)
        
        # Update transaction status
        return await self.repo.update_transaction_status(
            transaction_id,
            TransactionStatus.APPROVED,
            datetime.utcnow(),
        )
    
    async def cancel_transaction(
        self,
        transaction_id: str,
        user_id: str,
    ) -> Transaction:
        """Cancel a transaction (either party can cancel)."""
        transaction = await self.repo.get_transaction(transaction_id)
        if not transaction:
            raise ValueError("Transaction not found")
        
        # Verify user is involved in this transaction
        wallet = await self.repo.get_wallet_by_id(transaction.wallet_id)
        if not wallet:
            raise ValueError("Wallet not found")
        
        if wallet.issuer_id != user_id and wallet.holder_id != user_id:
            raise ValueError("Not authorized to cancel this transaction")
        
        # Only allow canceling if not already completed
        if transaction.status in [TransactionStatus.APPROVED, TransactionStatus.REDEEMED]:
            raise ValueError(f"Cannot cancel transaction with status: {transaction.status}")
        
        # Update status
        return await self.repo.update_transaction_status(
            transaction_id,
            TransactionStatus.CANCELED,
        )
    
    # Query methods
    async def get_transaction_history(self, holder_id: str) -> List[Transaction]:
        """Get transaction history for a holder."""
        return await self.repo.get_transactions_by_holder(holder_id)
    
    async def get_pending_verifications(self, issuer_id: str) -> List[Transaction]:
        """Get pending verification requests for an issuer (transactions waiting for approval)."""
        return await self.repo.get_transactions_by_issuer(
            issuer_id, 
            status=TransactionStatus.PENDING_APPROVAL
        )
    
    async def get_wallet_transactions(self, issuer_id: str, holder_id: str) -> List[Transaction]:
        """Get transactions for a specific wallet."""
        wallet = await self.repo.get_wallet(issuer_id, holder_id)
        if not wallet:
            return []
        return await self.repo.get_transactions_by_wallet(wallet.id)
