# Azure Speech deployment runbook (pilot scope)

Production transcription uses **Azure Speech Services only** for batch-quality speech-to-text and diarization. The pilot avoids **Azure Blob**, **Azure Queue**, and other Azure platform services beyond Speech to limit cost and ops surface.

## Current architecture (Mongo + self-hosted URLs)

| Concern | Pilot choice |
|---------|----------------|
| Speech engine | Azure Speech (**batch API** wired in Sprint 2B Chunk 3; requires a public HTTPS URL per job) |
| Job queue | Mongo FIFO (`TRANSCRIPTION_QUEUE_BACKEND=mongo` default) |
| Audio storage | Mongo GridFS (`TRANSCRIPTION_STORAGE_BACKEND=gridfs` default) |
| Azure-fetchable URL | **`GET /internal/audio/{audio_id}?token=...`** on your public backend; token is short-lived **HMAC** (see Chunk 2) |

Optional adapters remain in code for scale later:

- `TRANSCRIPTION_QUEUE_BACKEND=azure` — Azure Queue adapter (**implemented, not used in pilot**).
- `TRANSCRIPTION_STORAGE_BACKEND=azure_blob` — **no pilot implementation**; adapter pattern reserves the switch.

Roll back queues/storage by leaving env vars on `mongo` / `gridfs`; no redeploy required beyond config.

---

## Required environment variables (Speech + Mongo)

Set in **both** Render services (`clinic-ai-backend`, `clinic-ai-worker`) unless noted:

### Azure Speech

- `AZURE_SPEECH_KEY`: Cognitive Services Speech key.
- `AZURE_SPEECH_REGION`: e.g. `centralindia`.
- `AZURE_SPEECH_ENDPOINT`: Optional custom endpoint URL.
- `AZURE_SPEECH_BATCH_TRANSCRIPTION_LOCALE`: Default locale, e.g. `hi-IN`.

### MongoDB

- `MONGODB_URL`, `MONGODB_DB_NAME`
- `ALLOW_LOCAL_AUDIO_FALLBACK=false` in staging/production (GridFS canonical).

### Transcription backends (defaults)

- `TRANSCRIPTION_QUEUE_BACKEND=mongo`
- `TRANSCRIPTION_STORAGE_BACKEND=gridfs`

### Self-hosted signed URL for Azure batch audio fetch (**web service**)

Azure pulls audio over HTTPS **from your API origin** (same Render web URL patients hit).

- **`PUBLIC_BACKEND_URL`** — Canonical public base URL **without trailing slash**, e.g. `https://clinic-ai-backend.onrender.com` (set to your actual Render hostname).
- **`AUDIO_URL_SIGNING_SECRET`** — At least **32** random ASCII bytes for HMAC SHA-256. Never reuse across environments.

If either is unset or too weak, `/internal/audio` returns **503** or URL generation raises when the worker submits a batch job (Chunk 3).

---

## Operational note: Render web idle vs Azure fetch

Azure batch may dequeue and request your audio URL **minutes after** submission. Render **free** web services can sleep after ~15 minutes without traffic—Azure’s GET may then hit a cold/unreachable origin.

Mitigations:

- Paid Render tier for the API (recommended for transcription pilot), **or**
- Application-level keep-alive pinging the web service **while transcription jobs remain `processing`**, **or**
- Operational awareness and retry semantics at Azure/job level.

See `TECH_DEBT.md`: *Transcription / Azure Speech: Self-Hosted Signed URL + Render Idle Sleep*.

---

## Internal audio endpoint behaviour (reference)

Implemented in **`GET /internal/audio/{audio_id}`**:

- Validates `token`: HMAC, expiry (`generate_audio_access_url` default max **24 hours** configurable), path matches `audio_id`.
- Ensures Mongo `audio_files` record exists and a `transcription_jobs` row exists for this `audio_id` with **`status=processing`** (worker must transition before SAS URL reaches Azure batch).
- **Rate limit:** 10 attempts per sliding minute **per audio_id** (per API process — scale-out multiplies allowances).
- **Redemption ledger:** Mongo `audio_signed_url_redemptions` keyed by SHA-256 fingerprint of raw token strings; TTL ~48 hours for automatic cleanup while allowing idempotent retries of the **same URL** until token expiry (GET semantics).
- **Audit:** Rows with `doctor_id='azure_speech_batch'` (`audio_stream_attempt`, `audio_streamed_for_transcription`) — JWT audit middleware intentionally **does not** apply (Azure cannot send clinician JWTs).

Never log raw `token` query parameters in application logs.

---

## Optional local Azurite (queue adapter tests only)

Use only when validating `TRANSCRIPTION_QUEUE_BACKEND=azure` against Azurite.

```bash
docker compose up -d azurite
```

Ports: Blob `10000`, Queue `10001`. Use the Azurite connection string documented in Compose or prior dev notes.

Set `RUN_AZURITE_TESTS=true` before running Azurite-gated pytest modules.

Production pilot does **not** require Azurite or Azure Queue.

---

## Previously documented Azure Blob + Queue rollout

Historical templates may still mention `AZURE_*_QUEUE_*` / `AZURE_BLOB_*` on every checklist. Treat those as **optional future scale knobs**, **not pilot requirements**.

Health checks may expose `azure_queue` / `azure_blob` as omitted or degraded when unset—this is acceptable for Speech-only deployments.

---

## Capacity and cost reminders

Speech free tiers are inadequate for realistic clinic throughput. Estimate hours/month from visit volume and multiply by Speech batch pricing.

For this pilot scope, omit blob and queue calculators unless you deliberately enable those adapters.

