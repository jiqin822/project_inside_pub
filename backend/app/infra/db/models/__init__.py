"""Database models."""
from app.infra.db.models.user import UserModel
from app.infra.db.models.relationship import (
    RelationshipModel,
    ConsentModel,
    relationship_members,
    RelationshipType,
    RelationshipStatus,
    MemberRole,
    MemberStatus,
    ConsentStatus,
)
from app.infra.db.models.session import (
    SessionModel,
    NudgeEventModel,
    SessionReportModel,
    SessionFeatureFrameModel,
    session_participants,
    SessionStatus,
    ReportStatus,
)
from app.infra.db.models.events import PokeEventModel
from app.infra.db.models.notification import NotificationModel
from app.infra.db.models.device import DeviceModel
from app.infra.db.models.onboarding import OnboardingProgressModel
from app.infra.db.models.voice import VoiceEnrollmentModel, VoiceProfileModel, VoiceEnrollmentStatus
from app.infra.db.models.invite import (
    RelationshipInviteModel,
    InviteeRole,
    InviteStatus,
)
try:
    from app.infra.db.models.market import (
        EconomySettingsModel,
        WalletModel,
        MarketItemModel,
        TransactionModel,
        TransactionCategory,
        TransactionStatus,
    )
except ImportError:
    # Market models may not be available if migration hasn't been run
    EconomySettingsModel = None
    WalletModel = None
    MarketItemModel = None
    TransactionModel = None
    TransactionCategory = None
    TransactionStatus = None

try:
    from app.infra.db.models.love_map import (
        MapPromptModel,
        UserSpecModel,
        RelationshipMapProgressModel,
    )
except ImportError:
    # Love map models may not be available if migration hasn't been run
    MapPromptModel = None
    UserSpecModel = None
    RelationshipMapProgressModel = None

from app.infra.db.models.compass import (
    CompassEventModel,
    MemoryModel,
    PersonPortraitModel,
    DyadPortraitModel,
    RelationshipLoopModel,
    ActivityTemplateModel,
    DyadActivityHistoryModel,
    DiscoverFeedItemModel,
    DiscoverDismissalModel,
    ActivityWantToTryModel,
    ActivityMutualMatchModel,
    ContextSummaryModel,
    ActivityInviteModel,
    PlannedActivityModel,
)
from app.infra.db.models.lounge import (
    LoungeRoomModel,
    LoungeMemberModel,
    LoungeMessageModel,
    LoungeKaiContextModel,
    LoungeEventModel,
    LoungeKaiUserPreferenceModel,
)

__all__ = [
    "UserModel",
    "RelationshipModel",
    "ConsentModel",
    "relationship_members",
    "RelationshipType",
    "RelationshipStatus",
    "MemberRole",
    "MemberStatus",
    "ConsentStatus",
    "SessionModel",
    "NudgeEventModel",
    "SessionReportModel",
    "SessionFeatureFrameModel",
    "session_participants",
    "SessionStatus",
    "ReportStatus",
    "PokeEventModel",
    "OnboardingProgressModel",
    "VoiceEnrollmentModel",
    "VoiceProfileModel",
    "VoiceEnrollmentStatus",
    "RelationshipInviteModel",
    "InviteeRole",
    "InviteStatus",
    "EconomySettingsModel",
    "WalletModel",
    "MarketItemModel",
    "TransactionModel",
    "TransactionCategory",
    "TransactionStatus",
    "MapPromptModel",
    "UserSpecModel",
    "RelationshipMapProgressModel",
    "NotificationModel",
    "DeviceModel",
    "CompassEventModel",
    "MemoryModel",
    "PersonPortraitModel",
    "DyadPortraitModel",
    "RelationshipLoopModel",
    "ActivityTemplateModel",
    "DyadActivityHistoryModel",
    "DiscoverFeedItemModel",
    "DiscoverDismissalModel",
    "ActivityWantToTryModel",
    "ActivityMutualMatchModel",
    "ContextSummaryModel",
    "ActivityInviteModel",
    "PlannedActivityModel",
    "LoungeRoomModel",
    "LoungeMemberModel",
    "LoungeMessageModel",
    "LoungeKaiContextModel",
    "LoungeEventModel",
    "LoungeKaiUserPreferenceModel",
]
