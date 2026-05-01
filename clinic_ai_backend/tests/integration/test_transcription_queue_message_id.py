from __future__ import annotations

from datetime import datetime, timezone

from src.adapters.transcription.types import TranscriptionQueueJob


class _DummyStorageAdapter:
    async def upload(self, audio_bytes: bytes, filename: str, metadata: dict[str, str]) -> str:  # noqa: ARG002
        return "gridfs://dummy"

    async def download(self, blob_url: str) -> bytes:  # noqa: ARG002
        return b""

    async def delete_blob(self, blob_url: str | None) -> None:  # noqa: ARG002
        return None

    async def get_signed_url(self, blob_url: str, expires_in_seconds: int = 3600) -> str:  # noqa: ARG002
        return blob_url

    async def health_check(self) -> bool:
        return True


class _DummyQueueAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def enqueue(self, job: TranscriptionQueueJob) -> str:  # noqa: ARG002
        self.calls += 1
        return f"azure-msg-{self.calls}"

    async def dequeue(self, visibility_timeout: int = 600):  # noqa: ARG002
        return None

    async def acknowledge(self, job_id: str, receipt: str) -> None:  # noqa: ARG002
        return None

    async def move_to_poison(self, job_id: str, reason: str, receipt: str = "") -> None:  # noqa: ARG002
        return None

    async def get_queue_depth(self) -> int:
        return 0

    async def get_poison_queue_depth(self) -> int:
        return 0

    async def health_check(self) -> bool:
        return True


def test_transcription_job_records_queue_message_id(app_client, patched_db, monkeypatch) -> None:
    patched_db.pre_visit_summaries.insert_one(
        {
            "patient_id": "p1",
            "visit_id": "v1",
            "status": "generated",
            "updated_at": datetime.now(timezone.utc),
        }
    )
    queue = _DummyQueueAdapter()
    monkeypatch.setattr("src.api.routers.transcription.get_audio_storage_adapter", lambda: _DummyStorageAdapter())
    monkeypatch.setattr("src.api.routers.transcription.get_queue_adapter", lambda: queue)
    response = app_client.post(
        "/api/notes/transcribe",
        data={"patient_id": "p1", "visit_id": "v1"},
        files={"audio_file": ("sample.wav", b"abc123", "audio/wav")},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    job = patched_db.transcription_jobs.find_one({"job_id": job_id})
    assert job is not None
    assert job["queue_message_id"] == "azure-msg-1"
    assert queue.calls == 1


def test_transcription_retry_reuses_active_job_by_idempotency_key(app_client, patched_db, monkeypatch) -> None:
    patched_db.pre_visit_summaries.insert_one(
        {
            "patient_id": "p1",
            "visit_id": "v1",
            "status": "generated",
            "updated_at": datetime.now(timezone.utc),
        }
    )
    queue = _DummyQueueAdapter()
    monkeypatch.setattr("src.api.routers.transcription.get_audio_storage_adapter", lambda: _DummyStorageAdapter())
    monkeypatch.setattr("src.api.routers.transcription.get_queue_adapter", lambda: queue)

    first = app_client.post(
        "/api/notes/transcribe",
        data={"patient_id": "p1", "visit_id": "v1"},
        files={"audio_file": ("sample.wav", b"abc123", "audio/wav")},
        headers={"X-Idempotency-Key": "k-123"},
    )
    second = app_client.post(
        "/api/notes/transcribe",
        data={"patient_id": "p1", "visit_id": "v1"},
        files={"audio_file": ("sample.wav", b"abc123", "audio/wav")},
        headers={"X-Idempotency-Key": "k-123"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert queue.calls == 1
    assert patched_db.transcription_jobs.count_documents({}) == 1
