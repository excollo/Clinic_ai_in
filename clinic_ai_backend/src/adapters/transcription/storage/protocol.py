"""Abstract audio blob persistence (GridFS today, Azure Blob in staging/prod rollout)."""
from __future__ import annotations

from typing import Protocol


class AudioStoragePort(Protocol):
    async def upload(self, audio_bytes: bytes, filename: str, metadata: dict[str, str]) -> str:
        """Store bytes and return opaque storage reference (gridfs://, https://blob..., etc.)."""

    async def download(self, blob_url: str) -> bytes:
        """Load bytes from saved reference."""

    async def delete_blob(self, blob_url: str | None) -> None:
        """Best-effort delete after processing."""

    async def get_signed_url(self, blob_url: str, expires_in_seconds: int = 3600) -> str:
        """For Azure Speech batch (SAS). GridFS/local may return unchanged ref."""

    async def health_check(self) -> bool:
        """True if persistence layer responds."""
