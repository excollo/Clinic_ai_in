# BUILD AUDIT REPORT

Date: 2026-05-01  
Repository: `Clinic_ai_in`  
Audited areas: `clinic_ai_frontend` + backend contract surface in `clinic_ai_backend`

---

## Audit Scope and Method

This audit was generated from:

- Static source review of frontend routes, feature pages, API clients, offline queue, and mock layers.
- Backend route contract review (especially `frontend_contract` router and related API routers).
- Executed checks:
  - `npm run build` in frontend (successful; chunk and gzip sizes captured).
  - `pytest -q tests/integration/test_frontend_contract_endpoints.py` (30 passed).
  - `pytest -q tests/integration/test_auth_and_visit_workflow.py tests/integration/test_health_endpoints.py` (1 failed, 6 passed).
  - Lighthouse audits on `/dashboard` and `/login` using local preview build.

Limitations:

- No fully instrumented backend instance with production-like seed data was running for end-to-end API timing capture per endpoint.
- Runtime interaction timings such as modal animation, route transition, and patient list with exactly 100 server records were not fully automatable in this run without dedicated synthetic scripts and data fixtures.

Where measurements were not directly observed, this report marks them as **Not measured in this run** (instead of guessing).

---

## SECTION 2: Critical Journey Flow Diagrams

Legend:

- `[R]` Required (cannot be skipped)
- `[O]` Optional (skippable)
- `[C]` Conditional (shows only in some cases)

### Flow A: Doctor onboarding (first-time)

```mermaid
flowchart TD
  A1[Signup screen step 1 details [R]] --> A2[Send OTP [R]]
  A2 --> A3[OTP verification [R]]
  A3 --> A4[Clinic setup [R]]
  A4 --> A5[ABDM linkage step [O]]
  A5 --> A6[WhatsApp setup choice [O]]
  A6 --> A7[Finish setup and create session [R]]
  A7 --> A8[Welcome tour [C]]
  A8 --> A9[Dashboard [R]]
```

Status: ✅ Functional, with mock fallback on some auth calls.

### Flow B: Returning doctor login

```mermaid
flowchart TD
  B1[Login form mobile+password [R]] --> B2[POST /auth/login [R]]
  B2 -->|success| B3[Session stored [R]]
  B3 --> B4[Dashboard [R]]
  B2 -->|failure| B5[Error toast [C]]
```

Status: ⚠️ Partial. No fallback path for login; backend outage breaks sign-in.

### Flow C: Forgot password recovery

```mermaid
flowchart TD
  C1[Enter mobile [R]] --> C2[Send OTP [R]]
  C2 --> C3[Verify OTP [R]]
  C3 --> C4[Enter new password [R]]
  C4 --> C5[POST /auth/forgot-password [R]]
  C5 --> C6[Back to login [R]]
```

Status: ❌ Broken/incomplete. Backend integration test expects `/api/auth/forgot-password` + reset completion path but receives 404 in tested flow; requested `/auth/reset-password` endpoint is also not wired in frontend contract list.

### Flow D: Walk-in patient registration -> consent -> consultation

```mermaid
flowchart TD
  D1[Register modal defaults Walk-in [R]] --> D2[Submit /patients/register [R]]
  D2 --> D3[Consent screen [R]]
  D3 --> D4[Explicit consent checkbox [R]]
  D4 --> D5[Queue consent offline + sync attempt [R]]
  D5 --> D6[Walk-in confirmation token [R]]
  D6 --> D7[Open visit workspace [C]]
```

Status: ⚠️ Partial. Decline button exists but does not persist a decline record; token may be fallback display when backend not returning one.

### Flow E: Scheduled appointment registration -> consent -> confirmation

```mermaid
flowchart TD
  E1[Register modal switch to Scheduled [R]] --> E2[Pick date/time [R]]
  E2 --> E3[POST /patients/register [R]]
  E3 --> E4[Consent capture [R]]
  E4 --> E5[Schedule confirmation [R]]
```

Status: ⚠️ Partial. Confirmation text implies WhatsApp sent; backend send status not actually verified in page state.

### Flow F: Existing patient quick re-registration (walk-in)

