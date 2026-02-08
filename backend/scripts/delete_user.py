"""Script to delete a user and all related records."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import AsyncSessionLocal
from app.infra.db.models.user import UserModel
from app.infra.db.models.market import TransactionModel, WalletModel, MarketItemModel, EconomySettingsModel
from app.infra.db.models.love_map import UserSpecModel, RelationshipMapProgressModel
from app.infra.db.models.events import PokeEventModel
from app.infra.db.models.session import SessionModel, session_participants
from app.infra.db.models.invite import RelationshipInviteModel
from app.infra.db.models.relationship import relationship_members, RelationshipModel
from app.infra.db.models.voice import VoiceEnrollmentModel, VoiceProfileModel
from app.infra.db.models.onboarding import OnboardingProgressModel
from app.infra.db.models.lounge import (
    LoungeRoomModel,
    LoungeMemberModel,
    LoungeMessageModel,
    LoungeKaiContextModel,
    LoungeEventModel,
    LoungeKaiUserPreferenceModel,
)
from app.infra.db.models.compass import (
    CompassEventModel,
    UnstructuredMemoryModel,
    ThingToFindOutModel,
    MemoryModel,
    PersonPortraitModel,
    DyadPortraitModel,
    RelationshipLoopModel,
    DyadActivityHistoryModel,
    ActivityInviteModel,
    PlannedActivityModel,
    DiscoverFeedItemModel,
    DiscoverDismissalModel,
    ActivityWantToTryModel,
    ActivityMutualMatchModel,
    ContextSummaryModel,
)


async def delete_user_by_email_with_session(session: AsyncSession, email: str) -> bool:
    """Delete a user and all related records using the given session. Caller must commit.
    Returns True if user was found and deleted, False if not found."""
    result = await session.execute(
        select(UserModel).where(UserModel.email == email)
    )
    user = result.scalar_one_or_none()

    if not user:
        return False

    user_id = user.id
            
    # Delete related records in order (child tables first)
    # 1. Market: Transactions (has CASCADE, but delete explicitly for clarity)
    tx_count = await session.execute(
        select(TransactionModel).where(
            (TransactionModel.wallet_id.in_(
                select(WalletModel.id).where(
                    (WalletModel.issuer_id == user_id) | (WalletModel.holder_id == user_id)
                )
            ))
        )
    )
    transactions = tx_count.scalars().all()
    if transactions:
        await session.execute(
            delete(TransactionModel).where(
                TransactionModel.id.in_([tx.id for tx in transactions])
            )
        )

    # 2. Market: Wallets (has CASCADE)
    wallet_count = await session.execute(
        select(WalletModel).where(
            (WalletModel.issuer_id == user_id) | (WalletModel.holder_id == user_id)
        )
    )
    wallets = wallet_count.scalars().all()
    if wallets:
        await session.execute(
            delete(WalletModel).where(
                (WalletModel.issuer_id == user_id) | (WalletModel.holder_id == user_id)
            )
        )

    # 3. Market: Market Items (has CASCADE)
    items_count = await session.execute(
        select(MarketItemModel).where(MarketItemModel.issuer_id == user_id)
    )
    items = items_count.scalars().all()
    if items:
        await session.execute(
            delete(MarketItemModel).where(MarketItemModel.issuer_id == user_id)
        )

    # 4. Market: Economy Settings (has CASCADE)
    await session.execute(
        delete(EconomySettingsModel).where(EconomySettingsModel.user_id == user_id)
    )

    # 5. Love Map: Relationship Map Progress
    await session.execute(
        delete(RelationshipMapProgressModel).where(
            (RelationshipMapProgressModel.observer_id == user_id) |
            (RelationshipMapProgressModel.subject_id == user_id)
        )
    )

    # 6. Love Map: User Specs
    await session.execute(
        delete(UserSpecModel).where(UserSpecModel.user_id == user_id)
    )

    # 7. Events: Poke Events
    await session.execute(
        delete(PokeEventModel).where(
            (PokeEventModel.sender_id == user_id) | (PokeEventModel.receiver_id == user_id)
        )
    )

    # 8. Sessions: Session Participants
    await session.execute(
        delete(session_participants).where(session_participants.c.user_id == user_id)
    )

    # 9. Sessions: Sessions (where user is creator)
    await session.execute(
        delete(SessionModel).where(SessionModel.created_by_user_id == user_id)
    )

    # 10. Invites: Relationship Invites (as inviter or invitee)
    await session.execute(
        delete(RelationshipInviteModel).where(
            (RelationshipInviteModel.inviter_user_id == user_id) |
            (RelationshipInviteModel.invitee_user_id == user_id)
        )
    )

    # 11. Relationships: Relationship Members
    await session.execute(
        delete(relationship_members).where(relationship_members.c.user_id == user_id)
    )

    # 12. Relationships: Relationships (where user is creator)
    rel_count = await session.execute(
        select(RelationshipModel).where(RelationshipModel.created_by_user_id == user_id)
    )
    relationships = rel_count.scalars().all()
    if relationships:
        relationship_ids = [rel.id for rel in relationships]
        await session.execute(
            delete(relationship_members).where(
                relationship_members.c.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(PokeEventModel).where(PokeEventModel.relationship_id.in_(relationship_ids))
        )
        await session.execute(
            delete(RelationshipInviteModel).where(
                RelationshipInviteModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(SessionModel).where(SessionModel.relationship_id.in_(relationship_ids))
        )
        # Compass/love-map: delete all tables that reference relationship_id (child tables first)
        await session.execute(
            delete(DiscoverDismissalModel).where(
                DiscoverDismissalModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(ActivityWantToTryModel).where(
                ActivityWantToTryModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(ActivityMutualMatchModel).where(
                ActivityMutualMatchModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(DiscoverFeedItemModel).where(
                DiscoverFeedItemModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(PlannedActivityModel).where(
                PlannedActivityModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(ActivityInviteModel).where(
                ActivityInviteModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(DyadActivityHistoryModel).where(
                DyadActivityHistoryModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(RelationshipLoopModel).where(
                RelationshipLoopModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(DyadPortraitModel).where(
                DyadPortraitModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(PersonPortraitModel).where(
                PersonPortraitModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(MemoryModel).where(
                MemoryModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(UnstructuredMemoryModel).where(
                UnstructuredMemoryModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(ThingToFindOutModel).where(
                ThingToFindOutModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(ContextSummaryModel).where(
                ContextSummaryModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(CompassEventModel).where(
                CompassEventModel.relationship_id.in_(relationship_ids)
            )
        )
        await session.execute(
            delete(RelationshipModel).where(RelationshipModel.created_by_user_id == user_id)
        )

    # 12b. Compass: unstructured memories owned by user (may exist outside deleted relationships)
    await session.execute(
        delete(UnstructuredMemoryModel).where(
            UnstructuredMemoryModel.owner_user_id == user_id
        )
    )

    # 13. Voice: Voice Enrollments
    await session.execute(
        delete(VoiceEnrollmentModel).where(VoiceEnrollmentModel.user_id == user_id)
    )

    # 14. Voice: Voice Profiles
    await session.execute(
        delete(VoiceProfileModel).where(VoiceProfileModel.user_id == user_id)
    )

    # 15. Onboarding: Onboarding Progress
    await session.execute(
        delete(OnboardingProgressModel).where(OnboardingProgressModel.user_id == user_id)
    )

    # 15b. Lounge: rooms owned by user (child tables first; use subquery so deletes see consistent set)
    rooms_owned = select(LoungeRoomModel.id).where(
        LoungeRoomModel.owner_user_id == user_id
    )
    await session.execute(
        delete(LoungeMessageModel).where(LoungeMessageModel.room_id.in_(rooms_owned))
    )
    await session.execute(
        delete(LoungeEventModel).where(LoungeEventModel.room_id.in_(rooms_owned))
    )
    await session.execute(
        delete(LoungeKaiContextModel).where(
            LoungeKaiContextModel.room_id.in_(rooms_owned)
        )
    )
    await session.execute(
        delete(LoungeMemberModel).where(LoungeMemberModel.room_id.in_(rooms_owned))
    )
    await session.execute(
        delete(LoungeKaiUserPreferenceModel).where(
            LoungeKaiUserPreferenceModel.room_id.in_(rooms_owned)
        )
    )
    await session.execute(
        delete(LoungeRoomModel).where(LoungeRoomModel.owner_user_id == user_id)
    )
    await session.execute(
        delete(LoungeMemberModel).where(LoungeMemberModel.user_id == user_id)
    )
    await session.execute(
        delete(LoungeKaiUserPreferenceModel).where(
            LoungeKaiUserPreferenceModel.user_id == user_id
        )
    )
    await session.execute(
        delete(LoungeMessageModel).where(LoungeMessageModel.sender_user_id == user_id)
    )

    # 16. Finally: Delete the user
    await session.execute(
        delete(UserModel).where(UserModel.id == user_id)
    )

    return True


async def delete_user_by_email(email: str):
    """Delete a user and all related records (opens its own session)."""
    async with AsyncSessionLocal() as session:
        try:
            found = await delete_user_by_email_with_session(session, email)
            if not found:
                print(f"❌ User with email '{email}' not found.")
                return
            print(f"✅ Successfully deleted user '{email}' and all related records.")
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error deleting user: {e}")
            raise


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/delete_user.py <email>")
        print("Example: python scripts/delete_user.py c@g.com")
        sys.exit(1)
    
    email = sys.argv[1]
    print(f"🗑️  Deleting user with email: {email}\n")
    asyncio.run(delete_user_by_email(email))
