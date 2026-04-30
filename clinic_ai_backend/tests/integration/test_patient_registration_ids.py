"""Integration tests for opaque patient_id + CONSULT visit_id flow."""
from __future__ import annotations

import re

from src.application.utils.patient_id_crypto import decode_patient_id


def test_register_returns_opaque_patient_id_and_consult_visit_id(app_client) -> None:
    payload = {
        "name": "John",
        "phone_number": "+1 (555) 123-4567",
        "age": 30,
        "gender": "male",
        "preferred_language": "en",
        "travelled_recently": False,
        "constant": True,
    }
    res = app_client.post("/api/patients/register", json=payload)
    assert res.status_code == 200
    data = res.json()

    opaque_patient_id = data["patient_id"]
    internal = decode_patient_id(opaque_patient_id)
    assert internal == "john_15551234567"
    assert re.fullmatch(r"^CONSULT-\d{8}-\d{3}$", data["visit_id"]) is not None
    assert data.get("pending_schedule_for_intake") is True
    assert data.get("whatsapp_triggered") is False


def test_create_visit_accepts_opaque_patient_id(app_client, monkeypatch) -> None:
    monkeypatch.setattr(
        "src.application.services.intake_chat_service.IntakeChatService.start_intake",
        lambda *args, **kwargs: None,
    )
    register_payload = {
        "name": "Asha",
        "phone_number": "9876543210",
        "age": 29,
        "gender": "female",
        "preferred_language": "en",
        "travelled_recently": False,
        "constant": True,
    }
    reg = app_client.post("/api/patients/register", json=register_payload)
    assert reg.status_code == 200
    opaque_patient_id = reg.json()["patient_id"]

    res = app_client.post(f"/api/patients/{opaque_patient_id}/visits", json={})
    assert res.status_code == 200
    body = res.json()
    assert re.fullmatch(r"^CONSULT-\d{8}-\d{3}$", body["visit_id"]) is not None
    assert decode_patient_id(body["patient_id"]) == "asha_9876543210"
    assert body.get("pending_schedule_for_intake") is True
    assert body.get("intake_triggered") is False


def test_register_without_appointment_defers_intake(app_client, monkeypatch) -> None:
    calls: list[tuple] = []

    def _capture(*args, **kwargs) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(
        "src.application.services.intake_chat_service.IntakeChatService.start_intake",
        _capture,
    )
    payload = {
        "name": "Defer Intake",
        "phone_number": "9123456789",
        "age": 40,
        "gender": "male",
        "preferred_language": "en",
        "travelled_recently": False,
        "consent": True,
    }
    res = app_client.post("/api/patients/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data.get("whatsapp_triggered") is False
    assert data.get("pending_schedule_for_intake") is True
    assert calls == []

    visit_id = data["visit_id"]
    schedule = app_client.post(
        f"/api/visits/{visit_id}/schedule-intake",
        json={"appointment_date": "2099-01-01", "appointment_time": "10:30"},
    )
    assert schedule.status_code == 422

    from datetime import date, timedelta

    ok_day = (date.today() + timedelta(days=1)).isoformat()
    schedule_ok = app_client.post(
        f"/api/visits/{visit_id}/schedule-intake",
        json={"appointment_date": ok_day, "appointment_time": "10:30"},
    )
    assert schedule_ok.status_code == 200
    assert schedule_ok.json().get("whatsapp_triggered") is True
    assert len(calls) == 1


def test_register_accepts_full_intake_language_and_preserves_it_for_chat(app_client, monkeypatch) -> None:
    calls: list[tuple] = []

    def _capture(*args, **kwargs) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(
        "src.application.services.intake_chat_service.IntakeChatService.start_intake",
        _capture,
    )
    payload = {
        "name": "Hinglish Patient",
        "phone_number": "9988776655",
        "age": 33,
        "gender": "female",
        "preferred_language": "hi-eng",
        "travelled_recently": False,
        "consent": True,
        "appointment_date": "2099-01-01",
        "appointment_time": "10:30",
    }
    res = app_client.post("/api/patients/register", json=payload)
    assert res.status_code == 200
    assert len(calls) == 1
    assert calls[0][1]["language"] == "hi-eng"
