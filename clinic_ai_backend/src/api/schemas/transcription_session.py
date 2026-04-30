"""Visit transcription session DTOs (ported shapes from transcript-bundle)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TranscriptionSessionResponse(BaseModel):
    """TranscriptionSessionDTO as JSON for GET dialogue."""

    audio_file_path: str | None = None
    transcript: str | None = None
    transcription_status: str
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    audio_duration_seconds: float | None = None
    word_count: int | None = None
    structured_dialogue: list[dict[str, Any]] | None = None
