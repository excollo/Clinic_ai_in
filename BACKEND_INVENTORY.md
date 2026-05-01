# Backend Inventory (Step 0)

Date: 2026-05-01  
Scope: Endpoint inventory only (no implementation changes)  
Status taxonomy used:

- ✅ Endpoint exists in backend
- ✅ Endpoint connected to MongoDB
- ✅ Endpoint app registers/runs at startup
- ❌ Endpoint missing entirely
- ⚠️ Endpoint exists but throws / not registered / DB behavior not aligned

Evidence used:

- Static route scan from `clinic_ai_backend/src/api/routers/*`
- App registration scan from `clinic_ai_backend/src/app.py`
- Frontend API usage scan from `clinic_ai_frontend/src`
- Startup check: `python -c "from src.app import create_app; app=create_app(); print('APP_OK', len(app.routes))"` returned `APP_OK 96`

Important ground truth:

- Backend is currently **PyMongo-based**, not Beanie ODM (no Beanie symbols found).
- Many frontend-contract endpoints are mounted at non-`/api` paths via `frontend_contract` router.
- Several requested sprint routes are not implemented yet, or implemented with placeholder/fake seeded behavior.

---

## Route Inventory

### Authentication

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /auth/login` | ✅ | ✅ | ✅ | ✅ | Implemented in frontend contract router. |
| `POST /auth/signup` | ✅ | ✅ | ✅ | ✅ | Stores doctor doc. |
| `POST /auth/send-otp` | ✅ | ✅ | ✅ | ✅ | Uses DB; dev OTP fallback path exists. |
| `POST /auth/verify-otp` | ✅ | ✅ | ✅ | ✅ | Uses stored OTP requests. |
| `POST /auth/forgot-password` | ✅ | ✅ | ✅ | ✅ | Exists, but integration mismatch seen in prior test path for `/api/auth/*` flow. |
| `POST /auth/reset-password` | ❌ | ❌ | ❌ | ❌ | Missing entirely. |

### Patients

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /patients/register` | ✅ | ✅ | ✅ | ✅ | Creates patient/visit records. |
| `GET /patients` | ⚠️ | ✅ | ✅ | ✅ | `/patients` non-api endpoint missing; frontend falls back to `/api/patients`. |
| `GET /patients/{pid}` | ❌ | ❌ | ❌ | ❌ | Missing exact endpoint. |
| `POST /patients/abha/lookup` | ✅ | ⚠️ | ✅ | ⚠️ | Returns fabricated payload; not real ABDM-backed. |
| `POST /patients/abha/link` | ✅ | ✅ | ✅ | ❌ | Exists, not consumed by frontend. |
| `POST /patients/register/scan-share` | ✅ | ⚠️ | ✅ | ❌ | Returns fabricated parse payload. |
| `GET /patients/{pid}/continuity-summary` | ✅ | ✅ | ✅ | ❌ | Exists in frontend contract router; frontend continuity tab uses static values. |

### Appointments (NEW expected)

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /appointments` | ❌ | ❌ | ❌ | ❌ | Missing service. |
| `GET /appointments?date=...` | ❌ | ❌ | ❌ | ❌ | Missing service. |
| `GET /appointments/{id}` | ❌ | ❌ | ❌ | ❌ | Missing service. |
| `PATCH /appointments/{id}` | ❌ | ❌ | ❌ | ❌ | Missing service. |
| `DELETE /appointments/{id}` | ❌ | ❌ | ❌ | ❌ | Missing service. |
| `GET /appointments/available-slots?...` | ❌ | ❌ | ❌ | ❌ | Missing service. |

### Consent

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `GET /consent/text?language={lang}` | ✅ | ✅ | ✅ | ✅ | Reads consent text collection with fallback string. |
| `POST /consent/capture` | ✅ | ✅ | ✅ | ✅ | Writes consent + idempotency support. |
| `POST /consent/withdraw` | ❌ | ❌ | ❌ | ❌ | Missing. |
| `GET /consent/{patient_id}/history` | ❌ | ❌ | ❌ | ❌ | Missing. |

### Visits

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `GET /patients/{pid}/visits` | ❌ | ❌ | ❌ | ❌ | Missing exact path; similar `/api/visits/patient/{patient_id}` exists. |
| `GET /patients/{pid}/visits/{vid}` | ❌ | ❌ | ❌ | ❌ | Missing exact path; similar `/api/visits/{visit_id}` exists. |
| `POST /patients/{pid}/visits` | ✅ | ✅ | ✅ | ❌ | Exists under `/api/patients/{patient_id}/visits`; frontend does not use. |

### Vitals

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `GET /patients/{pid}/visits/{vid}/vitals/required-fields` | ✅ | ✅ | ✅ | ✅ | Uses visit + cache collections; includes LLM generation. |
| `POST /patients/{pid}/visits/{vid}/vitals` | ✅ | ✅ | ✅ | ✅ | Persists vitals with immutability check. |
| `GET /patients/{pid}/visits/{vid}/vitals` | ❌ | ❌ | ❌ | ❌ | Missing exact endpoint. |

### Transcription

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /notes/transcribe` | ✅ | ✅ | ✅ | ⚠️ | Implemented as `/api/notes/transcribe`; frontend uses that. |
| `GET /notes/transcribe/{job_id}/status` | ❌ | ❌ | ❌ | ❌ | Missing exact job-id form; implemented as `/api/notes/transcribe/status/{patient_id}/{visit_id}`. |
| `GET /notes/transcribe/{job_id}/result` | ❌ | ❌ | ❌ | ❌ | Missing exact route; result assembled via dialogue endpoints. |
| Worker process status | ⚠️ | ⚠️ | ⚠️ | N/A | Worker lifecycle hooks exist, but explicit health/status endpoint missing in API inventory. |

### Clinical Notes

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /notes/india-clinical-note` | ✅ | ✅ | ✅ | ✅ | Draft + approve via same route/status. |
| `GET /patients/{pid}/visits/{vid}/india-clinical-note` | ✅ | ✅ | ✅ | ✅ | Exists and consumed. |
| `PATCH /patients/{pid}/visits/{vid}/india-clinical-note` | ❌ | ❌ | ❌ | ❌ | Missing. |
| `POST /notes/india-clinical-note/approve` | ❌ | ❌ | ❌ | ❌ | Missing dedicated approve endpoint (approval folded into POST). |

### Post-visit

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /patients/summary/postvisit` | ✅ | ✅ | ✅ | ✅ | Builds recap from approved note. |
| `POST /whatsapp/send` | ✅ | ✅ | ✅ | ✅ | Persists send records; dev/mock provider mode exists. |
| `GET /whatsapp/templates` | ❌ | ❌ | ❌ | ❌ | Missing. |

### Medication

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /patients/{pid}/visits/{vid}/medication-schedule` | ✅ | ✅ | ✅ | ❌ | Exists; frontend page currently not wired. |
| `GET /patients/{pid}/visits/{vid}/medication-schedule` | ✅ | ✅ | ✅ | ❌ | Exists; not consumed by page. |
| `PATCH /medication-schedule/{id}/activate-reminders` | ❌ | ❌ | ❌ | ❌ | Missing. |

### Labs

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `POST /patients/{pid}/visits/{vid}/lab-results` | ✅ | ✅ | ✅ | ❌ | Exists in contract router; UI pages still mock-backed. |
| `GET /patients/{pid}/visits/{vid}/lab-results` | ✅ | ✅ | ✅ | ❌ | Exists, not consumed by current lab pages. |
| `GET /lab-inbox?doctor_id=...` | ❌ | ❌ | ❌ | ❌ | Missing exact endpoint. |
| `PATCH /lab-results/{id}/reviewed` | ❌ | ❌ | ❌ | ❌ | Missing exact endpoint. |

### Operations

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `GET /doctor/{did}/queue` | ✅ | ✅ | ✅ | ✅ | Exists and consumed by visit workspace. |
| `GET /notifications?doctor_id=...` | ✅ | ✅ | ✅ | ❌ | Exists but frontend notifications page still mock-based. |
| `PATCH /notifications/{id}/read` | ❌ | ❌ | ❌ | ❌ | Missing; only mark-all-read exists. |
| `GET /health` | ✅ | ⚠️ | ✅ | ✅ | Returns status only; no explicit MongoDB connectivity field yet. |

### Settings

| Route | Exists | MongoDB | Registers/Runs | Frontend Calling | Notes |
|---|---|---|---|---|---|
| `GET /doctor/profile` | ❌ | ❌ | ❌ | ❌ | Missing. |
| `PATCH /doctor/profile` | ❌ | ❌ | ❌ | ❌ | Missing. |
| `GET /clinic/settings` | ❌ | ❌ | ❌ | ❌ | Missing. |
| `PATCH /clinic/settings` | ❌ | ❌ | ❌ | ❌ | Missing. |
| `GET /audit-log?filters=...` | ❌ | ❌ | ❌ | ❌ | Missing. |

---

## Top 5 Missing Services (backend doesn't exist at all)

1. **Appointments service** (`/appointments*` family absent)
2. **Consent withdrawal/history** (`/consent/withdraw`, `/consent/{patient_id}/history`)
3. **Settings service** (`/doctor/profile`, `/clinic/settings`)
4. **Audit log service** (`/audit-log` family)
5. **Lab inbox/review endpoints** (`/lab-inbox`, `/lab-results/{id}/reviewed`)

## Top 5 Broken Services (exists but not working as required)

1. **Forgot-password/reset contract**: `/auth/forgot-password` exists, but reset flow is incomplete (no `/auth/reset-password`) and prior integration path showed mismatch.
2. **Transcription status/result contract mismatch**: implemented path shape differs from required `job_id` status/result APIs.
3. **`GET /patients` contract**: frontend calls `/patients` first, backend primary list is `/api/patients`; fallback currently masks mismatch.
4. **ABHA lookup/scan-share realism**: endpoints return fabricated data instead of real integration or explicit empty/503 semantics.
5. **`GET /health` completeness**: lacks explicit MongoDB connectivity state required by sprint spec.

## Top 5 Disconnected Services (backend works but frontend isn’t calling)

1. **Medication schedule endpoints** (present; medication page is still static/mock)
2. **Notifications endpoint** (present; notifications page uses local mocks)
3. **Lab results endpoints** (present; lab inbox/detail pages use mock data)
4. **Patient continuity summary endpoint** (present; continuity tab uses static placeholders)
5. **ABHA link endpoint** (present; scan flow not wired to link call)

---

## Honest Step-0 Conclusion

- **Built and connected to MongoDB (real):** significant subset of auth, registration, consent capture, vitals save, note save/get, recap generation, queue, whatsapp send, notifications list/mark-all-read.
- **Built but no real data source / placeholder behavior:** ABHA lookup/scan-share, parts of transcription contract shape, health signal completeness.
- **Not built (out of scope until implemented):** appointments, consent withdrawal/history, settings persistence APIs, audit log APIs, several labs/notification granular endpoints, reset-password endpoint.

