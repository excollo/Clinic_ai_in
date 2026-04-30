"""Audio and transcription API schemas module."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


NoiseEnvironment = Literal["quiet_clinic", "moderate_opd", "crowded_opd", "high_noise"]
SpeakerMode = Literal["two_speakers", "three_speakers"]


class TranscriptionUploadAcceptedResponse(BaseModel):
    """Async upload accepted response."""

    job_id: str
    message_id: str
    patient_id: str
    visit_id: str
    status: Literal["queued", "processing", "completed", "failed"]
    received_at: datetime
    message: str | None = None
