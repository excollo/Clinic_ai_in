# Chunk 0 Report: Transcription adapter pattern (rollback-safe)

## Pre-migration safety: filesystem grep (audio-path review)

Ran repository search for ephemeral file writes touching transcription-related code:

- Patterns: `open(...,'wb')`, `tempfile`, `/tmp`, `Path.write_bytes`
- Locations found:
  - `src/adapters/external/storage/object_storage.py` — **`Path.write_bytes`** when GridFS bucket is unavailable (fallback to `LOCAL_AUDIO_STORAGE_PATH`). **This is durable only when PyMongo attaches to a real `Database` and uploads go through GridFS.** On Render, misconfigured Mongo ⇒ `file://` refs ⇒ deploy data loss risk.
  - `src/workers/transcription_worker.py` — **`tempfile.NamedTemporaryFile`**, **`TemporaryDirectory`**, **`Path.write_bytes`** for FFmpeg chunking/normalization — **transient staging only**, not authoritative patient audio persistence.

Verdict: **Authoritative uploads must remain `gridfs://` on production Mongo** (or **`https://`** after Azure Blob in Chunk 2). **Temp FFmpeg scratch is acceptable** because output is discarded after Azure STT.

## Chunk 0 deliverables

- **Environment flags** (validated in `Settings`): `TRANSCRIPTION_QUEUE_BACKEND=mongo|azure`, `TRANSCRIPTION_STORAGE_BACKEND=gridfs|azure_blob`. Defaults preserve current behaviour (`mongo` + `gridfs`). Selecting `azure` / `azure_blob` before adapters exist raises **`ConfigurationError`** with a pointer to Chunk 1/2.
- **`TranscriptionQueuePort`** and **`AudioStoragePort`** `Protocol` definitions (`src/adapters/transcription/queue/protocol.py`, `storage/protocol.py`).
- **Typed envelopes:** `TranscriptionQueueJob`, `DequeuedJob` (`src/adapters/transcription/types.py`).
- **`MongoFifoQueueAdapter`** wraps existing `TranscriptionQueueProducer` / `TranscriptionQueueConsumer` FIFO semantics; optional **`transcription_poison_journal`** collection for poisoning (best-effort on test doubles).
- **`GridFsAudioStorageAdapter`** wraps legacy **`TranscriptionAudioStore`** (`src/adapters/transcription/storage/gridfs_audio_adapter.py`) exposing async protocol methods plus **`download_blocking`** / **`delete_blocking`** for synchronous FFmpeg/Azure REST paths running in executor threads.
- **Factory:** `get_queue_adapter()` / `get_audio_storage_adapter()` with `@lru_cache` + **`clear_transcription_adapter_cache()`** for tests (`src/adapters/transcription/factory.py`).
- **Routing:** `/api/notes/transcribe` uploads and enqueues via adapters; **`TranscriptionWorker.process_next_async`** dequeues/enqueues retries via **`MongoFifoQueueAdapter`**, **`acknowledge`** centralized in **`finally`** (duplicate consumer ack calls removed).

## Tests

- Integration monkeypatch updated to **`src.adapters.external.storage.object_storage.TranscriptionAudioStore.upload_audio`** (still exercised by **`GridFsAudioStorageAdapter`**).
- Recommended command after further chunks: `pytest -q clinic_ai_backend/tests/integration/test_transcription_flow.py`
