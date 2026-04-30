"""GridFS-backed audio storage (canonical on Render when PyMongo resolves to a real Database)."""
from __future__ import annotations

import asyncio

from src.adapters.external.storage.object_storage import TranscriptionAudioStore


class GridFsAudioStorageAdapter:
    """
    Wraps legacy ``TranscriptionAudioStore``.

    Blocking helpers are used inside ``asyncio.to_thread`` from synchronous STT pipelines.
    """

    def __init__(self) -> None:
        self._store = TranscriptionAudioStore()

    async def upload(self, audio_bytes: bytes, filename: str, metadata: dict[str, str]) -> str:
        patient_id = metadata.get("patient_id", "").strip()
        visit_id = metadata.get("visit_id", "").strip()
        mime = metadata.get("mime_type", "application/octet-stream")
        blob_path = f"{patient_id}/{visit_id}/{filename}"

        def _run() -> str:
            return self._store.upload_audio(blob_path=blob_path, audio_bytes=audio_bytes, mime_type=mime)

        return await asyncio.to_thread(_run)

    async def download(self, blob_url: str) -> bytes:
        return await asyncio.to_thread(self._store.download_audio, blob_url)

    async def delete_blob(self, blob_url: str | None) -> None:
        if not blob_url:
            return None
        await asyncio.to_thread(self._store.delete_by_ref, blob_url)
        return None

    async def get_signed_url(self, blob_url: str, expires_in_seconds: int = 3600) -> str:  # noqa: ARG002
        return blob_url

    async def health_check(self) -> bool:
        return True

    def download_blocking(self, blob_url: str) -> bytes:
        """Sync download for FFmpeg / Azure REST paths running inside threads."""
        return self._store.download_audio(blob_url)

    def delete_blocking(self, blob_url: str | None) -> None:
        self._store.delete_by_ref(blob_url)
