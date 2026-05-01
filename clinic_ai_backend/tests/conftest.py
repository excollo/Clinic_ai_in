"""Pytest fixtures and in-memory DB fakes."""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from pymongo import ReturnDocument

from src.app import create_app
from src.core import config as config_module


class InsertOneResult:
    def __init__(self, inserted_id: int) -> None:
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(self, matched_count: int) -> None:
        self.matched_count = matched_count
        self.modified_count = matched_count


class InMemoryCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self._next_id = 1

    def create_index(self, *_args, **_kwargs) -> None:
        return None

    def insert_one(self, doc: dict) -> InsertOneResult:
        item = deepcopy(doc)
        if "_id" not in item:
            item["_id"] = self._next_id
            self._next_id += 1
        self.docs.append(item)
        return InsertOneResult(item["_id"])

    def _matches(self, doc: dict, query: dict) -> bool:
        for key, value in query.items():
            doc_value = doc.get(key)
            if isinstance(value, dict):
                if "$lt" in value and not (doc_value is not None and doc_value < value["$lt"]):
                    return False
                if "$in" in value and doc_value not in value["$in"]:
                    return False
            elif doc_value != value:
                return False
        return True

    def find_one(
        self,
        query: dict | None = None,
        projection: dict | list[tuple[str, int]] | None = None,
        sort: list[tuple[str, int]] | None = None,
    ) -> dict | None:
        query = query or {}
        if isinstance(projection, list):
            sort = projection
            projection = None
        filtered = [doc for doc in self.docs if self._matches(doc, query)]
        if not filtered:
            return None
        if sort:
            for field, direction in reversed(sort):
                reverse = direction < 0
                filtered.sort(key=lambda item: item.get(field), reverse=reverse)
        item = deepcopy(filtered[0])
        if isinstance(projection, dict):
            include_keys = {key for key, value in projection.items() if value}
            if include_keys:
                item = {key: item.get(key) for key in include_keys if key in item}
            elif projection.get("_id") == 0:
                item.pop("_id", None)
        return item

    def find(self, query: dict | None = None, projection: dict | None = None) -> list[dict]:
        query = query or {}
        filtered = [deepcopy(doc) for doc in self.docs if self._matches(doc, query)]
        if projection is None:
            return filtered
        projected: list[dict] = []
        include_keys = {key for key, value in projection.items() if value}
        for item in filtered:
            if include_keys:
                projected.append({key: item.get(key) for key in include_keys if key in item})
            else:
                projected.append(item)
        return projected

    def delete_one(self, query: dict) -> None:
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.docs.pop(index)
                return

    def update_one(self, query: dict, update: dict, upsert: bool = False) -> UpdateResult:
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                updated = deepcopy(doc)
                for key, value in update.get("$set", {}).items():
                    updated[key] = value
                for key, value in update.get("$inc", {}).items():
                    updated[key] = int(updated.get(key, 0)) + int(value)
                self.docs[index] = updated
                return UpdateResult(1)
        if upsert and update.get("$set"):
            new_doc = {key: value for key, value in query.items()}
            new_doc.update(update["$set"])
            self.insert_one(new_doc)
            return UpdateResult(1)
        return UpdateResult(0)

    def update_many(self, query: dict, update: dict) -> None:
        modified = 0
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                updated = deepcopy(doc)
                for key, value in update.get("$set", {}).items():
                    updated[key] = value
                for key, value in update.get("$inc", {}).items():
                    updated[key] = int(updated.get(key, 0)) + int(value)
                self.docs[index] = updated
                modified += 1
        return UpdateResult(modified)

    def count_documents(self, query: dict) -> int:
        return len([doc for doc in self.docs if self._matches(doc, query)])

    def replace_one(self, query: dict, replacement: dict, upsert: bool = False) -> None:
        for index, doc in enumerate(self.docs):
            if self._matches(doc, query):
                item = deepcopy(replacement)
                item["_id"] = doc["_id"]
                self.docs[index] = item
                return
        if upsert:
            self.insert_one(replacement)

    def find_one_and_update(
        self,
        query: dict,
        update: dict,
        upsert: bool = False,
        return_document: ReturnDocument = ReturnDocument.BEFORE,
    ) -> dict | None:
        existing = self.find_one(query)
        if existing is None and upsert:
            seed = deepcopy(query)
            for key, value in update.get("$setOnInsert", {}).items():
                seed[key] = value
            self.insert_one(seed)
            existing = self.find_one(query)
        if existing is None:
            return None
        self.update_one(query, update, upsert=False)
        if return_document == ReturnDocument.AFTER:
            return self.find_one(query)
        return existing


