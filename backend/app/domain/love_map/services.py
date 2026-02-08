"""Love Map domain services."""
import json
import random
from typing import Any, List, Optional
from datetime import datetime

from app.domain.love_map.models import (
    MapPrompt,
    UserSpec,
    RelationshipMapProgress,
    QuizQuestion,
    MapProgressStatus,
)
from app.domain.love_map.repositories import (
    MapPromptRepository,
    UserSpecRepository,
    RelationshipMapProgressRepository,
)
from app.domain.common.types import generate_id
from app.domain.common.errors import NotFoundError, ValidationError


class LoveMapService:
    """Love Map service."""

    def __init__(
        self,
        prompt_repo: MapPromptRepository,
        spec_repo: UserSpecRepository,
        progress_repo: RelationshipMapProgressRepository,
        gemini_api_key: Optional[str] = None,
        llm_service: Optional[Any] = None,
    ):
        self.prompt_repo = prompt_repo
        self.spec_repo = spec_repo
        self.progress_repo = progress_repo
        self.gemini_api_key = gemini_api_key
        self.llm_service = llm_service

    async def get_unanswered_prompts(self, user_id: str) -> List[MapPrompt]:
        """Get prompts that user hasn't answered yet."""
        return await self.prompt_repo.get_unanswered_by_user(user_id)

    async def create_or_update_spec(
        self, user_id: str, prompt_id: str, answer_text: str
    ) -> UserSpec:
        """Create or update a user spec."""
        # Verify prompt exists
        prompt = await self.prompt_repo.get_by_id(prompt_id)
        if not prompt:
            raise NotFoundError(f"Prompt {prompt_id} not found")

        # Create or update spec
        spec = UserSpec(
            id=generate_id(),
            user_id=user_id,
            prompt_id=prompt_id,
            answer_text=answer_text,
            last_updated=datetime.utcnow(),
        )
        return await self.spec_repo.create_or_update(spec)

    async def get_progress_status(
        self, observer_id: str, subject_id: str
    ) -> MapProgressStatus:
        """Get map progress status for a relationship."""
        progress = await self.progress_repo.get_by_observer_and_subject(
            observer_id, subject_id
        )

        if not progress:
            # Create default progress
            progress = RelationshipMapProgress(
                id=generate_id(),
                observer_id=observer_id,
                subject_id=subject_id,
                level_tier=1,
                current_xp=0,
                stars={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            progress = await self.progress_repo.create_or_update(progress)

        # Get specs count by tier for subject
        specs_by_tier = {}
        total_specs = 0
        locked_levels = []
        unlocked_levels = []

        for tier in range(1, 7):  # Tiers 1-6
            count = await self.spec_repo.count_by_user_and_tier(subject_id, tier)
            specs_by_tier[tier] = count
            total_specs += count

            # Level is locked if subject has less than 3 specs for that tier
            if count < 3:
                locked_levels.append(tier)
            else:
                unlocked_levels.append(tier)

        return MapProgressStatus(
            level_tier=progress.level_tier,
            current_xp=progress.current_xp,
            stars=progress.stars or {},
            locked_levels=locked_levels,
            unlocked_levels=unlocked_levels,
            total_specs_count=total_specs,
            specs_by_tier=specs_by_tier,
        )

    async def generate_quiz(
        self, observer_id: str, subject_id: str, tier: int
    ) -> List[QuizQuestion]:
        """Generate quiz questions for a tier."""
        # Check if tier is unlocked
        progress_status = await self.get_progress_status(observer_id, subject_id)
        if tier in progress_status.locked_levels:
            raise ValidationError(
                f"Tier {tier} is locked. Subject must fill at least 3 specs for this tier."
            )

        # Get specs for subject at this tier
        specs = await self.spec_repo.get_by_user_and_tier(subject_id, tier)
        if len(specs) < 3:
            raise ValidationError(
                f"Insufficient data: Subject has only {len(specs)} specs for tier {tier}. Need at least 3."
            )

        # Get prompts for this tier
        prompts = await self.prompt_repo.get_by_tier(tier)

        # Select up to 5 random specs to create questions from
        selected_specs = random.sample(specs, min(5, len(specs)))

        quiz_questions = []
        for spec in selected_specs:
            # Find the prompt for this spec
            prompt = await self.prompt_repo.get_by_id(spec.prompt_id)
            if not prompt:
                continue

            # Generate distractors using AI
            distractors = await self._generate_distractors(
                prompt.question_template, spec.answer_text
            )

            # Create question with 4 options (1 correct + 3 distractors)
            options = [spec.answer_text] + distractors
            random.shuffle(options)
            correct_index = options.index(spec.answer_text)

            question = QuizQuestion(
                question_id=generate_id(),
                question_text=prompt.question_template.replace("[NAME]", "your partner"),
                options=options,
                correct_option_index=correct_index,
                prompt_id=prompt.id,
                category=prompt.category,
                difficulty_tier=prompt.difficulty_tier,
            )
            quiz_questions.append(question)

        return quiz_questions

    async def _generate_distractors(
        self, question_template: str, true_answer: str
    ) -> List[str]:
        """Generate 3 plausible distractors using AI."""
        fallback = [
            "I'm not sure",
            "Let me think about that",
            "That's a good question",
        ]
        if self.llm_service is None and not self.gemini_api_key:
            return fallback

        prompt = f"""Context: A trivia game about a partner in a relationship.

Question: {question_template}
True Answer: {true_answer}

Generate exactly 3 plausible but incorrect options (distractors) that are:
1. Tonally similar to the true answer
2. Realistic and believable
3. Different enough from the true answer to be clearly wrong

Return ONLY a JSON array of exactly 3 strings, no other text. Example format: ["option1", "option2", "option3"]
"""
        try:
            if self.llm_service is not None:
                text = (self.llm_service.generate_text(prompt, model="gemini-2.0-flash") or "").strip()
            else:
                try:
                    import google.genai as genai
                except (ImportError, ModuleNotFoundError):
                    return fallback
                client = genai.Client(api_key=self.gemini_api_key)
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                )
                text = (response.text or "").strip()

            if not text:
                return fallback
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()

            distractors = json.loads(text)
            if isinstance(distractors, list) and len(distractors) >= 3:
                return distractors[:3]
            return fallback
        except Exception as e:
            print(f"Error generating distractors with Gemini: {e}")
            return fallback

    async def complete_quiz(
        self,
        observer_id: str,
        subject_id: str,
        tier: int,
        score: int,  # Number of correct answers
        total_questions: int,
    ) -> RelationshipMapProgress:
        """Complete a quiz and update progress."""
        # Calculate XP (e.g., 10 XP per correct answer)
        xp_gained = score * 10

        # Update XP
        progress = await self.progress_repo.update_xp(
            observer_id, subject_id, xp_gained
        )

        # Calculate star rating (3 stars = 100%, 2 stars = 70-99%, 1 star = 50-69%, 0 stars = <50%)
        percentage = (score / total_questions) * 100 if total_questions > 0 else 0
        if percentage >= 100:
            stars = 3
        elif percentage >= 70:
            stars = 2
        elif percentage >= 50:
            stars = 1
        else:
            stars = 0

        # Update stars for this tier
        await self.progress_repo.update_stars(observer_id, subject_id, tier, stars)

        # Check if we should unlock next tier (e.g., if current tier is complete with 3 stars)
        if stars == 3 and progress.level_tier == tier:
            # Unlock next tier if not already unlocked
            next_tier = tier + 1
            if next_tier <= 6:
                await self.progress_repo.unlock_level(
                    observer_id, subject_id, next_tier
                )

        # Return updated progress
        return await self.progress_repo.get_by_observer_and_subject(
            observer_id, subject_id
        )
