# Clinic AI India Backend

## Architecture Overview
This project follows a Clean Architecture style with clear boundaries between presentation (`api`), application (`use_cases`, `ports`, `dto`), domain (`entities`, `value_objects`, `events`), and infrastructure (`adapters`). Shared cross-cutting concerns live in `core`, `middleware`, and `observability`. Background workflows are handled by `workers` for async processing and task sweeping.

## Local Setup
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
make dev
```

## API Startup (Canonical)
```bash
uvicorn src.app:create_app --reload --factory
# or
make api
```

## Environment Variables
| Variable | Required | Description | Example |
|---|---|---|---|
| OPENAI_API_KEY | Yes | API key for LLM provider | sk-... |
| OPENAI_MODEL | No | OpenAI model for chat/note generation | gpt-4o-mini |
| MONGODB_URL | Yes | MongoDB connection URI | mongodb://localhost:27017/clinic_ai |
| MONGODB_DB_NAME | Yes | MongoDB database name | clinic_ai |
| AZURE_SPEECH_KEY | Yes | Azure Speech Service API key | your-azure-speech-key |
| AZURE_SPEECH_REGION | Yes* | Azure Speech region (required if endpoint not fully set) | centralindia |
| AZURE_SPEECH_ENDPOINT | No | Optional explicit Speech endpoint | https://<region>.api.cognitive.microsoft.com/ |
| MAX_AUDIO_SIZE_MB | No | Max upload size in MB | 25 |
| TRANSCRIPTION_MAX_RETRIES | No | Retry attempts for failed jobs | 3 |
| TRANSCRIPTION_TIMEOUT_SEC | No | Worker timeout per transcription call | 120 |
| TRANSCRIPTION_QUEUE_BACKEND | No | `mongo` (default Mongo FIFO queue) or `azure` (**dormant** Azure Queue adapter; pilot uses mongo) | mongo |
| TRANSCRIPTION_STORAGE_BACKEND | No | `gridfs` (default); `azure_blob` adapter reserved/future (**not pilot**) | gridfs |
| PUBLIC_BACKEND_URL | When batch Speech needs a fetch URL | Public HTTPS origin of this API (**no trailing slash**). Azure Speech batch calls `GET /internal/audio/{audio_id}?token=...` against this host. Example: `https://your-backend.onrender.com` | _(empty)_ |
| AUDIO_URL_SIGNING_SECRET | Same as above | HMAC secret (**≥32** characters) protecting signed `/internal/audio` URLs | _(empty)_ |
| USE_LOCAL_ADAPTERS | No | If true: asyncio in-process transcription queue + temp files for audio when DB is not PyMongo | true |
| LOCAL_AUDIO_STORAGE_PATH | No | Directory for temp transcription audio (non-GridFS / local adapters) | /tmp/clinic_audio |
| MONGO_AUDIO_BUCKET_NAME | No | GridFS bucket name (Render + real MongoDB) | audio_blobs |
| DEFAULT_NOTE_TYPE | No | Auto note generation type after transcription | india_clinical |
| WHATSAPP_ACCESS_TOKEN | Yes (for WhatsApp) | Meta WhatsApp Cloud API token | EAA... |
| WHATSAPP_PHONE_NUMBER_ID | Yes (for WhatsApp) | WhatsApp phone number id | 101648... |
| WHATSAPP_VERIFY_TOKEN | Yes (for WhatsApp) | Webhook verify token | clinicai_india_webhook_2024 |
| WHATSAPP_API_VERSION | No | Meta API version | v21.0 |
| WHATSAPP_INTAKE_TEMPLATE_NAME | No | Initial outbound WhatsApp template name | opening_msg |
| WHATSAPP_INTAKE_TEMPLATE_LANG_EN | No | English template locale code | en_US |
| WHATSAPP_INTAKE_TEMPLATE_LANG_HI | No | Hindi template locale code | hi |
| WHATSAPP_INTAKE_TEMPLATE_PARAM_COUNT | No | Number of body params in template | 1 |
| INTAKE_USE_LLM_MESSAGE | No | Intake flag for LLM-based message generation (default false) | false |
| INTAKE_REQUIRE_ALL_AGENTS | No | Intake flag requiring all intake agents to be present (default true) | true |
| INTAKE_STRICT_VALIDATION | No | Intake flag for strict intake validation checks (default true) | true |

## Intake Rollout Guidance (Safe Defaults)
- Keep existing deployments safe by explicitly setting:
  - `INTAKE_USE_LLM_MESSAGE=false`
  - `INTAKE_REQUIRE_ALL_AGENTS=true`
  - `INTAKE_STRICT_VALIDATION=true`
- This keeps deterministic template fallback behavior active while still collecting validation/fallback telemetry.

### Phase 1: Log-Only Validation (No LLM Message Delivery)
- `INTAKE_USE_LLM_MESSAGE=false`
- `INTAKE_REQUIRE_ALL_AGENTS=true`
- `INTAKE_STRICT_VALIDATION=true`
- Goal: validate structure/message quality and reason-code telemetry without changing patient-facing question source.

