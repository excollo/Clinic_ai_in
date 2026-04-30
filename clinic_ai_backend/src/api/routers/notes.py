"""Clinical notes routes module."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.adapters.db.mongo.repositories.clinical_note_repository import ClinicalNoteRepository
from src.application.utils.patient_id_crypto import encode_patient_id, resolve_internal_patient_id
from src.api.schemas.notes import (
    ClinicalNoteTemplateRequest,
    NoteGenerateRequest,
    NoteGenerateResponse,
    NoteType,
    PostVisitWhatsAppSendRequest,
    PostVisitWhatsAppSendResponse,
)
from src.application.use_cases.generate_india_clinical_note import GenerateIndiaClinicalNoteUseCase
from src.application.use_cases.generate_post_visit_summary import GeneratePostVisitSummaryUseCase
from src.application.use_cases.generate_soap_note import GenerateSoapNoteUseCase
from src.application.use_cases.send_post_visit_summary_whatsapp_to_patient import (
    send_latest_post_visit_summary_whatsapp_to_patient,
)
from src.core.config import get_settings

router = APIRouter(prefix="/api/notes", tags=["Notes"])


def _encode_note_patient_id(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    raw = str(out.get("patient_id") or "").strip()
    if raw:
        out["patient_id"] = encode_patient_id(raw)
    return out


def _build_clinical_note_template(*, doctor_type: str, language_style: str, region: str, optional_preferences: str | None) -> dict[str, Any]:
    dt = str(doctor_type or '').strip().lower()
    style = str(language_style or '').strip()
    reg = str(region or '').strip()
    pref = str(optional_preferences or '').strip()

    if dt == 'ayurvedic':
        assessment = '<dosha_agni_ama_prakriti_based_assessment>'
        plan = '<pathya_apathya_lifestyle_and_balancing_plan>'
        medicine_name = '<ayurvedic_formulation_name_churna_vati_kwath_taila_ghrita>'
        note_hint = '<ayurvedic_clinical_narrative_with_holistic_language>'
    elif dt == 'homeopathic':
        assessment = '<constitutional_homeopathic_assessment>'
        plan = '<remedy_selection_with_potency_and_repetition_plan>'
        medicine_name = '<homeopathic_remedy_name>'
        note_hint = '<homeopathic_case_narrative_with_constitutional_symptoms>'
    else:
        assessment = '<clinical_assessment_summary>'
        plan = '<evidence_based_management_plan>'
        medicine_name = '<allopathic_medicine_name>'
        note_hint = '<clinical_narrative_in_standard_medical_tone>'

    if style:
        note_hint = f'{note_hint} | style={style}'
    if reg:
        note_hint = f'{note_hint} | region={reg}'
    if pref:
        note_hint = f'{note_hint} | preferences={pref}'

    return {
        'assessment': assessment,
        'plan': plan,
        'rx': [
            {
                'medicine_name': medicine_name,
                'dose': '<dose>',
                'frequency': '<frequency>',
                'duration': '<duration>',
                'route': '<route>',
                'food_instruction': '<food_instruction>',
                'generic_available': '<true_or_false>',
            }
        ],
        'investigations': [
            {
                'test_name': '<test_name>',
                'urgency': '<routine_or_urgent_or_stat>',
                'preparation_instructions': '<preparation_instructions_or_na>',
                'routing_note': '<routing_note>',
            }
        ],
        'red_flags': ['<red_flag_1>', '<red_flag_2>'],
        'follow_up_in': '<follow_up_interval>',
        'follow_up_date': '<yyyy-mm-dd_or_null>',
        'doctor_notes': note_hint,
        'chief_complaint': '<chief_complaint>',
        'data_gaps': ['<missing_info_1>', '<missing_info_2>'],
    }


@router.post('/clinical-note-template')
def get_clinical_note_template(body: ClinicalNoteTemplateRequest) -> dict[str, Any]:
    """Return reusable clinical note template adapted by doctor type/style/region."""
    return _build_clinical_note_template(
        doctor_type=body.doctor_type,
        language_style=body.language_style,
        region=body.region,
        optional_preferences=body.optional_preferences,
    )


@router.post("/clinical-note", response_model=NoteGenerateResponse)
def generate_clinical_note(request: NoteGenerateRequest) -> NoteGenerateResponse:
    """Generate clinical note (default note type)."""
    request.patient_id = resolve_internal_patient_id(request.patient_id, allow_raw_fallback=True)
    default_type = get_settings().default_note_type
    note_type: NoteType = request.note_type or default_type
    return _generate_by_type(note_type=note_type, request=request)


def generate_india_note(request: NoteGenerateRequest) -> NoteGenerateResponse:
    """Generate India clinical note explicitly."""
    doc = GenerateIndiaClinicalNoteUseCase().execute(
        patient_id=request.patient_id,
        visit_id=request.visit_id,
        transcription_job_id=request.transcription_job_id,
        force_regenerate=True,
        follow_up_date=request.follow_up_date,
    )
    return NoteGenerateResponse(**_encode_note_patient_id(doc))


def generate_soap_note(request: NoteGenerateRequest) -> NoteGenerateResponse:
    """Generate legacy SOAP note explicitly."""
    try:
        doc = GenerateSoapNoteUseCase().execute(
            patient_id=request.patient_id,
            visit_id=request.visit_id,
            transcription_job_id=request.transcription_job_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NoteGenerateResponse(**_encode_note_patient_id(doc))


@router.post("/post-visit-summary", response_model=NoteGenerateResponse)
def generate_post_visit_summary(request: NoteGenerateRequest) -> NoteGenerateResponse:
    """Generate patient-facing post-visit summary explicitly."""
    try:
        doc = GeneratePostVisitSummaryUseCase().execute(
            patient_id=request.patient_id,
            visit_id=request.visit_id,
            transcription_job_id=request.transcription_job_id,
            preferred_language=request.preferred_language,
            follow_up_date=request.follow_up_date,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 422 if "preferred_language" in detail else 404
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return NoteGenerateResponse(**_encode_note_patient_id(doc))


@router.get("/clinical-note", response_model=NoteGenerateResponse)
def get_latest_clinical_note(
    patient_id: str = Query(min_length=1),
    visit_id: str = Query(min_length=1),
    note_type: NoteType | None = Query(
        default=None,
        description="When set, fetch latest note of this type (e.g. soap). Otherwise uses server default_note_type.",
    ),
) -> NoteGenerateResponse:
    """Fetch latest clinical note for a patient visit."""
    resolved_type: NoteType = note_type or get_settings().default_note_type
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    note = ClinicalNoteRepository().find_latest(
        patient_id=internal_patient_id,
        visit_id=visit_id,
        note_type=resolved_type,
    )
    if not note:
        raise HTTPException(status_code=404, detail=f"No {resolved_type} note found")
    note.pop("_id", None)
    return NoteGenerateResponse(**_encode_note_patient_id(note))


@router.post(
    "/post-visit-summary/send-whatsapp",
    response_model=PostVisitWhatsAppSendResponse,
    summary="Send stored post-visit summary to patient WhatsApp",
)
def send_post_visit_summary_whatsapp_route(
    body: PostVisitWhatsAppSendRequest,
) -> PostVisitWhatsAppSendResponse:
    """Send latest saved post-visit summary template plus immediate Meta follow-up template."""
    try:
        result = send_latest_post_visit_summary_whatsapp_to_patient(
            patient_id=resolve_internal_patient_id(body.patient_id, allow_raw_fallback=True),
            visit_id=body.visit_id,
            phone_number_override=body.phone_number,
        )
        if result.get("patient_id"):
            result["patient_id"] = encode_patient_id(str(result["patient_id"]))
        return PostVisitWhatsAppSendResponse(**result)
    except ValueError as exc:
        detail = str(exc)
        if "No post_visit_summary" in detail:
            raise HTTPException(status_code=404, detail=detail) from exc
        if "Patient not found" in detail:
            raise HTTPException(status_code=404, detail=detail) from exc
        if "no phone number" in detail.lower():
            raise HTTPException(status_code=422, detail=detail) from exc
        raise HTTPException(status_code=400, detail=detail) from exc


@router.get("/post-visit-summary", response_model=NoteGenerateResponse)
def get_latest_post_visit_summary(
    patient_id: str = Query(min_length=1),
    visit_id: str = Query(min_length=1),
) -> NoteGenerateResponse:
    """Fetch latest post-visit summary note for a patient visit."""
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    note = ClinicalNoteRepository().find_latest(
        patient_id=internal_patient_id,
        visit_id=visit_id,
        note_type="post_visit_summary",
    )
    if not note:
        raise HTTPException(status_code=404, detail="No post_visit_summary note found")
    note.pop("_id", None)
    return NoteGenerateResponse(**_encode_note_patient_id(note))


def _generate_by_type(*, note_type: NoteType, request: NoteGenerateRequest) -> NoteGenerateResponse:
    if note_type == "soap":
        return generate_soap_note(request)
    if note_type == "post_visit_summary":
        return generate_post_visit_summary(request)
    try:
        doc = GenerateIndiaClinicalNoteUseCase().execute(
            patient_id=request.patient_id,
            visit_id=request.visit_id,
            transcription_job_id=request.transcription_job_id,
            force_regenerate=request.follow_up_date is not None,
            follow_up_date=request.follow_up_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return NoteGenerateResponse(**_encode_note_patient_id(doc))
