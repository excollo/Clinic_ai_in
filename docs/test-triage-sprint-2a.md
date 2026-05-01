# Test Triage: Sprint 2A Completion

Total integration tests: 63  
Passed: 38  
Failed: 0 (after triage actions)  
Skipped: 0  
XFailed: 25  
Error count: 0

Baseline run before triage actions (`test_results_full.txt`): 25 failed, 38 passed.

## Bucket A — Regressions (must fix now)

No Bucket A regressions found.

- Assessment method: compared failure traces against Sprint 2A touchpoints (`DPDPAuditMiddleware`, audit tagging in `frontend_contract.py`, consent capture/withdraw/history changes, consent-withdraw registration block).
- Result: all failures were endpoint-contract mismatches, missing endpoint families, or pre-existing implementation/test drift not introduced by Sprint 2A changes.

## Bucket B — Historical debt (feature not built / contract not yet migrated)

### Test: `tests/integration/test_auth_and_visit_workflow.py::test_forgot_password_returns_reset_token_and_allows_reset`
- Failure: `404 != 200` on `POST /api/auth/forgot-password`
- Missing feature: canonical/public auth reset contract still in migration (legacy `/api/...` test path)
- Defer to: Sprint 2B.1
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_patient_registration_ids.py::test_register_returns_opaque_patient_id_and_consult_visit_id`
- Failure: `404 != 200` on `POST /api/patients/register`
- Missing feature: legacy `/api/patients` contract path not canonicalized
- Defer to: Sprint 2B.4/2B.5
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_patient_registration_ids.py::test_create_visit_accepts_opaque_patient_id`
- Failure: `404 != 200` on `POST /api/patients/register`
- Missing feature: legacy patient+visit `/api` contract path migration pending
- Defer to: Sprint 2B.5
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_patient_registration_ids.py::test_register_without_appointment_defers_intake`
- Failure: `404 != 200` on `POST /api/patients/register`
- Missing feature: legacy intake scheduling `/api` path migration pending
- Defer to: Sprint 2B.5
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_patient_registration_ids.py::test_register_accepts_full_intake_language_and_preserves_it_for_chat`
- Failure: `404 != 200` on `POST /api/patients/register`
- Missing feature: legacy intake language contract on `/api` path pending migration
- Defer to: Sprint 2B.5
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_default_generate_prefers_india_note`
- Failure: `404 != 200` on `POST /notes/generate`
- Missing feature: notes-generation route contract not yet aligned to integration expectation
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_soap_endpoint_remains_operational`
- Failure: `404 != 200` on `POST /notes/soap`
- Missing feature: SOAP compatibility endpoint not exposed per integration contract
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_generate_india_with_follow_up_date_sets_payload_and_context`
- Failure: `404 != 200` on `POST /notes/generate`
- Missing feature: india-note generation endpoint contract migration pending
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_follow_up_reminders_run_sends_meta_template`
- Failure: `404 != 200` on `POST /workflow/follow-up-reminders/run`
- Missing feature: follow-up reminders run endpoint not exposed under tested contract
- Defer to: Sprint 2C
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_follow_up_reminders_run_sends_day_before_reminder`
- Failure: `404 != 200` on `POST /workflow/follow-up-reminders/run`
- Missing feature: follow-up reminders cron route contract pending
- Defer to: Sprint 2C
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_follow_up_reminders_run_fetches_patient_phone_when_to_number_missing`
- Failure: `404 != 200` on `POST /workflow/follow-up-reminders/run`
- Missing feature: follow-up reminders route contract pending
- Defer to: Sprint 2C
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_follow_up_reminders_run_requires_cron_secret_when_configured`
- Failure: `404 != 401` on `POST /workflow/follow-up-reminders/run`
- Missing feature: follow-up reminders route not present for auth-guard assertion
- Defer to: Sprint 2C
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_upload_happy_path`
- Failure: `404 != 202` on `POST /notes/transcribe`
- Missing feature: transcription upload contract endpoint not exposed
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_upload_rejects_when_previsit_missing`
- Failure: `404 != 409` on `POST /notes/transcribe`
- Missing feature: transcription upload endpoint missing under expected contract
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_visit_transcription_status_after_upload`
- Failure: `404 != 200` on `GET /notes/transcribe/status/{patient_id}/{visit_id}`
- Missing feature: transcription status endpoint family missing
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_visit_transcription_status_processing_naive_mongo_datetimes`
- Failure: `404 != 200` on `GET /notes/transcribe/status/{patient_id}/{visit_id}`
- Missing feature: transcription status endpoint family missing
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_visit_dialogue_returns_202_while_queued`
- Failure: `404 != 202` on `GET /notes/{patient}/visits/{visit}/dialogue`
- Missing feature: dialogue retrieval endpoint not exposed
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_visit_dialogue_returns_payload_when_completed`
- Failure: `404 != 200` on `GET /notes/{patient}/visits/{visit}/dialogue`
- Missing feature: dialogue retrieval endpoint not exposed
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_structure_dialogue_endpoint_persists`
- Failure: `404 != 200` on `POST /notes/{patient}/visits/{visit}/dialogue/structure`
- Missing feature: dialogue structuring endpoint not exposed
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_worker_marks_visit_session_completed`
- Failure: `404 != 202` on upload prerequisite (`POST /notes/transcribe`)
- Missing feature: transcription upload endpoint family missing
- Defer to: Sprint 2B.2
- Action: marked `xfail(strict=True)`

## Bucket C — Historical debt (broken implementation)

### Test: `tests/integration/test_soap_flow.py::test_post_visit_summary_includes_whatsapp_payload`
- Failure: monkeypatch target missing attribute `send_post_visit_summary_whatsapp`
- Broken thing: API drift between test hook target and current use-case exports
- Pilot-critical? No (not launch blocker for current pilot scope)
- Action: defer to Sprint 2C, marked `xfail(strict=True)` for now

### Test: `tests/integration/test_soap_flow.py::test_post_visit_summary_follow_up_date_overrides_next_visit`
- Failure: monkeypatch target missing attribute `send_post_visit_summary_whatsapp`
- Broken thing: same post-visit summary helper symbol drift
- Pilot-critical? No
- Action: defer to Sprint 2C, marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_post_visit_summary_uses_request_language_override`
- Failure: monkeypatch target missing attribute `send_post_visit_summary_whatsapp`
- Broken thing: same symbol drift between test and implementation
- Pilot-critical? No
- Action: defer to Sprint 2C, marked `xfail(strict=True)`

