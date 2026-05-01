# Diagnostic report — 2026-05-01

**Scope:** Backend ↔ MongoDB disconnect and related UI symptoms. **No fixes applied** in this sprint; this document is evidence and categorization only.

**Environment note:** Automated checks ran against the developer machine where `http://127.0.0.1:8000/health` responded and `clinic_ai_backend/.env` loads a MongoDB Atlas URI. Full UI flows (Network tab capture, manual registration with exact test names) were **not** executed end-to-end in the browser in this pass; API paths, code paths, and live DB metrics were verified instead.

---

## 1.1 Database connectivity verification

### Backend startup (`uvicorn`)

Command (alternate port, ~4s capture):

```bash
cd clinic_ai_backend
timeout 4 uvicorn src.app:create_app --factory --port 8010
```

**Captured output:**

```
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8010 (Press CTRL to quit)
```

**Findings:**

- There is **no** log line such as “Connected to MongoDB” in this codebase (confirmed by repository search).
- There is **no Beanie** usage; persistence is **PyMongo** with on-demand `get_database()` calls. The prompt’s “Beanie initialization / document models registered” checklist does not apply to this stack as written—models are not centralized ORM documents; collections are accessed by name (e.g. `db.patients`).

---

## 1.2 Health endpoint

```bash
curl http://127.0.0.1:8000/health
```

**Actual response (2026-05-01):**

```json
{
  "status": "ok",
  "mongodb": "connected",
  "azure_speech": "reachable",
  "azure_queue": "not_configured",
  "azure_blob": "not_configured",
  "worker_status": "missing",
  "worker_last_heartbeat": null,
  "timestamp": "2026-05-01T00:25:11.636420+00:00",
  "version": "0.1.0"
}
```

**Interpretation:**

- **MongoDB:** `connected` (definitive for this runtime).
- **Transcription worker:** `missing`; `worker_heartbeats` collection empty (see 1.7).
- Azure queue/blob: not configured in health’s sense; queue backend in app config may still be `mongo` (FIFO collection).

---

## 1.3 Direct MongoDB inspection

Connection: live read against the database named in `MONGODB_DB_NAME` (default/name in use: **`clinic_ai`**).

**Important:** This product does **not** use a standalone `appointments` collection for the calendar. Scheduled items are **`visits`** documents; “appointments” in the API are **projections** built from `visits` (see `list_provider_upcoming_visits`).

| Collection / topic | Exists | Approx. count (estimated_document_count) | Notes |
|-------------------|--------|------------------------------------------|--------|
| `patients` | Yes | 623 | Populated |
| `visits` | Yes | 494 | Populated |
| `consents` | Yes | 13 | Populated |
| `consent_withdrawals` | Yes | 3 | Populated |
| `audit_log` | Yes | 372 | Populated |
| `transcription_jobs` | Yes | 69 | See status breakdown below |
| `transcription_queue` | Yes | 0 | Empty at inspection time |
| `notifications` | Yes | 15 | Populated |
| `lab_results` | Yes | 0 | Empty |
| `medication_schedules` | Yes | 0 | Empty |
| `doctor_profiles` | Yes | 0 | Empty (code may use `doctors` instead; see below) |
| `clinic_settings` | Yes | 0 | Empty |
| `appointments` | **N/A** | — | **Not used** as a primary store; calendar sourced from `visits` |
| `doctors` | Yes | 8 | Populated (used by frontend contract paths) |
| `consent_texts` | Yes | 0 | Consent text endpoint falls back to hardcoded default when empty |
| `worker_heartbeats` | Yes | 0 | No heartbeats recorded |
| `pre_visit_summaries` | Yes | 101 | |
| `intake_sessions` | Yes | 316 | |

**`transcription_jobs` status distribution:**

- `completed`: 52  
- `failed`: 15  
- `queued`: 2 (stale; see 1.8 / 1.7)

**Indexes (sample):**

- `patients`: 1 index (default `_id` only at listing time)
- `visits`: 1 index (default `_id` only)
- `transcription_jobs`: 4 indexes (application creates job-related indexes)

**Honesty / spec gap:** The database is **not** “empty” or disconnected in this environment—it is **actively populated**. Symptoms such as “dummy data on dashboard” are unlikely to be explained by Mongo being down here; they point to **wrong API paths**, **frontend mocks**, **query filters**, or **dual-write patterns** instead.

---

## 1.4 End-to-end flow verification (code + API + DB evidence)

Full UI clicks with Network tab exports were **not** attached in this run. Below is **ground truth from code static analysis plus live checks** where applicable.

