"""Vitals API schemas module."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


class PatientLookupRequest(BaseModel):
    """Lookup request by name and phone."""

    name: str = Field(min_length=1, max_length=120)
    phone_number: str = Field(min_length=8, max_length=20)


class PatientLookupResponse(BaseModel):
    """Lookup response with resolved patient."""

    patient_id: str
    visit_id: str | None
    name: str
    phone_number: str


class VitalsField(BaseModel):
    """Dynamic vitals field metadata."""

    key: str
    label: str
    field_type: str
    unit: str | None = None
    required: bool
    reason: str


class VitalsFormResponse(BaseModel):
    """AI-generated vitals form response."""

    form_id: str
    patient_id: str
    visit_id: str | None = None
    needs_vitals: bool
    reason: str
    fields: list[VitalsField]
    generated_at: datetime


class VitalsValueEntry(BaseModel):
    """Single vital measurement; `key` must match `fields[].key` from the generated form."""

    key: str = Field(
        min_length=1,
        max_length=64,
        description=(
            "Exact `fields[].key` from the latest vitals form for this visit. "
            "When vitals are needed, the form always includes `body_weight_kg` and `blood_pressure_mmhg`; "
            "additional keys are illness-specific (up to three)."
        ),
        examples=["body_weight_kg", "blood_pressure_mmhg", "dynamic_contextual_key_from_generate_form"],
    )
    value: str | int | float | bool | None = Field(
        description="Staff-entered value (number, text such as 120/80 for BP, boolean, etc.)",
    )


VITALS_SUBMIT_EXAMPLE_FULL = {
    "patient_id": "string",
    "visit_id": "string",
    "form_id": "string",
    "staff_name": "string",
    "values": [
        {"key": "body_weight_kg", "value": 68.5},
        {"key": "blood_pressure_mmhg", "value": "122/78"},
        {"key": "dynamic_contextual_key_from_generate_form", "value": "string"},
    ],
}

VITALS_SUBMIT_EXAMPLE_FIXED_PLUS_PAIN = {
    **VITALS_SUBMIT_EXAMPLE_FULL,
    "values": [
        {"key": "body_weight_kg", "value": 72.0},
        {"key": "blood_pressure_mmhg", "value": "118/76"},
        {"key": "another_dynamic_key_from_generate_form", "value": "string"},
    ],
}

VITALS_SUBMIT_EXAMPLE_FIXED_ONLY = {
    **VITALS_SUBMIT_EXAMPLE_FULL,
    "values": [
        {"key": "body_weight_kg", "value": 65.0},
        {"key": "blood_pressure_mmhg", "value": "128/84"},
    ],
}

# Swagger: POST /vitals/submit — doctors copy keys from generate-form `fields`, then fill `value` only.
VITALS_SUBMIT_OPENAPI_EXAMPLES: dict[str, dict[str, Any]] = {
    "fixed_plus_contextual": {
        "summary": "Weight + BP + one illness-specific vital",
        "description": "Use `form_id` and exact keys from `POST /vitals/generate-form/...` response `fields` for that patient.",
        "value": VITALS_SUBMIT_EXAMPLE_FULL,
    },
    "fixed_plus_different_extra": {
        "summary": "Weight + BP + different extra (keys vary by complaint)",
        "value": VITALS_SUBMIT_EXAMPLE_FIXED_PLUS_PAIN,
    },
    "fixed_only": {
        "summary": "Only common vitals when the form had no extra rows",
        "value": VITALS_SUBMIT_EXAMPLE_FIXED_ONLY,
    },
    "recommended_dynamic_flow": {
        "summary": "Recommended: call submit-template for exact keys",
        "description": "Use GET /vitals/submit-template/{patient_id}/{visit_id} to get all required keys (dynamic per visit), then copy into POST /vitals/submit.",
        "value": VITALS_SUBMIT_EXAMPLE_FULL,
    },
}


class VitalsSubmitRequest(BaseModel):
    """Vitals submission payload."""

    patient_id: str
    visit_id: str
    form_id: str | None = Field(
        default=None,
        description="Copy `form_id` from POST /vitals/generate-form/{patient_id}/{visit_id} for this visit.",
    )
    staff_name: str = Field(min_length=1, max_length=120, description="Staff member capturing vitals")
    values: list[VitalsValueEntry] = Field(
        description=(
            "One `{key, value}` per row in `fields` from generate-form for this `form_id`. "
            "Submit a value for each **required** field (typically `body_weight_kg`, `blood_pressure_mmhg`, "
            "plus any illness-specific keys the form lists). Keys are not global—mirror the form for this visit."
        ),
        examples=[
            VITALS_SUBMIT_EXAMPLE_FULL["values"],
            VITALS_SUBMIT_EXAMPLE_FIXED_ONLY["values"],
        ],
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_flat_dict(cls, data: Any) -> Any:
        """Allow legacy clients that POST values as a JSON object map."""
        if not isinstance(data, dict):
            return data
        raw_values = data.get("values")
        if isinstance(raw_values, dict):
            coerced = [{"key": str(k), "value": v} for k, v in raw_values.items()]
            return {**data, "values": coerced}
        return data

    def values_as_dict(self) -> dict[str, str | int | float | bool | None]:
        """Flatten to the shape stored in Mongo."""
        return {entry.key: entry.value for entry in self.values}


class VitalsSubmitResponse(BaseModel):
    """Vitals submission response payload."""

    vitals_id: str
    patient_id: str
    visit_id: str | None = None
    submitted_at: datetime


class VitalsSubmitTemplateResponse(BaseModel):
    """Prebuilt submit payload template: exact keys from latest form + suggested values."""

    patient_id: str
    visit_id: str
    form_id: str
    staff_name: str
    values: list[VitalsValueEntry]
    source: str = Field(
        description="`latest_vitals` when values were prefilled from prior submission; otherwise `empty`."
    )


class LatestVitalsResponse(BaseModel):
    """Latest submitted vitals."""

    vitals_id: str
    patient_id: str
    visit_id: str | None = None
    form_id: str | None = None
    staff_name: str
    submitted_at: datetime
    values: dict[str, str | int | float | bool | None] = Field(
        description="Map of vital key → submitted value (same keys as the form at submit time).",
    )
