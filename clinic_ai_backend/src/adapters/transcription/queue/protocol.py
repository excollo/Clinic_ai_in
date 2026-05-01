"""Abstract transcription queue boundary (Mongo today, Azure Storage Queue soon)."""
from __future__ import annotations

from typing import Protocol

from src.adapters.transcription.types import DequeuedJob, TranscriptionQueueJob


class TranscriptionQueuePort(Protocol):
    async def enqueue(self, job: TranscriptionQueueJob) -> str:
        """Return a durable message identifier (opaque to callers)."""

    async def dequeue(self, visibility_timeout: int = 600) -> DequeuedJob | None:
        """Receive one pending job if any."""

    async def acknowledge(self, job_id: str, receipt: str) -> None:
        """Mark the message consumed (noop for destructive Mongo dequeue)."""

    async def move_to_poison(self, job_id: str, reason: str, receipt: str = "") -> None:
        """Park a failed record for ops review."""

    async def get_queue_depth(self) -> int:
        """Approximate runnable backlog."""

    async def get_poison_queue_depth(self) -> int:
        """Poison / dead-letter backlog."""

    async def health_check(self) -> bool:
        """True if backend is callable."""
