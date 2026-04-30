"""Transcription routes module."""
from __future__ import annotations

import asyncio
import logging
import hashlib
from datetime import datetime, timezone
from urllib.parse import unquote
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.repositories.audio_repository import AudioRepository
from src.adapters.db.mongo.repositories.visit_transcription_repository import VisitTranscriptionRepository
from src.adapters.external.queue.producer import TranscriptionQueueProducer
from src.adapters.external.storage.object_storage import TranscriptionAudioStore
from src.api.schemas.audio import (
    SpeakerMode,
    TranscriptionUploadAcceptedResponse,
)
from src.api.schemas.transcription_session import TranscriptionSessionResponse
from src.application.services.dialogue_pii import scrub_dialogue_turns
from src.application.services.structure_dialogue import structure_dialogue_from_transcript_sync
from src.application.utils.patient_id_crypto import encode_patient_id, resolve_internal_patient_id
from src.core.config import get_settings

router = APIRouter(prefix="/api/notes", tags=["Transcription"])
_upload_log = logging.getLogger(__name__)


def _as_utc_aware(value: datetime) -> datetime:
    """Mongo/BSON often returns naive UTC datetimes; normalize for arithmetic with aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc_aware(value).isoformat()


@router.post("/transcribe", response_model=TranscriptionUploadAcceptedResponse, status_code=202)
async def upload_transcription_audio(
    patient_id: str = Form(...),
    visit_id: str = Form(...),
    audio_file: UploadFile = File(...),
    language_mix: str = Form(default="en"),
    speaker_mode: SpeakerMode = Form(default="two_speakers"),
) -> TranscriptionUploadAcceptedResponse:
    """Upload audio, create job and enqueue async processing (visit session when visit_id is set)."""
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    db = get_database()
    previsit = db.pre_visit_summaries.find_one(
        {"patient_id": internal_patient_id, "visit_id": visit_id},
        sort=[("updated_at", -1)],
    )
    if not previsit:
        raise HTTPException(status_code=409, detail="PREVISIT_MISSING")

    settings = get_settings()
    if not settings.azure_speech_key:
        raise HTTPException(status_code=503, detail="AZURE_SPEECH_KEY is not configured")
    content_type = str(audio_file.content_type or "").strip().lower()
    if content_type not in settings.allowed_audio_mime_types:
        raise HTTPException(status_code=400, detail="Unsupported audio MIME type")

    payload = await audio_file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(payload) > settings.max_audio_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds max size")

    if settings.transcription_debug_bytes:
        _upload_log.info(
            "transcription_upload_multipart patient_id=%s visit_id=%s filename=%s bytes=%s content_type=%s",
            internal_patient_id,
            visit_id,
            audio_file.filename,
            len(payload),
            content_type,
        )

    digest = hashlib.sha256(payload).hexdigest()
    now = datetime.now(timezone.utc)
    audio_id = str(uuid4())
    job_id = str(uuid4())
    logical_name = f"{internal_patient_id}/{visit_id}/{audio_id}_{audio_file.filename}"
    storage_ref = TranscriptionAudioStore().upload_audio(
        blob_path=logical_name,
        audio_bytes=payload,
        mime_type=content_type or "application/octet-stream",
    )

    effective_language = _normalize_language_mix(language_mix)
    # Kept for audit consistency in stored docs; no longer user-configurable in API form.
    noise_environment = "quiet_clinic"

    repo = AudioRepository()
    repo.create_audio_file(
        audio_id=audio_id,
        patient_id=internal_patient_id,
        visit_id=visit_id,
        storage_ref=storage_ref,
        bucket=settings.mongo_audio_bucket_name,
        mime_type=content_type or "application/octet-stream",
        size_bytes=len(payload),
        sha256=digest,
        noise_environment=noise_environment,
        language_mix=effective_language,
        speaker_mode=speaker_mode,
    )
    repo.create_job(
        job_id=job_id,
        audio_id=audio_id,
        patient_id=internal_patient_id,
        visit_id=visit_id,
        provider="azure_speech",
        noise_environment=noise_environment,
        language_mix=effective_language,
        speaker_mode=speaker_mode,
        max_retries=settings.transcription_max_retries,
    )
    TranscriptionQueueProducer().enqueue(job_id)

    VisitTranscriptionRepository().upsert_queued(
        patient_id=internal_patient_id,
        visit_id=visit_id,
        job_id=job_id,
        audio_id=audio_id,
        audio_file_path=storage_ref,
        language_mix=effective_language,
    )

    _upload_log.info(
        "transcription_upload_accepted job_id=%s audio_id=%s multipart_bytes=%s",
        job_id,
        audio_id,
        len(payload),
    )
    if settings.transcription_debug_bytes:
        try:
            roundtrip = len(TranscriptionAudioStore().download_audio(storage_ref))
            if roundtrip != len(payload):
                _upload_log.error(
                    "transcription_upload_storage_mismatch audio_id=%s multipart_bytes=%s stored_read_bytes=%s",
                    audio_id,
                    len(payload),
                    roundtrip,
                )
            else:
                _upload_log.info(
                    "transcription_upload_storage_roundtrip_ok audio_id=%s bytes=%s",
                    audio_id,
                    roundtrip,
                )
        except Exception as exc:  # noqa: BLE001
            _upload_log.warning(
                "transcription_upload_storage_verify_failed audio_id=%s error=%s",
                audio_id,
                exc,
            )

    opaque_patient_id = encode_patient_id(internal_patient_id)
    poll_hint = f"/api/notes/transcribe/status/{opaque_patient_id}/{visit_id}"
    return TranscriptionUploadAcceptedResponse(
        job_id=job_id,
        message_id=job_id,
        patient_id=opaque_patient_id,
        visit_id=visit_id,
        status="queued",
        received_at=now,
        message=f"Transcription queued. Poll {poll_hint} for status.",
    )


@router.get("/transcribe/status/{patient_id}/{visit_id}")
def get_visit_transcription_status(patient_id: str, visit_id: str) -> dict:
    """Poll visit-scoped transcription status (transcript-bundle compatible fields)."""
    internal_pid = resolve_internal_patient_id(unquote(patient_id), allow_raw_fallback=True)
    internal_vid = unquote(visit_id)
    repo = VisitTranscriptionRepository()
    session = repo.get_session(patient_id=internal_pid, visit_id=internal_vid)
    if not session:
        return {"status": "pending", "message": "Transcription not started"}

    session.pop("_id", None)
    transcription_status = str(session.get("transcription_status") or "pending").lower()
    now = datetime.now(timezone.utc)

    started_at = session.get("started_at")
    last_poll_at = session.get("last_poll_at")
    started_at_utc = _as_utc_aware(started_at) if isinstance(started_at, datetime) else None
    is_stale = False
    age_minutes = 0.0
    if transcription_status == "processing" and started_at_utc is not None:
        age_minutes = (now - started_at_utc).total_seconds() / 60.0
        if last_poll_at is None:
            last_poll_age_minutes = age_minutes
        elif isinstance(last_poll_at, datetime):
            last_poll_age_minutes = (now - _as_utc_aware(last_poll_at)).total_seconds() / 60.0
        else:
            last_poll_age_minutes = age_minutes
        if age_minutes > 30 and (last_poll_age_minutes > 20 or last_poll_at is None):
            is_stale = True
            transcription_status = "stale_processing"

    repo.touch_poll(patient_id=internal_pid, visit_id=internal_vid, last_poll_status=transcription_status)

    status_info: dict = {
        "status": transcription_status,
        "transcription_id": session.get("transcription_id"),
        "started_at": _iso_utc(session.get("started_at")),
        "last_poll_status": transcription_status,
        "last_poll_at": _iso_utc(now),
        "error_message": session.get("error_message"),
        "enqueued_at": _iso_utc(session.get("enqueued_at")),
        "dequeued_at": _iso_utc(session.get("dequeued_at")),
    }

    if transcription_status == "completed":
        status_info["transcript_available"] = True
        status_info["word_count"] = session.get("word_count")
        status_info["duration"] = session.get("audio_duration_seconds")
        status_info["audio_duration_seconds"] = session.get("audio_duration_seconds")
        status_info["completed_at"] = _iso_utc(session.get("completed_at"))
        status_info["message"] = "Transcription completed successfully"
    elif transcription_status in ("processing", "stale_processing"):
        status_info["audio_duration_seconds"] = session.get("audio_duration_seconds")
        status_info["message"] = (
            f"Transcription appears stuck (processing for {age_minutes:.1f} minutes). May need manual intervention."
            if is_stale
            else (
                f"Transcription in progress (running for {(now - started_at_utc).total_seconds():.0f} seconds)"
                if started_at_utc is not None
                else "Transcription in progress"
            )
        )
        if is_stale:
            status_info["next_action"] = "retry_or_reset"
    elif transcription_status == "failed":
        status_info["error"] = session.get("error_message")
        status_info["message"] = f"Transcription failed: {session.get('error_message')}"
    else:
        status_info["message"] = f"Transcription status: {transcription_status}"

    return status_info


@router.get("/{patient_id}/visits/{visit_id}/dialogue", response_model=None)
async def get_visit_transcription_dialogue(patient_id: str, visit_id: str) -> Response | TranscriptionSessionResponse:
    """Return transcript + optional structured dialogue; 202 with Retry-After while processing."""
    internal_pid = resolve_internal_patient_id(unquote(patient_id), allow_raw_fallback=True)
    internal_vid = unquote(visit_id)
    repo = VisitTranscriptionRepository()
    session = repo.get_session(patient_id=internal_pid, visit_id=internal_vid)
    transcription_status = (
        str(session.get("transcription_status") or "").lower()
        if session
        else "pending"
    )
    transcript = (session or {}).get("transcript") if session else None

    if not session:
        return Response(status_code=202, headers={"Retry-After": "60"})
    if transcription_status in {"", "pending", "queued", "processing"}:
        return Response(status_code=202, headers={"Retry-After": "60"})
    if transcription_status != "failed" and not transcript:
        return Response(status_code=202, headers={"Retry-After": "60"})

    structured = session.get("structured_dialogue")
    return TranscriptionSessionResponse(
        audio_file_path=session.get("audio_file_path"),
        transcript=transcript,
        transcription_status=transcription_status,
        started_at=_iso_utc(session.get("started_at")),
        completed_at=_iso_utc(session.get("completed_at")),
        error_message=session.get("error_message"),
        audio_duration_seconds=session.get("audio_duration_seconds"),
        word_count=session.get("word_count"),
        structured_dialogue=structured,
    )


@router.post("/{patient_id}/visits/{visit_id}/dialogue/structure")
async def structure_visit_dialogue(patient_id: str, visit_id: str) -> JSONResponse:
    """Structure stored transcript into Doctor/Patient JSON and scrub PII; persists on the visit session."""
    internal_pid = resolve_internal_patient_id(unquote(patient_id), allow_raw_fallback=True)
    internal_vid = unquote(visit_id)
    vrepo = VisitTranscriptionRepository()
    session = vrepo.get_session(patient_id=internal_pid, visit_id=internal_vid)
    if not session or not (session.get("transcript") or "").strip():
        raise HTTPException(
            status_code=404,
            detail={"error": "TRANSCRIPT_NOT_FOUND", "message": "No transcript found for this visit"},
        )
    raw = str(session.get("transcript") or "")
    language_mix = str(session.get("language_mix") or "en")
    try:
        dialogue = await asyncio.to_thread(
            structure_dialogue_from_transcript_sync,
            raw_transcript=raw,
            language=language_mix,
        )
    except RuntimeError as exc:
        if "OPENAI_API_KEY" in str(exc):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    scrubbed = scrub_dialogue_turns(dialogue)
    vrepo.save_structured_dialogue(patient_id=internal_pid, visit_id=internal_vid, dialogue=scrubbed)
    return JSONResponse(status_code=200, content={"dialogue": scrubbed, "message": "Success"})


def _normalize_language_mix(value: str) -> str:
    """Normalize input language hints; guard against Swagger default placeholder."""
    normalized = str(value or "").strip().lower()
    if normalized in {"", "string", "default"}:
        return "en"
    return normalized