### Test: `tests/integration/test_soap_flow.py::test_post_visit_summary_prefers_india_note_without_transcript`
- Failure: monkeypatch target missing attribute `send_post_visit_summary_whatsapp`
- Broken thing: same symbol drift between test and implementation
- Pilot-critical? No
- Action: defer to Sprint 2C, marked `xfail(strict=True)`

### Test: `tests/integration/test_transcription_flow.py::test_worker_visit_uses_openai_structure_when_segments_are_unknown`
- Failure: `AssertionError: assert 1 >= 2` (`structured_dialogue` length)
- Broken thing: unknown-speaker normalization still collapses into single Patient turn; expected Doctor+Patient reconstruction
- Pilot-critical? Yes (clinical summarization quality and doctor trust risk)
- Action: prioritize in Sprint 2B.2 (before/with transcription contract rollout), marked `xfail(strict=True)` until implemented

## Bucket D — Test infrastructure issues

No Bucket D issues found in this pass.

- No fixture/mocking/environment breakages were identified as primary root cause for the 25 failures.
- Current suite health is deterministic after applying triage markers.

## Summary

- Bucket A count: 0 (must-fix-now regressions: none)
- Bucket B count: 20 (deferred with strict xfail + sprint references)
- Bucket C count: 5 (pilot-critical: 1, deferred: 4)
- Bucket D count: 0

Total work to make suite green without xfails: ~1.5 to 2.5 days (mostly Sprint 2B.2 + portions of 2C).  
Estimated time before Sprint 2B can start: complete (suite now stable with passed + xfailed only).

## Verification

- Baseline command: `pytest -q tests/integration > test_results_full.txt 2>&1`
  - Result: `25 failed, 38 passed`
- Post-triage command: `pytest -q tests/integration > test_results_post_triage.txt 2>&1`
  - Result: `38 passed, 25 xfailed`
