"""Patient web chat API schemas."""
from pydantic import BaseModel, Field


class StartPatientChatRequest(BaseModel):
    patient_id: str = Field(min_length=1)
    visit_id: str = Field(min_length=1)
    language: str = Field(default="en")


class ReplyPatientChatRequest(BaseModel):
    patient_id: str = Field(min_length=1)
    visit_id: str = Field(min_length=1)
    message_text: str = Field(min_length=1)
    message_id: str | None = None


class PatientChatStateResponse(BaseModel):
    patient_id: str
    visit_id: str
    status: str
    question_number: int
    last_outbound_text: str
    last_outbound_at: str | None = None


class PatientChatLookupByPhoneResponse(PatientChatStateResponse):
    phone_number: str

