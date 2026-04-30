"""Workflow routes module."""
from fastapi import APIRouter, Header, HTTPException

from src.adapters.db.mongo.client import get_database
from src.api.schemas.vitals import LatestVitalsResponse, VitalsFormResponse
from src.api.schemas.workflow import (
    DoctorAppointmentViewResponse,
    FollowUpRemindersRunResponse,
    PreVisitSummaryResponse,
)
from src.application.use_cases.generate_pre_visit_summary import GeneratePreVisitSummaryUseCase
from src.application.use_cases.process_follow_up_reminders import ProcessFollowUpRemindersUseCase
from src.application.use_cases.store_vitals import StoreVitalsUseCase
from src.application.utils.patient_id_crypto import encode_patient_id, resolve_internal_patient_id
from src.core.config import get_settings

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])


@router.post("/follow-up-reminders/run", response_model=FollowUpRemindersRunResponse)
def run_follow_up_reminders(x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret")) -> FollowUpRemindersRunResponse:
    """
    Process due follow-up WhatsApp template reminders (3 days and 24 hours before ``next_visit_at``).

    Intended to be called on a schedule (e.g. Render cron every hour). Optionally protect with
    ``FOLLOW_UP_REMINDER_CRON_SECRET`` and header ``X-Cron-Secret``.
    """
    settings = get_settings()
    expected = (settings.follow_up_reminder_cron_secret or "").strip()
    if expected and (x_cron_secret or "").strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Cron-Secret")
    result = ProcessFollowUpRemindersUseCase().execute(db=get_database())
    return FollowUpRemindersRunResponse(**result)


@router.post("/pre-visit-summary/{patient_id}/{visit_id}", response_model=PreVisitSummaryResponse)
def generate_pre_visit_summary(patient_id: str, visit_id: str) -> PreVisitSummaryResponse:
    """Generate pre-visit summary for the intake session tied to this visit."""
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    try:
        doc = GeneratePreVisitSummaryUseCase().execute(patient_id=internal_patient_id, visit_id=visit_id)
        doc["patient_id"] = encode_patient_id(str(doc.get("patient_id") or internal_patient_id))
        return PreVisitSummaryResponse(**doc)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/pre-visit-summary/{patient_id}/{visit_id}", response_model=PreVisitSummaryResponse)
def get_latest_pre_visit_summary(patient_id: str, visit_id: str) -> PreVisitSummaryResponse:
    """Fetch latest pre-visit summary for a specific visit."""
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    db = get_database()
    doc = db.pre_visit_summaries.find_one(
        {"patient_id": internal_patient_id, "visit_id": visit_id},
        sort=[("updated_at", -1)],
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Pre-visit summary not found")
    doc.pop("_id", None)
    doc["patient_id"] = encode_patient_id(str(doc.get("patient_id") or internal_patient_id))
    return PreVisitSummaryResponse(**doc)


@router.get("/doctor-appointment-view/{patient_id}/{visit_id}", response_model=DoctorAppointmentViewResponse)
def get_doctor_appointment_view(patient_id: str, visit_id: str) -> DoctorAppointmentViewResponse:
    """Provide doctor-ready appointment context with summary and vitals."""
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    db = get_database()
    summary_doc = db.pre_visit_summaries.find_one(
        {"patient_id": internal_patient_id, "visit_id": visit_id},
        sort=[("updated_at", -1)],
    )

    summary_obj = None
    if summary_doc:
        summary_doc.pop("_id", None)
        summary_doc["patient_id"] = encode_patient_id(str(summary_doc.get("patient_id") or internal_patient_id))
        summary_obj = PreVisitSummaryResponse(**summary_doc)

    vitals_use_case = StoreVitalsUseCase()
    form_doc = vitals_use_case.get_latest_vitals_form(internal_patient_id, visit_id)
    vitals_doc = vitals_use_case.get_latest_vitals(internal_patient_id, visit_id)

    form_obj = VitalsFormResponse(**form_doc) if form_doc else None
    vitals_obj = LatestVitalsResponse(**vitals_doc) if vitals_doc else None

    return DoctorAppointmentViewResponse(
        patient_id=encode_patient_id(internal_patient_id),
        visit_id=visit_id,
        pre_visit_summary=summary_obj,
        latest_vitals_form=form_obj,
        latest_vitals=vitals_obj,
    )
