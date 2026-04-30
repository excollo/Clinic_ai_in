"""Integration tests for transcription V2 endpoints and worker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.core import config as config_module
from src.workers.transcription_worker import TranscriptionWorker


def _no_auto_openai_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid calling OpenAI during worker tests when OPENAI_API_KEY is set in the environment."""
    monkeypatch.setattr(
        "src.workers.transcription_worker.structure_dialogue_from_transcript_sync",
        lambda **_kwargs: [],
    )


def _patch_upload_writes_temp_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Avoid GridFS in unit tests; persist upload bytes under tmp_path as file:// refs."""

    def _fake_upload(_self, *, blob_path: str, audio_bytes: bytes, mime_type: str) -> str:
        safe = blob_path.replace("/", "_")[-120:]
        path = tmp_path / f"up_{safe}"
        path.write_bytes(audio_bytes)
        return f"file://{path.as_posix()}"

    monkeypatch.setattr(
        "src.api.routers.transcription.TranscriptionAudioStore.upload_audio",
        _fake_upload,
    )


def _insert_previsit(fake_db, patient_id: str, visit_id: str = "v1") -> None:
    fake_db.pre_visit_summaries.insert_one(
        {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "status": "generated",
            "updated_at": datetime.now(timezone.utc),
        }
    )


