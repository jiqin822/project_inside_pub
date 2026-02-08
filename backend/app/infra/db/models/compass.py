"""Insider Compass database models (events, memories, portraits, loops, activity templates)."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB

from app.infra.db.base import Base


class CompassEventModel(Base):
    """Insider Compass event stream (generic event store)."""

    __tablename__ = "compass_events"

    event_id = Column(String, primary_key=True)
    type = Column(String, nullable=False, index=True)
    actor_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=True, index=True)
    payload_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    privacy_scope = Column(String, nullable=False, default="private")  # private | shared_with_partner | shared_with_group
    source = Column(String, nullable=False, index=True)  # love_map | therapist | live_coach | activity | economy | notification

    __table_args__ = (
        Index("ix_compass_events_actor_created", "actor_user_id", "created_at"),
        Index("ix_compass_events_relationship_created", "relationship_id", "created_at"),
        Index("ix_compass_events_source_created", "source", "created_at"),
    )


class UnstructuredMemoryModel(Base):
    """Unstructured memory (e.g. Kai insight text not merged into profile)."""

    __tablename__ = "unstructured_memories"

    id = Column(String, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=True, index=True)
    content_text = Column(Text, nullable=False)
    source = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_unstructured_memories_owner_created", "owner_user_id", "created_at"),
        Index("ix_unstructured_memories_relationship_created", "relationship_id", "created_at"),
    )


class ThingToFindOutModel(Base):
    """Things Kai wants to find out (questions to ask / learn)."""

    __tablename__ = "things_to_find_out"

    id = Column(String, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=True, index=True)
    question_text = Column(Text, nullable=False)
    source = Column(String, nullable=False, index=True)
    priority = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_things_to_find_out_owner_created", "owner_user_id", "created_at"),
        Index("ix_things_to_find_out_relationship_created", "relationship_id", "created_at"),
    )


class MemoryModel(Base):
    """Structured memory (preference, boundary, value, goal, etc.)."""

    __tablename__ = "memories"

    memory_id = Column(String, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=True, index=True)
    visibility = Column(String, nullable=False, default="private")
    memory_type = Column(String, nullable=False, index=True)  # preference | boundary | value | goal | trigger | ritual | biography | constraint
    canonical_key = Column(String, nullable=False, index=True)
    value_json = Column(JSONB, nullable=False, default=dict)
    confidence = Column(Float, nullable=False, default=0.5)
    status = Column(String, nullable=False, default="hypothesis", index=True)  # hypothesis | confirmed | rejected
    evidence_event_ids = Column(JSONB, nullable=True)  # array of event_id strings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_memories_owner_relationship", "owner_user_id", "relationship_id"),
        Index("ix_memories_canonical_owner", "canonical_key", "owner_user_id"),
    )


class PersonPortraitModel(Base):
    """Person portrait (who they are; narrative + facets)."""

    __tablename__ = "person_portraits"

    portrait_id = Column(String, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=True, index=True)
    visibility = Column(String, nullable=False, default="private")
    portrait_text = Column(Text, nullable=True)
    portrait_facets_json = Column(JSONB, nullable=True, default=dict)
    evidence_event_ids = Column(JSONB, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_person_portraits_owner_relationship", "owner_user_id", "relationship_id"),)


class DyadPortraitModel(Base):
    """Dyad portrait (relationship vibe)."""

    __tablename__ = "dyad_portraits"

    dyad_portrait_id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    portrait_text = Column(Text, nullable=True)
    facets_json = Column(JSONB, nullable=True, default=dict)
    evidence_event_ids = Column(JSONB, nullable=True)
    confidence = Column(Float, nullable=False, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class RelationshipLoopModel(Base):
    """Relationship loop (recurring pattern: trigger -> meaning -> reaction -> outcome)."""

    __tablename__ = "relationship_loops"

    loop_id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    trigger_signals_json = Column(JSONB, nullable=True, default=dict)
    meanings_json = Column(JSONB, nullable=True, default=dict)
    patterns_by_person_json = Column(JSONB, nullable=True, default=dict)
    heat_signature_json = Column(JSONB, nullable=True, default=dict)
    repair_attempts_json = Column(JSONB, nullable=True, default=dict)
    recommended_interruptions_json = Column(JSONB, nullable=True, default=dict)
    confidence = Column(Float, nullable=False, default=0.5)
    status = Column(String, nullable=False, default="hypothesis", index=True)  # hypothesis | confirmed
    evidence_event_ids = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)


class ActivityTemplateModel(Base):
    """Activity template (connection recipe)."""

    __tablename__ = "activity_templates"

    activity_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    relationship_types = Column(JSONB, nullable=False)  # ["partner"] | ["child"] | ["family"] | ["friend"]
    age_range = Column(JSONB, nullable=True)  # {"min": 3, "max": 10} or null
    vibe_tags = Column(JSONB, nullable=False)  # ["silly", "nostalgic", ...]
    risk_tags = Column(JSONB, nullable=True, default=list)
    constraints = Column(JSONB, nullable=True, default=dict)  # duration, budget, location, materials
    personalization_slots = Column(JSONB, nullable=True, default=dict)
    steps_markdown_template = Column(Text, nullable=True)
    variants = Column(JSONB, nullable=True, default=dict)
    safety_rules = Column(JSONB, nullable=True, default=dict)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class DyadActivityHistoryModel(Base):
    """Record of activity done by a dyad (for novelty / history)."""

    __tablename__ = "dyad_activity_history"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    activity_template_id = Column(String, ForeignKey("activity_templates.activity_id"), nullable=False, index=True)
    actor_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    planned_id = Column(String, nullable=True, index=True)  # link to planned_activities for grouping memories
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    rating = Column(Float, nullable=True)
    outcome_tags = Column(JSONB, nullable=True)
    notes_text = Column(Text, nullable=True)
    memory_urls = Column(JSONB, nullable=True)
    memory_entries = Column(JSONB, nullable=True)  # [{ "url": "...", "caption": "..." }] per participant
    scrapbook_layout = Column(JSONB, nullable=True)  # AI-generated layout for standalone memories (when planned_id is null)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_dyad_activity_history_relationship_started", "relationship_id", "started_at"),
    )


class ActivityInviteModel(Base):
    """Activity invite from one user to another within a relationship."""

    __tablename__ = "activity_invites"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    activity_template_id = Column(String, ForeignKey("activity_templates.activity_id"), nullable=False)
    from_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending | accepted | declined
    card_snapshot = Column(JSONB, nullable=True)  # full ActivityCard-like JSON when invite was sent
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_activity_invites_to_user_id_status", "to_user_id", "status"),
    )


class PlannedActivityModel(Base):
    """Planned activity agreed by both users (from an accepted invite)."""

    __tablename__ = "planned_activities"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    activity_template_id = Column(String, ForeignKey("activity_templates.activity_id"), nullable=False)
    initiator_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    invitee_user_id = Column(String, ForeignKey("users.id"), nullable=False)
    invite_id = Column(String, ForeignKey("activity_invites.id"), nullable=True)
    status = Column(String, nullable=False, default="planned")  # planned | completed
    agreed_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    notes_text = Column(Text, nullable=True)
    memory_urls = Column(JSONB, nullable=True)
    scrapbook_layout = Column(JSONB, nullable=True)  # AI-generated layout (themeColor, headline, narrative, etc.)
    card_snapshot = Column(JSONB, nullable=True)  # full ActivityCard-like JSON for UI (from invite or template)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_planned_activities_initiator_status", "initiator_user_id", "status"),
        Index("ix_planned_activities_invitee_status", "invitee_user_id", "status"),
    )


class DiscoverFeedItemModel(Base):
    """Discover feed item: activity card shown to both generator and recommended invitee."""

    __tablename__ = "discover_feed_items"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    activity_template_id = Column(String, ForeignKey("activity_templates.activity_id"), nullable=False, index=True)
    card_snapshot = Column(JSONB, nullable=True)
    generated_by_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    recommended_invitee_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_discover_feed_items_relationship_user", "relationship_id", "generated_by_user_id"),
        Index("ix_discover_feed_items_relationship_invitee", "relationship_id", "recommended_invitee_user_id"),
    )


class DiscoverDismissalModel(Base):
    """User dismissed a discover feed item (so it no longer appears in their feed)."""

    __tablename__ = "discover_dismissals"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    discover_feed_item_id = Column(String, ForeignKey("discover_feed_items.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_discover_dismissals_user_relationship", "user_id", "relationship_id"),)


class ActivityWantToTryModel(Base):
    """User tapped 'Want to try' on a discover feed card."""

    __tablename__ = "activity_want_to_try"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    discover_feed_item_id = Column(String, ForeignKey("discover_feed_items.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("ix_activity_want_to_try_feed_item", "discover_feed_item_id"),)


class ActivityMutualMatchModel(Base):
    """Mutual match: both users want to try the same activity; store accept/decline per user."""

    __tablename__ = "activity_mutual_matches"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=False, index=True)
    discover_feed_item_id = Column(String, ForeignKey("discover_feed_items.id"), nullable=False, index=True)
    user_a_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    user_b_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    user_a_response = Column(String, nullable=False, default="pending")  # pending | accept | decline
    user_b_response = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_activity_mutual_matches_user_a", "user_a_id", "user_a_response"),
        Index("ix_activity_mutual_matches_user_b", "user_b_id", "user_b_response"),
    )


class ContextSummaryModel(Base):
    """Per-use-case context summary (one statement per use case/scenario for personalization)."""

    __tablename__ = "context_summaries"

    id = Column(String, primary_key=True)
    relationship_id = Column(String, ForeignKey("relationships.id"), nullable=True, index=True)
    actor_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    use_case = Column(String, nullable=False, index=True)  # activities | economy | therapist | live_coach | dashboard
    scenario = Column(String, nullable=True, index=True)  # e.g. default | repair_ladder | in_session | post_session
    summary_text = Column(Text, nullable=False)
    evidence_event_ids = Column(JSONB, nullable=True)  # array of event_id strings
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_context_summaries_relationship_use_case", "relationship_id", "use_case"),
        Index("ix_context_summaries_actor_use_case", "actor_user_id", "use_case"),
    )
