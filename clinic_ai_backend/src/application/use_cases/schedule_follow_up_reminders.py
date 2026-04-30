"""Persist WhatsApp follow-up reminder schedule after post-visit summary generation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.application.services.intake_chat_service import IntakeChatService
from src.application.utils.follow_up_dates import parse_next_visit_at

_indexes_ensured = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def schedule_follow_up_after_post_visit(
    *,
    db: Any,
    patient_id: str,
    visit_id: str | None,
    note_id: str,
    payload: dict[str, Any],
    patient: dict[str, Any],
    preferred_language: str,
) -> None:
    """
    If the post-visit payload includes a parseable next visit instant, upsert a reminder row.

    A cron job calls ``ProcessFollowUpRemindersUseCase`` to send Meta template messages at T-3d and on the calendar day before the visit.
    """
    if not visit_id:
        return
    global _indexes_ensured
    if not _indexes_ensured:
        try:
            db.follow_up_reminders.create_index([("reminder_id", 1)], unique=True)
            db.follow_up_reminders.create_index([("patient_id", 1), ("visit_id", 1)], unique=True)
        except Exception:
            pass
        _indexes_ensured = True
    raw = payload.get("next_visit_date")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return
    next_at = parse_next_visit_at(raw)
    if next_at is None:
        return
    now = _utc_now()
    if next_at <= now:
        return
    phone = str(patient.get("phone_number") or "").strip()
    if not phone:
        return
    to_number = IntakeChatService._normalize_phone_number(phone)
    if not to_number:
        return
    follow_up_text = str(payload.get("follow_up") or "").strip() or "Follow-up visit scheduled."
    existing = db.follow_up_reminders.find_one({"patient_id": patient_id, "visit_id": visit_id})
    reminder_id = str((existing or {}).get("reminder_id") or uuid4())
    created_at = (existing or {}).get("created_at") or now
    doc = {
        "reminder_id": reminder_id,
        "patient_id": patient_id,
        "visit_id": visit_id,
        "note_id": note_id,
        "next_visit_at": next_at,
        "to_number": to_number,
        "preferred_language": preferred_language,
        "follow_up_text": follow_up_text,
        "remind_immediate_sent_at": None,
        "remind_3d_sent_at": None,
        "remind_24h_sent_at": None,
        "created_at": created_at,
        "updated_at": now,
    }
    db.follow_up_reminders.update_one(
        {"patient_id": patient_id, "visit_id": visit_id},
        {"$set": doc},
        upsert=True,
    )
