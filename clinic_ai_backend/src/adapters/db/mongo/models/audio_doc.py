"""Mongo audio document helpers."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return UTC timestamp."""
    return datetime.now(timezone.utc)


def build_audio_doc(
    *,
    audio_id: str,
    patient_id: str,
    visit_id: str | None,
    storage_ref: str,
    bucket: str,
    mime_type: str,
    size_bytes: int,
    sha256: str,
    noise_environment: str,
    language_mix: str,
    speaker_mode: str,
) -> dict:
    """Build a Mongo-safe audio file record (no Azure Blob)."""
    return {
        "audio_id": audio_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "storage_ref": storage_ref,
        "blob_url": storage_ref,
        "blob_path": storage_ref,
        "container": bucket,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "noise_environment": noise_environment,
        "language_mix": language_mix,
        "speaker_mode": speaker_mode,
        "uploaded_at": utc_now(),
    }
