"""Per-visit transcription session state for polling and dialogue APIs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING

from src.adapters.db.mongo.client import get_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VisitTranscriptionRepository:
    """Stores visit-scoped transcription lifecycle (aligned with transcript-bundle semantics)."""

    def __init__(self) -> None:
        self.db = get_database()
        self.collection = self.db.visit_transcription_sessions
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.collection.create_index(
            [("patient_id", ASCENDING), ("visit_id", ASCENDING)],
            unique=True,
        )
        self.collection.create_index([("patient_id", ASCENDING), ("updated_at", DESCENDING)])

    def upsert_queued(
        self,
        *,
        patient_id: str,
        visit_id: str,
        job_id: str,
        audio_id: str,
        audio_file_path: str | None,
        language_mix: str,
    ) -> None:
        now = _utc_now()
        self.collection.update_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            {
                "$set": {
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "job_id": job_id,
                    "audio_id": audio_id,
                    "audio_file_path": audio_file_path,
                    "language_mix": language_mix,
                    "transcription_status": "queued",
                    "transcript": None,
                    "structured_dialogue": None,
                    "error_message": None,
                    "word_count": None,
                    "audio_duration_seconds": None,
                    "transcription_id": None,
                    "enqueued_at": now,
                    "dequeued_at": None,
                    "started_at": None,
                    "completed_at": None,
                    "last_poll_at": None,
                    "last_poll_status": None,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

    def mark_processing(self, *, patient_id: str, visit_id: str) -> None:
        now = _utc_now()
        self.collection.update_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            {
                "$set": {
                    "transcription_status": "processing",
                    "started_at": now,
                    "dequeued_at": now,
                    "updated_at": now,
                }
            },
        )

    def mark_completed(
        self,
        *,
        patient_id: str,
        visit_id: str,
        transcript: str,
        structured_dialogue: list[dict[str, str]],
        word_count: int,
        audio_duration_seconds: float | None,
    ) -> None:
        now = _utc_now()
        self.collection.update_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            {
                "$set": {
                    "transcription_status": "completed",
                    "transcript": transcript,
                    "structured_dialogue": structured_dialogue,
                    "word_count": word_count,
                    "audio_duration_seconds": audio_duration_seconds,
                    "completed_at": now,
                    "error_message": None,
                    "updated_at": now,
                }
            },
        )

    def mark_failed(self, *, patient_id: str, visit_id: str, error_message: str) -> None:
        now = _utc_now()
        self.collection.update_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            {
                "$set": {
                    "transcription_status": "failed",
                    "error_message": error_message,
                    "completed_at": now,
                    "updated_at": now,
                }
            },
        )

    def touch_poll(self, *, patient_id: str, visit_id: str, last_poll_status: str) -> None:
        now = _utc_now()
        self.collection.update_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            {"$set": {"last_poll_at": now, "last_poll_status": last_poll_status, "updated_at": now}},
        )

    def get_session(self, *, patient_id: str, visit_id: str) -> dict[str, Any] | None:
        return self.collection.find_one({"patient_id": patient_id, "visit_id": visit_id})

    def save_structured_dialogue(self, *, patient_id: str, visit_id: str, dialogue: list[dict[str, str]]) -> bool:
        now = _utc_now()
        result = self.collection.update_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            {"$set": {"structured_dialogue": dialogue, "updated_at": now}},
        )
        return result.matched_count > 0
