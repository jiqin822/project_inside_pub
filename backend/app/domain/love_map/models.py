"""Love Map domain models."""
from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel


class MapPrompt(BaseModel):
    """Map prompt template."""
    id: str
    category: str
    difficulty_tier: int  # 1-5
    question_template: str
    input_prompt: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserSpec(BaseModel):
    """User specification (answer to a prompt)."""
    id: str
    user_id: str
    prompt_id: str
    answer_text: str
    last_updated: datetime
    embedding: Optional[List[float]] = None  # Optional vector embedding


class RelationshipMapProgress(BaseModel):
    """Relationship map progress (directional)."""
    id: str
    observer_id: str  # The Player/Guesser
    subject_id: str  # The Person being studied
    level_tier: int  # Current unlocked difficulty tier (1-6)
    current_xp: int  # Experience points
    stars: Optional[Dict[str, int]] = None  # {'tier_1': 3, 'tier_2': 1}
    created_at: datetime
    updated_at: datetime


class QuizQuestion(BaseModel):
    """Quiz question with options."""
    question_id: str
    question_text: str
    options: List[str]  # 4 options (1 correct + 3 distractors)
    correct_option_index: int  # Index of correct answer in options array
    prompt_id: str
    category: str
    difficulty_tier: int


class MapProgressStatus(BaseModel):
    """Map progress status for a relationship."""
    level_tier: int
    current_xp: int
    stars: Dict[str, int]
    locked_levels: List[int]  # Levels that are locked (subject hasn't filled specs)
    unlocked_levels: List[int]  # Levels that are unlocked
    total_specs_count: int  # Total specs filled by subject
    specs_by_tier: Dict[int, int]  # Count of specs per tier
