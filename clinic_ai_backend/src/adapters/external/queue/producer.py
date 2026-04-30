"""Transcription job queue — MongoDB FIFO collection (not Azure Storage Queue)."""
from __future__ import annotations

from asyncio import Queue
from datetime import datetime, timezone

from src.adapters.db.mongo.client import get_database
from src.core.config import get_settings


LOCAL_TRANSCRIPTION_QUEUE: Queue[str] = Queue()


class TranscriptionQueueProducer:
    """Persist queue messages for worker consumption."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.queue = get_database().transcription_queue

    def enqueue(self, job_id: str) -> None:
        if self.settings.use_local_adapters:
            LOCAL_TRANSCRIPTION_QUEUE.put_nowait(job_id)
            return
        self.queue.insert_one(
            {
                "job_id": job_id,
                "queued_at": datetime.now(timezone.utc),
            }
        )
