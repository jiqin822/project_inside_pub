"""Activity domain: suggestions (LLM + seed), scrapbook, sticker generator."""
from app.domain.activity.services import (
    ActivitySuggestionService,
    generate_scrapbook_layout,
    generate_scrapbook_options,
    generate_scrapbook_html,
    make_sticker_generator,
)
from app.domain.activity.seed_examples import SEED_EXAMPLE_ACTIVITIES

__all__ = [
    "ActivitySuggestionService",
    "generate_scrapbook_layout",
    "generate_scrapbook_options",
    "generate_scrapbook_html",
    "make_sticker_generator",
    "SEED_EXAMPLE_ACTIVITIES",
]
