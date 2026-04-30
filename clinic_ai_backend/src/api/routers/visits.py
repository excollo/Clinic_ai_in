"""Visit routes module."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.adapters.db.mongo.client import get_database
from src.api.schemas.patient import ScheduleVisitIntakeRequest, ScheduleVisitIntakeResponse
from src.application.services.intake_chat_service import IntakeChatService
from src.application.utils.patient_id_crypto import encode_patient_id, resolve_internal_patient_id
router = APIRouter(prefix="/api/visits", tags=["Visits"])

LOCKED_VISIT_STATUSES = {"completed", "closed", "ended", "cancelled"}
QUEUEABLE_VISIT_STATUSES = {"open", "scheduled", "queued", "in_queue"}
STARTABLE_VISIT_STATUSES = {"open", "scheduled", "queued", "in_queue"}


class VisitStatusUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=50)


def _find_visit(db, visit_id: str) -> dict | None:
    return db.visits.find_one({"visit_id": visit_id}) or db.visits.find_one({"id": visit_id})


def _visit_update_query(visit: dict, visit_id: str) -> dict:
    resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or visit_id)
    return {"visit_id": resolved_visit_id} if visit.get("visit_id") else {"id": resolved_visit_id}


def _normalize_visit_status(visit: dict) -> str:
    return str(visit.get("status") or "open").strip().lower()


def _serialize_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _public_visit_payload(visit: dict) -> dict:
    resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or "")
    patient_id = str(visit.get("patient_id") or "")
    return {
        "visit_id": resolved_visit_id,
        "id": resolved_visit_id,
        "patient_id": encode_patient_id(patient_id) if patient_id else "",
        "status": str(visit.get("status") or "open"),
        "scheduled_start": visit.get("scheduled_start"),
        "actual_start": _serialize_datetime(visit.get("actual_start")),
        "actual_end": _serialize_datetime(visit.get("actual_end")),
        "updated_at": _serialize_datetime(visit.get("updated_at")),
    }


def _extract_chief_complaint(db, patient_id: str, visit_id: str) -> str | None:
    previsit = db.pre_visit_summaries.find_one(
        {"patient_id": patient_id, "visit_id": visit_id},
        sort=[("updated_at", -1)],
    ) or {}
    sections = previsit.get("sections") or {}
    chief = (sections.get("chief_complaint") or {}).get("reason_for_visit")
    if chief:
        return str(chief)

    intake = db.intake_sessions.find_one(
        {"patient_id": patient_id, "visit_id": visit_id},
        sort=[("updated_at", -1)],
    ) or {}
    illness = intake.get("illness")
    if illness:
        return str(illness)
    for answer in intake.get("answers", []):
        if str(answer.get("question", "")).lower() == "illness" and answer.get("answer"):
            return str(answer.get("answer"))
    return None


def _appointment_time_valid(value: str) -> bool:
    parts = (value or "").strip().split(":")
    if len(parts) != 2:
        return False
    hour, minute = parts[0], parts[1]
    if len(hour) != 2 or len(minute) != 2 or not hour.isdigit() or not minute.isdigit():
        return False
    return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59


def _intake_send_allowed(db, visit_id: str) -> tuple[bool, bool]:
    """Return (allow_whatsapp_intake, skipped_due_to_existing_session)."""
    session = db.intake_sessions.find_one({"visit_id": visit_id}, sort=[("updated_at", -1)])
    if not session:
        return True, False
    status = str(session.get("status") or "")
    if status == "stopped":
        return True, False
    return False, True


def _set_visit_status(db, visit_id: str, status: str) -> dict:
    visit = _find_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    normalized_status = status.strip().lower()
    current_status = _normalize_visit_status(visit)
    if current_status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled visits cannot be updated")
    if current_status in LOCKED_VISIT_STATUSES - {"cancelled"} and normalized_status != current_status:
        raise HTTPException(status_code=409, detail="Completed visits cannot be updated")

    updates: dict = {"status": normalized_status, "updated_at": datetime.now(timezone.utc)}
    now = datetime.now(timezone.utc)
    if normalized_status in {"queued", "in_queue"}:
        if current_status in LOCKED_VISIT_STATUSES:
            raise HTTPException(status_code=409, detail="Completed/cancelled visits cannot enter queue")
        updates["status"] = "in_queue"
    elif normalized_status == "in_progress":
        if current_status not in STARTABLE_VISIT_STATUSES:
            raise HTTPException(status_code=409, detail="Visit cannot be started from its current status")
        updates["actual_start"] = visit.get("actual_start") or now
        updates["actual_end"] = None
    elif normalized_status == "completed":
        if current_status == "cancelled":
            raise HTTPException(status_code=409, detail="Cancelled visits cannot be completed")
        updates["actual_start"] = visit.get("actual_start") or now
        updates["actual_end"] = now
    elif normalized_status == "open":
        updates["actual_end"] = None
    elif normalized_status == "cancelled":
        raise HTTPException(status_code=400, detail="Use the cancel endpoint to cancel a visit")

    update_query = _visit_update_query(visit, visit_id)
    db.visits.update_one(update_query, {"$set": updates})
    refreshed = _find_visit(db, str(visit.get("visit_id") or visit.get("id") or visit_id)) or {}
    return _public_visit_payload(refreshed)


@router.post("/{visit_id}/schedule-intake", response_model=ScheduleVisitIntakeResponse)
def schedule_visit_and_send_intake(visit_id: str, payload: ScheduleVisitIntakeRequest) -> ScheduleVisitIntakeResponse:
    """Attach appointment time to a visit and start WhatsApp intake when appropriate."""
    if not _appointment_time_valid(payload.appointment_time):
        raise HTTPException(status_code=422, detail="appointment_time must be HH:MM in 24-hour format")

    try:
        chosen = datetime.strptime(payload.appointment_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="appointment_date must be YYYY-MM-DD") from exc

    today = datetime.now(timezone.utc).date()
    if chosen < today or chosen > today + timedelta(days=7):
        raise HTTPException(
            status_code=422,
            detail="appointment_date must be between today and the next 7 days",
        )

    scheduled_start = f"{payload.appointment_date}T{payload.appointment_time}:00"
    db = get_database()
    # Avoid Mongo $or here so in-memory test doubles can match visits.
    visit = _find_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or visit_id)
    internal_patient_id = str(visit.get("patient_id") or "")
    if not internal_patient_id:
        raise HTTPException(status_code=422, detail="Visit has no patient_id")
    visit_status = _normalize_visit_status(visit)
    if visit_status in LOCKED_VISIT_STATUSES:
        raise HTTPException(status_code=409, detail="Completed/cancelled visits cannot be rescheduled")

    now = datetime.now(timezone.utc)
    update_query = _visit_update_query(visit, resolved_visit_id)
    db.visits.update_one(
        update_query,
        {"$set": {"scheduled_start": scheduled_start, "status": "scheduled", "updated_at": now}},
    )

    patient = db.patients.find_one({"patient_id": internal_patient_id}) or {}
    phone_number = str(patient.get("phone_number") or "").strip()
    allow_intake, skipped = _intake_send_allowed(db, resolved_visit_id)
    whatsapp_triggered = False
    if allow_intake and phone_number:
        try:
            IntakeChatService().start_intake(
                patient_id=internal_patient_id,
                visit_id=resolved_visit_id,
                to_number=phone_number,
                language=str(patient.get("preferred_language") or "en"),
            )
            whatsapp_triggered = True
        except Exception:
            whatsapp_triggered = False

    return ScheduleVisitIntakeResponse(
        visit_id=resolved_visit_id,
        patient_id=encode_patient_id(internal_patient_id),
        scheduled_start=scheduled_start,
        whatsapp_triggered=whatsapp_triggered,
        intake_skipped_existing_session=skipped,
    )


@router.get("/provider/{provider_id}/upcoming")
def list_provider_upcoming_visits(provider_id: str) -> dict:
    """Return provider visits from Mongo for dashboard/calendar."""
    db = get_database()
    # Keep this endpoint fast: don't return the full visit history.
    # Without a limit/projection, the backend can hang on Render and the frontend shows "Failed to load visits".
    UPCOMING_LIMIT = 200
    records = list(
        db.visits.find(
            {
                "status": {"$nin": list(LOCKED_VISIT_STATUSES)},
                "$or": [
                    {"provider_id": provider_id},
                    {"provider_id": ""},
                    {"provider_id": None},
                    {"provider_id": {"$exists": False}},
                ],
                # Queue/board UI only cares about items with an appointment time fixed.
                "scheduled_start": {"$exists": True, "$ne": None, "$ne": ""},
            },
            {
                "_id": 0,
                "patient_id": 1,
                "visit_id": 1,
                "id": 1,
                "scheduled_start": 1,
                "visit_type": 1,
                "status": 1,
                "chief_complaint": 1,
            },
        )
        .sort("scheduled_start", 1)
        .limit(UPCOMING_LIMIT)
    )

    patient_ids = sorted({str(visit.get("patient_id") or "").strip() for visit in records if str(visit.get("patient_id") or "").strip()})
    visit_ids = sorted(
        {
            str(visit.get("visit_id") or visit.get("id") or "").strip()
            for visit in records
            if str(visit.get("visit_id") or visit.get("id") or "").strip()
        }
    )
    patient_map: dict[str, dict] = {}
    if patient_ids:
        for patient in db.patients.find({"patient_id": {"$in": patient_ids}}, {"_id": 0}):
            pid = str(patient.get("patient_id") or "").strip()
            if pid:
                patient_map[pid] = patient
    previsit_reason_by_visit: dict[str, str] = {}
    if visit_ids:
        for item in db.pre_visit_summaries.find(
            {"visit_id": {"$in": visit_ids}},
            {"_id": 0, "visit_id": 1, "sections.chief_complaint.reason_for_visit": 1, "updated_at": 1},
        ).sort("updated_at", -1):
            vid = str(item.get("visit_id") or "").strip()
            if not vid or vid in previsit_reason_by_visit:
                continue
            sections = item.get("sections") or {}
            chief = (sections.get("chief_complaint") or {}).get("reason_for_visit")
            if chief:
                previsit_reason_by_visit[vid] = str(chief)
    intake_reason_by_visit: dict[str, str] = {}
    if visit_ids:
        for item in db.intake_sessions.find(
            {"visit_id": {"$in": visit_ids}},
            {"_id": 0, "visit_id": 1, "illness": 1, "answers": 1, "updated_at": 1},
        ).sort("updated_at", -1):
            vid = str(item.get("visit_id") or "").strip()
            if not vid or vid in intake_reason_by_visit:
                continue
            illness = item.get("illness")
            if illness:
                intake_reason_by_visit[vid] = str(illness)
                continue
            for answer in item.get("answers", []):
                if str(answer.get("question", "")).lower() == "illness" and answer.get("answer"):
                    intake_reason_by_visit[vid] = str(answer.get("answer"))
                    break

    appointments: list[dict] = []
    for visit in records:
        patient_id = str(visit.get("patient_id") or "")
        resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or "")
        if not resolved_visit_id:
            continue
        patient = patient_map.get(patient_id, {})
        patient_name = (patient.get("name") or "").strip() or "Unknown Patient"
        scheduled_start = visit.get("scheduled_start")
        chief_complaint = (
            visit.get("chief_complaint")
            or previsit_reason_by_visit.get(resolved_visit_id)
            or intake_reason_by_visit.get(resolved_visit_id)
        )
        appointments.append(
            {
                "appointment_id": resolved_visit_id,
                "patient_id": encode_patient_id(patient_id) if patient_id else "",
                "patient_name": patient_name,
                "scheduled_start": scheduled_start,
                "chief_complaint": chief_complaint or "Visit",
                "appointment_type": visit.get("visit_type") or "visit",
                "previsit_completed": False,
                "visit_id": resolved_visit_id,
                "status": str(visit.get("status") or "open"),
            }
        )

    return {"appointments": appointments}


@router.get("/provider/{provider_id}")
def list_provider_visits(
    provider_id: str,
    status_filter: str | None = Query(default=None, description="Filter by visit status (scheduled, in_progress, completed, etc)"),
) -> list[dict]:
    """Return provider visits for Visits workspace list."""
    db = get_database()
    VISITS_LIMIT = 200
    query: dict = {
        "$or": [
            {"provider_id": provider_id},
            {"provider_id": ""},
            {"provider_id": None},
            {"provider_id": {"$exists": False}},
        ],
    }
    if status_filter:
        query["status"] = status_filter

    records = list(
        db.visits.find(
            query,
            {
                "_id": 0,
                "visit_id": 1,
                "id": 1,
                "patient_id": 1,
                "visit_type": 1,
                "status": 1,
                "scheduled_start": 1,
                "actual_start": 1,
                "actual_end": 1,
                "chief_complaint": 1,
                "created_at": 1,
            },
        )
        .sort("created_at", -1)
        .limit(VISITS_LIMIT)
    )
    patient_ids = sorted({str(visit.get("patient_id") or "").strip() for visit in records if str(visit.get("patient_id") or "").strip()})
    patient_map: dict[str, dict] = {}
    if patient_ids:
        for patient in db.patients.find({"patient_id": {"$in": patient_ids}}, {"_id": 0}):
            pid = str(patient.get("patient_id") or "").strip()
            if pid:
                patient_map[pid] = patient

    out: list[dict] = []
    for visit in records:
        resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or "")
        if not resolved_visit_id:
            continue
        internal_patient_id = str(visit.get("patient_id") or "")
        patient = patient_map.get(internal_patient_id, {})
        patient_name = str(patient.get("name") or "").strip() or "Unknown patient"
        patient_phone_number = str(patient.get("phone_number") or "").strip()
        scheduled_start = visit.get("scheduled_start")
        actual_start = visit.get("actual_start")
        actual_end = visit.get("actual_end")
        duration_minutes = None
        try:
            if isinstance(actual_start, datetime) and isinstance(actual_end, datetime):
                duration_minutes = int((actual_end - actual_start).total_seconds() / 60)
            elif isinstance(actual_start, str) and isinstance(actual_end, str):
                start_dt = datetime.fromisoformat(actual_start.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(actual_end.replace("Z", "+00:00"))
                duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
        except Exception:
            duration_minutes = None

        out.append(
            {
                "id": resolved_visit_id,
                "visit_id": resolved_visit_id,
                "patient_id": encode_patient_id(internal_patient_id) if internal_patient_id else "",
                "patient_name": patient_name,
                "mobile_number": patient_phone_number or None,
                "visit_type": (
                    "Visit"
                    if str(visit.get("visit_type") or "").strip().lower() in {"", "string"}
                    else str(visit.get("visit_type"))
                ),
                "status": str(visit.get("status") or "open"),
                "scheduled_start": scheduled_start,
                "actual_start": actual_start,
                "actual_end": actual_end,
                "duration_minutes": duration_minutes,
                "chief_complaint": visit.get("chief_complaint") or None,
                "created_at": visit.get("created_at") or "",
            }
        )

    return out


@router.get("/patient/{patient_id}")
def list_patient_visits(
    patient_id: str,
    status_filter: str | None = Query(default=None, description="Filter by visit status"),
) -> list[dict]:
    """Return visits for a single patient, resolving encrypted patient ids."""
    db = get_database()
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    query: dict = {"patient_id": internal_patient_id}
    if status_filter:
        query["status"] = status_filter

    records = list(db.visits.find(query, {"_id": 0}).sort("created_at", -1))
    out: list[dict] = []
    for visit in records:
        resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or "").strip()
        if not resolved_visit_id:
            continue
        out.append(
            {
                "id": resolved_visit_id,
                "visit_id": resolved_visit_id,
                "patient_id": encode_patient_id(internal_patient_id) if internal_patient_id else "",
                "status": str(visit.get("status") or "open"),
                "scheduled_start": visit.get("scheduled_start"),
                "created_at": visit.get("created_at") or "",
                "updated_at": visit.get("updated_at") or "",
            }
        )

    return out


@router.get("/{visit_id}")
def get_visit(visit_id: str) -> dict:
    """Return visit details for visit workflow page."""
    db = get_database()
    visit = _find_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or visit_id)
    patient_id = str(visit.get("patient_id") or "")
    patient = db.patients.find_one({"patient_id": patient_id}, {"_id": 0}) or {}
    full_name = (patient.get("name") or "").strip()
    name_parts = [part for part in full_name.split(" ") if part]
    first_name = name_parts[0] if name_parts else "Patient"
    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
    age = patient.get("age")
    year = datetime.now(timezone.utc).year - age if isinstance(age, int) and age > 0 else 1970

    resolved_chief_complaint = visit.get("chief_complaint") or _extract_chief_complaint(db, patient_id, resolved_visit_id)
    return {
        "id": resolved_visit_id,
        "patient_id": encode_patient_id(patient_id) if patient_id else "",
        "provider_id": str(visit.get("provider_id") or ""),
        "appointment_id": visit.get("appointment_id"),
        "visit_type": str(visit.get("visit_type") or "Visit"),
        "status": str(visit.get("status") or "open"),
        "chief_complaint": resolved_chief_complaint,
        "reason_for_visit": visit.get("reason_for_visit"),
        "scheduled_start": visit.get("scheduled_start"),
        "actual_start": _serialize_datetime(visit.get("actual_start")),
        "actual_end": _serialize_datetime(visit.get("actual_end")),
        "subjective": visit.get("subjective"),
        "objective": visit.get("objective"),
        "assessment": visit.get("assessment"),
        "plan": visit.get("plan"),
        "patient": {
            "id": encode_patient_id(patient_id) if patient_id else "",
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": str(patient.get("date_of_birth") or f"{year:04d}-01-01"),
            "gender": str(patient.get("gender") or "unknown"),
            "phone_number": patient.get("phone_number"),
        },
    }


@router.get("/{visit_id}/intake-session")
def get_visit_intake_session(visit_id: str) -> dict:
    """Return latest intake session question/answer history for a visit."""
    db = get_database()
    visit = _find_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    resolved_visit_id = str(visit.get("visit_id") or visit.get("id") or visit_id)
    intake = db.intake_sessions.find_one(
        {"visit_id": resolved_visit_id},
        sort=[("updated_at", -1)],
    )
    if not intake:
        return {
            "visit_id": resolved_visit_id,
            "status": "not_started",
            "question_answers": [],
            "illness": None,
            "updated_at": None,
        }

    normalized_answers: list[dict] = []
    for item in intake.get("answers", []):
        normalized_answers.append(
            {
                "question": str(item.get("question") or "").strip(),
                "answer": str(item.get("answer") or "").strip(),
                "topic": str(item.get("topic") or "").strip() or None,
                "asked_at": item.get("asked_at"),
                "answered_at": item.get("answered_at"),
            }
        )

    patient_id = str(intake.get("patient_id") or visit.get("patient_id") or "")
    return {
        "visit_id": resolved_visit_id,
        "patient_id": encode_patient_id(patient_id) if patient_id else "",
        "status": str(intake.get("status") or "in_progress"),
        "illness": intake.get("illness"),
        "question_answers": normalized_answers,
        "updated_at": intake.get("updated_at"),
        "created_at": intake.get("created_at"),
    }


@router.patch("/{visit_id}/status")
def update_visit_status(visit_id: str, payload: VisitStatusUpdateRequest) -> dict:
    db = get_database()
    return _set_visit_status(db, visit_id, payload.status)


@router.post("/{visit_id}/queue")
def queue_visit(visit_id: str) -> dict:
    db = get_database()
    return _set_visit_status(db, visit_id, "in_queue")


@router.post("/{visit_id}/start")
def start_visit_consultation(visit_id: str) -> dict:
    db = get_database()
    return _set_visit_status(db, visit_id, "in_progress")


@router.post("/{visit_id}/complete")
def complete_visit(visit_id: str) -> dict:
    db = get_database()
    return _set_visit_status(db, visit_id, "completed")


@router.post("/{visit_id}/no-show")
def mark_visit_no_show(visit_id: str) -> dict:
    db = get_database()
    return _set_visit_status(db, visit_id, "no_show")


@router.delete("/{visit_id}")
def cancel_visit(visit_id: str) -> dict:
    db = get_database()
    visit = _find_visit(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    current_status = _normalize_visit_status(visit)
    if current_status in {"completed", "closed", "ended"}:
        raise HTTPException(status_code=409, detail="Completed visits cannot be cancelled")
    if current_status == "cancelled":
        return _public_visit_payload(visit)

    db.visits.update_one(
        _visit_update_query(visit, visit_id),
        {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}},
    )
    refreshed = _find_visit(db, str(visit.get("visit_id") or visit.get("id") or visit_id)) or {}
    return _public_visit_payload(refreshed)
