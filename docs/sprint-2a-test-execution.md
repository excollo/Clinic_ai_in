# Sprint 2A Test Execution

Date: 2026-05-01  
Environment: local backend + local MongoDB

## Scope

- Audit action tagging via `request.state.*`
- Consent capture accepted/declined
- Consent withdrawal and history
- Register-block behavior when consent is withdrawn
- Audit log API + CSV export

## Manual Scenario Run

Doctor: `doctor-s2a-e2e2`

1. Register patient  
   - Endpoint: `POST /patients/register`  
   - Result: `200`  
   - Audit action observed: `patient_registered`

2. Capture consent (accepted)  
   - Endpoint: `POST /consent/capture`  
   - Result: `200`  
   - Audit action observed: `consent_captured`

3. List patients  
   - Endpoint: `GET /patients`  
   - Result: `200`  
   - Audit action observed: `patients_listed`

4. View consent history  
   - Endpoint: `GET /consent/{pid}/history`  
   - Result: `200`  
   - Audit action observed: `consent_history_viewed`

5. Withdraw consent  
   - Endpoint: `POST /consent/withdraw`  
   - Result: `200`  
   - Audit action observed: `consent_withdrawn`

6. Attempt new registration with same withdrawn-consent patient  
   - Endpoint: `POST /patients/register`  
   - Result: `403`  
   - Audit action observed: `register_blocked_consent_withdrawn`

## Artifacts

Artifacts generated at:

- `docs/audit-screenshots/sprint-2a/audit-log-sample.json`
- `docs/audit-screenshots/sprint-2a/consents-sample.json`
- `docs/audit-screenshots/sprint-2a/consent-withdrawals-sample.json`
- `docs/audit-screenshots/sprint-2a/phi-safety-summary.json`

## PHI Safety Check

Audit records were checked for forbidden plain-text fields such as:

- patient name
- mobile number
- diagnosis/assessment text
- blood pressure values

Result from `phi-safety-summary.json`:

- `entries_checked`: 6
- `violations`: 0

## Test Suite Results

- `pytest -q tests/integration/test_frontend_contract_endpoints.py` -> **30 passed**
- `pytest -q tests/integration` -> **fails due pre-existing unrelated integration failures** (transcription and legacy flows), not introduced by Sprint 2A changes.

## Notes on Missing Items

- Endpoint `GET /patients/{id}` does not exist yet in current backend contract layer, so `patient_viewed` action is not yet taggable on that route.
- Dedicated visit start endpoint in contract router is not yet available; `visit_started` tagging will be completed when that endpoint is added/wired in later sprint scope.
