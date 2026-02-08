"""Seed script for activity templates (Insider Compass connection recipes)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.infra.db.models.compass import ActivityTemplateModel
from app.settings import settings


# Partner + child templates per doc §5.1. Idempotent: fixed activity_id by slug.
TEMPLATES = [
    # --- Partner ---
    {
        "activity_id": "partner-cooking-blindfolded",
        "title": "Cooking blindfolded",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["silly", "intimate", "playful"],
        "risk_tags": ["physical"],
        "constraints": {"duration_min": 30, "budget": "low", "location": "indoor"},
        "personalization_slots": {"cuisine": "favorite cuisine"},
        "steps_markdown_template": """1. One partner wears a blindfold; the other guides hands to ingredients and tools.
2. Cook a simple dish together (e.g. pasta, salad).
3. Swap roles for dessert or a second round.
4. Eat together and rate the surprise.""",
        "variants": {"low_effort": "Use pre-made dough or box mix.", "high_effort": "Full meal from scratch."},
        "safety_rules": {"no_open_flame_near_face": True},
    },
    {
        "activity_id": "partner-recreate-first-date",
        "title": "Recreate first date",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["nostalgic", "calm", "intimate"],
        "risk_tags": [],
        "constraints": {"duration_min": 60, "budget": "flexible", "location": "any"},
        "personalization_slots": {"venue": "where you first met or had first date", "food": "what you ate"},
        "steps_markdown_template": """1. Agree on which "first date" to recreate (first ever, or a milestone).
2. Match the vibe: same type of place, similar food, or same activity.
3. Share one thing you each remember most from that day.
4. Optional: take a photo in the same pose or place.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "partner-tour-de-food",
        "title": "Tour de Food (three restaurants, three courses)",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["adventurous", "playful", "spontaneous"],
        "risk_tags": ["cost"],
        "constraints": {"duration_min": 90, "budget": "medium", "location": "outdoor/neighborhood"},
        "personalization_slots": {"restaurants": "three nearby spots"},
        "steps_markdown_template": """1. Pick three nearby spots: appetizer at A, main at B, dessert at C.
2. Walk or drive between them. One rule: no phones at the table.
3. At each stop, each share one thing you're grateful for about the other.
4. End with a short walk or one silly dare.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "partner-teach-me-something",
        "title": "Teach me something",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["creative", "calm", "intimate"],
        "risk_tags": [],
        "constraints": {"duration_min": 20, "budget": "low", "location": "any"},
        "personalization_slots": {"skill_a": "one thing you're good at", "skill_b": "one thing they're good at"},
        "steps_markdown_template": """1. Each person picks one small skill to teach (a recipe step, a chord, a phrase, a trick).
2. Set a timer for 10–15 min per "lesson."
3. Learner asks questions; teacher can't get frustrated.
4. Swap. Celebrate the attempt, not perfection.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "partner-blanket-fort-night",
        "title": "Blanket fort night",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["cozy", "silly", "calm"],
        "risk_tags": [],
        "constraints": {"duration_min": 60, "budget": "low", "location": "indoor"},
        "personalization_slots": {"snacks": "favorite movie snacks"},
        "steps_markdown_template": """1. Build a blanket fort together (chairs, couch, sheets, clips).
2. Bring pillows, string lights or a lamp, and snacks.
3. Watch a movie, read aloud, or play a simple card game inside.
4. No phones in the fort.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "partner-two-truths-and-a-wish",
        "title": "Two truths and a wish",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["playful", "intimate", "calm"],
        "risk_tags": [],
        "constraints": {"duration_min": 15, "budget": "low", "location": "any"},
        "personalization_slots": {},
        "steps_markdown_template": """1. Each person shares two true things about themselves (recent or old) and one wish (for the relationship or for life).
