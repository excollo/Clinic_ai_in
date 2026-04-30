"""Template API schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TemplateType = Literal["personal", "practice", "community"]


class TemplateMedication(BaseModel):
    """Medication row for clinical template."""

    medicine_name: str = ""
    dose: str = ""
    frequency: str = ""
    duration: str = ""
    route: str = ""
    food_instruction: str = ""


class TemplateInvestigation(BaseModel):
    """Investigation row for clinical template."""

    test_name: str = ""
    urgency: str = ""
    preparation_instructions: str = ""


class TemplateContent(BaseModel):
    """Reusable India clinical-note content block."""

    assessment: str = ""
    plan: str = ""
    rx: list[TemplateMedication] = []
    investigations: list[TemplateInvestigation] = []
    red_flags: list[str] = []
    follow_up_in: str = ""
    follow_up_date: str = ""
    doctor_notes: str = ""
    chief_complaint: str = ""
    data_gaps: list[str] = []


class CreateTemplateRequest(BaseModel):
    """Create template request payload."""

    name: str = Field(..., min_length=1)
    description: str = ""
    type: TemplateType = "personal"
    category: str = "General"
    specialty: str = ""
    content: TemplateContent
    tags: list[str] = []
    appointment_types: list[str] = []
    is_favorite: bool = False
    author_id: str | None = None
    author_name: str | None = None


class UpdateTemplateRequest(BaseModel):
    """Update template request payload."""

    name: str | None = None
    description: str | None = None
    type: TemplateType | None = None
    category: str | None = None
    specialty: str | None = None
    content: TemplateContent | None = None
    tags: list[str] | None = None
    appointment_types: list[str] | None = None
    is_favorite: bool | None = None
    is_active: bool | None = None


class TemplateResponse(BaseModel):
    """Template document response payload."""

    id: str
    name: str
    description: str
    type: TemplateType
    category: str
    specialty: str
    content: TemplateContent
    tags: list[str]
    appointment_types: list[str]
    is_favorite: bool
    author_id: str
    author_name: str
    usage_count: int
    last_used: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_active: bool


class ListTemplatesResponse(BaseModel):
    """Paginated template list response."""

    items: list[TemplateResponse]
    total: int
    page: int
    page_size: int


class RecordTemplateUsageRequest(BaseModel):
    """Template usage analytics payload."""

    visit_id: str | None = None
    patient_id: str | None = None


class ToggleTemplateFavoriteResponse(BaseModel):
    """Favorite toggle response."""

    id: str
    is_favorite: bool


class OkResponse(BaseModel):
    """Simple success payload."""

    ok: bool
