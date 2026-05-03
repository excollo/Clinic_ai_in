"""Frontend contract compatibility endpoints (non-/api paths)."""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
import httpx
from pymongo import ReturnDocument

from src.adapters.db.mongo.client import get_database
from src.adapters.external.ai.openai_client import OpenAIQuestionClient
from src.api.dependencies.contract_auth import require_contract_auth
from src.api.schemas.frontend_contract import (
    AbhaLinkRequest,
    AbhaLookupRequest,
    AbhaScanShareRequest,
    ConsentCaptureRequest,
    ConsentWithdrawRequest,
    ForgotPasswordRequest,
    IndiaClinicalNoteRequest,
    LabResultRequest,
    LoginRequest,
    MarkAllReadRequest,
    MedicationScheduleRequest,
    PostVisitSummaryRequest,
    RegisterPatientRequest,
    SendOtpRequest,
    SignupRequest,
    VerifyOtpRequest,
    VitalsRequest,
    WhatsAppSendRequest,
)
from src.application.utils.patient_id_crypto import resolve_internal_patient_id
from src.core.auth import hash_password, verify_password
from src.core.config import get_settings
from src.application.services.intake_chat_service import IntakeChatService
from jose import jwt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Frontend Contract"])

LOGIN_RATE_LIMIT: dict[str, dict[str, Any]] = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15
OTP_MAX_ATTEMPTS = 3
OTP_EXPIRY_SECONDS = 300

VITALS_PROMPT = """
You are a clinical assistant helping an Indian OPD doctor decide which
vital signs to measure for a patient.

The patient's chief complaint is: "{chief_complaint}"

The doctor will always measure blood pressure and body weight.
These are fixed and you must NOT include them.

Based only on the chief complaint, return a JSON array of additional
vital signs that are clinically relevant to measure.

Each item must have exactly these fields:
- key: snake_case identifier (e.g. "pulse", "spo2", "temperature")
- label: display name in English (e.g. "Pulse", "SpO₂", "Temperature")
- type: always "number"
- unit: measurement unit (e.g. "bpm", "%", "°F", "breaths/min", "mg/dL")
- normal_range: [min, max] as numbers, or null if not applicable
- ai_reason: one short sentence explaining why this vital is relevant

Return ONLY a valid JSON array. No explanation. No markdown. No preamble.
If no additional vitals are needed, return an empty array: []

Examples of valid keys you may return:
pulse, spo2, temperature, respiratory_rate, blood_glucose,
random_blood_sugar, peak_flow, pain_scale, gcs_score

Do not invent keys outside this list unless clearly clinically necessary.
"""

FIXED_FIELDS: list[dict[str, Any]] = [
    {
        "key": "blood_pressure",
        "label": "Blood pressure",
        "type": "bp_pair",
        "unit": "mmHg",
        "normal_range": {"systolic": [90, 130], "diastolic": [60, 85]},
    },
    {"key": "weight", "label": "Weight", "type": "number", "unit": "kg", "normal_range": None},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_audit_state(
    request: Request,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    status: str = "success",
    patient_id: str | None = None,
    visit_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    request.state.audit_action = action
    request.state.audit_resource_type = resource_type
    request.state.audit_resource_id = resource_id
    request.state.audit_status = status
    if patient_id:
        request.state.audit_patient_id = patient_id
    if visit_id:
        request.state.audit_visit_id = visit_id
    request.state.audit_context = context or {}


def _error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"request_id": str(uuid4()), "detail": detail})


