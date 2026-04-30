
"""Patient web chat routes."""
from fastapi import APIRouter, HTTPException, Query

from src.adapters.db.mongo.client import get_database
from src.api.schemas.patient_chat import (
    PatientChatLookupByPhoneResponse,
    PatientChatStateResponse,
    ReplyPatientChatRequest,
    StartPatientChatRequest,
)
from src.application.services.intake_chat_service import IntakeChatService
from src.application.utils.patient_id_crypto import encode_patient_id, resolve_internal_patient_id

router = APIRouter(prefix="/api/patient-chat", tags=["Workflow"])


@router.post("/start", response_model=PatientChatStateResponse)
def start_patient_chat(body: StartPatientChatRequest) -> PatientChatStateResponse:
    internal_patient_id = resolve_internal_patient_id(body.patient_id, allow_raw_fallback=True)
    db = get_database()
    patient = db.patients.find_one({"patient_id": internal_patient_id}) or {}
    phone_number = str(patient.get("phone_number") or "").strip()

    service = IntakeChatService()
    service.start_intake(
        patient_id=internal_patient_id,
        visit_id=body.visit_id,
        to_number=phone_number or internal_patient_id,
        language=str(body.language or "en"),
    )
    state = service.get_session_state(internal_patient_id, body.visit_id)
    state["patient_id"] = encode_patient_id(internal_patient_id)
    return PatientChatStateResponse(**state)


@router.post("/reply", response_model=PatientChatStateResponse)
def reply_patient_chat(body: ReplyPatientChatRequest) -> PatientChatStateResponse:
    internal_patient_id = resolve_internal_patient_id(body.patient_id, allow_raw_fallback=True)
    service = IntakeChatService()
    try:
        service.handle_web_reply(
            patient_id=internal_patient_id,
            visit_id=body.visit_id,
            message_text=body.message_text,
            message_id=body.message_id,
        )
        state = service.get_session_state(internal_patient_id, body.visit_id)
        state["patient_id"] = encode_patient_id(internal_patient_id)
        return PatientChatStateResponse(**state)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/state/{patient_id}/{visit_id}", response_model=PatientChatStateResponse)
def get_patient_chat_state(patient_id: str, visit_id: str) -> PatientChatStateResponse:
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    service = IntakeChatService()
    try:
        state = service.get_session_state(internal_patient_id, visit_id)
        state["patient_id"] = encode_patient_id(internal_patient_id)
        return PatientChatStateResponse(**state)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/latest-by-phone", response_model=PatientChatLookupByPhoneResponse)
def get_latest_patient_chat_by_phone(phone_number: str = Query(min_length=5)) -> PatientChatLookupByPhoneResponse:
    service = IntakeChatService()
    try:
        state = service.get_latest_session_by_phone(phone_number)
        if state.get("patient_id"):
            state["patient_id"] = encode_patient_id(str(state["patient_id"]))
        state["phone_number"] = phone_number
        return PatientChatLookupByPhoneResponse(**state)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

