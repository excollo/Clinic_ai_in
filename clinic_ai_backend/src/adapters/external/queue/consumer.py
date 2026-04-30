"""Transcription job consumer — MongoDB FIFO or in-process asyncio queue (not Azure Queue)."""
from __future__ import annotations

from asyncio import QueueEmpty
from pymongo import ASCENDING

from src.adapters.db.mongo.client import get_database
from src.adapters.external.queue.producer import LOCAL_TRANSCRIPTION_QUEUE
from src.core.config import get_settings


class TranscriptionQueueConsumer:
    """Read queue messages in FIFO order."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.queue = get_database().transcription_queue
        self.queue.create_index([("queued_at", ASCENDING)])

    def pop_next_job_id(self) -> str | None:
        if self.settings.use_local_adapters:
            try:
                return LOCAL_TRANSCRIPTION_QUEUE.get_nowait()
            except QueueEmpty:
                return None
        doc = self.queue.find_one(sort=[("queued_at", ASCENDING)])
        if not doc:
            return None
        self.queue.delete_one({"_id": doc["_id"]})
        return doc["job_id"]

    def ack_last(self) -> None:
        return