2. Partner guesses which is the wish.
3. Then briefly say how you could support that wish.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "partner-gratitude-walk",
        "title": "Gratitude walk",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["calm", "intimate"],
        "risk_tags": [],
        "constraints": {"duration_min": 20, "budget": "low", "location": "outdoor"},
        "personalization_slots": {},
        "steps_markdown_template": """1. Take a 15–20 min walk together (outside or pacing at home).
2. Take turns: each name one thing you're grateful for about the other this week.
3. No problem-solving; just listening and saying "thank you."
4. End with one sentence: "One thing I love about us is..." """,
        "variants": {},
        "safety_rules": {},
    },
    # --- Child / family ---
    {
        "activity_id": "child-scavenger-hunt",
        "title": "Scavenger hunt",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 4, "max": 12},
        "vibe_tags": ["adventurous", "silly", "playful"],
        "risk_tags": [],
        "constraints": {"duration_min": 20, "budget": "low", "location": "indoor or outdoor"},
        "personalization_slots": {"themes": "child's interests"},
        "steps_markdown_template": """1. Make a short list of things to find (e.g. something red, something soft, a leaf, a toy that starts with B).
2. Set a timer. Kid (and adult) hunt together or race.
3. When you finish, show each item and tell one short story about it.
4. Optional: take a silly photo with the haul.""",
        "variants": {"indoor": "house/room only", "outdoor": "yard or park"},
        "safety_rules": {"supervision": "Adult within sight for young children."},
    },
    {
        "activity_id": "child-build-a-fort",
        "title": "Build a fort",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 3, "max": 10},
        "vibe_tags": ["creative", "cozy", "playful"],
        "risk_tags": [],
        "constraints": {"duration_min": 30, "budget": "low", "location": "indoor"},
        "personalization_slots": {},
        "steps_markdown_template": """1. Gather blankets, pillows, chairs, and clips. Build a fort together.
2. Decide what the fort is (spaceship, cave, castle) and one rule inside (e.g. only silly voices).
3. Bring a book or a game and spend 15–20 min inside.
4. Optional: snack "rations" and a flashlight.""",
        "variants": {},
        "safety_rules": {"no_heavy_objects_on_top": True},
    },
    {
        "activity_id": "child-craft-and-story-night",
        "title": "Craft and story night",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 4, "max": 12},
        "vibe_tags": ["creative", "calm", "nostalgic"],
        "risk_tags": [],
        "constraints": {"duration_min": 30, "budget": "low", "location": "indoor"},
        "personalization_slots": {"characters": "child's favorite characters or animals"},
        "steps_markdown_template": """1. Pick a simple craft (drawing, clay, paper puppets) and do it side by side.
2. As you craft, take turns adding one sentence to a shared story (you start, kid adds, you add, etc.).
3. When the craft is done, act out or tell the story again with the creations.
4. Give the story a title and write it on the back or say it aloud.""",
        "variants": {},
        "safety_rules": {"age_appropriate_materials": True},
    },
    {
        "activity_id": "child-petting-zoo",
        "title": "Petting zoo (or animal visit)",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 2, "max": 10},
        "vibe_tags": ["calm", "adventurous"],
        "risk_tags": [],
        "constraints": {"duration_min": 60, "budget": "medium", "location": "outdoor"},
        "personalization_slots": {"animals": "child's favorite animals"},
        "steps_markdown_template": """1. Visit a petting zoo, farm, or aquarium. Go at the child's pace.
2. Let them choose which animals to approach; model gentle hands and calm voice.
3. Afterward, draw or name one favorite animal and one thing it did.
4. Optional: make a "thank you" drawing for the animals when you get home.""",
        "variants": {},
        "safety_rules": {"hand_washing_after": True, "supervision_near_animals": True},
    },
    {
        "activity_id": "family-silly-dance-party",
        "title": "Silly dance party",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 2, "max": 10},
        "vibe_tags": ["silly", "playful", "spontaneous"],
        "risk_tags": [],
        "constraints": {"duration_min": 10, "budget": "low", "location": "indoor"},
        "personalization_slots": {"songs": "kid's favorite songs"},
        "steps_markdown_template": """1. Put on 3–5 songs. Rule: everyone has to move (dance, jump, wiggle).
2. Take turns picking a "silly move" everyone has to copy for one song.
3. End with a "freeze dance" or a group hug when the music stops.
4. No judging—just fun.""",
        "variants": {},
        "safety_rules": {"clear_space": True},
    },
    {
        "activity_id": "family-nature-collection",
        "title": "Nature collection",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 4, "max": 12},
        "vibe_tags": ["calm", "adventurous", "creative"],
        "risk_tags": [],
        "constraints": {"duration_min": 30, "budget": "low", "location": "outdoor"},
        "personalization_slots": {},
        "steps_markdown_template": """1. Go on a short walk (yard, park, block). Collect small safe items: leaves, stones, sticks, flowers (where allowed).
2. At home, arrange them on a tray or paper. Give the "collection" a name.
3. Take a photo or draw the arrangement together.
4. Put items back outside or in a designated "nature bowl." """,
        "variants": {},
        "safety_rules": {"no_berries_or_unknown_plants": True},
    },
    # --- More partner (20–30 total per plan §6) ---
    {
        "activity_id": "partner-stargazing",
        "title": "Stargazing together",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["calm", "intimate", "nostalgic"],
        "risk_tags": [],
        "constraints": {"duration_min": 30, "budget": "low", "location": "outdoor"},
        "personalization_slots": {},
        "steps_markdown_template": """1. Find a dark spot (yard, roof, park). Bring a blanket and optional hot drinks.
2. Lie down and name one star or constellation you know; take turns.
3. Share one wish or hope for the two of you.
4. No phones—just quiet connection.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "partner-random-kindness",
        "title": "Random act of kindness for each other",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["playful", "intimate", "calm"],
        "risk_tags": [],
        "constraints": {"duration_min": 15, "budget": "low", "location": "any"},
        "personalization_slots": {"gesture": "something they'd love"},
        "steps_markdown_template": """1. Each person secretly plans one small kindness for the other (note, chore, snack, hug).
2. Do it without explaining. Let them discover it.
3. After both have happened, share what you did and how it felt.
4. Optional: make it a weekly ritual.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "partner-breakfast-in-bed",
        "title": "Breakfast in bed",
        "relationship_types": ["partner"],
        "age_range": None,
        "vibe_tags": ["cozy", "intimate", "calm"],
        "risk_tags": [],
        "constraints": {"duration_min": 45, "budget": "low", "location": "indoor"},
        "personalization_slots": {"favorite_breakfast": "their favorite"},
        "steps_markdown_template": """1. One person prepares a simple breakfast (or order in). The other stays in bed.
2. Serve together on a tray; eat side by side.
3. No devices. One question each: "What are you looking forward to this week?"
4. Swap roles next time.""",
        "variants": {},
        "safety_rules": {},
    },
    # --- More child/family ---
    {
        "activity_id": "child-puzzle-time",
        "title": "Puzzle time",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 4, "max": 12},
        "vibe_tags": ["calm", "creative", "playful"],
        "risk_tags": [],
        "constraints": {"duration_min": 20, "budget": "low", "location": "indoor"},
        "personalization_slots": {"theme": "child's favorite characters"},
        "steps_markdown_template": """1. Pick a puzzle (age-appropriate piece count). Work on it together.
2. Take turns finding pieces; celebrate when a section is done.
3. When finished, take a photo and give the puzzle a name.
4. Optional: glue and frame for the wall.""",
        "variants": {},
        "safety_rules": {},
    },
    {
        "activity_id": "family-cooking-together",
        "title": "Cooking together",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 5, "max": 12},
        "vibe_tags": ["creative", "calm", "playful"],
        "risk_tags": ["physical"],
        "constraints": {"duration_min": 45, "budget": "low", "location": "indoor"},
        "personalization_slots": {"recipe": "kid-friendly recipe"},
        "steps_markdown_template": """1. Choose a simple recipe (pizza, cookies, tacos). Assign tasks by age.
2. Cook together; one rule: no criticizing, only helping.
3. Set the table and eat together. Each say one thing that went well.
4. Clean up as a team.""",
        "variants": {},
        "safety_rules": {"adult_supervision_stove": True},
    },
    {
        "activity_id": "child-backyard-campout",
        "title": "Backyard campout",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 4, "max": 10},
        "vibe_tags": ["adventurous", "cozy", "playful"],
        "risk_tags": [],
        "constraints": {"duration_min": 120, "budget": "low", "location": "outdoor"},
        "personalization_slots": {},
        "steps_markdown_template": """1. Set up a tent or blanket fort in the yard. Bring pillows and flashlights.
2. Tell one short "campfire" story each (no screens).
3. Optional: simple snacks, star-gazing, or morning pancakes.
4. One rule: everyone stays together until "sunrise." """,
        "variants": {},
        "safety_rules": {"adult_present": True},
    },
    {
        "activity_id": "family-gratitude-jar",
        "title": "Gratitude jar",
        "relationship_types": ["child", "family"],
        "age_range": {"min": 4, "max": 12},
        "vibe_tags": ["calm", "nostalgic", "intimate"],
        "risk_tags": [],
        "constraints": {"duration_min": 20, "budget": "low", "location": "indoor"},
        "personalization_slots": {},
        "steps_markdown_template": """1. Decorate a jar together (stickers, paint, markers). This is the family gratitude jar.
2. Each person writes or draws one thing they're grateful for about the family on a slip of paper.
3. Put slips in the jar. Read a few aloud (or save for a weekly "gratitude moment").
4. Keep adding; open and read all on a special date (birthday, New Year).""",
        "variants": {},
        "safety_rules": {},
    },
]


async def seed_activity_templates():
    """Seed activity templates; skip any that already exist (idempotent)."""
    engine = create_async_engine(settings.database_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        added = 0
        for t in TEMPLATES:
            activity_id = t["activity_id"]
            existing = await session.execute(
                select(ActivityTemplateModel).where(ActivityTemplateModel.activity_id == activity_id)
            )
            if existing.scalar_one_or_none() is not None:
                continue
            model = ActivityTemplateModel(
                activity_id=activity_id,
                title=t["title"],
                relationship_types=t["relationship_types"],
                age_range=t.get("age_range"),
                vibe_tags=t["vibe_tags"],
                risk_tags=t.get("risk_tags") or [],
                constraints=t.get("constraints") or {},
                personalization_slots=t.get("personalization_slots") or {},
                steps_markdown_template=t.get("steps_markdown_template") or "",
                variants=t.get("variants") or {},
                safety_rules=t.get("safety_rules") or {},
                is_active=True,
            )
            session.add(model)
            added += 1
        await session.commit()
        print(f"Seeded {added} activity templates ({len(TEMPLATES) - added} already existed).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_activity_templates())
