"""Notes API schemas module."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


NoteType = Literal["india_clinical", "soap", "post_visit_summary"]
NoteStatus = Literal["generated", "fallback_generated", "failed"]
InvestigationUrgency = Literal["routine", "urgent", "stat"]


class MedicationItem(BaseModel):
    """Medication line item in India clinical note."""

    medicine_name: str
    dose: str
    frequency: str
    duration: str
    route: str
    food_instruction: str
    generic_available: bool | None = None


class InvestigationItem(BaseModel):
    """Investigation line item in India clinical note."""

    test_name: str
    urgency: InvestigationUrgency
    preparation_instructions: str | None = None
    routing_note: str | None = None


class IndiaClinicalNotePayload(BaseModel):
    """Strict India OPD note output contract."""

    assessment: str = Field(..., description="1-3 sentence clinical assessment in English")
    plan: str = Field(..., description="Brief actionable next steps")
    rx: list[MedicationItem]
    investigations: list[InvestigationItem]
    red_flags: list[str]
    follow_up_in: str | None = Field(default=None, description='Use this OR follow_up_date (e.g. "7 days")')
    follow_up_date: date | None = Field(default=None, description="Use this OR follow_up_in")
    doctor_notes: str | None = None
    chief_complaint: str | None = Field(
        default=None,
        description="Optional input context captured from transcript, not a generated section",
    )
    data_gaps: list[str]

    @model_validator(mode="after")
    def validate_follow_up_exclusivity(self) -> "IndiaClinicalNotePayload":
        """Require exactly one follow-up selector."""
        has_follow_up_in = bool((self.follow_up_in or "").strip())
        has_follow_up_date = self.follow_up_date is not None
        if has_follow_up_in == has_follow_up_date:
            raise ValueError("Use exactly one of follow_up_in or follow_up_date")
        return self


class PostVisitSummaryPayload(BaseModel):
    """Patient-friendly post-visit summary output contract."""

    visit_reason: str
    what_doctor_found: str
    medicines_to_take: list[str]
    tests_recommended: list[str]
    self_care: list[str]
    warning_signs: list[str]
    follow_up: str
    next_visit_date: str | None = Field(default=None, description="ISO YYYY-MM-DD when a return visit was scheduled")


class NoteGenerateRequest(BaseModel):
    """Generate/re-generate note request."""

    patient_id: str
    visit_id: str
    transcription_job_id: str | None = None
    note_type: NoteType | None = None
    preferred_language: str | None = None
    # Optional: staff-confirmed next visit (India note + post-visit scheduling). ISO date only.
    follow_up_date: date | None = Field(
        default=None,
        description="When set, stored on India clinical note as follow_up_date and used for post-visit reminder scheduling.",
    )


class NoteGenerateResponse(BaseModel):
    """Persisted note response payload."""

    note_id: str
    patient_id: str
    visit_id: str | None
    note_type: NoteType
    source_job_id: str | None
    status: NoteStatus
    version: int
    created_at: datetime
    payload: IndiaClinicalNotePayload | PostVisitSummaryPayload
    whatsapp_payload: str | None = None
    legacy: bool = False


class PostVisitWhatsAppSendRequest(BaseModel):
    """Doctor-triggered send of stored post-visit summary to patient WhatsApp."""

    patient_id: str = Field(..., min_length=1)
    visit_id: str = Field(..., min_length=1)
    phone_number: str | None = Field(
        default=None,
        description="Optional WhatsApp destination for this send only; otherwise uses patient.phone_number.",
    )


class PostVisitWhatsAppSendResponse(BaseModel):
    """Outcome of Meta template sends for post-visit + follow-up."""

    patient_id: str
    visit_id: str
    summary_template_sent: bool
    follow_up_template_sent: bool
    message: str


class ClinicalNoteTemplateRequest(BaseModel):
    """Request payload for generating reusable clinical note template."""

    doctor_type: str = Field(..., min_length=1, description="Ayurvedic | Allopathic | Homeopathic")
    language_style: str = Field(..., min_length=1, description="e.g., English clinical, Hinglish OPD")
    region: str = Field(..., min_length=1, description="e.g., India OPD")
    optional_preferences: str | None = Field(default=None, description="Optional custom instructions")
