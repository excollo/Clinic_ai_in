"""Typed envelopes for transcription queue and storage adapters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class TranscriptionQueueJob:
    """Minimal durable job envelope for queues; extended fields preserve forward compatibility."""

    job_id: str
    audio_storage_ref: str | None = None
    patient_id: str | None = None
    visit_id: str | None = None
    doctor_id: str | None = None
    noise_environment: str | None = None
    language_mix: str | None = None
    queued_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class DequeuedJob:
    """Result of dequeue: payload plus opaque acknowledgement handle for cloud queues."""

    job: TranscriptionQueueJob
    message_id: str = ""
    receipt: str = ""
    dequeue_count: int = 1
