"""Integration tests for notes generation flows."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.application.use_cases.process_follow_up_reminders import ProcessFollowUpRemindersUseCase
from src.core import config as config_module


def _insert_note_context(fake_db, patient_id: str, job_id: str = "job-n1", visit_id: str = "v1") -> None:
    fake_db.patients.insert_one(
        {
            "patient_id": patient_id,
            "name": "Ravi Kumar",
            "age": 42,
            "gender": "male",
            "preferred_language": "en",
            "phone_number": "+919876543210",
        }
    )
    fake_db.pre_visit_summaries.insert_one(
        {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "status": "generated",
            "updated_at": datetime.now(timezone.utc),
            "sections": {
                "chief_complaint": {"reason_for_visit": "Fever and cough"},
            },
        }
    )
    fake_db.intake_sessions.insert_one(
        {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "updated_at": datetime.now(timezone.utc),
            "answers": [{"question": "illness", "answer": "Fever and cough"}],
        }
    )
    fake_db.transcription_jobs.insert_one(
        {
            "job_id": job_id,
            "audio_id": "a1",
            "patient_id": patient_id,
            "visit_id": visit_id,
            "status": "completed",
            "created_at": datetime.now(timezone.utc),
            "completed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    fake_db.transcription_results.insert_one(
        {
            "job_id": job_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "language_detected": "en",
            "overall_confidence": 0.9,
            "requires_manual_review": False,
            "full_transcript_text": "Patient reports fever for three days with dry cough.",
            "segments": [],
            "created_at": datetime.now(timezone.utc),
        }
    )


def test_default_generate_prefers_india_note(app_client, fake_db, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_note_context(fake_db, patient_id="p-note-1", job_id="job-note-1")
    monkeypatch.setattr(
        "src.adapters.external.ai.openai_client.OpenAIQuestionClient.generate_india_clinical_note",
        lambda self, context: {
            "assessment": "Likely acute upper respiratory tract infection.",
            "plan": "Hydration, symptomatic care, and close review.",
            "rx": [],
            "investigations": [],
            "red_flags": ["Worsening breathlessness"],
            "follow_up_in": "5 days",
            "follow_up_date": None,
            "doctor_notes": None,
            "chief_complaint": "Fever and cough",
            "data_gaps": context.get("data_gaps", []),
        },
    )
    response = app_client.post(
        "/notes/generate",
        json={"patient_id": "p-note-1", "visit_id": "v1", "transcription_job_id": "job-note-1"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["note_type"] == "india_clinical"
    assert payload["payload"]["assessment"]
    assert payload["payload"]["follow_up_in"] == "5 days"


def test_soap_endpoint_remains_operational(app_client, fake_db) -> None:
    _insert_note_context(fake_db, patient_id="p-note-2", job_id="job-note-2")
    response = app_client.post(
        "/notes/soap",
        json={"patient_id": "p-note-2", "visit_id": "v1", "transcription_job_id": "job-note-2"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["note_type"] == "soap"
    assert payload["legacy"] is True
    assert "subjective:" in (payload["payload"]["doctor_notes"] or "")


def test_post_visit_summary_includes_whatsapp_payload(app_client, fake_db, monkeypatch: pytest.MonkeyPatch) -> None:
    post_visit_sends: list[dict] = []

    def _capture_post_visit_whatsapp(*, patient: dict, whatsapp_payload: str) -> None:
        post_visit_sends.append({"patient": patient, "whatsapp_payload": whatsapp_payload})

    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_post_visit_summary_whatsapp",
        _capture_post_visit_whatsapp,
    )
    follow_up_immediate: list[int] = []

    def _capture_follow_up_immediate(*args, **kwargs) -> None:
        follow_up_immediate.append(1)

    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_immediate_follow_up_template_whatsapp",
        _capture_follow_up_immediate,
    )
    _insert_note_context(fake_db, patient_id="p-note-3", job_id="job-note-3")
    fake_db.clinical_notes.insert_one(
        {
            "note_id": "n-india-1",
            "patient_id": "p-note-3",
            "visit_id": "v1",
            "note_type": "india_clinical",
            "source_job_id": "job-note-3",
            "status": "generated",
            "version": 1,
            "created_at": datetime.now(timezone.utc),
            "payload": {
                "assessment": "Viral upper respiratory infection",
                "plan": "Hydration and rest",
                "rx": [{"medicine_name": "Paracetamol", "dose": "500 mg", "frequency": "SOS", "duration": "3 days", "route": "oral", "food_instruction": "after food"}],
                "investigations": [{"test_name": "CBC", "urgency": "routine"}],
                "red_flags": ["Breathlessness"],
                "follow_up_in": "3 days",
                "follow_up_date": None,
                "doctor_notes": None,
                "chief_complaint": "Fever and cough",
                "data_gaps": [],
            },
        }
    )
    monkeypatch.setattr(
        "src.adapters.external.ai.openai_client.OpenAIQuestionClient.generate_post_visit_summary",
        lambda self, context, language_name: {
            "visit_reason": "Fever and cough",
            "what_doctor_found": "Looks like a viral infection.",
            "medicines_to_take": ["Paracetamol 500 mg after food"],
            "tests_recommended": ["CBC"],
            "self_care": ["Drink fluids"],
            "warning_signs": ["Trouble breathing"],
            "follow_up": "Visit again in 3 days",
            "next_visit_date": "2030-06-20",
        },
    )
    response = app_client.post(
        "/notes/post-visit-summary",
        json={"patient_id": "p-note-3", "visit_id": "v1", "transcription_job_id": "job-note-3"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["note_type"] == "post_visit_summary"
    assert payload["payload"]["what_doctor_found"] == "Looks like a viral infection."
    assert "🩺" in payload["whatsapp_payload"]
    assert "💊" in payload["whatsapp_payload"]
    assert "🔬" in payload["whatsapp_payload"]
    assert "📅" in payload["whatsapp_payload"]
    assert "⚠️" in payload["whatsapp_payload"]
    reminder = fake_db.follow_up_reminders.find_one({"patient_id": "p-note-3", "visit_id": "v1"})
    assert reminder is not None
    assert reminder.get("to_number") == "919876543210"
    assert reminder.get("note_id") == payload.get("note_id")
    assert len(post_visit_sends) == 1
    assert "Post-visit summary" in post_visit_sends[0]["whatsapp_payload"]
    assert len(follow_up_immediate) == 1


def test_post_visit_summary_follow_up_date_overrides_next_visit(app_client, fake_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_post_visit_summary_whatsapp",
        lambda **_: None,
    )
    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_immediate_follow_up_template_whatsapp",
        lambda **_: None,
    )
    _insert_note_context(fake_db, patient_id="p-note-fu-pv", job_id="job-note-fu-pv")
    fake_db.clinical_notes.insert_one(
        {
            "note_id": "n-india-fu-pv",
            "patient_id": "p-note-fu-pv",
            "visit_id": "v1",
            "note_type": "india_clinical",
            "source_job_id": "job-note-fu-pv",
            "status": "generated",
            "version": 1,
            "created_at": datetime.now(timezone.utc),
            "payload": {
                "assessment": "DM follow-up",
                "plan": "Continue care",
                "rx": [],
                "investigations": [],
                "red_flags": [],
                "follow_up_in": "14 days",
                "follow_up_date": None,
                "doctor_notes": None,
                "chief_complaint": "Diabetes",
                "data_gaps": [],
            },
        }
    )
    monkeypatch.setattr(
        "src.adapters.external.ai.openai_client.OpenAIQuestionClient.generate_post_visit_summary",
        lambda self, context, language_name: {
            "visit_reason": "Diabetes",
            "what_doctor_found": "Stable.",
            "medicines_to_take": [],
            "tests_recommended": [],
            "self_care": [],
            "warning_signs": [],
            "follow_up": "Return in 2 weeks",
            "next_visit_date": "2030-06-20",
        },
    )
    response = app_client.post(
        "/notes/post-visit-summary",
        json={
            "patient_id": "p-note-fu-pv",
            "visit_id": "v1",
            "transcription_job_id": "job-note-fu-pv",
            "follow_up_date": "2030-08-10",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["payload"]["next_visit_date"] == "2030-08-10"
    reminder = fake_db.follow_up_reminders.find_one({"patient_id": "p-note-fu-pv", "visit_id": "v1"})
    assert reminder is not None
    assert reminder["next_visit_at"].date().isoformat() == "2030-08-10"


def test_generate_india_with_follow_up_date_sets_payload_and_context(app_client, fake_db, monkeypatch: pytest.MonkeyPatch) -> None:
    _insert_note_context(fake_db, patient_id="p-note-fu-in", job_id="job-note-fu-in")
    captured: dict = {}

    def _fake_generate(self, context: dict) -> dict:
        captured["context"] = context
        return {
            "assessment": "Stable chronic illness.",
            "plan": "Continue meds.",
            "rx": [],
            "investigations": [],
            "red_flags": [],
            "follow_up_in": "7 days",
            "follow_up_date": None,
            "doctor_notes": None,
            "chief_complaint": "Diabetes",
            "data_gaps": context.get("data_gaps", []),
        }

    monkeypatch.setattr(
        "src.adapters.external.ai.openai_client.OpenAIQuestionClient.generate_india_clinical_note",
        _fake_generate,
    )
    response = app_client.post(
        "/notes/generate",
        json={
            "patient_id": "p-note-fu-in",
            "visit_id": "v1",
            "transcription_job_id": "job-note-fu-in",
            "follow_up_date": "2030-11-01",
        },
    )
    assert response.status_code == 200
    assert captured["context"].get("staff_confirmed_follow_up_date") == "2030-11-01"
    assert response.json()["payload"]["follow_up_date"] == "2030-11-01"
    assert response.json()["payload"].get("follow_up_in") is None


def test_follow_up_reminders_run_sends_meta_template(app_client, patched_db, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cron endpoint sends WhatsApp template at T-3d (uses intake/opening_msg template when follow-up name unset)."""
    settings = config_module.get_settings()
    settings.whatsapp_access_token = "test-token"
    settings.whatsapp_phone_number_id = "test-phone-id"
    settings.whatsapp_intake_template_name = "opening_msg"
    settings.whatsapp_followup_template_name = ""
    monkeypatch.setattr("src.core.config.get_settings", lambda: settings)

    sent: list[dict] = []

    def _stub_send_template(_self, *, to_number: str, template_name: str, language_code: str, body_values=None) -> None:
        sent.append(
            {"to": to_number, "template_name": template_name, "language_code": language_code, "body_values": body_values}
        )

    monkeypatch.setattr(
        "src.application.use_cases.process_follow_up_reminders.MetaWhatsAppClient.send_template",
        _stub_send_template,
    )

    nv = datetime(2030, 6, 20, 9, 0, tzinfo=timezone.utc)
    patched_db.follow_up_reminders.insert_one(
        {
            "reminder_id": "r-fu-1",
            "patient_id": "p-fu",
            "visit_id": "v-fu",
            "note_id": "n-fu",
            "next_visit_at": nv,
            "to_number": "919876543210",
            "preferred_language": "en",
            "follow_up_text": "Bring prior labs",
            "remind_3d_sent_at": None,
            "remind_24h_sent_at": None,
            "created_at": nv - timedelta(days=10),
            "updated_at": nv - timedelta(days=10),
        }
    )

    fixed_now = datetime(2030, 6, 18, 10, 0, tzinfo=timezone.utc)
    orig_execute = ProcessFollowUpRemindersUseCase.execute

    def _execute_with_fixed_now(self, *, db, now=None):
        return orig_execute(self, db=db, now=fixed_now)

    monkeypatch.setattr(ProcessFollowUpRemindersUseCase, "execute", _execute_with_fixed_now)

    response = app_client.post("/workflow/follow-up-reminders/run")
    assert response.status_code == 200
    body = response.json()
    assert body["sent_3d"] == 1
    assert body["sent_24h"] == 0
    assert len(sent) == 1
    assert sent[0]["template_name"] == "opening_msg"
    assert sent[0]["to"] == "919876543210"

    updated = patched_db.follow_up_reminders.find_one({"reminder_id": "r-fu-1"})
    assert updated.get("remind_3d_sent_at") is not None


