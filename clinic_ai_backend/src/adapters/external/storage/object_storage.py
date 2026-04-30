"""Transcription audio bytes: MongoDB GridFS (Render/production) or local temp files (dev/tests)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from gridfs import GridFSBucket
from pymongo.database import Database

from src.adapters.db.mongo.client import get_database
from src.core.config import get_settings


class TranscriptionAudioStore:
    """
    Stores doctor-uploaded audio for the transcription pipeline.

    - Production (real PyMongo ``Database``): **GridFS** only — no Azure Blob.
    - Non-database test doubles / local: **filesystem** under ``LOCAL_AUDIO_STORAGE_PATH``.

    Azure Speech is called with **raw HTTP POST body bytes** (no cloud storage URL).
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.bucket_name = self.settings.mongo_audio_bucket_name
        self._gridfs_bucket: GridFSBucket | None = None

    def _gridfs(self) -> GridFSBucket | None:
        db = get_database()
        if not isinstance(db, Database):
            return None
        if self._gridfs_bucket is None:
            self._gridfs_bucket = GridFSBucket(db, bucket_name=self.bucket_name)
        return self._gridfs_bucket

    def upload_audio(self, *, blob_path: str, audio_bytes: bytes, mime_type: str) -> str:
        """Persist bytes and return a ``gridfs://`` or ``file://`` reference."""
        gfs = self._gridfs()
        if gfs is not None:
            file_id = gfs.upload_from_stream(
                blob_path,
                BytesIO(audio_bytes),
                metadata={"mime_type": mime_type, "logical_path": blob_path},
            )
            return f"gridfs://{file_id}"

        base = Path(self.settings.local_audio_storage_path)
        base.mkdir(parents=True, exist_ok=True)
        safe = f"{uuid4()}_{Path(blob_path).name}"
        path = (base / safe).resolve()
        path.write_bytes(audio_bytes)
        return f"file://{path.as_posix()}"

    def download_audio(self, storage_ref: str) -> bytes:
        """Load bytes from ``gridfs://`` or ``file://`` reference."""
        if storage_ref.startswith("file://"):
            path = Path(storage_ref[7:])
            if not path.is_file():
                raise RuntimeError(f"Transcription audio file missing: {path}")
            return path.read_bytes()
        if storage_ref.startswith("gridfs://"):
            gfs = self._gridfs()
            if gfs is None:
                raise RuntimeError("GridFS is not available for this database client")
            object_id_str = storage_ref[len("gridfs://") :].strip()
            if not object_id_str:
                raise RuntimeError("Missing GridFS object id in storage reference")
            stream = BytesIO()
            gfs.download_to_stream(ObjectId(object_id_str), stream)
            return stream.getvalue()
        raise RuntimeError(
            "Unsupported transcription audio reference (expected gridfs:// or file://). "
            "Azure Blob URLs are not supported."
        )

    def delete_by_ref(self, storage_ref: str | None) -> None:
        """Remove stored audio after processing (best-effort)."""
        if not storage_ref:
            return
        if storage_ref.startswith("file://"):
            path = Path(storage_ref[7:])
            try:
                path.unlink(missing_ok=True)
            except OSError:
                return
            return
        if storage_ref.startswith("gridfs://"):
            gfs = self._gridfs()
            if gfs is None:
                return
            oid_str = storage_ref[len("gridfs://") :].strip()
            if not oid_str:
                return
            try:
                gfs.delete(ObjectId(oid_str))
            except Exception:  # noqa: BLE001 — GridFS delete is best-effort
                return
