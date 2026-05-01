"""Internal endpoints for integrations (Azure Speech batch audio fetch — no JWT)."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pymongo.errors import DuplicateKeyError

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.repositories.audio_repository import AudioRepository
from src.adapters.external.storage.object_storage import TranscriptionAudioStore
from src.application.services.audio_signed_url import (
    token_fingerprint,
    verify_audio_access_token,
)
from src.core.errors import ConfigurationError

router = APIRouter(prefix="/internal/audio", tags=["Internal"])
_log = logging.getLogger(__name__)

# Per-process rate limit: max 10 attempted fetches per minute per audio_id (all outcomes).
_rate_buckets: defaultdict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 10
_RATE_WINDOW_SEC = 60.0


def _audit_signed_audio_access(
    *,
    request: Request,
    action: str,
    resource_id: str,
    status: str,
    status_code: int,
    extra: dict | None = None,
) -> None:
    db = get_database()
    ctx = {"path": str(request.url.path), "method": request.method}
    if isinstance(extra, dict):
        ctx.update(extra)
    try:
        db.audit_log.insert_one(
            {
                "entry_id": f"audit_{uuid4().hex[:16]}",
                "doctor_id": "azure_speech_batch",
                "patient_id": None,
                "visit_id": None,
                "action": action,
                "resource_type": "audio_file",
                "resource_id": resource_id,
                "ip_address": request.client.host if request.client else "",
                "user_agent": request.headers.get("user-agent", ""),
                "timestamp": datetime.now(timezone.utc),
                "status_code": status_code,
                "audit_status": status,
                "additional_context": ctx,
            }
        )
    except AttributeError:
        pass


def _rate_limit(audio_id: str) -> None:
    now = time.time()
    cutoff = now - _RATE_WINDOW_SEC
    bucket = _rate_buckets[audio_id]
    bucket[:] = [t for t in bucket if t >= cutoff]
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="RATE_LIMIT_AUDIO_FETCH")
    bucket.append(now)


@router.get("/{audio_id}")
async def stream_audio_for_transcription(
    request: Request,
    audio_id: str,
    token: str = Query(..., description="HMAC-signed, time-limited access token"),
) -> Response:
    """Allow Azure Speech (or similar) to download audio bytes from GridFS using a signed URL."""
    if not token.strip():
        raise HTTPException(status_code=400, detail="missing_token")

    try:
        verified = verify_audio_access_token(audio_id=audio_id, token=token)
    except ConfigurationError:
        raise HTTPException(status_code=503, detail="AUDIO_URL_SIGNING_MISCONFIGURED") from None
    except ValueError as exc:
        reason = str(exc.args[0] if exc.args else exc)
        _audit_signed_audio_access(
            request=request,
            action="audio_stream_attempt",
            resource_id=audio_id,
            status="failure",
            status_code=401,
            extra={"reason": reason},
        )
        raise HTTPException(status_code=401, detail="INVALID_OR_EXPIRED_TOKEN") from exc

    _rate_limit(verified.audio_id)

    repo = AudioRepository()
    audio_doc = repo.get_audio_by_id(audio_id)
    if not audio_doc:
        _audit_signed_audio_access(
            request=request,
            action="audio_stream_attempt",
            resource_id=audio_id,
            status="failure",
            status_code=404,
            extra={"reason": "audio_not_found"},
        )
        raise HTTPException(status_code=404, detail="AUDIO_NOT_FOUND")

    job = repo.transcription_jobs.find_one({"audio_id": audio_id}, sort=[("updated_at", -1)])
    if not job or str(job.get("status") or "").lower() != "processing":
        _audit_signed_audio_access(
            request=request,
            action="audio_stream_attempt",
            resource_id=audio_id,
            status="failure",
            status_code=403,
            extra={"reason": "job_not_processing", "job_status": job.get("status") if job else None},
        )
        raise HTTPException(status_code=403, detail="JOB_NOT_PROCESSING")

    fp = token_fingerprint(token)
    now = datetime.now(timezone.utc)
    redemption_doc = {"fingerprint": fp, "audio_id": audio_id, "redeemed_at": now}
    try:
        repo.audio_signed_url_redemptions.insert_one(redemption_doc)
    except DuplicateKeyError:
        prior = repo.audio_signed_url_redemptions.find_one({"fingerprint": fp})
        if prior and str(prior.get("audio_id", "")) == audio_id:
            # Idempotent retries (Azure batch / CDN / network) reuse the same URL until token expiry.
            pass
        else:
            _audit_signed_audio_access(
                request=request,
                action="audio_stream_attempt",
                resource_id=audio_id,
                status="failure",
                status_code=403,
                extra={"reason": "token_fingerprint_mismatch"},
            )
            raise HTTPException(status_code=403, detail="TOKEN_ALREADY_USED") from None

    storage_ref = str(
        audio_doc.get("storage_ref") or audio_doc.get("blob_url") or audio_doc.get("blob_path") or ""
    ).strip()
    if not storage_ref:
        raise HTTPException(status_code=404, detail="STORAGE_REF_MISSING")

    try:
        data = TranscriptionAudioStore().download_audio(storage_ref)
    except Exception as exc:  # noqa: BLE001
        _audit_signed_audio_access(
            request=request,
            action="audio_stream_attempt",
            resource_id=audio_id,
            status="failure",
            status_code=502,
            extra={"reason": "download_failed"},
        )
        raise HTTPException(status_code=502, detail="AUDIO_DOWNLOAD_FAILED") from exc

    mime = str(audio_doc.get("mime_type") or "application/octet-stream")

    _audit_signed_audio_access(
        request=request,
        action="audio_streamed_for_transcription",
        resource_id=audio_id,
        status="success",
        status_code=200,
        extra={"bytes": len(data), "mime_type": mime},
    )

    return Response(content=data, media_type=mime)
