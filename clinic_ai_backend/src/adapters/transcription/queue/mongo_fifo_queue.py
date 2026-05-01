"""MongoDB FIFO transcription queue adapter (baseline + rollback path)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from src.adapters.db.mongo.client import get_database
from src.adapters.external.queue.consumer import TranscriptionQueueConsumer
from src.adapters.external.queue.producer import TranscriptionQueueProducer
from src.adapters.transcription.types import DequeuedJob, TranscriptionQueueJob


class MongoFifoQueueAdapter:
    """Destructive dequeue on pop; acknowledgement is implicit (Chunk 5 adds durable retry semantics)."""

    def __init__(self) -> None:
        TranscriptionQueueConsumer()  # ensure indexes on transcription_queue collection

    async def enqueue(self, job: TranscriptionQueueJob) -> str:
        """Persist job identifier in FIFO."""

        def _run() -> str:
            TranscriptionQueueProducer().enqueue(job.job_id)
            return job.job_id

        return await asyncio.to_thread(_run)

    async def dequeue(self, visibility_timeout: int = 600) -> DequeuedJob | None:
        visibility_timeout = int(visibility_timeout)  # noqa: ARG001 reserved for Azure

        def _pop() -> str | None:
            return TranscriptionQueueConsumer().pop_next_job_id()

        job_id = await asyncio.to_thread(_pop)
        if not job_id:
            return None
        return DequeuedJob(
            job=TranscriptionQueueJob(job_id=job_id),
            receipt="",
        )

    async def acknowledge(self, job_id: str, receipt: str) -> None:  # noqa: ARG002
        return None

    async def move_to_poison(self, job_id: str, reason: str, receipt: str = "") -> None:  # noqa: ARG002
        db = get_database()

        def _sync_ins() -> None:
            doc = getattr(db, "transcription_poison_journal", None)
            if doc is None:
                return
            try:
                doc.insert_one(
                    {
                        "job_id": job_id,
                        "reason": reason,
                        "moved_at": datetime.now(timezone.utc),
                    }
                )
            except AttributeError:
                pass

        await asyncio.to_thread(_sync_ins)

    async def get_queue_depth(self) -> int:
        db = get_database()

        def _count() -> int:
            try:
                return int(db.transcription_queue.count_documents({}))
            except Exception:
                return 0

        return await asyncio.to_thread(_count)

    async def get_poison_queue_depth(self) -> int:
        db = get_database()

        def _count() -> int:
            try:
                return int(db.transcription_poison_journal.count_documents({}))
            except Exception:
                return 0

        return await asyncio.to_thread(_count)

    async def health_check(self) -> bool:
        db = get_database()

        def _ping() -> bool:
            try:
                db.command("ping")
                return True
            except Exception:
                return False

        return await asyncio.to_thread(_ping)
