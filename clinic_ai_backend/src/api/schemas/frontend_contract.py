from datetime import datetime
import re
from typing import Literal, Optional, List

from pydantic import BaseModel, Field, validator


class LoginRequest(BaseModel):
    mobile: str
    password: str

    @validator("mobile")
    def mobile_must_be_indian(cls, v):
        v = v.replace(" ", "").replace("+91", "").replace("-", "")
        if not re.match(r"^[6-9]\d{9}$", v):
            raise ValueError("Must be a valid Indian mobile number")
        return v


class SignupRequest(BaseModel):
    name: str
    mobile: str
    email: Optional[str] = None
    mci_number: str
    specialty: str
    password: str
    clinic_name: str
    city: str
    pincode: str
    opd_hours: dict
    languages: List[str]
    token_prefix: str = "OPD-"
    abdm_hfr_id: Optional[str] = None
    whatsapp_mode: Literal["platform_default", "own_number"]


class SendOtpRequest(BaseModel):
    mobile: str


class VerifyOtpRequest(BaseModel):
    mobile: str
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    request_id: str


class ForgotPasswordRequest(BaseModel):
    mobile: str
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    request_id: str
    new_password: str = Field(min_length=8)


class ConsentCaptureRequest(BaseModel):
    patient_id: str
    visit_id: str
    doctor_id: str
    language: str
    consent_text_version: str
    patient_confirmed: bool
    timestamp: datetime


class RegisterPatientRequest(BaseModel):
    name: str
    age: int = Field(ge=0, le=120)
    sex: Literal["M", "F", "Other"]
    mobile: str
    language: str
    chief_complaint: str = Field(min_length=1, max_length=200)
    workflow_type: Literal["walk_in", "scheduled"]
    scheduled_date: Optional[str] = None
    scheduled_time: Optional[str] = None
    intake_mode: Optional[Literal["whatsapp", "in_clinic"]] = None


class AbhaLookupRequest(BaseModel):
    abha_id: str


class AbhaLinkRequest(BaseModel):
    patient_id: str
    abha_id: str


class AbhaScanShareRequest(BaseModel):
    abha_qr_data: str


class BloodPressure(BaseModel):
    systolic: int = Field(ge=60, le=250)
    diastolic: int = Field(ge=40, le=150)


class VitalsRequest(BaseModel):
    blood_pressure: BloodPressure
    weight: float = Field(gt=0, le=300)
    dynamic_values: dict = Field(default_factory=dict)


class RxItem(BaseModel):
    name: str
    dose: str
    frequency: str
    duration: str
    food_instruction: str


class InvestigationItem(BaseModel):
    test: str
    urgency: Literal["routine", "urgent", "stat"]
    timing: str


class FollowUp(BaseModel):
    date: Optional[str] = None
    instruction: Optional[str] = None


class IndiaClinicalNoteRequest(BaseModel):
    visit_id: str
    patient_id: str
    transcript_id: Optional[str] = None
    assessment: str = Field(max_length=500)
    plan: str = Field(max_length=800)
    rx: List[RxItem] = Field(default_factory=list)
    investigations: List[InvestigationItem] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    follow_up: FollowUp = Field(default_factory=FollowUp)
    status: Literal["draft", "approved"]


class MedicineSchedule(BaseModel):
    name: str
    dose: str
    morning_time: Optional[str] = None
    afternoon_time: Optional[str] = None
    night_time: Optional[str] = None
    food_instruction: str
    duration_days: int = Field(ge=1, le=365)


class MedicationScheduleRequest(BaseModel):
    medicines: List[MedicineSchedule]


class LabResultRequest(BaseModel):
    file_url: str
    file_type: Literal["pdf", "image"]
    source: Literal["whatsapp", "upload"]


class WhatsAppSendRequest(BaseModel):
    visit_id: str
    patient_id: str
    recipient_mobile: str
    language: str
    message_type: Literal["post_visit_recap", "medication_reminder", "lab_result", "appointment_confirmation"]
    template_variables: dict = Field(default_factory=dict)


class MarkAllReadRequest(BaseModel):
    doctor_id: str


class PostVisitSummaryRequest(BaseModel):
    visit_id: str
    language: str = "en"