```mermaid
flowchart TD
  F1[Open patient detail/list [R]] --> F2[Start new visit from existing patient [C]]
  F2 --> F3[Consent -> consult [R]]
```

Status: ❌ Incomplete. Existing-patient re-registration API path (`POST /patients/{pid}/visits`) exists in backend but is not surfaced as a clear frontend quick flow.

### Flow G: ABHA scan registration

```mermaid
flowchart TD
  G1[Open scan-share page [R]] --> G2[Camera QR scan [C]]
  G1 --> G3[Manual ABHA entry [C]]
  G2 --> G4[Lookup ABHA [R]]
  G3 --> G4
  G4 --> G5[Prefill patient registration/list [R]]
```

Status: ⚠️ Partial. Frontend currently calls mock lookup path; backend ABHA endpoints are not fully consumed.

### Flow H: Full visit workflow (registration -> vitals -> transcription -> clinical note -> WhatsApp recap)

```mermaid
flowchart TD
  H1[Registration+consent [R]] --> H2[Previsit tab [R]]
  H2 --> H3[Vitals tab save/skip [R]]
  H3 --> H4[Transcription record/upload [R]]
  H4 --> H5[Clinical note draft/approve [R]]
  H5 --> H6[Recap preview [R]]
  H6 --> H7[Send WhatsApp [R]]
```

Status: ⚠️ Partial. Strong guided tab progression exists, but multiple sub-steps depend on mock/fallback behavior and not all send outcomes are persisted.

### Flow I: CarePrep review -> start consult

```mermaid
flowchart TD
  I1[CarePrep list filters [R]] --> I2[Open intake workspace [R]]
  I2 --> I3[Review red flags/Q&A/images [R]]
  I3 --> I4[Start consult button [R]]
```

Status: ❌ Incomplete. Entire flow is currently mock-data driven; no verified backend queue source.

### Flow J: Lab result ingestion -> review -> send to patient

```mermaid
flowchart TD
  J1[Lab inbox list [R]] --> J2[Open lab detail [R]]
  J2 --> J3[Review extracted values [R]]
  J3 --> J4[Send to patient [R]]
```

Status: ❌ Incomplete. UI uses mock data and simulated send delay; listed lab endpoints are not consumed by these screens.

### Flow K: Medication schedule generation -> activate reminders

```mermaid
flowchart TD
  K1[Open medication schedule page [R]] --> K2[View/edit slots [O]]
  K2 --> K3[Activate reminders [R]]
```

Status: ❌ Incomplete. No API wiring observed to backend medication schedule endpoints.

### Flow L: Continuity summary -> start new visit with context

```mermaid
flowchart TD
  L1[Patient detail continuity tab [R]] --> L2[Review prior diagnosis/meds/labs [R]]
  L2 --> L3[Start context-aware visit [C]]
```

Status: ❌ Incomplete. Continuity content is static/mock and no direct transition with backend context hydration.

### Flow M: Notification -> drill-down to specific record

```mermaid
flowchart TD
  M1[Notifications list [R]] --> M2[Filter by type [O]]
  M2 --> M3[Click notification [R]]
  M3 --> M4[Navigate target route [R]]
```

Status: ⚠️ Partial. Drill-down navigation works, but list is mock-backed rather than live `/notifications`.

### Flow N: Settings change -> save -> confirmation

```mermaid
flowchart TD
  N1[Open settings tab [R]] --> N2[Change field(s) [R]]
  N2 --> N3[Save button [R]]
  N3 --> N4[Success toast [R]]
```

Status: ⚠️ Partial. Save uses mock patch call; no real backend persistence for profile/clinic/audit settings pathways.

---

## SECTION 3: Backend Endpoint Integration

Status legend:

- 🟢 Wired and working
- 🟡 Wired but using mock fallback
- 🔴 Not wired (mock only)
- ⚫ Endpoint exists but not consumed yet

Average response times and 4xx/5xx are based on this audit run only; where no live call was made they are marked as not measured.