def _create_contract_jwt(doctor_id: str, mobile: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "doctor_id": doctor_id,
        "mobile": mobile,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _record_login_failure(mobile: str) -> None:
    now = datetime.now(timezone.utc)
    entry = LOGIN_RATE_LIMIT.get(mobile, {"failures": 0, "locked_until": None})
    locked_until = entry.get("locked_until")
    if locked_until and now >= locked_until:
        entry = {"failures": 0, "locked_until": None}
    entry["failures"] = int(entry.get("failures", 0)) + 1
    if entry["failures"] >= MAX_LOGIN_ATTEMPTS:
        entry["locked_until"] = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
    LOGIN_RATE_LIMIT[mobile] = entry


def _is_login_locked(mobile: str) -> bool:
    entry = LOGIN_RATE_LIMIT.get(mobile)
    if not entry:
        return False
    locked_until = entry.get("locked_until")
    if not locked_until:
        return False
    if datetime.now(timezone.utc) >= locked_until:
        LOGIN_RATE_LIMIT.pop(mobile, None)
        return False
    return True


def _clear_login_failures(mobile: str) -> None:
    LOGIN_RATE_LIMIT.pop(mobile, None)


def _is_indian_mobile(mobile: str) -> bool:
    normalized = mobile.replace(" ", "").replace("+91", "").replace("-", "")
    return normalized.isdigit() and len(normalized) == 10 and normalized[0] in {"6", "7", "8", "9"}


def _as_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _generate_dynamic_vitals_with_llm(chief_complaint: str) -> list[dict[str, Any]]:
    try:
        content = OpenAIQuestionClient._chat_completion(  # pylint: disable=protected-access
            prompt=VITALS_PROMPT.format(chief_complaint=chief_complaint),
            system_role="You are a clinical vitals recommendation engine. Return strict JSON only.",
        )
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            return []
        output: list[dict[str, Any]] = []
        required_keys = {"key", "label", "type", "unit", "normal_range", "ai_reason"}
        for item in parsed:
            if not isinstance(item, dict):
                continue
            if set(item.keys()) != required_keys:
                continue
            if item.get("type") != "number":
                continue
            output.append(item)
        return output
    except Exception:
        return []


def _enforce_chest_pain_minimum_fields(
    chief_complaint: str, dynamic_fields: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    complaint = (chief_complaint or "").strip().lower()
    if "chest pain" not in complaint:
        return dynamic_fields

    index = {str(item.get("key", "")).strip().lower(): item for item in dynamic_fields}
    minimum_fields = [
        {
            "key": "pulse",
            "label": "Pulse",
            "type": "number",
            "unit": "bpm",
            "normal_range": [60, 100],
            "ai_reason": "Pulse is essential when assessing chest pain.",
        },
        {
            "key": "spo2",
            "label": "SpO2",
            "type": "number",
            "unit": "%",
            "normal_range": [95, 100],
            "ai_reason": "Oxygen saturation helps triage cardiopulmonary chest pain causes.",
        },
        {
            "key": "temperature",
            "label": "Temperature",
            "type": "number",
            "unit": "°F",
            "normal_range": [97, 99],
            "ai_reason": "Temperature helps identify infectious causes overlapping chest pain.",
        },
        {
            "key": "respiratory_rate",
            "label": "Respiratory Rate",
            "type": "number",
            "unit": "breaths/min",
            "normal_range": [12, 20],
            "ai_reason": "Respiratory rate helps assess breathing distress with chest pain.",
        },
    ]
    for field in minimum_fields:
        if field["key"] not in index:
            dynamic_fields.append(field)
    return dynamic_fields


@router.post("/auth/login")
def auth_login(body: LoginRequest, request: Request) -> dict[str, Any]:
    mobile = body.mobile.strip()
    if _is_login_locked(mobile):
        _set_audit_state(request, action="failed_login_attempt", resource_type="session", resource_id="credential_check", status="failure")
        raise _error(429, "Too many failed attempts. Try again in 15 minutes.")
    db = get_database()
    doc = db.doctors.find_one({"mobile": mobile}) or db.users.find_one({"phone": mobile}) or db.users.find_one({"mobile": mobile})
    if not doc:
        _record_login_failure(mobile)
        _set_audit_state(request, action="failed_login_attempt", resource_type="session", resource_id="credential_check", status="failure")
        raise _error(401, "Invalid credentials")
    password_hash = str(doc.get("password_hash") or doc.get("hashed_password") or "")
    if not password_hash or not verify_password(body.password, password_hash):
        _record_login_failure(mobile)
        _set_audit_state(request, action="failed_login_attempt", resource_type="session", resource_id="credential_check", status="failure")
        raise _error(401, "Invalid credentials")
    _clear_login_failures(mobile)
    doctor_id = str(doc.get("doctor_id") or doc.get("id") or f"doctor_{mobile[-6:]}")
    doctor_name = str(doc.get("name") or doc.get("full_name") or doc.get("doctor_name") or "doctor")
    token = _create_contract_jwt(doctor_id=doctor_id, mobile=mobile)
    _set_audit_state(request, action="login", resource_type="session", resource_id=doctor_id)
    return {"token": token, "doctor_id": doctor_id, "doctor_name": doctor_name}


@router.post("/auth/signup")
def auth_signup(body: SignupRequest) -> dict[str, Any]:
    mobile = body.mobile.strip()
    name = body.name.strip()
    db = get_database()
    existing = db.doctors.find_one({"mobile": mobile}) or db.users.find_one({"mobile": mobile}) or db.users.find_one({"phone": mobile})
    if existing:
        raise _error(409, "Mobile already registered")
    doctor_id = f"doctor_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    db.doctors.insert_one(
        {
            "doctor_id": doctor_id,
            "name": name,
            "mobile": mobile,
            "email": body.email,
            "mci_number": body.mci_number,
            "specialty": body.specialty,
            "password_hash": hash_password(body.password),
            "clinic": {
                "name": body.clinic_name,
                "city": body.city,
                "pincode": body.pincode,
                "opd_hours": body.opd_hours,
                "languages": body.languages,
                "token_prefix": body.token_prefix,
            },
            "abdm_hfr_id": body.abdm_hfr_id,
            "whatsapp_mode": body.whatsapp_mode,
            "token_counter": 0,
            "created_at": now,
            "updated_at": now,
        }
    )
    token = _create_contract_jwt(doctor_id=doctor_id, mobile=mobile)
    return {"doctor_id": doctor_id, "token": token}


@router.post("/auth/send-otp")
def auth_send_otp(body: SendOtpRequest) -> dict[str, Any]:
    mobile = body.mobile.strip()
    settings = get_settings()
    db = get_database()
    request_id = f"otp_{uuid4().hex[:16]}"
    plain_otp = "".join(str(random.randint(0, 9)) for _ in range(6))
    is_dev_mode = not settings.msg91_api_key
    if is_dev_mode:
        plain_otp = "123456"
    otp_hash = hash_password(plain_otp)
    now = datetime.now(timezone.utc)
    db.otp_requests.insert_one(
        {
            "request_id": request_id,
            "mobile": mobile,
            "otp_hash": otp_hash,
            "expires_at": now + timedelta(seconds=OTP_EXPIRY_SECONDS),
            "attempts": 0,
            "used": False,
            "created_at": now,
        }
    )
    if is_dev_mode:
        logger.info("[DEV MODE] OTP for %s: %s", mobile, plain_otp)
        db.dev_otps.insert_one({"request_id": request_id, "mobile": mobile, "otp": plain_otp, "created_at": now})
        return {"request_id": request_id, "expires_in": OTP_EXPIRY_SECONDS}
    if not settings.msg91_template_id:
        raise _error(500, "MSG91_TEMPLATE_ID is required when MSG91_API_KEY is configured")
    payload = {
        "template_id": settings.msg91_template_id,
        "mobile": f"91{mobile}",
        "otp": plain_otp,
    }
    headers = {"authkey": settings.msg91_api_key, "Content-Type": "application/json"}
    with httpx.Client(timeout=10) as client:
        response = client.post("https://control.msg91.com/api/v5/otp", json=payload, headers=headers)
    if response.status_code >= 400:
        raise _error(502, "Failed to dispatch OTP")
    return {"request_id": request_id, "expires_in": OTP_EXPIRY_SECONDS}


@router.post("/auth/verify-otp")
def auth_verify_otp(body: VerifyOtpRequest) -> dict[str, Any]:
    mobile = body.mobile.strip()
    otp = body.otp.strip()
    request_id = body.request_id.strip()
    db = get_database()
    req = db.otp_requests.find_one({"request_id": request_id, "mobile": mobile})
    if not req:
        raise _error(401, "invalid otp")
    if bool(req.get("used")):
        raise _error(401, "invalid otp")
    expires_at = _as_utc_datetime(req.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        raise _error(401, "invalid otp")
    attempts = int(req.get("attempts") or 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        raise _error(429, "Too many OTP attempts")
    otp_hash = str(req.get("otp_hash") or "")
    if not otp_hash or not verify_password(otp, otp_hash):
        db.otp_requests.update_one({"request_id": request_id}, {"$set": {"attempts": attempts + 1}})
        raise _error(401, "invalid otp")
    db.otp_requests.update_one({"request_id": request_id}, {"$set": {"used": True, "verified_at": datetime.now(timezone.utc)}})
    user = db.doctors.find_one({"mobile": mobile}) or db.users.find_one({"phone": mobile}) or db.users.find_one({"mobile": mobile})
    doctor_id = str((user or {}).get("doctor_id") or (user or {}).get("id") or f"doctor_{mobile[-6:]}")
    token = _create_contract_jwt(doctor_id=doctor_id, mobile=mobile)
    return {"token": token, "doctor_id": doctor_id}


@router.post("/auth/forgot-password")
def auth_forgot_password(body: ForgotPasswordRequest, request: Request) -> dict[str, Any]:
    db = get_database()
    req = db.otp_requests.find_one({"request_id": body.request_id, "mobile": body.mobile})
    if not req:
        raise _error(401, "invalid otp")
    expires_at = _as_utc_datetime(req.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        raise _error(401, "invalid otp")
    attempts = int(req.get("attempts") or 0)
    if attempts >= OTP_MAX_ATTEMPTS:
        raise _error(429, "Too many OTP attempts")
    otp_hash = str(req.get("otp_hash") or "")
    if not otp_hash or not verify_password(body.otp, otp_hash):
        db.otp_requests.update_one({"request_id": body.request_id}, {"$set": {"attempts": attempts + 1}})
        raise _error(401, "invalid otp")
    db.otp_requests.update_one({"request_id": body.request_id}, {"$set": {"used": True, "verified_at": datetime.now(timezone.utc)}})
    _set_audit_state(request, action="password_reset_requested", resource_type="session", resource_id="password_reset")
    updated = db.doctors.update_one(
        {"mobile": body.mobile},
        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": datetime.now(timezone.utc)}},
    )
    if int(getattr(updated, "matched_count", 0)) == 0:
        raise _error(404, "doctor not found")
    doctor = db.doctors.find_one({"mobile": body.mobile}) or {}
    if doctor.get("doctor_id"):
        _set_audit_state(request, action="password_reset_completed", resource_type="session", resource_id=str(doctor.get("doctor_id")))
    return {"success": True}


@router.post("/consent/capture")
def consent_capture(
    body: ConsentCaptureRequest,
    request: Request,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    if not x_idempotency_key:
        _set_audit_state(request, action="consent_captured", resource_type="consent", resource_id="missing-idempotency", status="failure")
        raise _error(422, "X-Idempotency-Key header is required")
    db = get_database()
    existing = db.consents.find_one({"idempotency_key": x_idempotency_key})
    if existing:
        return {"consent_id": str(existing["consent_id"]), "recorded_at": str(existing["recorded_at"])}
    status = body.status or ("accepted" if bool(body.patient_confirmed) else "declined")
    if status == "declined" and not body.decline_reason:
        _set_audit_state(request, action="consent_declined", resource_type="consent", resource_id="validation-error", status="failure", patient_id=body.patient_id, visit_id=body.visit_id)
        raise _error(422, "decline_reason is required when status is declined")
    consent_id = f"consent_{uuid4().hex[:16]}"
    recorded_at = _now_iso()
    db.consents.insert_one(
        {
            "consent_id": consent_id,
            "idempotency_key": x_idempotency_key,
            "patient_id": body.patient_id,
            "visit_id": body.visit_id,
            "doctor_id": doctor_id,
            "language": body.language,
            "consent_text_version": body.consent_text_version,
            "patient_confirmed": status == "accepted",
            "status": status,
            "decline_reason": body.decline_reason,
            "timestamp": body.timestamp,
            "recorded_at": recorded_at,
        }
    )
    if status == "accepted":
        db.visits.update_one(
            {"visit_id": body.visit_id},
            {"$set": {"consent_captured": True, "consent_id": consent_id, "updated_at": datetime.now(timezone.utc)}},
        )
        db.patients.update_one({"patient_id": body.patient_id}, {"$set": {"consent_status": "accepted", "updated_at": datetime.now(timezone.utc)}})
        _set_audit_state(
            request,
            action="consent_captured",
            resource_type="consent",
            resource_id=consent_id,
            patient_id=body.patient_id,
            visit_id=body.visit_id,
            context={"status": "accepted"},
        )
    else:
        db.visits.update_one(
            {"visit_id": body.visit_id},
            {"$set": {"consent_captured": False, "consent_status": "declined", "updated_at": datetime.now(timezone.utc)}},
        )
        db.patients.update_one({"patient_id": body.patient_id}, {"$set": {"consent_status": "declined", "updated_at": datetime.now(timezone.utc)}})
        _set_audit_state(
            request,
            action="consent_declined",
            resource_type="consent",
            resource_id=consent_id,
            patient_id=body.patient_id,
            visit_id=body.visit_id,
            context={"status": "declined"},
        )
    return {"consent_id": consent_id, "recorded_at": recorded_at, "status": status}


@router.post("/consent/withdraw")
def consent_withdraw(
    body: ConsentWithdrawRequest,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    db = get_database()
    latest = db.consents.find_one(
        {"patient_id": body.patient_id, "status": {"$in": ["accepted", "declined"]}},
        sort=[("recorded_at", -1)],
    )
    if not latest:
        _set_audit_state(request, action="consent_withdrawn", resource_type="consent", resource_id=body.patient_id, status="failure", patient_id=body.patient_id)
        raise _error(404, "no consent history found for patient")
    original_consent_id = body.original_consent_id or str(latest.get("consent_id") or "")
    withdrawal_id = f"withdrawal_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)
    db.consent_withdrawals.insert_one(
        {
            "withdrawal_id": withdrawal_id,
            "patient_id": body.patient_id,
            "doctor_id": doctor_id,
            "original_consent_id": original_consent_id,
            "withdrawal_reason": body.withdrawal_reason,
            "initiated_by": body.initiated_by,
            "timestamp": now,
        }
    )
    db.patients.update_one(
        {"patient_id": body.patient_id},
        {"$set": {"consent_status": "withdrawn", "consent_withdrawn_at": now, "updated_at": now}},
    )
    _set_audit_state(
        request,
        action="consent_withdrawn",
        resource_type="consent",
        resource_id=withdrawal_id,
        patient_id=body.patient_id,
        context={"initiated_by": body.initiated_by},
    )
    return {
        "withdrawal_id": withdrawal_id,
        "patient_id": body.patient_id,
        "status": "withdrawn",
        "timestamp": now.isoformat(),
    }


@router.get("/consent/{patient_id}/history")
def consent_history(
    patient_id: str,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> list[dict[str, Any]]:
    _set_audit_state(request, action="consent_history_viewed", resource_type="consent", resource_id=patient_id, patient_id=patient_id)
    _ = auth
    db = get_database()
    records = list(db.consents.find({"patient_id": patient_id}, {"_id": 0}))
    withdrawals = list(db.consent_withdrawals.find({"patient_id": patient_id}, {"_id": 0}))
    events: list[dict[str, Any]] = []
    for item in records:
        events.append(
            {
                "consent_id": item.get("consent_id"),
                "status": item.get("status") or ("accepted" if item.get("patient_confirmed") else "declined"),
                "language": item.get("language"),
                "version": item.get("consent_text_version"),
                "timestamp": item.get("timestamp"),
                "captured_by": item.get("doctor_id"),
                "decline_reason": item.get("decline_reason"),
            }
        )
    for item in withdrawals:
        events.append(
            {
                "consent_id": item.get("original_consent_id"),
                "status": "withdrawn",
                "withdrawal_reason": item.get("withdrawal_reason"),
                "timestamp": item.get("timestamp"),
                "initiated_by": item.get("initiated_by"),
            }
        )
    events.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
    return events


@router.get("/consent/text")
def consent_text(language: str = "en", version: str = "latest") -> dict[str, Any]:
    db = get_database()
    doc = db.consent_texts.find_one({"language": language, "version": version}) or db.consent_texts.find_one(
        {"language": language}
    )
    text = str((doc or {}).get("text") or "I consent to collection and processing of my data for clinical care.")
    resolved_version = str((doc or {}).get("version") or version)
    return {"text": text, "version": resolved_version, "language": language}


@router.post("/patients/register")
def patients_register(
    body: RegisterPatientRequest,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    db = get_database()
    existing_patient = db.patients.find_one({"doctor_id": doctor_id, "mobile": body.mobile})
    if existing_patient and str(existing_patient.get("consent_status") or "") == "withdrawn":
        _set_audit_state(
            request,
            action="register_blocked_consent_withdrawn",
            resource_type="patient",
            resource_id=str(existing_patient.get("patient_id") or body.mobile),
            status="failure",
        )
        raise _error(403, "consent withdrawn; re-consent required before starting a new visit")
    patient_id = str(existing_patient.get("patient_id")) if existing_patient else f"pat_{uuid4().hex[:10]}"
    visit_id = f"vis_{uuid4().hex[:10]}"
    token_number = None
    whatsapp_triggered = False
    now = datetime.now(timezone.utc)
    if existing_patient:
        db.patients.update_one(
            {"patient_id": patient_id},
            {
                "$set": {
                    "doctor_id": doctor_id,
                    "name": body.name,
                    "age": body.age,
                    "sex": body.sex,
                    "mobile": body.mobile,
                    "language": body.language,
                    "updated_at": now,
                },
                "$inc": {"visit_count": 1},
            },
        )
    else:
        db.patients.insert_one(
            {
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "name": body.name,
                "age": body.age,
                "sex": body.sex,
                "mobile": body.mobile,
                "language": body.language,
                "abha_id": None,
                "chronic_conditions": [],
                "created_at": now,
                "updated_at": now,
                "visit_count": 0,
            }
        )
    if body.workflow_type == "walk_in":
        doctor = db.doctors.find_one_and_update(
            {"doctor_id": doctor_id},
            {"$inc": {"token_counter": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        token_prefix = str((doctor or {}).get("clinic", {}).get("token_prefix") or "OPD-")
        token_counter = int((doctor or {}).get("token_counter") or 1)
        token_number = f"{token_prefix}{token_counter}"
    db.visits.insert_one(
        {
            "visit_id": visit_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "chief_complaint": body.chief_complaint,
            "workflow_type": body.workflow_type,
            "scheduled_date": body.scheduled_date,
            "scheduled_time": body.scheduled_time,
            "intake_mode": body.intake_mode,
            "status": "waiting",
            "token_number": token_number,
            "created_at": now,
            "updated_at": now,
        }
    )
    # Auto-trigger WhatsApp intake for scheduled appointments unless explicitly in-clinic.
    if body.workflow_type == "scheduled" and body.intake_mode != "in_clinic":
        if body.mobile:
            try:
                IntakeChatService().start_intake(
                    patient_id=patient_id,
                    visit_id=visit_id,
                    to_number=body.mobile,
                    language=str(body.language or "en"),
                )
                whatsapp_triggered = True
            except Exception:
                logger.exception(
                    "scheduled_registration_intake_trigger_failed patient_id=%s visit_id=%s",
                    patient_id,
                    visit_id,
                )
    _set_audit_state(
        request,
        action="patient_registered",
        resource_type="patient",
        resource_id=patient_id,
        patient_id=patient_id,
        visit_id=visit_id,
        context={"workflow_type": body.workflow_type, "language": body.language},
    )
    return {
        "patient_id": patient_id,
        "visit_id": visit_id,
        "token_number": token_number,
        "consent_required": True,
        "whatsapp_triggered": whatsapp_triggered,
    }


@router.get("/patients")
def patients_list(
    request: Request,
    limit: int = 20,
    offset: int = 0,
    search: str = "",
    filter: str = "all",
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    db = get_database()
    rows = list(
        db.patients.find(
            {
                "$or": [
                    {"doctor_id": doctor_id},
                    {"doctor_id": ""},
                    {"doctor_id": None},
                    {"doctor_id": {"$exists": False}},
                ]
            },
            {"_id": 0},
        )
    )
    if search.strip():
        q = search.strip().lower()
        rows = [r for r in rows if q in str(r.get("name", "")).lower() or q in str(r.get("mobile", ""))]
    mapped = [
        {
            "patient_id": str(r.get("patient_id") or ""),
            "name": str(r.get("name") or ""),
            "age": int(r.get("age") or 0),
            "sex": str(r.get("sex") or "other").lower(),
            "mobile": str(r.get("mobile") or ""),
            "language": str(r.get("language") or "english"),
            "abha_id": r.get("abha_id"),
            "visit_count": int(r.get("visit_count") or 0),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "chronic_conditions": r.get("chronic_conditions") or [],
        }
        for r in rows
    ]
    if filter == "abha":
        mapped = [r for r in mapped if r.get("abha_id")]
    total = len(mapped)
    sliced = mapped[offset : offset + limit]
    _set_audit_state(request, action="patients_listed", resource_type="patient", resource_id=doctor_id, context={"filter": filter})
    return {"patients": sliced, "total": total, "limit": limit, "offset": offset}


@router.post("/patients/abha/lookup")
def patients_abha_lookup(
    body: AbhaLookupRequest,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _set_audit_state(request, action="abha_lookup_attempted", resource_type="patient", resource_id="abha_lookup")
    _ = auth
    _ = body
    settings = get_settings()
    if not settings.abdm_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "abdm_not_configured",
                "message": "ABDM integration is not configured for this clinic. Manual registration is available.",
                "fallback": "manual_registration",
            },
        )
    raise HTTPException(status_code=501, detail="ABDM integration pending")


@router.post("/patients/abha/link")
def patients_abha_link(
    body: AbhaLinkRequest,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    _ = body
    settings = get_settings()
    if not settings.abdm_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "abdm_not_configured",
                "message": "ABDM integration is not configured for this clinic. Manual registration is available.",
                "fallback": "manual_registration",
            },
        )
    raise HTTPException(status_code=501, detail="ABDM integration pending")


@router.post("/patients/register/scan-share")
def patients_register_scan_share(
    body: AbhaScanShareRequest,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    _ = body
    settings = get_settings()
    if not settings.abdm_enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "abdm_not_configured",
                "message": "ABDM integration is not configured for this clinic. Manual registration is available.",
                "fallback": "manual_registration",
            },
        )
    raise HTTPException(status_code=501, detail="ABDM integration pending")


@router.get("/patients/{patient_id}/visits/{visit_id}/vitals/required-fields")
def vitals_required_fields(
    patient_id: str,
    visit_id: str,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    visit = db.visits.find_one({"visit_id": visit_id, "patient_id": patient_id}) or {}
    complaint = str(visit.get("chief_complaint") or "general")
    cached = db.vitals_dynamic_cache.find_one({"visit_id": visit_id}, {"_id": 0})
    if cached and isinstance(cached.get("dynamic_fields"), list):
        dynamic_fields = cached.get("dynamic_fields", [])
        dynamic_fields = _enforce_chest_pain_minimum_fields(complaint, dynamic_fields)
    else:
        dynamic_fields = _generate_dynamic_vitals_with_llm(complaint)
        dynamic_fields = _enforce_chest_pain_minimum_fields(complaint, dynamic_fields)
        db.vitals_dynamic_cache.update_one(
            {"visit_id": visit_id},
            {
                "$set": {
                    "visit_id": visit_id,
                    "dynamic_fields": dynamic_fields,
                    "cached_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    return {
        "fixed_fields": FIXED_FIELDS,
        "dynamic_fields": dynamic_fields,
        "complaint_processed": complaint.lower(),
    }


@router.post("/patients/{patient_id}/visits/{visit_id}/vitals")
def vitals_save(
    request: Request,
    patient_id: str,
    visit_id: str,
    body: VitalsRequest,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    db = get_database()
    existing = db.vitals.find_one({"patient_id": patient_id, "visit_id": visit_id})
    if existing:
        raise _error(409, "vitals already recorded and immutable")
    vitals_id = f"vitals_{uuid4().hex[:12]}"
    recorded_at = _now_iso()
    payload = body.model_dump()
    db.vitals.insert_one(
        {
            "vitals_id": vitals_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            "doctor_id": doctor_id,
            "blood_pressure": payload["blood_pressure"],
            "weight": payload["weight"],
            "dynamic_values": payload.get("dynamic_values", {}),
            "recorded_at": recorded_at,
        }
    )
    db.visits.update_one(
        {"visit_id": visit_id, "patient_id": patient_id},
        {"$set": {"vitals_id": vitals_id, "vitals_recorded": True, "updated_at": datetime.now(timezone.utc)}},
    )
    _set_audit_state(request, action="vitals_captured", resource_type="visit", resource_id=visit_id, patient_id=patient_id, visit_id=visit_id)
    return {"vitals_id": vitals_id, "recorded_at": recorded_at}


@router.get("/patients/{patient_id}/visits/{visit_id}/vitals")
def vitals_get(
    patient_id: str,
    visit_id: str,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    """Return persisted vitals for this visit when already recorded."""
    _ = auth
    db = get_database()
    doc = db.vitals.find_one({"patient_id": patient_id, "visit_id": visit_id}, {"_id": 0})
    if not doc:
        raise _error(404, "vitals not found")
    return doc


@router.get("/patients/{patient_id}/visits/{visit_id}/workspace-progress")
def workspace_progress(
    patient_id: str,
    visit_id: str,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    """Summarize saved workflow artifact so clients can hydrate without redoing generation."""
    _ = auth
    db = get_database()
    internal_pid = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    vitals_doc = db.vitals.find_one({"patient_id": patient_id, "visit_id": visit_id}, {"_id": 0})
    visit_row = db.visits.find_one({"visit_id": visit_id, "patient_id": patient_id}) or {}
    vitals_recorded = bool(vitals_doc or visit_row.get("vitals_recorded"))

    session = db.visit_transcription_sessions.find_one(
        {"patient_id": internal_pid, "visit_id": visit_id}, {"_id": 0}
    )
    ts = str((session or {}).get("transcription_status") or "").lower()
    transcription_complete = ts == "completed" and bool(
        (session or {}).get("structured_dialogue") or (session or {}).get("transcript")
    )

    note = db.india_clinical_notes.find_one({"patient_id": patient_id, "visit_id": visit_id}, {"_id": 0})
    clinical_note_status: str | None = None
    if note:
        clinical_note_status = str(note.get("status") or "draft")

    recap_sent = (
        db.whatsapp_messages.count_documents(
            {
                "visit_id": visit_id,
                "patient_id": patient_id,
                "message_type": "post_visit_recap",
                "status": "queued",
            }
        )
        > 0
    )

    return {
        "vitals_recorded": vitals_recorded,
        "vitals": vitals_doc,
        "transcription_complete": transcription_complete,
        "clinical_note_status": clinical_note_status,
        "recap_sent": recap_sent,
    }


@router.post("/notes/india-clinical-note")
def notes_india_clinical(
    body: IndiaClinicalNoteRequest,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    db = get_database()
    now = datetime.now(timezone.utc)
    existing = db.india_clinical_notes.find_one({"visit_id": body.visit_id, "doctor_id": doctor_id})
    if body.status == "draft":
        note_id = str((existing or {}).get("note_id") or f"note_{uuid4().hex[:12]}")
        created_at = str((existing or {}).get("created_at") or _now_iso())
        db.india_clinical_notes.update_one(
            {"visit_id": body.visit_id, "doctor_id": doctor_id},
            {
                "$set": {
                    "note_id": note_id,
                    "visit_id": body.visit_id,
                    "patient_id": body.patient_id,
                    "doctor_id": doctor_id,
                    "transcript_id": body.transcript_id,
                    "assessment": body.assessment,
                    "plan": body.plan,
                    "rx": [item.model_dump() for item in body.rx],
                    "investigations": [item.model_dump() for item in body.investigations],
                    "red_flags": body.red_flags,
                    "follow_up": body.follow_up.model_dump(),
                    "status": "draft",
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": created_at},
            },
            upsert=True,
        )
        _set_audit_state(request, action="note_drafted", resource_type="visit", resource_id=body.visit_id, patient_id=body.patient_id, visit_id=body.visit_id)
        return {"note_id": note_id, "status": "draft", "created_at": created_at}

    if existing and str(existing.get("status")) == "approved":
        raise _error(409, "note already approved")
    if not existing:
        raise _error(404, "draft note not found")
    note_id = str(existing.get("note_id") or f"note_{uuid4().hex[:12]}")
    created_at = str(existing.get("created_at") or _now_iso())
    db.india_clinical_notes.update_one(
        {"visit_id": body.visit_id, "doctor_id": doctor_id},
        {"$set": {"status": "approved", "approved_at": now, "updated_at": now, "note_id": note_id}},
    )
    db.visits.update_one(
        {"visit_id": body.visit_id, "patient_id": body.patient_id},
        {"$set": {"note_approved": True, "note_id": note_id, "updated_at": now}},
    )
    _set_audit_state(request, action="note_approved", resource_type="visit", resource_id=body.visit_id, patient_id=body.patient_id, visit_id=body.visit_id)
    return {"note_id": note_id, "status": "approved", "created_at": created_at}


@router.get("/patients/{patient_id}/visits/{visit_id}/india-clinical-note")
def notes_india_get(
    patient_id: str,
    visit_id: str,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    doc = db.india_clinical_notes.find_one({"patient_id": patient_id, "visit_id": visit_id}, {"_id": 0})
    if not doc:
        raise _error(404, "india clinical note not found")
    return doc


@router.post("/patients/summary/postvisit")
def postvisit_summary(
    body: PostVisitSummaryRequest,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    db = get_database()
    note = db.india_clinical_notes.find_one(
        {"visit_id": body.visit_id, "doctor_id": doctor_id, "status": "approved"},
        {"_id": 0},
    )
    if not note:
        raise _error(404, "approved note not found")
    patient = db.patients.find_one({"patient_id": note.get("patient_id")}, {"_id": 0}) or {}
    doctor = db.doctors.find_one({"doctor_id": doctor_id}, {"_id": 0}) or {}
    greeting = f"Hello {patient.get('name', 'Patient')}"
    if body.language.lower().startswith("hi"):
        greeting = f"Namaskar {patient.get('name', 'Patient')}"
    whatsapp_payload = {
        "greeting": greeting,
        "diagnosis": str(note.get("assessment") or ""),
        "medicines": [
            {
                "name": item.get("name"),
                "dose": item.get("dose"),
                "timing": item.get("frequency"),
                "food_instruction": item.get("food_instruction"),
            }
            for item in note.get("rx", [])
        ],
        "tests": [
            {
                "test": item.get("test"),
                "urgency": item.get("urgency"),
                "timing": item.get("timing"),
            }
            for item in note.get("investigations", [])
        ],
        "follow_up": note.get("follow_up") or {},
        "warning_signs": note.get("red_flags") or [],
        "footer": f"— Dr. {doctor.get('name', 'Doctor')}, {(doctor.get('clinic') or {}).get('name', 'Clinic')}",
    }
    _set_audit_state(request, action="postvisit_summary_generated", resource_type="visit", resource_id=body.visit_id, visit_id=body.visit_id)
    return {"visit_id": body.visit_id, "whatsapp_payload": whatsapp_payload}


@router.post("/patients/{patient_id}/visits/{visit_id}/medication-schedule")
def medication_schedule_save(
    patient_id: str,
    visit_id: str,
    body: MedicationScheduleRequest,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    schedule_id = f"sched_{uuid4().hex[:12]}"
    db.medication_schedules.update_one(
        {"patient_id": patient_id, "visit_id": visit_id},
        {
            "$set": {
                "schedule_id": schedule_id,
                "patient_id": patient_id,
                "visit_id": visit_id,
                **body.model_dump(),
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    return {"schedule_id": schedule_id}


@router.get("/patients/{patient_id}/visits/{visit_id}/medication-schedule")
def medication_schedule_get(
    patient_id: str,
    visit_id: str,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    doc = db.medication_schedules.find_one({"patient_id": patient_id, "visit_id": visit_id}, {"_id": 0}) or {}
    return {
        "medicines": doc.get("medicines", []),
        "course_days": int(doc.get("course_days") or 7),
        "reminders_active": bool(doc.get("reminders_active", False)),
    }


@router.post("/patients/{patient_id}/visits/{visit_id}/lab-results")
def lab_results_create(
    patient_id: str,
    visit_id: str,
    body: LabResultRequest,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    lab_id = f"lab_{uuid4().hex[:12]}"
    db.lab_results.insert_one(
        {
            "lab_id": lab_id,
            "patient_id": patient_id,
            "visit_id": visit_id,
            **body.model_dump(),
            "processing_status": "pending",
        }
    )
    _set_audit_state(request, action="lab_uploaded", resource_type="lab", resource_id=lab_id, patient_id=patient_id, visit_id=visit_id)
    return {"lab_id": lab_id, "processing_status": "pending"}


@router.get("/patients/{patient_id}/visits/{visit_id}/lab-results")
def lab_results_list(
    patient_id: str,
    visit_id: str,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    rows = list(db.lab_results.find({"patient_id": patient_id, "visit_id": visit_id}, {"_id": 0}))
    mapped = [
        {
            "lab_id": r.get("lab_id"),
            "report_type": r.get("report_type", "lab"),
            "abnormal": bool(r.get("abnormal", False)),
            "values": r.get("values", []),
            "doctor_summary": r.get("doctor_summary", ""),
            "patient_explanation": r.get("patient_explanation", ""),
            "confidence_score": float(r.get("confidence_score", 0.0)),
        }
        for r in rows
    ]
    _set_audit_state(request, action="lab_viewed", resource_type="lab", resource_id=visit_id, patient_id=patient_id, visit_id=visit_id)
    return {"results": mapped}


@router.get("/patients/{patient_id}/continuity-summary")
def continuity_summary(
    patient_id: str,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    db = get_database()
    visits = [v for v in db.visits.find({"patient_id": patient_id, "doctor_id": doctor_id}, {"_id": 0})]
    visits.sort(key=lambda item: item.get("created_at"), reverse=True)
    recent_visits = visits[:5]
    if not recent_visits:
        return {
            "last_diagnosis": None,
            "current_medications": [],
            "last_lab_abnormals": [],
            "last_advice": None,
            "last_visit_date": None,
        }
    visit_ids = [str(v.get("visit_id") or "") for v in recent_visits if str(v.get("visit_id") or "")]
    approved_notes = [
        n
        for n in db.india_clinical_notes.find({"patient_id": patient_id, "doctor_id": doctor_id}, {"_id": 0})
        if str(n.get("status") or "") == "approved" and str(n.get("visit_id") or "") in visit_ids
    ]
    approved_notes.sort(key=lambda item: item.get("approved_at") or item.get("updated_at"), reverse=True)
    latest_note = approved_notes[0] if approved_notes else {}
    latest_lab = db.lab_results.find_one({"patient_id": patient_id}, sort=[("created_at", -1)]) or {}
    lab_values = latest_lab.get("values") or []
    last_lab_abnormals = [v for v in lab_values if bool((v or {}).get("abnormal"))]
    return {
        "last_diagnosis": latest_note.get("assessment"),
        "current_medications": latest_note.get("rx", []),
        "last_lab_abnormals": last_lab_abnormals,
        "last_advice": latest_note.get("plan"),
        "last_visit_date": recent_visits[0].get("created_at"),
    }


@router.get("/doctor/{doctor_id}/queue")
def doctor_queue(
    doctor_id: str,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    all_today = []
    visit_query = {
        "$or": [
            {"doctor_id": doctor_id},
            {"provider_id": doctor_id},
            {"doctor_id": ""},
            {"doctor_id": None},
            {"doctor_id": {"$exists": False}},
        ]
    }
    for v in db.visits.find(visit_query, {"_id": 0}):
        created_at = _as_utc_datetime(v.get("created_at"))
        if created_at and created_at >= start_of_day:
            all_today.append(v)
    if db.notifications.count_documents({"doctor_id": doctor_id}) == 0:
        seed = [
            {"type": "lab_ready", "title": "Lab result ready", "message": "A new lab report is ready for review."},
            {"type": "follow_up_due", "title": "Follow-up due", "message": "A patient follow-up is due today."},
            {"type": "whatsapp_failed", "title": "WhatsApp failed", "message": "A WhatsApp message failed to send."},
            {"type": "lab_ready", "title": "Lab result ready", "message": "CBC report processed and ready."},
            {"type": "follow_up_due", "title": "Follow-up due", "message": "Reminder for scheduled follow-up."},
        ]
        for idx, item in enumerate(seed):
            db.notifications.insert_one(
                {
                    "notification_id": f"notif_{uuid4().hex[:10]}",
                    "doctor_id": doctor_id,
                    "read": False,
                    "created_at": now - timedelta(minutes=idx),
                    **item,
                }
            )
    active_visits = [v for v in all_today if str(v.get("status") or "").lower() not in {"done", "completed"}]
    patients_map = {p["patient_id"]: p for p in db.patients.find({}, {"_id": 0}) if p.get("patient_id")}
    patients = []
    for v in active_visits:
        pid = str(v.get("patient_id") or "")
        p = patients_map.get(pid, {})
        token = str(v.get("token_number") or "")
        token_num = int("".join(ch for ch in token if ch.isdigit()) or "999999")
        patients.append(
            {
                "patient_id": pid,
                "visit_id": str(v.get("visit_id") or ""),
                "token_number": token,
                "name": str(p.get("name") or ""),
                "age": p.get("age"),
                "sex": p.get("sex"),
                "chief_complaint": str(v.get("chief_complaint") or p.get("chief_complaint") or ""),
                "status": str(v.get("status") or "waiting"),
                "visit_type": str(v.get("workflow_type") or ""),
                "careprep_ready": False,
                "red_flags": [],
                "_token_sort": token_num,
            }
        )
    patients.sort(key=lambda item: (0 if item["status"] == "in_consult" else 1, item["_token_sort"]))
    for item in patients:
        item.pop("_token_sort", None)
    total_today = len(all_today)
    in_consult = sum(1 for v in active_visits if str(v.get("status") or "").lower() == "in_consult")
    done = sum(1 for v in all_today if str(v.get("status") or "").lower() in {"done", "completed"})
    return {"patients": patients, "total_today": total_today, "in_consult": in_consult, "done": done}


@router.post("/whatsapp/send")
def whatsapp_send(
    body: WhatsAppSendRequest,
    request: Request,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    doctor_id = auth["doctor_id"]
    if not _is_indian_mobile(body.recipient_mobile):
        raise _error(422, "Invalid recipient mobile")
    settings = get_settings()
    db = get_database()
    status = "queued"
    template_name = ""
    if body.message_type == "post_visit_recap":
        template_name = settings.whatsapp_template_post_visit_recap
    template_variables = dict(body.template_variables or {})
    if not settings.whatsapp_api_key:
        message_id = f"dev_mock_{uuid4().hex[:12]}"
        logger.info(
            "[DEV MODE] WhatsApp send %s to %s vars=%s",
            body.message_type,
            body.recipient_mobile,
            template_variables,
        )
    else:
        if not settings.whatsapp_phone_number_id:
            raise _error(500, "WHATSAPP_PHONE_NUMBER_ID is required")
        if not template_name:
            raise _error(500, "Template is not configured for message type")
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"https://graph.facebook.com/v21.0/{settings.whatsapp_phone_number_id}/messages",
                headers={
                    "Authorization": f"Bearer {settings.whatsapp_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": body.recipient_mobile,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": "en"},
                    },
                },
            )
        if resp.status_code >= 400:
            status = "failed"
            message_id = f"wa_fail_{uuid4().hex[:10]}"
        else:
            message_id = str((resp.json().get("messages") or [{}])[0].get("id") or f"wa_{uuid4().hex[:14]}")
    db.whatsapp_messages.insert_one(
        {
            "visit_id": body.visit_id,
            "patient_id": body.patient_id,
            "doctor_id": doctor_id,
            "recipient_mobile": body.recipient_mobile,
            "language": body.language,
            "message_type": body.message_type,
            "template_variables": template_variables,
            "status": status,
            "message_id": message_id,
            "sent_at": datetime.now(timezone.utc),
        }
    )
    _set_audit_state(request, action="whatsapp_sent" if status == "queued" else "whatsapp_failed", resource_type="visit", resource_id=body.visit_id, patient_id=body.patient_id, visit_id=body.visit_id)
    return {"message_id": message_id, "status": status}


@router.get("/notifications")
def notifications_list(
    doctor_id: str,
    limit: int = 20,
    offset: int = 0,
    filter: str = "all",
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    q: dict[str, Any] = {"doctor_id": doctor_id}
    if filter != "all":
        q["type"] = filter
    rows = list(db.notifications.find(q, {"_id": 0}))
    rows.sort(key=lambda item: item.get("created_at"), reverse=True)
    rows = rows[offset : offset + limit]
    unread_count = db.notifications.count_documents({"doctor_id": doctor_id, "read": False})
    return {"notifications": rows, "unread_count": unread_count}


@router.patch("/notifications/mark-all-read")
def notifications_mark_all_read(
    body: MarkAllReadRequest,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    doctor_id = body.doctor_id.strip()
    db = get_database()
    result = db.notifications.update_many({"doctor_id": doctor_id, "read": False}, {"$set": {"read": True}})
    updated = int(getattr(result, "modified_count", 0))
    return {"updated": updated}


@router.get("/audit-log")
def audit_log_list(
    doctor_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    action: str | None = None,
    patient_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    query: dict[str, Any] = {"doctor_id": doctor_id}
    if action:
        query["action"] = action
    if patient_id:
        query["patient_id"] = patient_id
    if start_date or end_date:
        t_query: dict[str, Any] = {}
        if start_date:
            t_query["$gte"] = datetime.fromisoformat(start_date)
        if end_date:
            t_query["$lte"] = datetime.fromisoformat(end_date)
        query["timestamp"] = t_query
    total = db.audit_log.count_documents(query)
    rows = list(db.audit_log.find(query, {"_id": 0}).sort("timestamp", -1).skip(offset).limit(limit))
    return {"entries": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/audit-log/stats")
def audit_log_stats(
    doctor_id: str,
    period: str = "last_30_days",
    auth: dict[str, str] = Depends(require_contract_auth),
) -> dict[str, Any]:
    _ = auth
    db = get_database()
    start = datetime.now(timezone.utc) - timedelta(days=30)
    if period == "last_7_days":
        start = datetime.now(timezone.utc) - timedelta(days=7)
    cursor = db.audit_log.aggregate(
        [
            {"$match": {"doctor_id": doctor_id, "timestamp": {"$gte": start}}},
            {"$group": {"_id": "$action", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
    )
    return {"period": period, "counts": [{"action": item["_id"], "count": item["count"]} for item in cursor]}


@router.get("/audit-log/export")
def audit_log_export(
    doctor_id: str,
    format: str = "csv",
    auth: dict[str, str] = Depends(require_contract_auth),
):
    _ = auth
    if format.lower() != "csv":
        raise _error(400, "only csv export is supported")
    db = get_database()
    rows = list(db.audit_log.find({"doctor_id": doctor_id}, {"_id": 0}).sort("timestamp", -1))
    header = "entry_id,doctor_id,patient_id,visit_id,action,resource_type,resource_id,ip_address,user_agent,timestamp\n"
    lines = [header]
    for row in rows:
        lines.append(
            ",".join(
                [
                    str(row.get("entry_id", "")),
                    str(row.get("doctor_id", "")),
                    str(row.get("patient_id", "")),
                    str(row.get("visit_id", "")),
                    str(row.get("action", "")),
                    str(row.get("resource_type", "")),
                    str(row.get("resource_id", "")),
                    str(row.get("ip_address", "")),
                    str(row.get("user_agent", "")).replace(",", " "),
                    str(row.get("timestamp", "")),
                ]
            )
            + "\n"
        )
    return PlainTextResponse("".join(lines), media_type="text/csv")
