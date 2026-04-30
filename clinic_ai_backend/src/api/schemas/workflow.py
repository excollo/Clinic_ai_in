"""Workflow API schemas module."""
from __future__ import annotations

from pydantic import BaseModel

from src.api.schemas.vitals import LatestVitalsResponse, VitalsFormResponse

class ChiefComplaintSection(BaseModel):
    """Chief complaint section."""

    reason_for_visit: str
    symptom_duration_or_onset: str


class HPISection(BaseModel):
    """HPI section."""

    associated_symptoms: list[str]
    symptom_severity_or_progression: str
    impact_on_daily_life: str


class CurrentMedicationSection(BaseModel):
    """Current medication and home remedies section."""

    medications_or_home_remedies: str


class PastHistoryAllergiesSection(BaseModel):
    """Past medical history and allergies section."""

    past_medical_history: str
    allergies: str


class PreVisitSections(BaseModel):
    """All five pre-visit summary sections."""

    chief_complaint: ChiefComplaintSection
    hpi: HPISection
    current_medication: CurrentMedicationSection
    past_medical_history_allergies: PastHistoryAllergiesSection
    red_flag_indicators: list[str]


class PreVisitSummaryResponse(BaseModel):
    """Pre-visit summary response payload."""

    patient_id: str
    visit_id: str | None = None
    intake_session_id: str
    language: str
    status: str
    sections: PreVisitSections


class FollowUpRemindersRunResponse(BaseModel):
    """Result of processing scheduled follow-up WhatsApp reminders."""

    sent_immediate: int = 0
    sent_3d: int
    sent_24h: int
    skipped: int
    debug: dict[str, int] | None = None
    last_error: str | None = None


class DoctorAppointmentViewResponse(BaseModel):
    """Doctor view with summary and vitals context."""

    patient_id: str
    visit_id: str
    pre_visit_summary: PreVisitSummaryResponse | None
    latest_vitals_form: VitalsFormResponse | None
    latest_vitals: LatestVitalsResponse | None
