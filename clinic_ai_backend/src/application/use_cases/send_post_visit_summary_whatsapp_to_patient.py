"""Doctor-triggered WhatsApp: latest stored post-visit summary + immediate follow-up Meta template."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.repositories.clinical_note_repository import ClinicalNoteRepository
from src.application.services.post_visit_whatsapp import (
    send_immediate_follow_up_template_whatsapp,
    send_post_visit_summary_whatsapp,
)
from src.application.use_cases.generate_post_visit_summary import GeneratePostVisitSummaryUseCase


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def send_latest_post_visit_summary_whatsapp_to_patient(
    *,
    patient_id: str,
    visit_id: str,
    phone_number_override: str | None = None,
) -> dict[str, Any]:
    """
    Load the latest persisted post-visit summary for this visit and send:
    1) Post-visit summary template (WHATSAPP_POST_VISIT_TEMPLATE_NAME or intake fallback)
    2) Immediate follow-up Meta template (same channel as cron follow-up reminders)

    Optional ``phone_number_override`` uses that number for this send only (not persisted).
    """
    db = get_database()
    patient = dict(db.patients.find_one({"patient_id": patient_id}) or {})
    if not patient.get("patient_id"):
        raise ValueError("Patient not found")

    if phone_number_override and str(phone_number_override).strip():
        patient = {**patient, "phone_number": str(phone_number_override).strip()}

    raw_phone = str(patient.get("phone_number") or "").strip()
    if not raw_phone:
        raise ValueError(
            "Patient has no phone number on file; register a WhatsApp number or pass phone_number in the request body"
        )

    note = ClinicalNoteRepository().find_latest(
        patient_id=patient_id,
        visit_id=visit_id,
        note_type="post_visit_summary",
    )
    if not note:
        raise ValueError("No post_visit_summary note found for this visit")

    payload = dict(note.get("payload") or {})
    whatsapp_payload = str(note.get("whatsapp_payload") or "").strip()
    if not whatsapp_payload:
        whatsapp_payload = GeneratePostVisitSummaryUseCase._build_whatsapp_payload(payload=payload)

    resolved_language = GeneratePostVisitSummaryUseCase._resolve_language(
        patient_preferred_language=patient.get("preferred_language"),
        request_language=None,
    )
    if not resolved_language:
        resolved_language = "en"

    summary_sent = send_post_visit_summary_whatsapp(patient=patient, whatsapp_payload=whatsapp_payload)
    follow_up_sent = False
    # Enforce order: follow-up template is allowed only after summary send succeeds.
    if summary_sent:
        follow_up_sent = send_immediate_follow_up_template_whatsapp(
            patient=patient,
            payload=payload,
            preferred_language=resolved_language,
        )

    if follow_up_sent:
        db.follow_up_reminders.update_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            {"$set": {"remind_immediate_sent_at": _utc_now()}},
        )

    if summary_sent and follow_up_sent:
        message = "Post-visit summary and follow-up template sent on WhatsApp."
    elif summary_sent:
        message = "Post-visit summary template sent; follow-up template was not sent (check follow-up template config or Meta logs)."
    elif follow_up_sent:
        message = "Follow-up template sent after summary."
    else:
        if summary_sent:
            message = (
                "Post-visit summary was sent, but follow-up template was not sent "
                "(check follow-up template config or Meta logs)."
            )
        else:
            message = (
                "No WhatsApp messages were delivered. Post-visit summary template failed, "
                "so follow-up was not attempted. Check Meta credentials (WHATSAPP_ACCESS_TOKEN, "
                "WHATSAPP_PHONE_NUMBER_ID), WHATSAPP_POST_VISIT_TEMPLATE_NAME, and recipient number."
            )

    return {
        "patient_id": patient_id,
        "visit_id": visit_id,
        "summary_template_sent": summary_sent,
        "follow_up_template_sent": follow_up_sent,
        "message": message,
    }
