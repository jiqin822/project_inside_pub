# Love Maps Module Implementation

## Overview

The Love Maps module is a gamified knowledge graph system that digitizes "Love Maps" (cognitive understanding of a partner's inner world) by turning personal facts into a playable trivia game.

## Architecture

### Database Schema

1. **map_prompts** - Global template library of questions
   - Categories: Dreams, Stress, History, Intimacy, Work, etc.
   - Difficulty tiers: 1 (Easy/Basics) to 5 (Deep/Esoteric)
   - Question templates and input prompts

2. **user_specs** - User's answers about themselves (Ground Truth)
   - Links user_id to prompt_id
   - Stores answer_text
   - Tracks last_updated for stale data detection

3. **relationship_map_progress** - Directional progress tracking
   - observer_id (Player/Guesser) → subject_id (Person being studied)
   - level_tier (1-6)
   - current_xp
   - stars (JSONB: {'tier_1': 3, 'tier_2': 1})

### API Endpoints

All endpoints are under `/v1/love-map`:

#### Specification Management

- `GET /v1/love-map/prompts?status=unanswered` - Get prompts (optionally filter to unanswered)
- `POST /v1/love-map/specs` - Create or update a user spec
  ```json
  {
    "prompt_id": "uuid",
    "answer_text": "Spicy Ramen with extra egg"
  }
  ```

#### Gameplay

- `GET /v1/love-map/progress/{subject_id}` - Get map progress status
  - Returns: level_tier, current_xp, stars, locked_levels, unlocked_levels, total_specs_count, specs_by_tier

- `POST /v1/love-map/quiz/generate` - Generate quiz questions
  ```json
  {
    "subject_id": "uuid",
    "tier": 1
  }
  ```
  Returns: Array of quiz questions with 4 options (1 correct + 3 AI-generated distractors)

- `POST /v1/love-map/quiz/complete` - Complete quiz and update progress
  ```json
  {
    "subject_id": "uuid",
    "tier": 1,
    "score": 4,
    "total_questions": 5
  }
  ```
  - Awards XP (10 per correct answer)
  - Calculates star rating (3 stars = 100%, 2 = 70-99%, 1 = 50-69%, 0 = <50%)
  - Unlocks next tier if current tier completed with 3 stars

## Setup

### 1. Run Database Migration

```bash
cd backend
alembic upgrade head
```

### 2. Seed Initial Prompts

```bash
cd backend
python scripts/seed_love_map_prompts.py
```

### 3. Configure Gemini API (Optional)

Add to `.env`:
```
GEMINI_API_KEY=your_api_key_here
```

If not configured, the system will use simple fallback distractors instead of AI-generated ones.

## Business Logic

### Quiz Generation Algorithm

1. Check if tier is unlocked (subject has ≥3 specs for that tier)
2. Fetch subject's specs for the tier
3. Select up to 5 random specs
4. For each spec:
   - Generate 3 distractors using Gemini AI (or fallback)
   - Create question with 4 shuffled options
   - Mark correct option index

### Unlocking Mechanism

- A tier is **locked** if the subject has <3 specs for that tier
- When observer tries to play a locked tier, returns error with message
- System can generate notifications: "User A wants to know about your Deep Fears. Fill out your Love Map to unlock this level!"

### Progress Tracking

- **XP System**: 10 XP per correct answer
- **Star Ratings**: Based on percentage correct
- **Level Unlocking**: Automatically unlocks next tier when current tier is completed with 3 stars

## Frontend Integration

The frontend should:

1. **My Specs Mode**: Show unanswered prompts, allow users to fill them out
2. **Quiz Mode**: Show available tiers, generate quizzes, track progress
3. **Progress Visualization**: Display level tiers, XP, stars, locked/unlocked status
4. **Room Status**: Aggregate status for "Living Room" based on combined progress

## Testing

To test the implementation:

1. Create two users
2. User A fills out specs (at least 3 for tier 1)
3. User B tries to generate quiz about User A
4. User B completes quiz
5. Check progress and XP updates

## Future Enhancements

- Vector embeddings for semantic matching
- Stale data notifications (if answer hasn't been updated in X months)
- Artifacts system (completed specs generate room decorations)
- Integration with Global XP and Economy Currency systems
