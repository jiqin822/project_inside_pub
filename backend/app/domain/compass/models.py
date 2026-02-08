"""Insider Compass enums and constants."""
from enum import Enum


class EventSource(str, Enum):
    """Event source for compass events."""
    LOVE_MAP = "love_map"
    THERAPIST = "therapist"
    LIVE_COACH = "live_coach"
    ACTIVITY = "activity"
    ECONOMY = "economy"
    NOTIFICATION = "notification"


class PrivacyScope(str, Enum):
    """Visibility / privacy scope."""
    PRIVATE = "private"
    SHARED_WITH_PARTNER = "shared_with_partner"
    SHARED_WITH_GROUP = "shared_with_group"


class MemoryType(str, Enum):
    """Structured memory type."""
    PREFERENCE = "preference"
    BOUNDARY = "boundary"
    VALUE = "value"
    GOAL = "goal"
    TRIGGER = "trigger"
    RITUAL = "ritual"
    BIOGRAPHY = "biography"
    CONSTRAINT = "constraint"


class MemoryStatus(str, Enum):
    """Memory confirmation status."""
    HYPOTHESIS = "hypothesis"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class LoopStatus(str, Enum):
    """Relationship loop status."""
    HYPOTHESIS = "hypothesis"
    CONFIRMED = "confirmed"


# Use cases for personalization (context summaries and recommendations)
USE_CASE_ACTIVITIES = "activities"
USE_CASE_ECONOMY = "economy"
USE_CASE_THERAPIST = "therapist"
USE_CASE_LIVE_COACH = "live_coach"
USE_CASE_DASHBOARD = "dashboard"
PERSONALIZATION_USE_CASES = [
    USE_CASE_ACTIVITIES,
    USE_CASE_ECONOMY,
    USE_CASE_THERAPIST,
    USE_CASE_LIVE_COACH,
    USE_CASE_DASHBOARD,
]

# Portrait facet keys (doc §3.2.1)
PORTRAIT_FACET_KEYS = [
    "communication_vibe",  # direct | gentle | humorous | intellectual | emotional
    "play_style",         # silly | competitive | cozy | adventurous | creative
    "meaning_markers",    # nostalgia | acts_of_service | words | touch | shared_projects | quality_time
    "identity_threads",   # builder, caregiver, explorer
    "stress_signature",
    "repair_signature",
    "anti_patterns",
    "symbolic_gestures",
]