def test_follow_up_reminders_run_sends_day_before_reminder(app_client, patched_db, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second template fires once we are on the calendar day before next_visit_at (same 09:00 UTC anchor)."""
    settings = config_module.get_settings()
    settings.whatsapp_access_token = "test-token"
    settings.whatsapp_phone_number_id = "test-phone-id"
    settings.whatsapp_intake_template_name = "opening_msg"
    settings.whatsapp_followup_template_name = ""
    monkeypatch.setattr("src.core.config.get_settings", lambda: settings)

    sent: list[dict] = []

    def _stub_send_template(_self, *, to_number: str, template_name: str, language_code: str, body_values=None) -> None:
        sent.append(
            {"to": to_number, "template_name": template_name, "language_code": language_code, "body_values": body_values}
        )

    monkeypatch.setattr(
        "src.application.use_cases.process_follow_up_reminders.MetaWhatsAppClient.send_template",
        _stub_send_template,
    )

    nv = datetime(2030, 6, 20, 9, 0, tzinfo=timezone.utc)
    patched_db.follow_up_reminders.insert_one(
        {
            "reminder_id": "r-fu-2",
            "patient_id": "p-fu-2",
            "visit_id": "v-fu-2",
            "note_id": "n-fu-2",
            "next_visit_at": nv,
            "to_number": "919876543210",
            "preferred_language": "en",
            "follow_up_text": "Bring BP log",
            "remind_3d_sent_at": datetime(2030, 6, 17, 9, 0, tzinfo=timezone.utc),
            "remind_24h_sent_at": None,
            "created_at": nv - timedelta(days=10),
            "updated_at": nv - timedelta(days=10),
        }
    )

    fixed_now = datetime(2030, 6, 19, 10, 0, tzinfo=timezone.utc)
    orig_execute = ProcessFollowUpRemindersUseCase.execute

    def _execute_with_fixed_now(self, *, db, now=None):
        return orig_execute(self, db=db, now=fixed_now)

    monkeypatch.setattr(ProcessFollowUpRemindersUseCase, "execute", _execute_with_fixed_now)

    response = app_client.post("/workflow/follow-up-reminders/run")
    assert response.status_code == 200
    body = response.json()
    assert body["sent_3d"] == 0
    assert body["sent_24h"] == 1
    assert len(sent) == 1
    assert "tomorrow" in (sent[0]["body_values"] or [""])[0].lower()

    updated = patched_db.follow_up_reminders.find_one({"reminder_id": "r-fu-2"})
    assert updated.get("remind_24h_sent_at") is not None


def test_follow_up_reminders_run_fetches_patient_phone_when_to_number_missing(
    app_client, patched_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = config_module.get_settings()
    settings.whatsapp_access_token = "test-token"
    settings.whatsapp_phone_number_id = "test-phone-id"
    settings.whatsapp_intake_template_name = "opening_msg"
    settings.whatsapp_followup_template_name = ""
    monkeypatch.setattr("src.core.config.get_settings", lambda: settings)

    sent: list[dict] = []

    def _stub_send_template(_self, *, to_number: str, template_name: str, language_code: str, body_values=None) -> None:
        sent.append(
            {"to": to_number, "template_name": template_name, "language_code": language_code, "body_values": body_values}
        )

    monkeypatch.setattr(
        "src.application.use_cases.process_follow_up_reminders.MetaWhatsAppClient.send_template",
        _stub_send_template,
    )

    patched_db.patients.insert_one(
        {
            "patient_id": "p-fu-phone",
            "name": "Rahul",
            "phone_number": "+91 98765 43210",
        }
    )
    nv = datetime(2030, 6, 20, 9, 0, tzinfo=timezone.utc)
    patched_db.follow_up_reminders.insert_one(
        {
            "reminder_id": "r-fu-phone",
            "patient_id": "p-fu-phone",
            "visit_id": "v-fu-phone",
            "note_id": "n-fu-phone",
            "next_visit_at": nv,
            "to_number": "",
            "preferred_language": "en",
            "follow_up_text": "Bring inhaler",
            "remind_3d_sent_at": None,
            "remind_24h_sent_at": None,
            "created_at": nv - timedelta(days=10),
            "updated_at": nv - timedelta(days=10),
        }
    )

    fixed_now = datetime(2030, 6, 18, 10, 0, tzinfo=timezone.utc)
    orig_execute = ProcessFollowUpRemindersUseCase.execute

    def _execute_with_fixed_now(self, *, db, now=None):
        return orig_execute(self, db=db, now=fixed_now)

    monkeypatch.setattr(ProcessFollowUpRemindersUseCase, "execute", _execute_with_fixed_now)

    response = app_client.post("/workflow/follow-up-reminders/run")
    assert response.status_code == 200
    body = response.json()
    assert body["sent_3d"] == 1
    assert len(sent) == 1
    assert sent[0]["to"] == "919876543210"
    updated = patched_db.follow_up_reminders.find_one({"reminder_id": "r-fu-phone"})
    assert updated.get("to_number") == "919876543210"


def test_follow_up_reminders_run_requires_cron_secret_when_configured(
    app_client, patched_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = config_module.get_settings()
    settings.follow_up_reminder_cron_secret = "expected-secret"
    monkeypatch.setattr("src.core.config.get_settings", lambda: settings)
    bad = app_client.post("/workflow/follow-up-reminders/run", headers={"X-Cron-Secret": "wrong"})
    assert bad.status_code == 401
    ok = app_client.post("/workflow/follow-up-reminders/run", headers={"X-Cron-Secret": "expected-secret"})
    assert ok.status_code == 200


def test_post_visit_summary_uses_request_language_override(app_client, fake_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_post_visit_summary_whatsapp",
        lambda **_: None,
    )
    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_immediate_follow_up_template_whatsapp",
        lambda **_: None,
    )
    _insert_note_context(fake_db, patient_id="p-note-4", job_id="job-note-4")
    captured: dict = {}

    def _fake_generate(self, context, language_name):
        captured["language_name"] = language_name
        return {
            "visit_reason": "Reason",
            "what_doctor_found": "Finding",
            "medicines_to_take": [],
            "tests_recommended": [],
            "self_care": [],
            "warning_signs": [],
            "follow_up": "7 days",
            "next_visit_date": None,
        }

    monkeypatch.setattr("src.adapters.external.ai.openai_client.OpenAIQuestionClient.generate_post_visit_summary", _fake_generate)
    response = app_client.post(
        "/notes/post-visit-summary",
        json={
            "patient_id": "p-note-4",
            "visit_id": "v1",
            "transcription_job_id": "job-note-4",
            "preferred_language": "hi",
        },
    )
    assert response.status_code == 200
    assert captured["language_name"] == "Hindi"


def test_post_visit_summary_prefers_india_note_without_transcript(app_client, fake_db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_post_visit_summary_whatsapp",
        lambda **_: None,
    )
    monkeypatch.setattr(
        "src.application.use_cases.generate_post_visit_summary.send_immediate_follow_up_template_whatsapp",
        lambda **_: None,
    )
    fake_db.patients.insert_one(
        {
            "patient_id": "p-note-5",
            "name": "Asha",
            "age": 31,
            "gender": "female",
            "preferred_language": "en",
        }
    )
    fake_db.clinical_notes.insert_one(
        {
            "note_id": "n-india-2",
            "patient_id": "p-note-5",
            "visit_id": "v5",
            "note_type": "india_clinical",
            "source_job_id": "job-note-5",
            "status": "generated",
            "version": 1,
            "created_at": datetime.now(timezone.utc),
            "payload": {
                "assessment": "Likely gastritis.",
                "plan": "Dietary care and medicines.",
                "rx": [{"medicine_name": "Pantoprazole", "dose": "40 mg", "frequency": "OD", "duration": "5 days", "route": "oral", "food_instruction": "before food"}],
                "investigations": [],
                "red_flags": ["Vomiting blood"],
                "follow_up_in": "5 days",
                "follow_up_date": None,
                "doctor_notes": None,
                "chief_complaint": "Acidity",
                "data_gaps": [],
            },
        }
    )
    monkeypatch.setattr(
        "src.adapters.external.ai.openai_client.OpenAIQuestionClient.generate_post_visit_summary",
        lambda self, context, language_name: {
            "visit_reason": "Acidity",
            "what_doctor_found": "Stomach irritation signs.",
            "medicines_to_take": ["Pantoprazole 40 mg before food"],
            "tests_recommended": [],
            "self_care": ["Avoid spicy food"],
            "warning_signs": ["Blood in vomit"],
            "follow_up": "Review in 5 days",
        },
    )
    response = app_client.post(
        "/notes/post-visit-summary",
        json={"patient_id": "p-note-5", "visit_id": "v5"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_job_id"] == "job-note-5"
