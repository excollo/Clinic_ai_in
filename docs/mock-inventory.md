# Frontend mock inventory (Day 1 prep)

Purpose: single index of **`@/lib/mocks/**`** usage, hybrid API+mock callers, and environment gates. Scoped to **`clinic_ai_frontend/src`**. No behavioral changes listed here beyond what code does today.

## Environment gates

| Variable | Meaning | Files |
| --- | --- | --- |
| `VITE_USE_MOCK_VITALS` | When `"true"`, skips **`GET …/vitals/required-fields`** and returns mock shape. | `lib/vitalsService.ts` |
| `VITE_CONSENT_SYNC_TEST_MODE` | When `"true"`, first three offline consent POST attempts **throw** (simulated failures), then succeed. | `lib/offline/sync.ts` |
| `import.meta.env.DEV` | Dev-only OTP banner in auth UI (not backend mock). | `features/auth/components.tsx` |

Everything else listed below is either **always mock/static**, **hybrid try-API-then-fallback**, or **types-only** imports.

---

## Line-by-line: consumers (`clinic_ai_frontend/src`)

Paths are repo-relative under `clinic_ai_frontend/src/`.

| File | Imports / mocks | Behavior | Env gate |
| --- | --- | --- | --- |
| `features/auth/components.tsx` | `sendOtp`, `verifyOtp` from `lib/mocks/auth` | OTP UI; calls mock module (which prefers API — see **`lib/mocks/auth.ts`**). DEV banner via `import.meta.env.DEV`. | `DEV` banner only |
| `lib/vitalsService.ts` | `getMockVitalsRequiredFields` | API unless `VITE_USE_MOCK_VITALS==="true"` | **`VITE_USE_MOCK_VITALS`** |
| `lib/registrationService.ts` | `registerPatientMock` | **`POST /patients/register`**; on throw/catch uses **`registerPatientMock`**. | None |
| `lib/offline/sync.ts` | *(no mocks import)* | Consent POST path can **simulate failures** via localStorage-backed attempt counter when test flag set. Vitals/note paths always hit **`apiClient`**. | **`VITE_CONSENT_SYNC_TEST_MODE`** |
| `pages/ConsentPage.tsx` | `fetchConsentText` from **`lib/mocks/consent`** | **`GET /consent/text`**; catch returns static Hindi/English paragraphs. Submission uses real **`POST /consent/capture`**. | None |
| `pages/DashboardPage.tsx` | **`fetchCareprepQueue`** | Static queue + artificial delay (**`lib/mocks/careprep`**). | None |
| `pages/CarePrepListPage.tsx` | **`fetchCareprepQueue`** | Same as dashboard. | None |
| `pages/IntakeWorkspacePage.tsx` | **`getCareprepByVisitId`** | Resolves workspace header/context from **`careprepQueue`** in mock module. | None |
| `pages/VisitWorkspacePage.tsx` | **`getMockVisitById`** | Tries **`GET /doctor/:id/queue`** first; if visit row missing, **falls back** to **`getMockVisitById`**. | None |
| `pages/PatientDetailPage.tsx` | **`mockPatients`** | Chooses **`state.patient`**, else **`mockPatients.find`**, else **`mockPatients[0]`**. | None |
| `pages/patient-detail/OverviewTab.tsx` | Type **`PatientRecord`** from **`lib/mocks/patients`** | Types only | — |
| `pages/patient-detail/VisitsTab.tsx` | Type **`PatientRecord`** | Types only | — |
| `pages/patient-detail/ContinuityTab.tsx` | Type **`PatientRecord`** | Types only | — |
| `pages/NotificationsPage.tsx` | **`mockNotifications`** | Renders fixed list | None |
| `pages/LabInboxPage.tsx` | **`mockLabs`** | Renders inbox from static array | None |
| `pages/LabResultDetailPage.tsx` | **`getLabById`** | Resolves detail from **`mockLabs`** | None |
| `pages/LoginPage.tsx` | **`loginDoctor`** | **No fallback** — direct **`POST /auth/login`** only (failure surfaces to UI). Lives in mocks file for bundling/auth grouping. | None |
| `pages/SignupPage.tsx` | **`sendOtp`, `signupDoctor`** | Prefer API inside **`lib/mocks/auth`**; signup/OTP fallback on failure. | None |
| `pages/ForgotPasswordPage.tsx` | **`sendOtp`, `forgotPassword`** | **`sendOtp`** hybrid; **`forgotPassword`** is **API-only** (throws if backend absent). | None |
| `pages/SettingsPage.tsx` | **`patchSettingsMock`** | Save handler invokes mock **`patchSettingsMock(active, {})`** (**`auditEntries`** unused by page today). | None |

---

## `lib/mocks/*` definitions (authoritative list)

| Module | Exported surface | Role |
| --- | --- | --- |
| `auth.ts` | `sendOtp`, `verifyOtp`, `signupDoctor`, `loginDoctor`, `forgotPassword` | Hybrid: **`sendOtp` / `verifyOtp` / `signupDoctor`** try API then fallback; **`loginDoctor` / `forgotPassword`** are API-only. |
| `consent.ts` | `fetchConsentText` | API first; static text on failure. |
| `registration.ts` | `registerPatientMock`, `getMockSlots` | Fallback patient registration payload; **`getMockSlots`** currently **unused** by pages (dead export for demos). |
| `vitalsRequiredFields.ts` | `getMockVitalsRequiredFields` | Used only when **`VITE_USE_MOCK_VITALS`** is set. |
| `patients.ts` | `PatientRecord`, `mockPatients` | Synthetic list + shared type. |
| `visits.ts` | `mockVisits`, `getMockVisitById`, `MockVisit` | Fallback when queue API has no matching visit. |
| `careprep.ts` | `careprepQueue`, `fetchCareprepQueue`, `getCareprepByVisitId` | Entire CarePrep funnel is mock-backed in listed pages. |
| `labs.ts` | `mockLabs`, `getLabById`, `LabResult` | Labs inbox/detail fully mock-backed. |
| `notifications.ts` | `mockNotifications`, `AppNotification` | Notifications list mock-backed. |
| `settings.ts` | `patchSettingsMock`, `auditEntries` | Save is mock; audit array unused in current Settings flow. |
| `abha.ts` | *(file present)* | **No imports** under `src/` — orphan / future. |
| `calendar.ts` | *(file present)* | **No imports** under `src/` — orphan / future. |

---

## Day 1 quick wins (prioritization hints)

1. **`SettingsPage`** + **`patchSettingsMock`**: wire to real PATCH endpoints or remove sham success.
2. **CarePrep + Labs + Notifications + Patient detail**: replace **`fetchCareprepQueue`** / **`mockLabs`** / **`mockNotifications`** / **`mockPatients`** with React Query + API routes matching **`clinic-ai-in`** OpenAPI.
3. **`registrationService`**, **`ConsentPage`** consent text: remove silent catch fallbacks once backend contract is trusted, or gate behind **`VITE_`** dev flag.
4. **`VisitWorkspacePage`**: clarify when mock visit is acceptable (e.g. only `DEV`).
5. **Orphans**: **`abha.ts`**, **`calendar.ts`**, **`getMockSlots`** — delete or document as demo-only.

---

*Generated from static analysis of **`clinic_ai_frontend/src`** imports; rerun `rg '@/lib/mocks/' clinic_ai_frontend/src` after refactors.*
