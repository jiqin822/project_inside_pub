"""Insider Compass domain entities (Pydantic)."""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel

from app.domain.common.types import generate_id


class CompassEvent(BaseModel):
    """Compass event (ingest payload)."""
    event_id: Optional[str] = None
    type: str
    actor_user_id: str
    relationship_id: Optional[str] = None
    payload_json: dict = {}
    created_at: Optional[datetime] = None
    privacy_scope: str = "private"
    source: str


class Memory(BaseModel):
    """Structured memory."""
    memory_id: str
    owner_user_id: str
    relationship_id: Optional[str] = None
    visibility: str
    memory_type: str
    canonical_key: str
    value_json: dict
    confidence: float
    status: str
    evidence_event_ids: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime


class PersonPortrait(BaseModel):
    """Person portrait."""
    portrait_id: str
    owner_user_id: str
    relationship_id: Optional[str] = None
    visibility: str
    portrait_text: Optional[str] = None
    portrait_facets_json: dict = {}
    evidence_event_ids: Optional[List[str]] = None
    confidence: float
    created_at: datetime
    updated_at: datetime


class DyadPortrait(BaseModel):
    """Dyad portrait."""
    dyad_portrait_id: str
    relationship_id: str
    portrait_text: Optional[str] = None
    facets_json: dict = {}
    evidence_event_ids: Optional[List[str]] = None
    confidence: float
    created_at: datetime
    updated_at: datetime


class RelationshipLoop(BaseModel):
    """Relationship loop."""
    loop_id: str
    relationship_id: str
    name: str
    trigger_signals_json: dict = {}
    meanings_json: dict = {}
    patterns_by_person_json: dict = {}
    heat_signature_json: dict = {}
    repair_attempts_json: dict = {}
    recommended_interruptions_json: dict = {}
    confidence: float
    status: str
    evidence_event_ids: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None


class ActivityTemplate(BaseModel):
    """Activity template (connection recipe)."""
    activity_id: str
    title: str
    relationship_types: List[str]
    age_range: Optional[dict] = None
    vibe_tags: List[str]
    risk_tags: List[str] = []
    constraints: dict = {}
    personalization_slots: dict = {}
    steps_markdown_template: Optional[str] = None
    variants: dict = {}
    safety_rules: dict = {}
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class DyadActivityRecord(BaseModel):
    """Dyad activity history record."""
    id: str
    relationship_id: str
    activity_template_id: str
    actor_user_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    rating: Optional[float] = None
    outcome_tags: Optional[List[Any]] = None
    created_at: datetime