| Endpoint | Method | Used By Screen(s) | Status | Mock or Real | Avg ms | 4xx/5xx Seen | Response Shape Match |
|---|---|---|---|---|---:|---|---|
| `/auth/login` | POST | `LoginPage` | 🟢 | Real | Not measured | None observed in tests for this exact route | Appears matched |
| `/auth/signup` | POST | `SignupPage` | 🟡 | Real + fallback | Not measured | None observed | Mostly matched |
| `/auth/send-otp` | POST | `SignupPage`, `ForgotPasswordPage` | 🟡 | Real + fallback | Not measured | None observed | Matched |
| `/auth/verify-otp` | POST | OTP step component | 🟡 | Real + fallback | Not measured | None observed | Matched |
| `/auth/forgot-password` | POST | `ForgotPasswordPage` | 🟠 | Real path present but broken in related integration path | Not measured | **404 observed** in auth workflow integration test path | Needs contract alignment |
| `/auth/reset-password` | POST | None | 🔴 | Not wired | N/A | N/A | Missing from consumed contract |
| `/patients/register` | POST | `RegisterPatientModal` | 🟡 | Real + fallback | Not measured | None observed | Matched for required fields |
| `/patients` | GET | `PatientsPage` via hook | 🟡 | Real + fallback to `/api/patients` | Not measured | None observed | Requires normalization adapter |
| `/patients/{pid}` | GET | None | ⚫ | Endpoint not consumed | N/A | N/A | Not validated in UI |
| `/patients/abha/lookup` | POST | ABHA flow conceptually | 🔴 | Frontend currently mock lookup | N/A | N/A | Not validated |
| `/patients/abha/link` | POST | None | ⚫ | Exists in backend contract | N/A | N/A | Not validated |
| `/patients/register/scan-share` | POST | None | ⚫ | Exists in backend contract | N/A | N/A | Not validated |
| `/patients/{pid}/continuity-summary` | GET | None | ⚫ | Exists in backend contract | N/A | N/A | Not validated |
| `/consent/text?language={lang}` | GET | `ConsentPage` | 🟡 | Real + local language fallback | Not measured | None observed | Matched (`text`) |
| `/consent/capture` | POST | Offline sync worker | 🟢 | Real with idempotency header | Not measured | None observed | Matched payload envelope |
| `/patients/{pid}/visits/{vid}` | GET | None (frontend uses `/api/visits/{id}` shape elsewhere) | ⚫ | Exists in requested list, not consumed | N/A | N/A | Not validated |
| `/patients/consultations/answer` | POST | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/patients/consultations/answer` | PATCH | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/patients/webhook/images` | POST | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/patients/summary/previsit` | POST | None | ⚫ | Similar backend capability under workflow routes, different path | N/A | N/A | Path mismatch risk |
| `/patients/{pid}/visits/{vid}/vitals/required-fields` | GET | `VitalsTab` via service | 🟡 | Real; optional mock via env flag | Not measured | None observed | Matched dynamic fields contract |
| `/patients/{pid}/visits/{vid}/vitals` | POST | `VitalsTab`, offline sync | 🟢 | Real | Not measured | 409 handled in UI | Matched |
| `/patients/{pid}/visits/{vid}/vitals` | GET | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/notes/transcribe` | POST | Transcription feature (uses `/api/notes/transcribe`) | 🟠 | Real-like but path convention differs from requested list | Not measured | None observed | Needs naming alignment |
| `/notes/india-clinical-note` | POST | `ClinicalNoteTab`, offline sync | 🟢 | Real | Not measured | None observed | Matched |
| `/patients/{pid}/visits/{vid}/india-clinical-note` | GET | `ClinicalNoteTab` initial load | 🟢 | Real | Not measured | 404 tolerated as no-note case | Matched |
| `/notes/soap/generate` | POST | None | ⚫ | Legacy endpoint not in default UI | N/A | N/A | Intentional legacy |
| `/patients/summary/postvisit` | POST | `RecapTab` preview | 🟢 | Real | Not measured | Error toast fallback on failure | Mostly matched |
| `/whatsapp/send` | POST | `RecapTab` send action | 🟢 | Real | Not measured | Error toast on failure | Matched |
| `/patients/{pid}/visits/{vid}/medication-schedule` | POST | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/patients/{pid}/visits/{vid}/medication-schedule` | GET | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/patients/{pid}/visits/{vid}/lab-results` | POST | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/patients/{pid}/visits/{vid}/lab-results` | GET | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/lab-inbox` | GET | None (lab pages use mocks) | 🔴 | Mock only | N/A | N/A | Not validated |
| `/doctor/{did}/queue` | GET | `VisitWorkspacePage` | 🟢 | Real + mock fallback queue mapping | Not measured | None observed | Matched enough for workspace |
| `/notifications` | GET | None (notifications page uses mocks) | 🔴 | Mock only | N/A | N/A | Not validated |
| `/health` | GET | `ProtectedShell` top bar | 🟢 | Real | Not measured | Health test passed | Matched |
| `/doctor/profile` | GET | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/doctor/profile` | PATCH | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/clinic/settings` | GET | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/clinic/settings` | PATCH | None | ⚫ | Not consumed | N/A | N/A | Not validated |
| `/audit-log` | GET | None (audit tab uses mock rows) | 🔴 | Mock only | N/A | N/A | Not validated |

---

## SECTION 4: Compliance and Critical Features

### 4.1 DPDP Consent Compliance

- ✅ Consent screen requires explicit checkbox before capture.
- ✅ Consent text fetched by selected patient language (with fallback).
- ⚠️ "Patient declined" button exists but no persisted decline workflow observed.
- ⚠️ Consent queue record includes patient/doctor/language/version/timestamp/id, but verification of full backend persisted schema not completed.
- ❌ Audit log capture of every consent event is not wired to real audit endpoint.
- ❌ Consent withdrawal mechanism not implemented in UI flow.

### 4.2 Offline Support

- ✅ IndexedDB queue set up via Dexie.
- ✅ Consent capture enqueues immediately in IndexedDB.
- ✅ Sync worker retries with backoff tiers.
- ✅ Top bar shows unsynced count.
- ✅ Auto-clean for synced records older than 30 days implemented.
- ✅ Vitals can be queued via sync pathway.
- ✅ Clinical note queue pathway exists.
- ⚠️ End-to-end kill-backend/restart scenario not executed in this run.

### 4.3 Multi-language Support

- ✅ Preferred language captured at registration.
- ✅ Consent text renders in selected language (or fallback language text).
- ⚠️ WhatsApp recap has language selector, but full backend language correctness not validated.
- ⚠️ Many strings use i18n keys, but some hardcoded English strings remain in pages.
- ✅ Hindi locale file exists alongside English.
- ✅ Registration supports Hindi, English, Marathi, Tamil, Telugu, Bengali, Kannada.

### 4.4 India-format Clinical Output

- ✅ India clinical note is wired in primary note tab.
- ⚠️ Output sections include assessment/plan/rx/follow-up and red flags display, but investigations/red-flags lists are sparsely populated in current UX.
- ✅ Rx is structured with dose/frequency/duration/food instruction.
- ✅ SOAP is legacy and not default UI path.

### 4.5 WhatsApp Primary Output Channel

- ✅ Post-visit recap generates WhatsApp preview payload.
- ⚠️ Send-to options visible (patient/different/family), but family sub-flow fields are not fully integrated with payload.
- ✅ Preview pane styled as WhatsApp-like bubble card.
- ✅ Language selector exists.
- ⚠️ Sent confirmation is route-based success; delivery status detail is minimal.
- ❌ Failed sends are not queued for retry in recap send path.

### 4.6 Walk-in-First Workflow

- ✅ Register modal defaults to Walk-in.
- ⚠️ Token assignment expected from backend but fallback token can appear.
- ✅ Queue visibility exists in dashboard/workspace patterns.
- ✅ Token number displayed in visit workspace header.

### 4.7 Dynamic Vitals

- ✅ BP and Weight fixed.
- ✅ Additional fields fetched via required-fields endpoint.
- ✅ Supports different field sets by complaint via backend/mocks.
- ✅ Graceful fallback message when dynamic vitals API fails (fixed fields still usable).

---

## SECTION 5: Performance Metrics

### 5.1 Bundle Sizes (from `npm run build`)

- Main entry chunk: `16.46 KB` (`index-DGO_LkYn.js`, gzip `5.21 KB`)
- `/login` chunk: `2.48 KB` (gzip `1.17 KB`)
- `/signup` chunk: `8.32 KB` (gzip `2.21 KB`)
- `/dashboard` chunk: `2.67 KB` (gzip `1.11 KB`)
- `/patients` chunk: `5.58 KB` (gzip `2.13 KB`)
- `/patients/register` chunk: uses modal in shared chunk (`components-BdloeCRd.js`) `3.91 KB` (gzip `1.61 KB`)
- `/consent` chunk: `5.08 KB` (gzip `2.05 KB`)
- `/visits/:id` chunk: `6.53 KB` (gzip `2.34 KB`)
- `/careprep` chunk: `2.88 KB` (gzip `1.21 KB`)
- `/lab-inbox` chunk: `3.54 KB` (gzip `1.50 KB`)
- `/calendar` chunk: `5.54 KB` (gzip `1.97 KB`)
- `/settings` chunk: `3.48 KB` (gzip `1.42 KB`)
- `react-vendor`: `164.52 KB` (gzip `54.01 KB`)
- `form-vendor`: `74.41 KB` (gzip `22.46 KB`)
- `i18n-vendor`: `48.55 KB` (gzip `16.02 KB`)
- `query-vendor`: `35.51 KB` (gzip `10.75 KB`)
- offline (Dexie) chunk: `sync-7qj1XIQm.js` `98.92 KB` (gzip `33.48 KB`)

Total bundle size (JS + CSS + HTML listed by Vite): ~`757 KB` uncompressed  
Total gzipped (same listed assets): ~`231 KB`

### 5.2 Runtime Performance

- Time to interactive on `/login` (cold cache): **3085 ms** (Lighthouse interactive metric)
- Time to interactive on `/dashboard` (after login): **2554 ms** (Lighthouse interactive metric on dashboard route)
- Patient list load time with 100 records: **Not measured in this run**
- Patient list search debounce response: configured debounce **300 ms** (code), runtime not benchmarked
- Modal open animation: **Not measured in this run**
- Route transition time: **Not measured in this run**
- Skeleton loader threshold: skeletons shown on query loading states immediately; no explicit spinner-vs-skeleton threshold constant observed

### 5.3 Lighthouse Scores (`/dashboard`)

- Performance: **94 /100**
- Accessibility: **95 /100**
- Best Practices: **96 /100**
- SEO: **82 /100**

Critical Lighthouse failures flagged:

- Forced reflow insight (score 0)
- Network dependency tree insight (score 0)
- FCP and LCP are acceptable but still above instant-response goals (`2.2s` and `2.6s`)

---

## SECTION 6: Known Issues and Bugs

### Issue #1: Forgot-password integration mismatch
- Severity: Critical
- Affected screen(s): Forgot Password flow, auth backend pathing
- Steps to reproduce: Run backend auth workflow integration test; invoke forgot-password route
- Current behavior: Returns 404 in tested workflow
- Expected behavior: Return success token/flow continuation for reset
- Workaround if any: None reliable
- Estimated fix effort: 0.5-1 day

### Issue #2: Consent decline is non-functional as first-class path
- Severity: High
- Affected screen(s): Consent
- Steps to reproduce: Click decline in consent screen
- Current behavior: Button present, no persisted decline event flow
- Expected behavior: Persist decline with audit trail and route consequence
- Workaround if any: Manual cancellation outside flow
- Estimated fix effort: 1 day

### Issue #3: Notifications page not using live endpoint
- Severity: High
- Affected screen(s): Notifications
- Steps to reproduce: Open notifications page and inspect data source
- Current behavior: Mock list rendered
- Expected behavior: Consume `/notifications`, support read-state persistence
- Workaround if any: None
- Estimated fix effort: 1-2 days

### Issue #4: Lab inbox and detail are mock-backed
- Severity: High
- Affected screen(s): Lab inbox/detail
- Steps to reproduce: Open lab inbox and lab detail
- Current behavior: Static/generated mocks and simulated send
- Expected behavior: Live ingestion/review/send flow with backend
- Workaround if any: None
- Estimated fix effort: 2-3 days

### Issue #5: Medication schedule page lacks API wiring
- Severity: High
- Affected screen(s): Medication schedule
- Steps to reproduce: Open schedule page and activate reminders
- Current behavior: UI only, no backend call
- Expected behavior: Load/save schedule and activate reminder pipeline
- Workaround if any: None
- Estimated fix effort: 1-2 days

### Issue #6: ABHA scan uses mock lookup path
- Severity: Medium
- Affected screen(s): Scan-share
- Steps to reproduce: Submit ABHA manual/scan value
- Current behavior: Uses local mock lookup helper
- Expected behavior: Use backend ABHA lookup/link endpoints
- Workaround if any: None
- Estimated fix effort: 1-2 days

### Issue #7: Settings save is mock-only
- Severity: Medium
- Affected screen(s): Settings tabs
- Steps to reproduce: Update fields and click save
- Current behavior: Mock patch with success toast
- Expected behavior: Persist to doctor/clinic settings APIs
- Workaround if any: None
- Estimated fix effort: 2 days

### Issue #8: Login has no mock fallback unlike other auth calls
- Severity: Medium
- Affected screen(s): Login
- Steps to reproduce: Backend unavailable during login attempt
- Current behavior: Hard failure and error toast
- Expected behavior: Either robust error recovery or explicit offline mode handling
- Workaround if any: Restore backend connectivity
- Estimated fix effort: 0.5 day

### Issue #9: Endpoint path naming drift for transcription
- Severity: Medium
- Affected screen(s): Transcription
- Steps to reproduce: Compare expected endpoint list vs frontend/backend paths
- Current behavior: UI calls `/api/notes/transcribe` while audit spec expects `/notes/transcribe`
- Expected behavior: Consistent public contract naming
- Workaround if any: Document and keep a compatibility alias
- Estimated fix effort: 0.5 day

### Issue #10: Existing-patient quick re-registration flow not explicit
- Severity: Medium
- Affected screen(s): Patients/Patient detail
- Steps to reproduce: Attempt to start new walk-in quickly for existing patient
- Current behavior: No clear dedicated quick re-registration action tied to backend endpoint
- Expected behavior: One-click/new-visit path with consent/queue continuation
- Workaround if any: Register again manually
- Estimated fix effort: 1 day

---

## SECTION 7: Deviations from Spec

1. **Spec:** Full endpoint consumption across notifications/labs/settings  
   **Built:** Several key areas remain mock-backed  
   **Why:** UI scaffolding delivered before backend wiring completion  
   **Impact:** User-facing data may be synthetic; integration confidence reduced  
   **Fix before launch?** Yes

2. **Spec:** Forgot-password recovery includes reset-password continuity  
   **Built:** Forgot-password path exists but related tested flow fails (404), and reset endpoint in requested matrix not wired  
   **Why:** Contract drift between auth router variants  
   **Impact:** Account recovery risk/blocker  
   **Fix before launch?** Yes (critical)

3. **Spec:** Walk-in and scheduled confirmation should reflect real actions  
   **Built:** Confirmation UX can show success language without hard delivery evidence  
   **Why:** Optimistic UI implementation  
   **Impact:** Potential false confidence for staff  
   **Fix before launch?** Yes

4. **Spec:** Continuity summary should drive context-rich new visit  
   **Built:** Continuity tab mostly static/mock  
   **Why:** Deferred integration  
   **Impact:** Reduced clinical context quality  
   **Fix before launch?** Prefer yes for pilot, mandatory for GA

5. **Spec:** Dynamic operational observability and compliance traceability  
   **Built:** Partial offline compliance and consent capture; no fully wired audit/withdrawal UX  
   **Why:** Compliance hardening deferred  
   **Impact:** Regulatory and audit readiness risk  
   **Fix before launch?** Yes

No, the implementation does **not** match spec exactly; deviations are material and should be tracked.

---

## SECTION 8: Tech Debt Register

`TECH_DEBT.md` has been updated in repo root with categorized entries for:

- Bundle optimization deferred
- Backend integration mocked
- UX refinements deferred
- Edge cases not handled
- Testing coverage gaps
- Accessibility issues
- Performance issues
- Security considerations deferred

Each entry includes description, defer reason, estimated effort, and trigger condition.

---

## SECTION 9: File Structure Inventory

### Expected vs actual

Expected feature-first structure in spec:

`src/features/{auth,dashboard,patients,visits,careprep,calendar,lab-inbox,consent,whatsapp,settings}`

Observed in repo:

- Present in `src/features`: `auth`, `patients`, `visits`
- Missing in `src/features`: `dashboard`, `careprep`, `calendar`, `lab-inbox`, `consent`, `whatsapp`, `settings`
- These missing feature areas are largely implemented under `src/pages` instead.

### Top-level `src` folders observed

- `api`, `app`, `components`, `features`, `hooks`, `i18n`, `lib`, `pages`, `store`, `styles`, `types`, `utils`

### File count per existing feature folder (`src/features`)

- `auth`: 1
- `patients`: 1
- `visits`: 1

### Structure deviations and why

- Heavy route/page logic is centralized in `src/pages` rather than domain feature folders; likely due rapid UI delivery and route-first composition.
- Shared UI and workflow orchestration are mostly in `components` + `pages/visit-workspace`, creating mixed concerns.
- Mock infrastructure is in `src/lib/mocks` and powers major user-facing flows, making folder structure appear complete while feature boundaries remain thin.

### Files that do not fit intended structure (examples)

- Careprep pages under `src/pages` instead of `src/features/careprep`
- Lab inbox pages under `src/pages` instead of `src/features/lab-inbox`
- Settings tab implementations under `src/pages/settings-tabs` instead of `src/features/settings`

---

## SECTION 10: Testing Status

| Feature | Unit Tests | Integration Tests | Manual Test Coverage |
|---|---|---|---|
| Authentication | Backend unit tests present; frontend unit tests minimal | Backend integration includes auth workflow; one forgot-password path failing | Partial |
| Registration + Consent | Limited frontend automated tests | Backend frontend-contract integration covers endpoints (pass) | Partial |
| Visit workflow tabs | Minimal direct frontend unit tests | Backend contract tests for relevant APIs pass; full UI integration limited | Partial |
| Transcription | Backend unit/integration tests present | Integration flow tests present | Partial |
| Clinical note | Backend tests present | Covered in contract integration set | Partial |
| WhatsApp recap | Limited frontend automation | Some backend workflow tests present; delivery UX not deeply asserted | Partial |
| Patients listing/search | No dedicated frontend unit suite found | Endpoint contract indirectly covered | Partial |
| CarePrep | No dedicated tests found | Not integrated to live APIs | Low |
| Labs | No dedicated live integration tests for UI | Backend has lab-related modules/tests, UI currently mock | Low |
| Notifications | No dedicated frontend tests for live endpoint use | Endpoint exists but UI not consuming | Low |
| Settings | Minimal/no direct tests | UI save is mock; real settings endpoint integration untested | Low |
| Health shell indicator | N/A | Health endpoint tests pass | Medium |

Notes:

- Frontend test footprint observed includes a few Playwright specs; coverage is far from comprehensive for critical clinical journeys.
- Backend integration suite is stronger but not fully clean (auth reset path issue).

---

## SECTION 11: What’s Ready for Real Users

### Ready for internal testing (employees, design partners)

- [x] Yes, with caveats:
  - Forgot-password reset path must be fixed.
  - Teams should treat notifications/labs/settings/ABHA flows as partially mocked.
  - Consent decline + audit/withdrawal compliance still incomplete.

### Ready for pilot clinics (1-3 friendly clinics, supervised)

- [ ] Yes, after these fixes
- [x] No, because:
  - Critical account recovery inconsistency.
  - Too many operational flows still mock-backed.
  - Compliance-adjacent consent/audit features incomplete.

### Ready for general availability

- [ ] Yes
- [x] No, blockers:
  1. Forgot-password/reset flow reliability and endpoint alignment.
  2. Real backend wiring for notifications/labs/settings/medication schedule.
  3. Compliance completion: consent decline persistence, withdrawal mechanism, audit completeness.
  4. Stronger automated coverage for end-to-end clinical journeys.

---

## Go/No-Go Conclusion

Current recommendation: **Not ready for pilot/GA yet; suitable only for controlled internal testing with explicit caveats.**

This build has a strong foundation in route structure, offline primitives, and core consultation UX, but the release risk remains high because backend wiring is uneven and one critical auth recovery path already fails in integration testing.

