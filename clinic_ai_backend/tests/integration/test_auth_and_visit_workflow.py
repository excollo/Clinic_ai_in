from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.core.auth import verify_password


def test_forgot_password_returns_reset_token_and_allows_reset(app_client, patched_db) -> None:
    now = datetime.now(timezone.utc)
    patched_db.users.insert_one(
        {
            "id": "user-1",
            "email": "doctor@example.com",
            "username": "doctor",
            "hashed_password": "old-hash",
            "full_name": "Doctor Demo",
            "role": "doctor",
            "is_active": True,
            "is_verified": True,
            "created_at": now,
            "updated_at": now,
        }
    )

    forgot = app_client.post("/api/auth/forgot-password", json={"email": "doctor@example.com"})
    assert forgot.status_code == 200
    body = forgot.json()
    assert body["message"]
    assert body["reset_token"]

    reset = app_client.post(
        "/api/auth/reset-password",
        json={"token": body["reset_token"], "password": "new-password-123"},
    )
    assert reset.status_code == 200
    assert reset.json()["message"] == "Password reset successful"

    updated_user = patched_db.users.find_one({"id": "user-1"})
    assert updated_user is not None
    assert verify_password("new-password-123", str(updated_user["hashed_password"]))


def test_visit_lifecycle_supports_queue_start_complete_and_cancel(app_client, patched_db) -> None:
    now = datetime.now(timezone.utc)
    patched_db.patients.insert_one(
        {
            "patient_id": "patient-1",
            "name": "Queued Patient",
            "phone_number": "9999999999",
            "created_at": now,
            "updated_at": now,
        }
    )
    patched_db.visits.insert_one(
        {
            "visit_id": "CONSULT-20260428-001",
            "patient_id": "patient-1",
            "status": "scheduled",
            "scheduled_start": (now + timedelta(hours=1)).isoformat(),
            "created_at": now,
            "updated_at": now,
        }
    )

    queued = app_client.post("/api/visits/CONSULT-20260428-001/queue")
    assert queued.status_code == 200
    assert queued.json()["status"] == "in_queue"

    started = app_client.post("/api/visits/CONSULT-20260428-001/start")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    assert started.json()["actual_start"]

    completed = app_client.post("/api/visits/CONSULT-20260428-001/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["actual_end"]

    cancel_after_complete = app_client.delete("/api/visits/CONSULT-20260428-001")
    assert cancel_after_complete.status_code == 409


def test_cancelled_visit_cannot_be_rescheduled(app_client, patched_db) -> None:
    now = datetime.now(timezone.utc)
    patched_db.patients.insert_one(
        {
            "patient_id": "patient-2",
            "name": "Cancel Patient",
            "phone_number": "8888888888",
            "created_at": now,
            "updated_at": now,
        }
    )
    patched_db.visits.insert_one(
        {
            "visit_id": "CONSULT-20260428-002",
            "patient_id": "patient-2",
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
    )

    cancel = app_client.delete("/api/visits/CONSULT-20260428-002")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    reschedule = app_client.post(
        "/api/visits/CONSULT-20260428-002/schedule-intake",
        json={"appointment_date": tomorrow, "appointment_time": "09:30"},
    )
    assert reschedule.status_code == 409


def test_no_show_status_action(app_client, patched_db) -> None:
    now = datetime.now(timezone.utc)
    patched_db.patients.insert_one(
        {
            "patient_id": "patient-3",
            "name": "No Show",
            "phone_number": "7777777777",
            "created_at": now,
            "updated_at": now,
        }
    )
    patched_db.visits.insert_one(
        {
            "visit_id": "CONSULT-20260428-003",
            "patient_id": "patient-3",
            "status": "scheduled",
            "created_at": now,
            "updated_at": now,
        }
    )

    no_show = app_client.post("/api/visits/CONSULT-20260428-003/no-show")
    assert no_show.status_code == 200
    assert no_show.json()["status"] == "no_show"


def test_follow_through_continuity_update_completes_visit(app_client, patched_db) -> None:
    now = datetime.now(timezone.utc)
    patched_db.patients.insert_one(
        {
            "patient_id": "patient-4",
            "name": "Lab Follow Through",
            "phone_number": "6666666666",
            "created_at": now,
            "updated_at": now,
        }
    )
    patched_db.visits.insert_one(
        {
            "visit_id": "CONSULT-20260428-004",
            "patient_id": "patient-4",
            "status": "in_progress",
            "created_at": now,
            "updated_at": now,
        }
    )

    created = app_client.post(
        "/api/follow-through/lab-records",
        json={
            "visit_id": "CONSULT-20260428-004",
            "source": "whatsapp",
            "raw_text": "Glucose 240, SpO2 90",
        },
    )
    assert created.status_code == 200
    record_id = created.json()["record_id"]

    extracted = app_client.post(f"/api/follow-through/lab-records/{record_id}/extract")
    assert extracted.status_code == 200
    assert extracted.json()["status"] == "extracted"

    reviewed = app_client.post(f"/api/follow-through/lab-records/{record_id}/review", json={"decision": "approved"})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "doctor_reviewed"

    continuity = app_client.post(
        f"/api/follow-through/lab-records/{record_id}/continuity-update",
        json={"continuity_summary": "Patient improved after medication adjustment.", "mark_visit_completed": True},
    )
    assert continuity.status_code == 200
    assert continuity.json()["status"] == "continuity_updated"

    visit = patched_db.visits.find_one({"visit_id": "CONSULT-20260428-004"})
    assert visit is not None
    assert visit.get("status") == "completed"


def test_follow_through_accepts_case_insensitive_visit_lookup(app_client, patched_db) -> None:
    now = datetime.now(timezone.utc)
    patched_db.patients.insert_one(
        {
            "patient_id": "patient-5",
            "name": "Case Lookup",
            "phone_number": "5555555555",
            "created_at": now,
            "updated_at": now,
        }
    )
    patched_db.visits.insert_one(
        {
            "visit_id": "CONSULT-20260429-167",
            "patient_id": "patient-5",
            "status": "in_progress",
            "created_at": now,
            "updated_at": now,
        }
    )

    created = app_client.post(
        "/api/follow-through/lab-records",
        json={
            "visit_id": "consult-20260429-167",
            "source": "whatsapp",
            "raw_text": "Glucose 210",
        },
    )
    assert created.status_code == 200
    assert created.json()["visit_id"] == "CONSULT-20260429-167"


def test_follow_through_extract_uses_ocr_text_when_raw_text_empty(app_client, patched_db) -> None:
    now = datetime.now(timezone.utc)
    patched_db.follow_through_lab_records.insert_one(
        {
            "record_id": "LAB-OCR-1",
            "visit_id": "CONSULT-20260429-987",
            "patient_id": "patient-ocr",
            "source": "whatsapp",
            "status": "received",
            "raw_text": "",
            "ocr_text": "Glucose 240 SpO2 90",
            "extracted_values": [],
            "flags": [],
            "created_at": now,
            "updated_at": now,
        }
    )

    extracted = app_client.post("/api/follow-through/lab-records/LAB-OCR-1/extract")
    assert extracted.status_code == 200
    payload = extracted.json()
    assert payload["status"] == "extracted"
    assert len(payload["extracted_values"]) >= 2