### Flow A — Patient registration

| Step | Expected / verified |
|------|---------------------|
| Frontend call | `POST /patients/register` via `registrationService.ts` → `frontend_contract.patients_register` |
| Persistence | Writes `patients` + `visits` in MongoDB (`insert_one` / `update_one`) when auth headers valid |
| **Critical bug pattern** | On **any** API failure (`catch` with no discrimination), frontend calls **`registerPatientMock`** and returns success **without persistence** |

**Bucket risk:** Bucket **2** (mock fallback masking errors), and Bucket **5**/*auth* if 401 hides real failure.

Mongo field naming: contract patients use **`mobile`** and **`doctor_id`**; legacy/internal router uses different shapes (`phone_number`, deterministic IDs). Mixed clients can cause confusion when comparing to docs.

---

### Flow B — Calendar / scheduled registration

**Verified HTTP routing:**

- Frontend `CalendarPage.tsx` calls: `GET /visits/provider/${doctorId}/upcoming`
- Backend route is registered under the visits router prefix **`/api/visits`** → canonical URL is **`/api/visits/provider/{id}/upcoming`**.

**Live check:**

- `GET http://127.0.0.1:8000/visits/provider/foo/upcoming` → **404**
- `GET http://127.0.0.1:8000/api/visits/provider/foo/upcoming` → **200**

So the calendar list call, as written in the frontend, **does not hit the backend route** unless something else rewrites the path (there is **no** path rewrite in `vite.config.ts`).

**Data shape mismatch (even if URL were fixed):**

- `frontend_contract` visit insert for registration includes `scheduled_date` and `scheduled_time` but **does not set `scheduled_start`**.
- Backend upcoming query **requires** `scheduled_start` to exist and be non-empty.
- Live DB: all **`workflow_type: "scheduled"`** visits (**4** documents) have **`scheduled_date` / `scheduled_time`** and **none** have a usable `scheduled_start` for that workflow.

**Bucket:** Strong **7** (wrong path) plus **5** (backend filter excludes intended rows) / **3** (field mismatch between write and read paths).

---

### Flow C — Patient list rendering

| Item | Detail |
|------|--------|
| Frontend | `GET /patients` with JWT + doctor headers (`usePatients.ts`) |
| Backend | `frontend_contract.patients_list` filters **`{"doctor_id": doctor_id}`** |
| Comparison | Aligns with Mongo **when** the same doctor id is used and writes go through contract |

Failure modesIf registration silently used mocks, **new patients never hit DB**but list still shows stored patients.

**Patient detail page:** falls back **`mockPatients`** when navigation state/`id` don’t resolve—dummy data independent of Mongo.

---

### Flow D — Transcription

| Item | Detail |
|------|--------|
| Frontend | `POST /api/notes/transcribe`; poll `GET /api/notes/transcribe/status/...` (prefix **`/api`** is correct) |
| Worker | **`/health`** reports `worker_status: "missing"`; `worker_heartbeats` count **0** |
| Mongo | `TRANSCRIPTION_QUEUE_BACKEND` default **`mongo`**; `transcription_queue` count **0**; **`transcription_jobs` has 2 stale `queued`** jobs |
| Recent failure example | Error message observed in DB: *“Azure Speech HTTP 400 … Unsupported audio format.”* (e.g. browser **webm** vs service expectations / conversion path) |

**Bucket:** Combination of **1** misinterpreted (“DB broken” vs “jobs not processed”), **worker not running**, and **adapter/audio format** failures—not a disconnected MongoDB in this probe.

---

### Flow E — Dashboard data

| Source | Detail |
|--------|--------|
| Queue | **`GET /doctor/{doctorId}/queue`** — exists on **`frontend_contract`** (no `/api` prefix—consistent with queue) |
| Care Prep prefetch | **`fetchCareprepQueue`** from **`@/lib/mocks/careprep`** seeded into React Query cache on mount—even if UI doesn’t render it on Dashboard, **`mock`** data **is deliberately loaded into client cache**. |

---

## 1.5 Mock fallback audit (frontend grep)

Commands (counts):

- Files under `src/` matching `mock` (`.ts`/`.tsx`): **26**
- Files matching `MOCK`: **1**

**High-impact matches (not exhaustive):**

| Area | File | Behavior | Dev-gated? | Dummy data risk |
|------|------|----------|------------|-----------------|
| Registration | `src/lib/registrationService.ts` | **`catch` → `registerPatientMock`** | **No** — any error | **Yes** — success without DB |
| Auth | `src/lib/mocks/auth.ts` | Console warnings + mock tokens when API fails | Conditional on failure paths | Login/signup feel “fine” without backend |
| Dashboard cache | `src/pages/DashboardPage.tsx` | `prefetchQuery` with **`fetchCareprepQueue`** mock | **No** | Injects mock queue into TanStack Query |
| Patients main list | `src/features/patients/hooks/usePatients.ts` | Real **`/patients`** | — | Uses API when authenticated |
| Patient detail | `src/pages/PatientDetailPage.tsx` | **`mockPatients` fallback** | **No** | **Yes** |
| Visit workspace | `src/pages/VisitWorkspacePage.tsx` | **`getMockVisitById`** | **No** | **Yes** |
| Notifications | `src/pages/NotificationsPage.tsx` | **`mockNotifications` ×120** | **No** | **Yes** |
| Labs | `src/pages/LabInboxPage.tsx`, `LabResultDetailPage.tsx` | Mock labs | **No** | **Yes** |
| Settings | `src/pages/SettingsPage.tsx` | **`patchSettingsMock`** | **No** | **Yes** |
| Vitals | `src/lib/vitalsService.ts` | Mock when **`VITE_USE_MOCK_VITALS === "true"`** | **Yes** (`false` in `.env`) | Conditional |
| Consent offline sync | `src/lib/offline/sync.ts` | **`VITE_CONSENT_SYNC_TEST_MODE`** forces mock failures/success | **Yes** — **`true` in `clinic_ai_frontend/.env`** | **Breaks/skews consent sync paths in dev** |
| Suspense placeholders | Various `fallback={...}` | UI loading placeholders | React semantics | Not business mock data |

**React i18n** `fallbackLng: "en"` in `src/i18n/index.ts` — localization fallback, **not** data mocking.

---

## 1.6 Environment configuration check

**Naming correction:** Backend uses **`MONGODB_URL`** and **`MONGODB_DB_NAME`**, not **`MONGO_URI`**.

### Backend (`clinic_ai_backend/.env`) — values **redacted**; presence only:

- **`MONGODB_URL`:** set (Atlas-style URI observed)
- **`MONGODB_DB_NAME`:** `clinic_ai`
- **`AZURE_SPEECH_*`:** present in local `.env` (key/region/endpoint)
- **`TRANSCRIPTION_QUEUE_BACKEND`:** not present in terse grep slice; **`config.py` default `"mongo"`** applies when unset
- **`TRANSCRIPTION_STORAGE_BACKEND`:** default **`gridfs`** when unset (`config.py`)
- **`ALLOW_LOCAL_AUDIO_FALLBACK`:** default **`false`** (`config.py`); **`USE_LOCAL_ADAPTERS`** / **`LOCAL_AUDIO_STORAGE_PATH`** seen in `.env`/example affect local adapters
- **`RUN_TRANSCRIPTION_WORKERS_IN_API`:** not present in abbreviated scan → default **`false`** → workers **not** started inside API unless overridden
- **`CORS_ORIGINS`:** includes `localhost:5173` and `127.0.0.1:5173` in local file (good for Vite)

### Frontend (`clinic_ai_frontend/.env`):

- **`VITE_API_BASE_URL=http://127.0.0.1:8000`**
- **`VITE_USE_MOCK_VITALS=false`**
- **`VITE_CONSENT_SYNC_TEST_MODE=true`** — **activates mock consent sync behavior** in `offline/sync.ts`

---

## 1.7 Worker process check

- **`grep ps` / task-style scan:** **`worker_startup.py` not observed** among running processes; **`uvicorn`** processes were present (multiple instances on machine).
- **Mongo:** `worker_heartbeats` **0 documents** → aligns with **`/health`** `worker_status: "missing"` and `worker_last_heartbeat: null`.
- **Queue backlog:** **`transcription_queue` count 0**; **`transcription_jobs` status `queued` = 2** (old)—suggests **orphaned / never-completed jobs**, not active FIFO pressure at inspection.

Render dashboard was **not** accessed in this sprint.

---

## 1.8 Backend log review

- No Render log pull (no dashboard access scripted).
- Repo **does not emit** Mongo “connected” on startup; brief local uvicorn stdout showed only standard Uvicorn lines.
- **Evidence from persisted job errors:** at least some failures are **`Azure Speech HTTP 400` / unsupported audio format**, not Mongo write failures.

---

## STEP 2 — Root cause categorization (buckets)

| Flow / symptom | Primary bucket(s) | Short rationale |
|----------------|-------------------|-----------------|
| Calendar empty / slot registration invisible | **7**, **5**, **3** | Wrong URL (`/visits/...` vs `/api/visits/...`); upcoming query requires `scheduled_start` while contract writes `scheduled_date`/`scheduled_time` only |
| “Registration works but nowhere in app” | **2**, optionally **7** | Silent **`registerPatientMock`** on HTTP error; calendar path broken |
| Dashboard / lists feel “fake” | **2**, **4** | Mock care-prep prefetch + multiple pages entirely mock-driven |
| Patient detail wrong | **2** | Explicit **`mockPatients` / mock visit** fallback |
| Transcription fails / stuck | Worker **not evidenced locally**, adapter errors | **`/health`** worker missing; `queued`/failed jobs; Azure 400 audio format failures in DB—not Mongo disconnect |
| “Mongo empty” narrative | — | **Contradicted** by live counts (hundreds of patients/visits) for this Atlas DB |

Additional note on **provider scoping:** `list_provider_upcoming_visits` matches visits whose `provider_id` is missing/empty/`null`/equal to URL param—not `doctor_id`. That may be intentional “board shows all slots without provider assignment,” but it is **orthogonal** to the **404** and **`scheduled_start`** issues—which already fully explain calendar failure for contract-scheduled flows.

---

## STEP 3 — STOP AND REPORT (summary answers)

### Is MongoDB actually connected?

**Yes** for the checked stack (`/health` + direct `ping` + non-zero collection counts).

### Are records actually being written?

**Yes** for `patients`, `visits`, and many other collections in this database. **However**, the **frontend can report success without writing** if `/patients/register` throws and the client uses **mock registration**.

### Where is dummy data coming from?

**`src/lib/mocks/*`**, **registration mock fallback**, **Dashboard mock prefetch**, **Patient detail / visit workspace mocks**, labs/notifications pages—many **always active**, not gated to `DEV`.

### Why calendar registration does not show?

1. **`GET /visits/.../upcoming` returns 404** (missing **`/api`** prefix).  
2. Even with a fix, **`scheduled_start`** is absent on contract-created scheduled visits, but **both** backend list query and frontend filter **require `scheduled_start`**.

### Why is transcription failing (in this snapshot)?

- **No worker heartbeat** locally; **`RUN_TRANSCRIPTION_WORKERS_IN_API`** default false unless env enables it **or** a separate **`worker_startup.py`** process runs.  
- **Failed jobs** show **unsupported audio format** for Azure STT path.  
- **Stale `queued`** jobs indicate incomplete processing historically.

---

## Top 5 root causes (ranked by impact)

1. **Frontend/API path inconsistencies** (`/api` prefix omitted on calendar but required on backend for visits). **Symptom:** broken calendar and anything else misaligned the same way.  
2. **Contract registration writes schedule fields incompatible with upcoming-visit queries** (`scheduled_date`/`scheduled_time` vs required `scheduled_start`). **Symptom:** “registered for slot but never appears.”  
3. **Silent mock fallbacks** (especially **`registrationService` catch-all**). **Symptom:** UI success, **no Mongo row**, appears as “backend not persisting.”  
4. **Large surface of non-gated mock pages** (Dashboard prefetch, patient detail, visit workspace, labs, notifications). **Symptom:** persistent dummy data despite real DB.  
5. **Transcription worker + audio pipeline not aligned with ops** (no heartbeat, orphaned `queued`, Azure 400 on format). **Symptom:** timeouts, failed jobs, “transcription broken” independent of Mongo connectivity.

---

## Previously claimed vs observed (critical honesty)

- If prior sprints asserted **“mock fallbacks removed for production-ready flows,”** the **grep audit and code review contradict that**—multiple mocks remain on hot paths (**registration catch**, **patient detail**, **visit workspace**, **dashboard prefetch**, **labs/notifications**).
- Prompt assumptions about **Beanie** and log line **“Connected to MongoDB”** **do not match** this codebase; **PyMongo lazy access** plus **`/health` ping** are the operative signals.

---

## Recommended next step (out of scope for this sprint)

After sign-off: fix **calendar URL + scheduled_start derivation**, remove or hard-gate **`registerPatientMock`** on failures, converge **doctor_id vs provider_id** semantics if per-doctor isolation is required, run **`worker_startup.py`** (or enable in-API workers) for transcription smoke tests, **set `VITE_CONSENT_SYNC_TEST_MODE=false`** unless deliberately testing failures.
