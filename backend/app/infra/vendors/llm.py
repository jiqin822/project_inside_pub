"""LLM vendor adapter."""
from typing import Any
from app.domain.coach.services import LLMAdapter


class OpenAIAdapter(LLMAdapter):
    """OpenAI LLM adapter."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_insight(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generate an insight from context."""
        # Skeleton implementation
        return {
            "insight": "This is a placeholder insight",
            "confidence": 0.5,
        }

    async def analyze_communication(self, messages: list[dict]) -> dict[str, Any]:
        """Analyze communication patterns."""
        # Skeleton implementation
        return {
            "sentiment": "positive",
            "topics": ["general"],
            "suggestions": ["Keep up the good communication!"],
        }


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter for testing."""

    async def generate_insight(self, context: dict[str, Any]) -> dict[str, Any]:
        """Generate a mock insight."""
        return {
            "insight": "Mock insight",
            "confidence": 0.8,
        }

    async def analyze_communication(self, messages: list[dict]) -> dict[str, Any]:
        """Generate mock analysis."""
        return {
            "sentiment": "neutral",
            "topics": ["mock"],
            "suggestions": ["Mock suggestion"],
        }
