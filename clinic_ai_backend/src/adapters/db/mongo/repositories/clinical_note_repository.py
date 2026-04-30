"""Mongo repository for clinical notes."""
from __future__ import annotations

from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING

from src.adapters.db.mongo.client import get_database


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ClinicalNoteRepository:
    """Repository for India clinical and legacy SOAP notes."""

    def __init__(self) -> None:
        self.db = get_database()
        self.collection = self.db.clinical_notes
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.collection.create_index([("note_id", ASCENDING)], unique=True)
        self.collection.create_index([("patient_id", ASCENDING), ("created_at", DESCENDING)])
        self.collection.create_index([("visit_id", ASCENDING), ("note_type", ASCENDING)])
        self.collection.create_index([("source_job_id", ASCENDING), ("note_type", ASCENDING)])

    def create_note(self, doc: dict) -> dict:
        payload = dict(doc)
        payload.setdefault("created_at", _utc_now())
        payload.setdefault("version", 1)
        self.collection.insert_one(payload)
        return payload

    def find_by_note_id(self, note_id: str) -> dict | None:
        return self.collection.find_one({"note_id": note_id})

    def find_latest(
        self,
        *,
        patient_id: str | None = None,
        visit_id: str | None = None,
        note_type: str | None = None,
    ) -> dict | None:
        query: dict[str, object] = {}
        if patient_id:
            query["patient_id"] = patient_id
        if visit_id:
            query["visit_id"] = visit_id
        if note_type:
            query["note_type"] = note_type
        return self.collection.find_one(query, sort=[("created_at", -1)])

    def find_by_source_job(self, *, source_job_id: str, note_type: str) -> dict | None:
        return self.collection.find_one(
            {"source_job_id": source_job_id, "note_type": note_type},
            sort=[("created_at", -1)],
        )
