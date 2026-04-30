"""Post-visit summary generation service."""
from __future__ import annotations

from src.adapters.external.ai.openai_client import OpenAIQuestionClient


class PostVisitSummaryService:
    """Generate patient-friendly post-visit summary."""

    def __init__(self) -> None:
        self.openai = OpenAIQuestionClient()

    def generate(self, *, context: dict, language_name: str) -> dict:
        """Generate structured summary using AI service."""
        return self.openai.generate_post_visit_summary(context=context, language_name=language_name)
