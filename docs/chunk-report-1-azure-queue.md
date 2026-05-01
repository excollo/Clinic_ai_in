# Chunk 1 Report: AzureQueueAdapter

**Pilot stance (cost / simplicity):** the adapter is merged and exercised under Azurite, but **`TRANSCRIPTION_QUEUE_BACKEND` stays `mongo` in prod** unless Mongo queue ergonomics degrade. Operational guidance moved to **`TECH_DEBT.md`** (*Azure Queue adapter: dormant*) and **`docs/deployment-azure-speech.md`** (Speech-only scope).

## What was built

- Added pre-chunk safety gate:
  - `ALLOW_LOCAL_AUDIO_FALLBACK` in `src/core/config.py` (default `false`)
  - `StorageError` in `src/core/errors.py`
  - Hard fail in `src/adapters/external/storage/object_storage.py` when GridFS is unavailable and local fallback is disabled.
- Implemented `AzureQueueAdapter` in `src/adapters/transcription/queue/azure_queue_adapter.py`:
  - Base64 JSON payload encoding
  - Main + poison queue auto-create
  - Dequeue returns `message_id`, `receipt`, `dequeue_count`
  - Acknowledge by `message_id + pop_receipt`
  - Manual poison move with optional source-delete via receipt
  - Queue depth + poison depth + health checks
  - Connection-string validation and trimming
- Updated adapter contract:
  - `move_to_poison(..., receipt="")` in queue protocol.
- Updated adapter factory:
  - `TRANSCRIPTION_QUEUE_BACKEND=azure` now resolves to `AzureQueueAdapter`.
  - `mongo` rollback path remains intact.
- Added queue message id persistence:
  - `POST /api/notes/transcribe` now stores `queue_message_id` on `transcription_jobs`.
- Added Azurite local dev support:
  - `docker-compose.yml` includes `azurite` service and volume.
  - `docs/deployment-azure-speech.md` updated with Azurite setup and `ALLOW_LOCAL_AUDIO_FALLBACK`.
- Added tests:
  - `tests/integration/test_azure_queue_adapter.py` (10 Azurite integration cases, gated by `RUN_AZURITE_TESTS=true`)
  - `tests/integration/test_transcription_queue_message_id.py` (ensures `queue_message_id` is stored)

## Test results

- `pytest -q tests/integration/test_transcription_queue_message_id.py`
  - `1 passed`
- `pytest -q tests/integration/test_transcription_flow.py`
  - `2 passed, 9 xfailed` (existing triage posture preserved)
- `pytest -q tests/integration/test_azure_queue_adapter.py`
  - `10 skipped` because `RUN_AZURITE_TESTS` was not enabled in this run

## Mongo rollback confirmation

- Existing Mongo queue path still works under `TRANSCRIPTION_QUEUE_BACKEND=mongo`.
- Transcription flow regression suite remains green under current triage baseline.

## Sample transcription job record (with queue message id)

```json
{
  "job_id": "f4f9f4d5-7b2c-4f2f-9fb5-9a8d0f88d113",
  "audio_id": "c19f1b84-d4b5-4f67-9478-58f7c057f106",
  "patient_id": "p1",
  "visit_id": "v1",
  "status": "queued",
  "provider": "azure_speech",
  "queue_message_id": "azure-msg-123"
}
```

(Verified by integration test with patched queue adapter in `test_transcription_queue_message_id.py`.)

## Deviations

- Azurite-backed queue tests were added but are currently gated behind `RUN_AZURITE_TESTS=true` to prevent CI/local hangs when Azurite is not running.
- Docker executable was unavailable in this run environment, so live Azurite execution was not performed here.

## Next chunk readiness

- Ready for Chunk 2 (Azure Blob adapter).
- Queue backend switching + rollback controls are now in place.
