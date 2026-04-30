"""Patient API schemas module."""
from pydantic import BaseModel, Field
from pydantic import field_validator

from src.core.language_support import intake_language_validation_message
from src.core.language_support import is_supported_intake_language
from src.core.language_support import normalize_intake_language


class PatientRegisterRequest(BaseModel):
    """Request body for staff-driven patient registration."""

    name: str = Field(min_length=1, max_length=120)
    phone_number: str = Field(min_length=8, max_length=20)
    age: int = Field(ge=0, le=130)
    gender: str = Field(min_length=1, max_length=20)
    preferred_language: str = Field(default="en")
    travelled_recently: bool = Field(default=False)
    consent: bool = Field(default=True)
    # Optional appointment-style fields from registration UI
    workflow_type: str | None = None
    country: str | None = None
    emergency_contact: str | None = None
    address: str | None = None
    appointment_date: str | None = None
    appointment_time: str | None = None
    visit_type: str | None = None

    @field_validator("preferred_language")
    @classmethod
    def validate_preferred_language(cls, value: str) -> str:
        """Accept language aliases and normalize to supported app values."""
        raw_value = (value or "").strip()
        if raw_value and not is_supported_intake_language(raw_value):
            raise ValueError(intake_language_validation_message(extra_values=("en_US",)))
        return normalize_intake_language(raw_value)


class PatientRegisterResponse(BaseModel):
    """Response body for registration endpoint."""

    patient_id: str
    visit_id: str
    whatsapp_triggered: bool
    existing_patient: bool = False
    pending_schedule_for_intake: bool = False


class PatientSummaryResponse(BaseModel):
    """Compact patient payload used by provider visit scheduling UI."""

    id: str
    patient_id: str
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: str
    mrn: str
    age: int | None = None
    gender: str | None = None
    phone_number: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CreateVisitFromPatientRequest(BaseModel):
    """Request body for creating a new visit from an existing patient."""

    provider_id: str | None = None
    scheduled_start: str | None = None


class CreateVisitFromPatientResponse(BaseModel):
    """Response body for creating a new visit from patient selection."""

    patient_id: str
    visit_id: str
    status: str
    scheduled_start: str | None = None
    intake_triggered: bool = False
    pending_schedule_for_intake: bool = False


class ScheduleVisitIntakeRequest(BaseModel):
    """Set appointment datetime on a visit and start WhatsApp intake (if eligible)."""

    appointment_date: str = Field(min_length=10, max_length=10)
    appointment_time: str = Field(
        min_length=5,
        max_length=5,
        description="24-hour local time HH:MM (same format as patient registration).",
    )


class ScheduleVisitIntakeResponse(BaseModel):
    """Result of scheduling + optional intake kickoff."""

    visit_id: str
    patient_id: str
    scheduled_start: str
    whatsapp_triggered: bool
    intake_skipped_existing_session: bool = False