### Phase 2: Staging Enablement
- `INTAKE_USE_LLM_MESSAGE=true`
- `INTAKE_REQUIRE_ALL_AGENTS=true`
- `INTAKE_STRICT_VALIDATION=true`
- Goal: verify that LLM messages pass validation and that template fallback remains safe under staging traffic.

### Phase 3: Production Gradual Enable
- Start canary with:
  - `INTAKE_USE_LLM_MESSAGE=true`
  - `INTAKE_REQUIRE_ALL_AGENTS=true`
  - `INTAKE_STRICT_VALIDATION=true`
- Gradually increase rollout only if monitoring remains healthy; immediately rollback to `INTAKE_USE_LLM_MESSAGE=false` on regressions.

### Monitoring Checklist
- Fallback rate: track share of turns where `last_message_source != llm`.
- Repeated topic rate: track repeated-topic recovery/fallback occurrences.
- Completion rate: track intake sessions reaching normal completion.
- Error reason distribution: monitor `last_fallback_reason` (for example `openai_http_error`, `json_parse_error`, `schema_invalid`, `message_invalid`, `topic_mismatch`, `unknown_exception`).

## Doctor transcription (upload → poll → dialogue)
- **Queue**: MongoDB FIFO (`TRANSCRIPTION_QUEUE_BACKEND=mongo` default). An **Azure Queue** adapter exists (`azure`) but the pilot keeps it dormant; optional Azurite tests remain for future scale (`RUN_AZURITE_TESTS=true`).
- **Audio**: **GridFS** on real Mongo (`TRANSCRIPTION_STORAGE_BACKEND=gridfs`). Pilot does **not** use Azure Blob. Local/dev stubs may persist under `LOCAL_AUDIO_STORAGE_PATH` when `ALLOW_LOCAL_AUDIO_FALLBACK=true`.
- **Azure Speech (current worker)**: Short-audio REST with **HTTP POST bodies** chunked by the worker (**no SAS URL yet**).
- **Azure Speech (batch rollout, Sprint 2B Chunk 3)**: Requires a **world-readable HTTPS URL** for Azure to pull WAV/MP3. Chunk 2 implements **`GET /internal/audio/{audio_id}?token=...`** minted via `PUBLIC_BACKEND_URL` + `AUDIO_URL_SIGNING_SECRET`; see `docs/deployment-azure-speech.md` and **`TECH_DEBT.md`** on Render idle-sleep risks.

## Transcription lifecycle
- `POST /api/notes/transcribe` is asynchronous and returns quickly with a job id.
- Poll `GET /api/notes/transcribe/status/{patient_id}/{visit_id}` until terminal status.
- Fetch structured transcript via `GET /api/notes/{patient_id}/visits/{visit_id}/dialogue` when status is `completed`.
- Long-running jobs remain `queued`/`processing`/`timeout`; they are not treated as failed unless backend marks `failed`.

### Start transcription request
```http
POST /api/notes/transcribe
Content-Type: multipart/form-data
X-Idempotency-Key: transcription:pat_123:vis_123:sha256...
```

### Start transcription response (202)
```json
{
  "job_id": "job_abc123",
  "message_id": "job_abc123",
  "patient_id": "opaque_patient_id",
  "visit_id": "vis_123",
  "status": "queued",
  "message": "Transcription queued. Poll /api/notes/transcribe/status/opaque_patient_id/vis_123 for status."
}
```

### Status response example (processing)
```json
{
  "jobId": "job_abc123",
  "status": "processing",
  "progress": 65,
  "etaSeconds": null,
  "errorCode": null,
  "errorMessage": null,
  "retryable": false,
  "message": "Transcription in progress (running for 84 seconds)"
}
```

### Status response example (completed)
```json
{
  "jobId": "job_abc123",
  "status": "completed",
  "progress": 100,
  "transcript_available": true,
  "message": "Transcription completed successfully"
}
```

## Azure Speech and MP3 uploads
Transcription sends audio to Azure’s short-audio REST API. Some MP3 variants decode to “success” with an empty transcript. The worker **normalizes uploads with FFmpeg** to 16 kHz mono PCM WAV before calling Azure when `ffmpeg` is on `PATH`.

- **Docker**: `deployments/docker/Dockerfile.api` and `Dockerfile.worker` install `ffmpeg`; rebuild and redeploy the image.
- **Native Python on a host (e.g. Render without Docker)**: install `ffmpeg` in the environment (for example add a build step that installs it, or use a base image that includes it). If `ffmpeg` is missing, the worker falls back to the original bytes and MP3 failures are more likely.

## Endpoint Module Map
- Health: `src/api/routers/health.py`
- Patients: `src/api/routers/patients.py`
- Notes: `src/api/routers/notes.py`
- Transcription: `src/api/routers/transcription.py`
- Internal Azure batch fetch: `src/api/routers/internal_audio.py` (`/internal/audio/...`)
- Vitals: `src/api/routers/vitals.py`
- WhatsApp: `src/api/routers/whatsapp.py`
- Workflow: `src/api/routers/workflow.py`
