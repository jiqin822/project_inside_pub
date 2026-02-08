"""Market API routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.admin.models import User
from app.domain.market.models import TransactionCategory, TransactionStatus
from app.domain.market.services import MarketService
from app.infra.db.repositories.market_repo import MarketRepositoryImpl
from app.services.notification_service import deliver_notification

router = APIRouter()


# Request/Response Models
class EconomySettingsResponse(BaseModel):
    """Economy settings response."""
    user_id: str
    currency_name: str
    currency_symbol: str


class EconomySettingsRequest(BaseModel):
    """Economy settings request."""
    currency_name: str
    currency_symbol: str


class MarketItemResponse(BaseModel):
    """Market item response."""
    id: str
    issuer_id: str
    title: str
    description: Optional[str]
    cost: int
    icon: Optional[str]
    category: str
    is_active: bool
    visible_to_relationship_ids: Optional[List[str]] = None


class MarketItemRequest(BaseModel):
    """Market item request."""
    title: str
    description: Optional[str] = None
    cost: int
    icon: Optional[str] = None
    category: str  # "SPEND" or "EARN"
    relationship_ids: Optional[List[str]] = None  # List of relationship IDs that can see this item. If None/empty, available to all loved ones. Issuer can always see their own items.


class MarketResponse(BaseModel):
    """Market response (catalog + balance)."""
    items: List[MarketItemResponse]
    balance: int
    currency_name: str
    currency_symbol: str


class PurchaseRequest(BaseModel):
    """Purchase request."""
    item_id: str
    issuer_id: str


class TransactionResponse(BaseModel):
    """Transaction response."""
    id: str
    wallet_id: str
    market_item_id: Optional[str]
    category: str
    amount: int
    status: str
    metadata: Optional[dict]
    created_at: str
    completed_at: Optional[str]


# Economy Configuration
@router.get("/me/economy", response_model=EconomySettingsResponse)
async def get_my_economy(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's economy settings."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    settings = await service.get_economy_settings(current_user.id)
    if not settings:
        # Return default if not set
        return EconomySettingsResponse(
            user_id=current_user.id,
            currency_name="Love Tokens",
            currency_symbol="🪙",
        )
    
    return EconomySettingsResponse(
        user_id=settings.user_id,
        currency_name=settings.currency_name,
        currency_symbol=settings.currency_symbol,
    )


@router.put("/me/economy", response_model=EconomySettingsResponse)
async def update_my_economy(
    request: EconomySettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's economy settings."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    settings = await service.create_or_update_economy_settings(
        user_id=current_user.id,
        currency_name=request.currency_name,
        currency_symbol=request.currency_symbol,
    )
    
    return EconomySettingsResponse(
        user_id=settings.user_id,
        currency_name=settings.currency_name,
        currency_symbol=settings.currency_symbol,
    )


# Marketplace Viewing
@router.get("/profiles/{user_id}/market", response_model=MarketResponse)
async def get_user_market(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get market catalog for a user and current user's balance in that currency."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    # Get issuer's economy settings
    economy_settings = await service.get_economy_settings(user_id)
    if not economy_settings:
        economy_settings = await service.create_or_update_economy_settings(
            user_id=user_id,
            currency_name="Love Tokens",
            currency_symbol="🪙",
        )
    
    # Get the relationship ID between issuer and current user (if they have one)
    relationship_id = None
    try:
        from app.domain.admin.services import RelationshipService, UserRepository
        from app.infra.db.repositories.relationship_repo import RelationshipRepositoryImpl
        from app.infra.db.repositories.user_repo import UserRepositoryImpl
        
        relationship_repo = RelationshipRepositoryImpl(db)
        user_repo = UserRepositoryImpl(db)
        relationship_service = RelationshipService(relationship_repo, user_repo)
        
        # Get all relationships for current user
        relationships = await relationship_service.list_user_relationships(current_user.id)
        # Find relationship that includes both issuer and current user
        for rel in relationships:
            # Get members of this relationship
            members = await relationship_repo.get_members(rel.id)
            member_ids = [m.user_id for m in members]
            if user_id in member_ids and current_user.id in member_ids:
                relationship_id = rel.id
                break
    except Exception as e:
        # If we can't find relationship, relationship_id stays None (items available to all will still show)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not find relationship between {current_user.id} and {user_id}: {e}")
    
    # Get market items, filtered by relationship if available
    # Pass viewer_id to handle case where user views their own market
    items = await service.get_market_items(
        user_id, 
        active_only=True, 
        relationship_id=relationship_id,
        viewer_id=current_user.id
    )
    
    # Get current user's balance in issuer's currency
    balance = await service.get_wallet_balance(user_id, current_user.id)
    
    return MarketResponse(
        items=[
            MarketItemResponse(
                id=item.id,
                issuer_id=item.issuer_id,
                title=item.title,
                description=item.description,
                cost=item.cost,
                icon=item.icon,
                category=item.category.value,
                is_active=item.is_active,
                visible_to_relationship_ids=item.visible_to_relationship_ids,
            )
            for item in items
        ],
        balance=balance,
        currency_name=economy_settings.currency_name,
        currency_symbol=economy_settings.currency_symbol,
    )


# Market Item Management
@router.post("/items", response_model=MarketItemResponse)
async def create_market_item(
    request: MarketItemRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a market item (Issuer only)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        category = TransactionCategory(request.category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid category. Must be 'SPEND' or 'EARN'",
        )
    
    item = await service.create_market_item(
        issuer_id=current_user.id,
        title=request.title,
        description=request.description,
        cost=request.cost,
        icon=request.icon,
        category=category,
        relationship_ids=request.relationship_ids,
    )
    
    return MarketItemResponse(
        id=item.id,
        issuer_id=item.issuer_id,
        title=item.title,
        description=item.description,
        cost=item.cost,
        icon=item.icon,
        category=item.category.value,
        is_active=item.is_active,
        visible_to_relationship_ids=item.visible_to_relationship_ids,
    )


@router.delete("/items/{item_id}")
async def delete_market_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a market item (soft delete)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        await service.delete_market_item(item_id, current_user.id)
        return {"message": "Item deleted successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Transactional Operations
@router.get("/wallets/transactions", response_model=List[TransactionResponse])
async def get_my_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get transaction history for the logged-in user."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    transactions = await service.get_transaction_history(current_user.id)
    
    return [
        TransactionResponse(
            id=tx.id,
            wallet_id=tx.wallet_id,
            market_item_id=tx.market_item_id,
            category=tx.category.value,
            amount=tx.amount,
            status=tx.status.value,
            metadata=tx.metadata,
            created_at=tx.created_at.isoformat(),
            completed_at=tx.completed_at.isoformat() if tx.completed_at else None,
        )
        for tx in transactions
    ]


class VerificationRequestResponse(BaseModel):
    """Verification request response with holder information."""
    id: str
    wallet_id: str
    market_item_id: Optional[str]
    category: str
    amount: int
    status: str
    metadata: Optional[dict]
    created_at: str
    completed_at: Optional[str]
    holder_id: str  # ID of the user who completed the task
    holder_name: Optional[str] = None  # Name of the holder (if available)


@router.get("/verification-requests", response_model=List[VerificationRequestResponse])
async def get_pending_verifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get pending verification requests for the logged-in user (as issuer)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    transactions = await service.get_pending_verifications(current_user.id)
    
    # Enrich with holder information
    from app.infra.db.repositories.user_repo import UserRepositoryImpl
    from app.domain.admin.services import UserRepository
    user_repo: UserRepository = UserRepositoryImpl(db)
    
    result = []
    for tx in transactions:
        # Get wallet to find holder_id
        wallet = await repo.get_wallet_by_id(tx.wallet_id)
        holder_id = wallet.holder_id if wallet else None
        
        # Get holder name
        holder_name = None
        if holder_id:
            try:
                holder = await user_repo.get_by_id(holder_id)
                if holder:
                    holder_name = holder.display_name or holder.email
            except Exception:
                pass  # If we can't get holder name, leave it as None
        
        result.append(VerificationRequestResponse(
            id=tx.id,
            wallet_id=tx.wallet_id,
            market_item_id=tx.market_item_id,
            category=tx.category.value,
            amount=tx.amount,
            status=tx.status.value,
            metadata=tx.metadata,
            created_at=tx.created_at.isoformat(),
            completed_at=tx.completed_at.isoformat() if tx.completed_at else None,
            holder_id=holder_id or "",
            holder_name=holder_name,
        ))
    
    return result


@router.post("/transactions/purchase", response_model=TransactionResponse)
async def purchase_item(
    request: PurchaseRequest,
    current_user: User = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Purchase an item (Spend flow - PURCHASE)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        transaction = await service.purchase_item(
            item_id=request.item_id,
            issuer_id=request.issuer_id,
            holder_id=current_user.id,
            idempotency_key=idempotency_key,
        )
        # Notify buyer (inbox + WebSocket + push)
        item = await repo.get_market_item(request.item_id)
        title = item.title if item else "Item"
        await deliver_notification(db, current_user.id, "system", "Purchase Complete", f"{title} added to your vault.")
        # Notify issuer that someone purchased their offer
        if request.issuer_id != current_user.id:
            buyer_name = current_user.display_name or "Someone"
            await deliver_notification(db, request.issuer_id, "transaction", "Offer purchased", f"{buyer_name} purchased your offer: {title}.")
        return TransactionResponse(
            id=transaction.id,
            wallet_id=transaction.wallet_id,
            market_item_id=transaction.market_item_id,
            category=transaction.category.value,
            amount=transaction.amount,
            status=transaction.status.value,
            metadata=transaction.metadata,
            created_at=transaction.created_at.isoformat(),
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/transactions/{transaction_id}/redeem", response_model=TransactionResponse)
async def redeem_item(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Redeem a purchased item (Spend flow - REDEEM)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        transaction = await service.redeem_item(transaction_id, current_user.id)
        
        return TransactionResponse(
            id=transaction.id,
            wallet_id=transaction.wallet_id,
            market_item_id=transaction.market_item_id,
            category=transaction.category.value,
            amount=transaction.amount,
            status=transaction.status.value,
            metadata=transaction.metadata,
            created_at=transaction.created_at.isoformat(),
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/transactions/accept", response_model=TransactionResponse)
async def accept_task(
    request: PurchaseRequest,  # Reuse PurchaseRequest for item_id and issuer_id
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept a task (Earn flow - ACCEPT)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        transaction = await service.accept_task(
            item_id=request.item_id,
            issuer_id=request.issuer_id,
            holder_id=current_user.id,
        )
        # Notify holder (quest started; inbox + WebSocket + push)
        item = await repo.get_market_item(request.item_id)
        title = item.title if item else "Quest"
        await deliver_notification(db, current_user.id, "system", "Quest Started", f'"{title}" is now in your Vault.')
        # Notify issuer that someone accepted their bounty
        if request.issuer_id != current_user.id:
            holder_name = current_user.display_name or "Someone"
            await deliver_notification(db, request.issuer_id, "transaction", "Bounty accepted", f"{holder_name} accepted your bounty: {title}.")
        return TransactionResponse(
            id=transaction.id,
            wallet_id=transaction.wallet_id,
            market_item_id=transaction.market_item_id,
            category=transaction.category.value,
            amount=transaction.amount,
            status=transaction.status.value,
            metadata=transaction.metadata,
            created_at=transaction.created_at.isoformat(),
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/transactions/{transaction_id}/submit", response_model=TransactionResponse)
async def submit_for_review(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit task for review (Earn flow - SUBMIT_FOR_REVIEW)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        transaction = await service.submit_for_review(transaction_id, current_user.id)
        # Notify issuer that someone submitted a task for approval
        item = await repo.get_market_item(transaction.market_item_id) if transaction.market_item_id else None
        if item and item.issuer_id and item.issuer_id != current_user.id:
            holder_name = current_user.display_name or "Someone"
            await deliver_notification(db, item.issuer_id, "transaction", "Approval requested", f"{holder_name} submitted a task for your approval: {item.title}.")
        return TransactionResponse(
            id=transaction.id,
            wallet_id=transaction.wallet_id,
            market_item_id=transaction.market_item_id,
            category=transaction.category.value,
            amount=transaction.amount,
            status=transaction.status.value,
            metadata=transaction.metadata,
            created_at=transaction.created_at.isoformat(),
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/transactions/{transaction_id}/approve", response_model=TransactionResponse)
async def approve_task(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a task (Earn flow - APPROVE)."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        transaction = await service.approve_task(transaction_id, current_user.id)
        # Notify holder (bounty approved; inbox + WebSocket + push)
        wallet = await repo.get_wallet_by_id(transaction.wallet_id)
        if wallet and wallet.holder_id:
            await deliver_notification(db, wallet.holder_id, "reward", "Bounty Approved", "Currency transfer confirmed.")
        return TransactionResponse(
            id=transaction.id,
            wallet_id=transaction.wallet_id,
            market_item_id=transaction.market_item_id,
            category=transaction.category.value,
            amount=transaction.amount,
            status=transaction.status.value,
            metadata=transaction.metadata,
            created_at=transaction.created_at.isoformat(),
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/transactions/{transaction_id}/cancel", response_model=TransactionResponse)
async def cancel_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a transaction."""
    repo = MarketRepositoryImpl(db)
    service = MarketService(repo, db)
    
    try:
        transaction = await service.cancel_transaction(transaction_id, current_user.id)
        
        return TransactionResponse(
            id=transaction.id,
            wallet_id=transaction.wallet_id,
            market_item_id=transaction.market_item_id,
            category=transaction.category.value,
            amount=transaction.amount,
            status=transaction.status.value,
            metadata=transaction.metadata,
            created_at=transaction.created_at.isoformat(),
            completed_at=transaction.completed_at.isoformat() if transaction.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
