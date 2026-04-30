"""Transcription adapters: queue + storage backends selected via environment."""
from __future__ import annotations

from functools import lru_cache

from src.adapters.transcription.queue.mongo_fifo_queue import MongoFifoQueueAdapter
from src.adapters.transcription.queue.protocol import TranscriptionQueuePort
from src.adapters.transcription.storage.gridfs_audio_adapter import GridFsAudioStorageAdapter
from src.adapters.transcription.storage.protocol import AudioStoragePort
from src.core.config import get_settings
from src.core.errors import ConfigurationError


@lru_cache(maxsize=1)
def get_queue_adapter() -> TranscriptionQueuePort:
    backend = getattr(get_settings(), "transcription_queue_backend", "mongo").lower().strip()
    if backend == "mongo":
        return MongoFifoQueueAdapter()
    if backend == "azure":
        raise ConfigurationError(
            "TRANSCRIPTION_QUEUE_BACKEND=azure is configured but the Azure Queue adapter "
            "ships in Sprint 2B Chunk 1. Use TRANSCRIPTION_QUEUE_BACKEND=mongo until then."
        )
    raise ConfigurationError(f"Unknown TRANSCRIPTION_QUEUE_BACKEND={backend!r}")


@lru_cache(maxsize=1)
def get_audio_storage_adapter() -> AudioStoragePort:
    backend = getattr(get_settings(), "transcription_storage_backend", "gridfs").lower().strip()
    if backend == "gridfs":
        return GridFsAudioStorageAdapter()
    if backend == "azure_blob":
        raise ConfigurationError(
            "TRANSCRIPTION_STORAGE_BACKEND=azure_blob is configured but the Azure Blob adapter "
            "ships in Sprint 2B Chunk 2. Use TRANSCRIPTION_STORAGE_BACKEND=gridfs until then."
        )
    raise ConfigurationError(f"Unknown TRANSCRIPTION_STORAGE_BACKEND={backend!r}")


def clear_transcription_adapter_cache() -> None:
    """Test hook to rebuild adapters after monkeypatching settings."""
    get_queue_adapter.cache_clear()
    get_audio_storage_adapter.cache_clear()
