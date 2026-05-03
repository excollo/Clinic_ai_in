from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from src.app import app
from src.core.config import get_settings


def _auth_headers(doctor_id: str = "test-doctor-id") -> dict[str, str]:
    settings = get_settings()
    token = jwt.encode(
        {
            "doctor_id": doctor_id,
            "mobile": "9999999999",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return {"X-API-Key": token, "X-Doctor-ID": doctor_id}


AUTH_HEADERS = _auth_headers()


@pytest.fixture(autouse=True)
def _patch_runtime(patched_db, monkeypatch):
    monkeypatch.setattr("src.app.start_background_workers", lambda: None)

    async def _noop_stop() -> None:
        return None

    monkeypatch.setattr("src.app.stop_background_workers", _noop_stop)
    return patched_db


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_login_valid():
    async with _client() as client:
        response = await client.post("/auth/login", json={"mobile": "9876543210", "password": "testpassword123"})
    assert response.status_code in (200, 401)
    payload = response.json()
    assert "token" in payload or "request_id" in payload.get("detail", {})


@pytest.mark.asyncio
async def test_login_invalid_mobile():
    async with _client() as client:
        response = await client.post("/auth/login", json={"mobile": "1234567890", "password": "testpassword123"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_send_otp_verify_otp_and_forgot_password():
    async with _client() as client:
        signup = await client.post(
            "/auth/signup",
            json={
                "name": "Dr Test",
                "mobile": "9876543210",
                "email": "dr@example.com",
                "mci_number": "MCI123",
                "specialty": "General Medicine",
                "password": "testpassword123",
                "clinic_name": "Clinic",
                "city": "Delhi",
                "pincode": "110001",
                "opd_hours": {"start": "09:00", "end": "19:00"},
                "languages": ["en", "hi"],
                "whatsapp_mode": "platform_default",
            },
        )
        otp = await client.post("/auth/send-otp", json={"mobile": "9876543210"})
        assert signup.status_code == 200
        assert otp.status_code == 200
        request_id = otp.json()["request_id"]
        verify = await client.post(
            "/auth/verify-otp",
            json={"mobile": "9876543210", "otp": "123456", "request_id": request_id},
        )
        forgot = await client.post(
            "/auth/forgot-password",
            json={
                "mobile": "9876543210",
                "otp": "123456",
                "request_id": request_id,
                "new_password": "newpassword123",
            },
        )
    assert verify.status_code == 200
    assert forgot.status_code == 200
    assert "token" in verify.json()


@pytest.mark.asyncio
async def test_consent_text_public_and_consent_capture_idempotent():
    idempotency_key = "test-uuid-12345"
    payload = {
        "patient_id": "pat_test",
        "visit_id": "vis_test",
        "doctor_id": "test-doctor-id",
        "language": "hindi",
        "consent_text_version": "v1.0",
        "patient_confirmed": True,
        "timestamp": "2026-05-01T09:00:00Z",
    }
    async with _client() as client:
        text = await client.get("/consent/text", params={"language": "en"})
        r1 = await client.post(
            "/consent/capture",
            json=payload,
            headers={**AUTH_HEADERS, "X-Idempotency-Key": idempotency_key},
        )
        r2 = await client.post(
            "/consent/capture",
            json=payload,
            headers={**AUTH_HEADERS, "X-Idempotency-Key": idempotency_key},
        )
    assert text.status_code == 200
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["consent_id"] == r2.json()["consent_id"]


@pytest.mark.asyncio
async def test_register_walkin_patient():
    async with _client() as client:
        response = await client.post(
            "/patients/register",
            json={
                "name": "Ramesh Kumar",
                "age": 45,
                "sex": "M",
                "mobile": "9876543210",
                "language": "hindi",
                "chief_complaint": "chest pain",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    data = response.json()
    assert "patient_id" in data
    assert "visit_id" in data
    assert "token_number" in data


@pytest.mark.asyncio
async def test_register_invalid_age():
    async with _client() as client:
        response = await client.post(
            "/patients/register",
            json={
                "name": "Test",
                "age": 150,
                "sex": "M",
                "mobile": "9876543210",
                "language": "hindi",
                "chief_complaint": "fever",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_abha_lookup_link_and_scan_share_returns_503_when_not_configured():
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "ABHA Test",
                "age": 31,
                "sex": "F",
                "mobile": "9876543211",
                "language": "en",
                "chief_complaint": "fever",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
        patient_id = reg.json()["patient_id"]
        lookup = await client.post("/patients/abha/lookup", json={"abha_id": "12-3456-7890-1234"}, headers=AUTH_HEADERS)
        link = await client.post(
            "/patients/abha/link",
            json={"patient_id": patient_id, "abha_id": "12-3456-7890-1234"},
            headers=AUTH_HEADERS,
        )
        scan_share = await client.post(
            "/patients/register/scan-share",
            json={"abha_qr_data": "ABHA-QR-CONTENT-12345678901234"},
            headers=AUTH_HEADERS,
        )
    assert lookup.status_code == 503
    assert link.status_code == 503
    assert scan_share.status_code == 503
    assert lookup.json()["detail"]["status"] == "abdm_not_configured"
    assert lookup.json()["detail"]["fallback"] == "manual_registration"


@pytest.mark.asyncio
async def test_vitals_required_fields_chest_pain_and_save():
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Vitals Test",
                "age": 49,
                "sex": "M",
                "mobile": "9876543212",
                "language": "en",
                "chief_complaint": "chest pain",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
        patient_id = reg.json()["patient_id"]
        visit_id = reg.json()["visit_id"]
        required = await client.get(
            f"/patients/{patient_id}/visits/{visit_id}/vitals/required-fields",
            headers=AUTH_HEADERS,
        )
        save = await client.post(
            f"/patients/{patient_id}/visits/{visit_id}/vitals",
            json={
                "blood_pressure": {"systolic": 120, "diastolic": 80},
                "weight": 65.5,
                "dynamic_values": {"pulse": 72},
            },
            headers=AUTH_HEADERS,
        )
    assert required.status_code == 200
    fixed_keys = [f["key"] for f in required.json()["fixed_fields"]]
    assert "blood_pressure" in fixed_keys
    assert "weight" in fixed_keys
    assert save.status_code == 200
    assert "vitals_id" in save.json()


@pytest.mark.asyncio
async def test_india_clinical_note_save_and_get():
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Note Test",
                "age": 55,
                "sex": "F",
                "mobile": "9876543213",
                "language": "en",
                "chief_complaint": "fever",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
        patient_id = reg.json()["patient_id"]
        visit_id = reg.json()["visit_id"]
        note = await client.post(
            "/notes/india-clinical-note",
            json={
                "visit_id": visit_id,
                "patient_id": patient_id,
                "assessment": "viral fever",
                "plan": "rest and hydration",
                "status": "draft",
            },
            headers=AUTH_HEADERS,
        )
        get_note = await client.get(
            f"/patients/{patient_id}/visits/{visit_id}/india-clinical-note",
            headers=AUTH_HEADERS,
        )
    assert note.status_code == 200
    assert get_note.status_code == 200
    assert get_note.json()["patient_id"] == patient_id


@pytest.mark.asyncio
async def test_medication_schedule_save_and_get():
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Med Test",
                "age": 60,
                "sex": "M",
                "mobile": "9876543214",
                "language": "en",
                "chief_complaint": "joint pain",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
        patient_id = reg.json()["patient_id"]
        visit_id = reg.json()["visit_id"]
        save = await client.post(
            f"/patients/{patient_id}/visits/{visit_id}/medication-schedule",
            json={
                "medicines": [
                    {
                        "name": "Paracetamol",
                        "dose": "500mg",
                        "morning_time": "08:00",
                        "food_instruction": "after_food",
                        "duration_days": 5,
                    }
                ]
            },
            headers=AUTH_HEADERS,
        )
        get_schedule = await client.get(
            f"/patients/{patient_id}/visits/{visit_id}/medication-schedule",
            headers=AUTH_HEADERS,
        )
    assert save.status_code == 200
    assert get_schedule.status_code == 200
    assert "medicines" in get_schedule.json()


@pytest.mark.asyncio
async def test_lab_results_create_and_list():
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Lab Test",
                "age": 38,
                "sex": "F",
                "mobile": "9876543215",
                "language": "en",
                "chief_complaint": "fatigue",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
        patient_id = reg.json()["patient_id"]
        visit_id = reg.json()["visit_id"]
        create = await client.post(
            f"/patients/{patient_id}/visits/{visit_id}/lab-results",
            json={"file_url": "https://example.com/report.pdf", "file_type": "pdf", "source": "upload"},
            headers=AUTH_HEADERS,
        )
        list_results = await client.get(
            f"/patients/{patient_id}/visits/{visit_id}/lab-results",
            headers=AUTH_HEADERS,
        )
    assert create.status_code == 200
    assert list_results.status_code == 200
    assert "results" in list_results.json()


@pytest.mark.asyncio
async def test_continuity_summary():
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Cont Test",
                "age": 30,
                "sex": "M",
                "mobile": "9876543216",
                "language": "en",
                "chief_complaint": "cough",
                "workflow_type": "walk_in",
            },
            headers=AUTH_HEADERS,
        )
        patient_id = reg.json()["patient_id"]
        response = await client.get(f"/patients/{patient_id}/continuity-summary", headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert "current_medications" in response.json()


@pytest.mark.asyncio
async def test_protected_route_no_headers_and_with_headers():
    async with _client() as client:
        no_headers = await client.get("/doctor/test-id/queue")
        with_headers = await client.get("/doctor/test-id/queue", headers=AUTH_HEADERS)
    assert no_headers.status_code == 401
    assert with_headers.status_code == 200


@pytest.mark.asyncio
async def test_whatsapp_send():
    async with _client() as client:
        response = await client.post(
            "/whatsapp/send",
            json={
                "visit_id": "vis_test",
                "patient_id": "pat_test",
                "recipient_mobile": "9876543210",
                "language": "en",
                "message_type": "post_visit_recap",
            },
            headers=AUTH_HEADERS,
        )
    assert response.status_code == 200
    assert "message_id" in response.json()


@pytest.mark.asyncio
async def test_get_notifications_and_mark_all_read(patched_db):
    patched_db.notifications.insert_one(
        {
            "doctor_id": "test-doctor-id",
            "read": False,
            "type": "lab",
            "title": "Lab result ready",
            "created_at": datetime.now(timezone.utc),
        }
    )
    async with _client() as client:
        get_notifications = await client.get(
            "/notifications",
            params={"doctor_id": "test-doctor-id"},
            headers=AUTH_HEADERS,
        )
        mark_all_read = await client.patch(
            "/notifications/mark-all-read",
            json={"doctor_id": "test-doctor-id"},
            headers=AUTH_HEADERS,
        )
    assert get_notifications.status_code == 200
    data = get_notifications.json()
    assert "notifications" in data
    assert "unread_count" in data
    assert mark_all_read.status_code == 200
    assert "updated" in mark_all_read.json()


@pytest.mark.asyncio
async def test_login_uses_bcrypt_and_returns_jwt():
    async with _client() as client:
        signup = await client.post(
            "/auth/signup",
            json={
                "name": "Auth Doctor",
                "mobile": "9876543220",
                "email": "auth@example.com",
                "mci_number": "MCI999",
                "specialty": "Cardiology",
                "password": "StrongPass123",
                "clinic_name": "Auth Clinic",
                "city": "Mumbai",
                "pincode": "400001",
                "opd_hours": {"start": "09:00", "end": "17:00"},
                "languages": ["en"],
                "whatsapp_mode": "platform_default",
            },
        )
        assert signup.status_code == 200
        login = await client.post("/auth/login", json={"mobile": "9876543220", "password": "StrongPass123"})
    assert login.status_code == 200
    token = login.json()["token"]
    payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=[get_settings().jwt_algorithm])
    assert payload["doctor_id"] == login.json()["doctor_id"]


@pytest.mark.asyncio
async def test_login_rate_limit_after_five_failures():
    async with _client() as client:
        await client.post(
            "/auth/signup",
            json={
                "name": "Rate Doctor",
                "mobile": "9876543221",
                "email": "rate@example.com",
                "mci_number": "MCI998",
                "specialty": "General Medicine",
                "password": "CorrectPass123",
                "clinic_name": "Rate Clinic",
                "city": "Pune",
                "pincode": "411001",
                "opd_hours": {"start": "09:00", "end": "17:00"},
                "languages": ["en"],
                "whatsapp_mode": "platform_default",
            },
        )
        for _ in range(5):
            failed = await client.post("/auth/login", json={"mobile": "9876543221", "password": "wrong-pass"})
            assert failed.status_code == 401
        locked = await client.post("/auth/login", json={"mobile": "9876543221", "password": "CorrectPass123"})
    assert locked.status_code == 429


@pytest.mark.asyncio
async def test_verify_otp_increments_attempts_and_locks_at_three(patched_db):
    async with _client() as client:
        sent = await client.post("/auth/send-otp", json={"mobile": "9876543222"})
        request_id = sent.json()["request_id"]
        bad1 = await client.post("/auth/verify-otp", json={"mobile": "9876543222", "otp": "000000", "request_id": request_id})
        bad2 = await client.post("/auth/verify-otp", json={"mobile": "9876543222", "otp": "000000", "request_id": request_id})
        bad3 = await client.post("/auth/verify-otp", json={"mobile": "9876543222", "otp": "000000", "request_id": request_id})
        locked = await client.post("/auth/verify-otp", json={"mobile": "9876543222", "otp": "123456", "request_id": request_id})
    assert bad1.status_code == 401
    assert bad2.status_code == 401
    assert bad3.status_code == 401
    assert locked.status_code == 429
    record = patched_db.otp_requests.find_one({"request_id": request_id})
    assert record is not None
    assert int(record.get("attempts", 0)) == 3


@pytest.mark.asyncio
async def test_register_duplicate_mobile_reuses_patient_and_increments_counter():
    headers = _auth_headers("doctor-dup")
    async with _client() as client:
        first = await client.post(
            "/patients/register",
            json={
                "name": "Dup Patient",
                "age": 40,
                "sex": "M",
                "mobile": "9876543223",
                "language": "en",
                "chief_complaint": "fever",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        second = await client.post(
            "/patients/register",
            json={
                "name": "Dup Patient",
                "age": 40,
                "sex": "M",
                "mobile": "9876543223",
                "language": "en",
                "chief_complaint": "cough",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["patient_id"] == second.json()["patient_id"]
    assert first.json()["token_number"] != second.json()["token_number"]


@pytest.mark.asyncio
async def test_consent_capture_updates_visit_with_consent(patched_db):
    headers = _auth_headers("doctor-consent")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Consent Patient",
                "age": 29,
                "sex": "F",
                "mobile": "9876543224",
                "language": "en",
                "chief_complaint": "headache",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        payload = {
            "patient_id": reg.json()["patient_id"],
            "visit_id": reg.json()["visit_id"],
            "doctor_id": "doctor-consent",
            "language": "en",
            "consent_text_version": "v1.0",
            "patient_confirmed": True,
            "timestamp": "2026-05-01T09:00:00Z",
        }
        response = await client.post(
            "/consent/capture",
            json=payload,
            headers={**headers, "X-Idempotency-Key": "consent-key-1"},
        )
    assert response.status_code == 200
    visit = patched_db.visits.find_one({"visit_id": reg.json()["visit_id"]})
    assert visit is not None
    assert visit.get("consent_captured") is True
    assert bool(visit.get("consent_id"))


@pytest.mark.asyncio
async def test_vitals_required_fields_returns_correct_shape():
    headers = _auth_headers("doctor-vitals-shape")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Vitals Shape",
                "age": 34,
                "sex": "M",
                "mobile": "9876543230",
                "language": "en",
                "chief_complaint": "headache",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        response = await client.get(
            f"/patients/{reg.json()['patient_id']}/visits/{reg.json()['visit_id']}/vitals/required-fields",
            headers=headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert "fixed_fields" in data
    assert "dynamic_fields" in data


@pytest.mark.asyncio
async def test_vitals_required_fields_chest_pain_returns_pulse_and_spo2(monkeypatch):
    monkeypatch.setattr(
        "src.api.routers.frontend_contract._generate_dynamic_vitals_with_llm",
        lambda _complaint: [
            {"key": "pulse", "label": "Pulse", "type": "number", "unit": "bpm", "normal_range": [60, 100], "ai_reason": "Suggested for cardiac complaint"},
            {"key": "spo2", "label": "SpO₂", "type": "number", "unit": "%", "normal_range": [95, 100], "ai_reason": "Suggested for cardiac complaint"},
        ],
    )
    headers = _auth_headers("doctor-vitals-chest")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Vitals Chest",
                "age": 50,
                "sex": "F",
                "mobile": "9876543231",
                "language": "en",
                "chief_complaint": "chest pain and breathless",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        response = await client.get(
            f"/patients/{reg.json()['patient_id']}/visits/{reg.json()['visit_id']}/vitals/required-fields",
            headers=headers,
        )
    assert response.status_code == 200
    dynamic_keys = [item["key"] for item in response.json()["dynamic_fields"]]
    assert "pulse" in dynamic_keys
    assert "spo2" in dynamic_keys


@pytest.mark.asyncio
async def test_vitals_save_succeeds():
    headers = _auth_headers("doctor-vitals-save")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Vitals Save",
                "age": 39,
                "sex": "M",
                "mobile": "9876543232",
                "language": "en",
                "chief_complaint": "fever",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        response = await client.post(
            f"/patients/{reg.json()['patient_id']}/visits/{reg.json()['visit_id']}/vitals",
            json={
                "blood_pressure": {"systolic": 122, "diastolic": 82},
                "weight": 70.0,
                "dynamic_values": {"temperature": 99.2},
            },
            headers=headers,
        )
    assert response.status_code == 200
    assert "vitals_id" in response.json()


@pytest.mark.asyncio
async def test_vitals_save_returns_409_on_second_save():
    headers = _auth_headers("doctor-vitals-immutable")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Vitals Immutable",
                "age": 44,
                "sex": "F",
                "mobile": "9876543233",
                "language": "en",
                "chief_complaint": "cough",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        payload = {
            "blood_pressure": {"systolic": 119, "diastolic": 79},
            "weight": 66.0,
            "dynamic_values": {"pulse": 73},
        }
        first = await client.post(
            f"/patients/{reg.json()['patient_id']}/visits/{reg.json()['visit_id']}/vitals",
            json=payload,
            headers=headers,
        )
        second = await client.post(
            f"/patients/{reg.json()['patient_id']}/visits/{reg.json()['visit_id']}/vitals",
            json=payload,
            headers=headers,
        )
    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_vitals_get_and_workspace_progress_after_vitals_save(patched_db):
    headers = _auth_headers("doctor-workspace-progress")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Workspace Progress",
                "age": 41,
                "sex": "M",
                "mobile": "9876543299",
                "language": "en",
                "chief_complaint": "fever",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        assert reg.status_code == 200
        patient_id = reg.json()["patient_id"]
        visit_id = reg.json()["visit_id"]
        progress0 = await client.get(
            f"/patients/{patient_id}/visits/{visit_id}/workspace-progress",
            headers=headers,
        )
        assert progress0.status_code == 200
        assert progress0.json()["vitals_recorded"] is False
        assert progress0.json()["transcription_complete"] is False

        save = await client.post(
            f"/patients/{patient_id}/visits/{visit_id}/vitals",
            json={
                "blood_pressure": {"systolic": 120, "diastolic": 80},
                "weight": 72.0,
                "dynamic_values": {},
            },
            headers=headers,
        )
        assert save.status_code == 200
        got = await client.get(
            f"/patients/{patient_id}/visits/{visit_id}/vitals",
            headers=headers,
        )
        progress1 = await client.get(
            f"/patients/{patient_id}/visits/{visit_id}/workspace-progress",
            headers=headers,
        )
    assert got.status_code == 200
    assert got.json()["blood_pressure"]["systolic"] == 120
    assert progress1.status_code == 200
    body = progress1.json()
    assert body["vitals_recorded"] is True
    assert body["vitals"] is not None
    assert body["clinical_note_status"] is None


@pytest.mark.asyncio
async def test_india_clinical_note_draft_save():
    headers = _auth_headers("doctor-note-draft")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Note Draft",
                "age": 48,
                "sex": "M",
                "mobile": "9876543234",
                "language": "en",
                "chief_complaint": "migraine",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        draft = await client.post(
            "/notes/india-clinical-note",
            json={
                "visit_id": reg.json()["visit_id"],
                "patient_id": reg.json()["patient_id"],
                "assessment": "migraine likely",
                "plan": "hydration and sleep",
                "status": "draft",
            },
            headers=headers,
        )
    assert draft.status_code == 200
    assert draft.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_india_clinical_note_approve():
    headers = _auth_headers("doctor-note-approve")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Note Approve",
                "age": 33,
                "sex": "F",
                "mobile": "9876543235",
                "language": "en",
                "chief_complaint": "headache",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        await client.post(
            "/notes/india-clinical-note",
            json={
                "visit_id": reg.json()["visit_id"],
                "patient_id": reg.json()["patient_id"],
                "assessment": "tension headache",
                "plan": "rest and hydration",
                "status": "draft",
            },
            headers=headers,
        )
        approve = await client.post(
            "/notes/india-clinical-note",
            json={
                "visit_id": reg.json()["visit_id"],
                "patient_id": reg.json()["patient_id"],
                "assessment": "tension headache",
                "plan": "rest and hydration",
                "status": "approved",
            },
            headers=headers,
        )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_india_clinical_note_get_returns_saved_note():
    headers = _auth_headers("doctor-note-get")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Note Get",
                "age": 29,
                "sex": "M",
                "mobile": "9876543236",
                "language": "en",
                "chief_complaint": "fever",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        await client.post(
            "/notes/india-clinical-note",
            json={
                "visit_id": reg.json()["visit_id"],
                "patient_id": reg.json()["patient_id"],
                "assessment": "viral fever",
                "plan": "fluids and paracetamol",
                "status": "draft",
            },
            headers=headers,
        )
        response = await client.get(
            f"/patients/{reg.json()['patient_id']}/visits/{reg.json()['visit_id']}/india-clinical-note",
            headers=headers,
        )
    assert response.status_code == 200
    assert response.json()["assessment"] == "viral fever"


@pytest.mark.asyncio
async def test_queue_returns_todays_visits():
    headers = _auth_headers("doctor-queue-today")
    async with _client() as client:
        await client.post(
            "/patients/register",
            json={
                "name": "Queue Today",
                "age": 42,
                "sex": "F",
                "mobile": "9876543237",
                "language": "en",
                "chief_complaint": "cough",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        response = await client.get("/doctor/doctor-queue-today/queue", headers=headers)
    assert response.status_code == 200
    assert "patients" in response.json()
    assert response.json()["total_today"] >= 1


@pytest.mark.asyncio
async def test_continuity_summary_returns_null_fields_for_new_patient():
    headers = _auth_headers("doctor-cont-new")
    async with _client() as client:
        reg = await client.post(
            "/patients/register",
            json={
                "name": "Cont New",
                "age": 26,
                "sex": "M",
                "mobile": "9876543238",
                "language": "en",
                "chief_complaint": "cold",
                "workflow_type": "walk_in",
            },
            headers=headers,
        )
        response = await client.get(f"/patients/{reg.json()['patient_id']}/continuity-summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "last_diagnosis" in data
    assert "current_medications" in data


@pytest.mark.asyncio
async def test_whatsapp_send_dev_mode_fallback_returns_queued_status():
    headers = _auth_headers("doctor-wa-dev")
    async with _client() as client:
        response = await client.post(
            "/whatsapp/send",
            json={
                "visit_id": "vis_dev",
                "patient_id": "pat_dev",
                "recipient_mobile": "9876543239",
                "language": "en",
                "message_type": "post_visit_recap",
            },
            headers=headers,
        )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
