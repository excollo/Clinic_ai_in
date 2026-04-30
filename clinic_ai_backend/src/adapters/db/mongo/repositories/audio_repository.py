"""Mongo repository for transcription pipeline."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pymongo import ASCENDING, DESCENDING

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.models.audio_doc import build_audio_doc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AudioRepository:
    """Repository for audio files, jobs and transcription results."""

    def __init__(self) -> None:
        self.db = get_database()
        self.audio_files = self.db.audio_files
        self.transcription_jobs = self.db.transcription_jobs
        self.transcription_results = self.db.transcription_results
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.audio_files.create_index([("sha256", ASCENDING), ("patient_id", ASCENDING), ("visit_id", ASCENDING)])
        self.transcription_jobs.create_index([("job_id", ASCENDING)], unique=True)
        self.transcription_jobs.create_index([("patient_id", ASCENDING), ("created_at", DESCENDING)])
        self.transcription_jobs.create_index([("visit_id", ASCENDING), ("created_at", DESCENDING)])

    def create_audio_file(self, **kwargs: object) -> dict:
        doc = build_audio_doc(**kwargs)
        self.audio_files.insert_one(doc)
        return doc

    def create_job(
        self,
        *,
        job_id: str,
        audio_id: str,
        patient_id: str,
        visit_id: str | None,
        provider: str,
        noise_environment: str,
        language_mix: str,
        speaker_mode: str,
        max_retries: int,
    ) -> dict:
        now = _utc_now()
        doc = {
            "job_id": job_id,
            "audio_id": audio_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "status": "queued",
            "provider": provider,
            "noise_environment": noise_environment,
            "language_mix": language_mix,
            "speaker_mode": speaker_mode,
            "retry_count": 0,
            "max_retries": max_retries,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "updated_at": now,
            "error_code": None,
            "error_message": None,
        }
        self.transcription_jobs.insert_one(doc)
        return doc

    def get_job(self, job_id: str) -> dict | None:
        return self.transcription_jobs.find_one({"job_id": job_id})

    def get_audio_by_id(self, audio_id: str) -> dict | None:
        return self.audio_files.find_one({"audio_id": audio_id})

    def mark_processing(self, job_id: str) -> None:
        now = _utc_now()
        self.transcription_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "processing", "started_at": now, "updated_at": now, "error_code": None, "error_message": None}},
        )

    def mark_completed(self, job_id: str) -> None:
        now = _utc_now()
        self.transcription_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "completed", "completed_at": now, "updated_at": now}},
        )

    def mark_failed(self, job_id: str, *, error_code: str, error_message: str) -> None:
        now = _utc_now()
        self.transcription_jobs.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "completed_at": now,
                    "updated_at": now,
                    "error_code": error_code,
                    "error_message": error_message,
                }
            },
        )

    def increment_retry(
        self, job_id: str, *, error_code: str | None = None, error_message: str | None = None
    ) -> dict | None:
        now = _utc_now()
        update: dict = {"$inc": {"retry_count": 1}, "$set": {"status": "queued", "updated_at": now}}
        if error_code is not None:
            update["$set"]["error_code"] = error_code
        if error_message is not None:
            update["$set"]["error_message"] = error_message
        self.transcription_jobs.update_one(
            {"job_id": job_id},
            update,
        )
        return self.get_job(job_id)

    def requeue_stale_processing_jobs(self, *, max_processing_sec: int) -> list[str]:
        """Move stale processing jobs back to queued and return their IDs."""
        cutoff = _utc_now() - timedelta(seconds=max_processing_sec)
        stale_jobs = list(
            self.transcription_jobs.find(
                {
                    "status": "processing",
                    "started_at": {"$lt": cutoff},
                },
                {"job_id": 1},
            )
        )
        if not stale_jobs:
            return []
        stale_job_ids = [str(item.get("job_id", "")).strip() for item in stale_jobs if item.get("job_id")]
        if not stale_job_ids:
            return []
        now = _utc_now()
        self.transcription_jobs.update_many(
            {"job_id": {"$in": stale_job_ids}},
            {
                "$inc": {"retry_count": 1},
                "$set": {
                    "status": "queued",
                    "updated_at": now,
                    "error_code": "TRANSCRIPTION_STALE_REQUEUED",
                    "error_message": "Job was stale in processing and has been requeued",
                },
            },
        )
        return stale_job_ids

    def save_result(self, result_doc: dict) -> None:
        result_doc["created_at"] = _utc_now()
        self.transcription_results.replace_one({"job_id": result_doc["job_id"]}, result_doc, upsert=True)

    def get_result(self, job_id: str) -> dict | None:
        return self.transcription_results.find_one({"job_id": job_id})