class InMemoryDatabase:
    def __init__(self) -> None:
        self.users = InMemoryCollection()
        self.doctors = InMemoryCollection()
        self.otp_requests = InMemoryCollection()
        self.dev_otps = InMemoryCollection()
        self.consents = InMemoryCollection()
        self.consent_texts = InMemoryCollection()
        self.audio_files = InMemoryCollection()
        self.transcription_jobs = InMemoryCollection()
        self.transcription_results = InMemoryCollection()
        self.transcription_queue = InMemoryCollection()
        self.pre_visit_summaries = InMemoryCollection()
        self.intake_sessions = InMemoryCollection()
        self.patients = InMemoryCollection()
        self.visits = InMemoryCollection()
        self.vitals = InMemoryCollection()
        self.vitals_forms = InMemoryCollection()
        self.patient_vitals = InMemoryCollection()
        self.vitals_dynamic_cache = InMemoryCollection()
        self.clinical_notes = InMemoryCollection()
        self.india_clinical_notes = InMemoryCollection()
        self.medication_schedules = InMemoryCollection()
        self.lab_results = InMemoryCollection()
        self.continuity_summaries = InMemoryCollection()
        self.notifications = InMemoryCollection()
        self.whatsapp_messages = InMemoryCollection()
        self.follow_up_reminders = InMemoryCollection()
        self.follow_through_lab_records = InMemoryCollection()
        self.visit_transcription_sessions = InMemoryCollection()


@pytest.fixture
def fake_db() -> InMemoryDatabase:
    return InMemoryDatabase()


@pytest.fixture(autouse=True)
def force_azure_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic regardless of your local `.env`."""
    settings = config_module.get_settings()
    settings.use_local_adapters = False
    settings.azure_speech_key = settings.azure_speech_key or "test-azure-key"
    settings.allow_local_audio_fallback = True
    monkeypatch.setattr("src.core.config.get_settings", lambda: settings)


@pytest.fixture
def patched_db(fake_db: InMemoryDatabase, monkeypatch: pytest.MonkeyPatch) -> InMemoryDatabase:
    monkeypatch.setattr("src.adapters.db.mongo.client.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.workflow.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.transcription.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.followthrough.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.patients.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.visits.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.contextai.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.frontend_contract.get_database", lambda: fake_db)
    monkeypatch.setattr("src.adapters.external.queue.producer.get_database", lambda: fake_db)
    monkeypatch.setattr("src.adapters.external.queue.consumer.get_database", lambda: fake_db)
    monkeypatch.setattr("src.adapters.db.mongo.repositories.audio_repository.get_database", lambda: fake_db)
    monkeypatch.setattr(
        "src.adapters.db.mongo.repositories.visit_transcription_repository.get_database", lambda: fake_db
    )
    monkeypatch.setattr("src.adapters.db.mongo.repositories.clinical_note_repository.get_database", lambda: fake_db)
    monkeypatch.setattr("src.workers.transcription_worker.get_database", lambda: fake_db)
    monkeypatch.setattr("src.application.use_cases.generate_india_clinical_note.get_database", lambda: fake_db)
    monkeypatch.setattr("src.application.use_cases.generate_post_visit_summary.get_database", lambda: fake_db)
    monkeypatch.setattr("src.application.use_cases.generate_soap_note.get_database", lambda: fake_db)
    monkeypatch.setattr("src.api.routers.transcription.asyncio.create_task", lambda coro: coro.close())
    return fake_db


@pytest.fixture
def app_client(patched_db: InMemoryDatabase, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Disable background transcription workers so the in-memory queue stays deterministic."""
    monkeypatch.setattr("src.app.start_background_workers", lambda: None)

    async def _noop_stop() -> None:
        return None

    monkeypatch.setattr("src.app.stop_background_workers", _noop_stop)
    app = create_app()
    return TestClient(app)