def test_upload_happy_path(app_client, fake_db, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _insert_previsit(fake_db, "p1")
    _patch_upload_writes_temp_file(monkeypatch, tmp_path)

    response = app_client.post(
        "/notes/transcribe",
        data={
            "patient_id": "p1",
            "visit_id": "v1",
            "noise_environment": "quiet_clinic",
            "language_mix": "hi-en",
            "speaker_mode": "two_speakers",
        },
        files={"audio_file": ("sample.wav", b"abc123", "audio/wav")},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["patient_id"] == "p1"
    assert payload["visit_id"] == "v1"
    assert payload["status"] == "queued"
    assert payload["job_id"] == payload["message_id"]
    assert "Poll" in (payload.get("message") or "")
    assert len(fake_db.audio_files.docs) == 1
    assert len(fake_db.transcription_jobs.docs) == 1
    assert len(fake_db.transcription_queue.docs) == 1
    assert len(fake_db.visit_transcription_sessions.docs) == 1


def test_upload_rejects_when_previsit_missing(app_client) -> None:
    response = app_client.post(
        "/notes/transcribe",
        data={
            "patient_id": "missing-patient",
            "visit_id": "v1",
            "noise_environment": "quiet_clinic",
            "language_mix": "hi-en",
            "speaker_mode": "two_speakers",
        },
        files={"audio_file": ("sample.wav", b"abc123", "audio/wav")},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "PREVISIT_MISSING"


def test_worker_defensive_gate_fails_cleanly(fake_db, patched_db, tmp_path: Path) -> None:
    audio_path = tmp_path / "a1.wav"
    audio_path.write_bytes(b"x")
    ref = f"file://{audio_path.as_posix()}"
    fake_db.audio_files.insert_one(
        {
            "audio_id": "a1",
            "patient_id": "p2",
            "visit_id": "v2",
            "storage_ref": ref,
            "blob_url": ref,
            "blob_path": ref,
        }
    )
    fake_db.transcription_jobs.insert_one(
        {
            "job_id": "j1",
            "audio_id": "a1",
            "patient_id": "p2",
            "visit_id": "v2",
            "status": "queued",
            "retry_count": 0,
            "max_retries": 2,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    fake_db.transcription_queue.insert_one({"job_id": "j1", "queued_at": datetime.now(timezone.utc)})

    worker = TranscriptionWorker()
    worked = worker.process_next()

    assert worked is True
    job = fake_db.transcription_jobs.find_one({"job_id": "j1"})
    assert job["status"] == "failed"
    assert job["error_code"] == "PREVISIT_MISSING"


def test_low_confidence_triggers_manual_review(
    fake_db, patched_db, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _no_auto_openai_structure(monkeypatch)
    _insert_previsit(fake_db, "p3", "v3")
    audio_path = tmp_path / "a3.wav"
    audio_path.write_bytes(b"x")
    ref = f"file://{audio_path.as_posix()}"
    fake_db.audio_files.insert_one(
        {
            "audio_id": "a3",
            "patient_id": "p3",
            "visit_id": "v3",
            "storage_ref": ref,
            "blob_url": ref,
            "blob_path": ref,
        }
    )
    fake_db.transcription_jobs.insert_one(
        {
            "job_id": "j3",
            "audio_id": "a3",
            "patient_id": "p3",
            "visit_id": "v3",
            "status": "queued",
            "noise_environment": "crowded_opd",
            "language_mix": "hi-en",
            "speaker_mode": "two_speakers",
            "retry_count": 0,
            "max_retries": 2,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    fake_db.transcription_queue.insert_one({"job_id": "j3", "queued_at": datetime.now(timezone.utc)})
    monkeypatch.setattr(
        "src.workers.transcription_worker.TranscriptionWorker._call_azure_speech",
        lambda self, **_kwargs: {
            "language_detected": "hi-en",
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 500,
                    "speaker_label": "doctor",
                    "text": "namaste",
                    "confidence": 0.4,
                },
                {
                    "start_ms": 501,
                    "end_ms": 1000,
                    "speaker_label": "patient",
                    "text": "dard",
                    "confidence": 0.45,
                },
            ],
        },
    )
    worker = TranscriptionWorker()
    worker.process_next()

    result = fake_db.transcription_results.find_one({"job_id": "j3"})
    assert result is not None
    assert result["requires_manual_review"] is True
    assert all(segment["needs_manual_review"] for segment in result["segments"])


def test_visit_transcription_status_after_upload(
    app_client, fake_db, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _insert_previsit(fake_db, "p1")
    _patch_upload_writes_temp_file(monkeypatch, tmp_path)
    app_client.post(
        "/notes/transcribe",
        data={
            "patient_id": "p1",
            "visit_id": "v1",
            "noise_environment": "quiet_clinic",
            "language_mix": "hi-en",
            "speaker_mode": "two_speakers",
        },
        files={"audio_file": ("sample.wav", b"abc123", "audio/wav")},
    )
    response = app_client.get("/notes/transcribe/status/p1/v1")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert "enqueued_at" in body


def test_visit_transcription_status_processing_naive_mongo_datetimes(app_client, fake_db) -> None:
    """Processing age must tolerate naive UTC datetimes (common BSON decode); must not 500."""
    aware = datetime.now(timezone.utc)
    naive_started = aware.replace(tzinfo=None)
    naive_poll = (aware - timedelta(minutes=1)).replace(tzinfo=None)
    fake_db.visit_transcription_sessions.insert_one(
        {
            "patient_id": "p-naive",
            "visit_id": "v-naive",
            "transcription_status": "processing",
            "started_at": naive_started,
            "last_poll_at": naive_poll,
            "transcript": None,
            "job_id": "j1",
        }
    )
    response = app_client.get("/notes/transcribe/status/p-naive/v-naive")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "processing"
    assert "progress" in (body.get("message") or "").lower()


def test_visit_dialogue_returns_202_while_queued(
    app_client, fake_db, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _insert_previsit(fake_db, "p1")
    _patch_upload_writes_temp_file(monkeypatch, tmp_path)
    app_client.post(
        "/notes/transcribe",
        data={
            "patient_id": "p1",
            "visit_id": "v1",
            "noise_environment": "quiet_clinic",
            "language_mix": "en",
            "speaker_mode": "two_speakers",
        },
        files={"audio_file": ("sample.wav", b"x", "audio/wav")},
    )
    response = app_client.get("/notes/p1/visits/v1/dialogue")
    assert response.status_code == 202
    assert response.headers.get("Retry-After") == "60"


def test_visit_dialogue_returns_payload_when_completed(app_client, fake_db) -> None:
    now = datetime.now(timezone.utc)
    fake_db.visit_transcription_sessions.insert_one(
        {
            "patient_id": "p1",
            "visit_id": "v1",
            "transcription_status": "completed",
            "transcript": "hello world",
            "structured_dialogue": [{"Doctor": "hello"}],
            "audio_file_path": "p1/v1/a.wav",
            "started_at": now,
            "completed_at": now,
            "word_count": 2,
            "audio_duration_seconds": 1.0,
            "error_message": None,
        }
    )
    response = app_client.get("/notes/p1/visits/v1/dialogue")
    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "hello world"
    assert body["structured_dialogue"][0]["Doctor"] == "hello"


def test_structure_dialogue_endpoint_persists(
    app_client, fake_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_db.visit_transcription_sessions.insert_one(
        {
            "patient_id": "p1",
            "visit_id": "v1",
            "transcription_status": "completed",
            "transcript": "Doctor: How are you? Patient: Fine.",
            "language_mix": "en",
            "structured_dialogue": None,
        }
    )

    def _fake_structure(*, raw_transcript: str, language: str = "en") -> list[dict[str, str]]:
        assert "How are you" in raw_transcript
        return [{"Doctor": "How are you?"}, {"Patient": "Fine."}]

    monkeypatch.setattr(
        "src.api.routers.transcription.structure_dialogue_from_transcript_sync",
        _fake_structure,
    )
    response = app_client.post("/notes/p1/visits/v1/dialogue/structure")
    assert response.status_code == 200
    assert response.json()["dialogue"][0]["Doctor"] == "How are you?"
    stored = fake_db.visit_transcription_sessions.find_one({"patient_id": "p1", "visit_id": "v1"})
    assert stored is not None
    assert stored["structured_dialogue"][0]["Doctor"] == "How are you?"


def test_worker_marks_visit_session_completed(
    app_client, fake_db, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _no_auto_openai_structure(monkeypatch)
    _insert_previsit(fake_db, "p9", "v9")
    _patch_upload_writes_temp_file(monkeypatch, tmp_path)
    upload = app_client.post(
        "/notes/transcribe",
        data={
            "patient_id": "p9",
            "visit_id": "v9",
            "noise_environment": "quiet_clinic",
            "language_mix": "en",
            "speaker_mode": "two_speakers",
        },
        files={"audio_file": ("sample.wav", b"x", "audio/wav")},
    )
    assert upload.status_code == 202
    monkeypatch.setattr(
        "src.workers.transcription_worker.TranscriptionWorker._call_azure_speech",
        lambda self, **_kwargs: {
            "language_detected": "en",
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 500,
                    "speaker_label": "doctor",
                    "text": "namaste",
                    "confidence": 0.95,
                },
            ],
        },
    )
    worker = TranscriptionWorker()
    worker.process_next()
    session = fake_db.visit_transcription_sessions.find_one({"patient_id": "p9", "visit_id": "v9"})
    assert session is not None
    assert session["transcription_status"] == "completed"
    assert "namaste" in (session.get("transcript") or "")
    assert session.get("structured_dialogue")


def test_worker_visit_uses_openai_structure_when_segments_are_unknown(
    fake_db,
    patched_db,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Target 2: single unknown STT segment must not be the only dialogue — OpenAI fills Doctor/Patient."""
    settings = config_module.get_settings()
    settings.openai_api_key = "sk-test-not-called"
    monkeypatch.setattr("src.core.config.get_settings", lambda: settings)

    def _fake_structure(*, raw_transcript: str, language: str = "en") -> list[dict[str, str]]:
        assert "throat" in raw_transcript.lower()
        return [{"Doctor": "Tell me more."}, {"Patient": "My throat hurts."}]

    monkeypatch.setattr(
        "src.workers.transcription_worker.structure_dialogue_from_transcript_sync",
        _fake_structure,
    )

    _insert_previsit(fake_db, "p10", "v10")
    audio_path = tmp_path / "a10.wav"
    audio_path.write_bytes(b"x")
    ref = f"file://{audio_path.as_posix()}"
    fake_db.audio_files.insert_one(
        {
            "audio_id": "a10",
            "patient_id": "p10",
            "visit_id": "v10",
            "storage_ref": ref,
            "blob_url": ref,
            "blob_path": ref,
            "mime_type": "audio/wav",
        }
    )
    fake_db.transcription_jobs.insert_one(
        {
            "job_id": "j10",
            "audio_id": "a10",
            "patient_id": "p10",
            "visit_id": "v10",
            "status": "queued",
            "language_mix": "en",
            "retry_count": 0,
            "max_retries": 2,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    fake_db.transcription_queue.insert_one({"job_id": "j10", "queued_at": datetime.now(timezone.utc)})
    now = datetime.now(timezone.utc)
    fake_db.visit_transcription_sessions.insert_one(
        {
            "patient_id": "p10",
            "visit_id": "v10",
            "job_id": "j10",
            "audio_id": "a10",
            "audio_file_path": ref,
            "language_mix": "en",
            "transcription_status": "queued",
            "transcript": None,
            "structured_dialogue": None,
            "enqueued_at": now,
            "updated_at": now,
        }
    )

    monkeypatch.setattr(
        "src.workers.transcription_worker.TranscriptionWorker._call_azure_speech",
        lambda self, **_kwargs: {
            "language_detected": "en-IN",
            "segments": [
                {
                    "start_ms": 0,
                    "end_ms": 1200,
                    "speaker_label": "unknown",
                    "text": "Doctor, my throat hurts since yesterday.",
                    "confidence": 0.9,
                },
            ],
        },
    )

    worker = TranscriptionWorker()
    worker.process_next()

    session = fake_db.visit_transcription_sessions.find_one({"patient_id": "p10", "visit_id": "v10"})
    assert session is not None
    sd = session.get("structured_dialogue") or []
    assert len(sd) >= 2
    assert any("Doctor" in turn for turn in sd)
    assert any("Patient" in turn for turn in sd)

    result = fake_db.transcription_results.find_one({"job_id": "j10"})
    assert result is not None
    assert len(result.get("segments") or []) == 1
    assert result["segments"][0]["speaker_label"] == "Patient"
