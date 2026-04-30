"""ContextAI compatibility routes for provider visit sidebar cards."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from src.adapters.db.mongo.client import get_database
from src.application.utils.patient_id_crypto import encode_patient_id, resolve_internal_patient_id

router = APIRouter(prefix="/api/contextai", tags=["ContextAI"])


def _get_patient_or_404(patient_id: str) -> dict:
    db = get_database()
    patient = db.patients.find_one({"patient_id": patient_id}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


def _pick_visit_id(patient_id: str, visit_id: str | None) -> str | None:
    if visit_id:
        return visit_id
    db = get_database()
    latest_visit = db.visits.find_one({"patient_id": patient_id}, sort=[("created_at", -1)])
    return str(latest_visit.get("visit_id")) if latest_visit and latest_visit.get("visit_id") else None


def _get_latest_intake(patient_id: str, visit_id: str | None) -> dict | None:
    db = get_database()
    query: dict = {"patient_id": patient_id}
    if visit_id:
        query["visit_id"] = visit_id
    return db.intake_sessions.find_one(query, sort=[("updated_at", -1)])


def _get_latest_previsit(patient_id: str, visit_id: str | None) -> dict | None:
    db = get_database()
    query: dict = {"patient_id": patient_id}
    if visit_id:
        query["visit_id"] = visit_id
    return db.pre_visit_summaries.find_one(query, sort=[("updated_at", -1)])


def _extract_chief_complaint(previsit: dict | None, intake: dict | None) -> str | None:
    if previsit:
        sections = previsit.get("sections") or {}
        chief = (sections.get("chief_complaint") or {}).get("reason_for_visit")
        if chief:
            return str(chief)
    if intake:
        illness = intake.get("illness")
        if illness:
            return str(illness)
        answers = intake.get("answers") or []
        for answer in answers:
            if str(answer.get("question", "")).lower() == "illness" and answer.get("answer"):
                return str(answer.get("answer"))
    return None


def _extract_medications(previsit: dict | None, intake: dict | None) -> list[dict]:
    medications: list[dict] = []
    meds_text = None
    if previsit:
        sections = previsit.get("sections") or {}
        meds_text = (sections.get("current_medication") or {}).get("medications_or_home_remedies")
    if not meds_text and intake:
        for answer in intake.get("answers", []):
            question = str(answer.get("question", "")).lower()
            if "medication" in question or "medicine" in question:
                meds_text = answer.get("answer")
                if meds_text:
                    break
    if not meds_text:
        return medications

    chunks = [part.strip() for part in str(meds_text).replace("\n", ",").split(",")]
    cleaned = [part for part in chunks if part and part.lower() not in {"none", "not provided", "na", "n/a"}]
    for idx, med in enumerate(cleaned):
        medications.append(
            {
                "medication_id": f"intake-med-{idx + 1}",
                "name": med,
                "dosage": "As reported",
                "frequency": "Not specified",
                "route": "oral",
                "start_date": datetime.now(timezone.utc).date().isoformat(),
                "status": "active",
                "prescriber": "Self-reported",
                "indication": "From intake form",
            }
        )
    return medications


@router.get("/context/{patient_id}")
def get_patient_context(patient_id: str, visit_id: str | None = Query(default=None)) -> dict:
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    opaque_patient_id = encode_patient_id(internal_patient_id)
    patient = _get_patient_or_404(internal_patient_id)
    resolved_visit_id = _pick_visit_id(internal_patient_id, visit_id)
    intake = _get_latest_intake(internal_patient_id, resolved_visit_id)
    previsit = _get_latest_previsit(internal_patient_id, resolved_visit_id)
    chief_complaint = _extract_chief_complaint(previsit, intake)
    has_intake_responses = bool((intake or {}).get("answers"))
    triage_level = (previsit or {}).get("triage_level")
    urgency = (previsit or {}).get("urgency")
    last_response_date = (previsit or {}).get("updated_at") or (intake or {}).get("updated_at")
    name = str(patient.get("name") or "").strip()
    parts = [p for p in name.split(" ") if p]
    first_name = parts[0] if parts else "Unknown"
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    age = patient.get("age")
    birth_year = datetime.now(timezone.utc).year - age if isinstance(age, int) and age > 0 else 1970

    return {
        "patient_id": opaque_patient_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_sources": ["patients"],
        "demographics": {
            "patient_id": opaque_patient_id,
            "mrn": str(patient.get("mrn") or internal_patient_id),
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": str(patient.get("date_of_birth") or f"{birth_year:04d}-01-01"),
            "age": int(age) if isinstance(age, int) else 0,
            "gender": str(patient.get("gender") or "unknown"),
            "phone": patient.get("phone_number"),
            "email": str(patient.get("email") or ""),
            "address": {
                "street": "",
                "city": "",
                "state": "",
                "zip_code": "",
            },
            "emergency_contact": {
                "name": "",
                "phone": "",
            },
        },
        "medical_history": {},
        "previsit": {
            "has_responses": has_intake_responses,
            "last_response_date": last_response_date.isoformat() if hasattr(last_response_date, "isoformat") else None,
            "chief_complaint": chief_complaint,
            "triage_level": triage_level,
            "urgency": urgency,
        },
        "summary": {
            "has_data": True,
            "data_completeness": 85.0 if has_intake_responses else 60.0,
            "alerts": [],
            "highlights": [
                "ContextAI profile connected",
                "Intake responses synced" if has_intake_responses else "Waiting for intake responses",
            ],
        },
    }


@router.get("/risk-assessment/{patient_id}")
def get_risk_assessment(patient_id: str) -> dict:
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    _get_patient_or_404(internal_patient_id)
    return {
        "patient_id": encode_patient_id(internal_patient_id),
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "overall_risk_level": "moderate",
        "risk_scores": [
            {
                "risk_type": "general",
                "score": 45,
                "category": "moderate",
                "factors": ["Age and routine clinical profile"],
                "recommendations": ["Review vitals and recent history during visit"],
            }
        ],
    }


@router.get("/care-gaps/{patient_id}")
def get_care_gaps(patient_id: str) -> dict:
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    _get_patient_or_404(internal_patient_id)
    return {
        "patient_id": encode_patient_id(internal_patient_id),
        "gaps": [],
        "total_gaps": 0,
        "high_priority_count": 0,
        "overdue_count": 0,
    }


@router.get("/medication-review/{patient_id}")
def get_medication_review(patient_id: str, visit_id: str | None = Query(default=None)) -> dict:
    internal_patient_id = resolve_internal_patient_id(patient_id, allow_raw_fallback=True)
    _get_patient_or_404(internal_patient_id)
    resolved_visit_id = _pick_visit_id(internal_patient_id, visit_id)
    intake = _get_latest_intake(internal_patient_id, resolved_visit_id)
    previsit = _get_latest_previsit(internal_patient_id, resolved_visit_id)
    medications = _extract_medications(previsit, intake)
    return {
        "patient_id": encode_patient_id(internal_patient_id),
        "medications": medications,
        "interactions": [],
        "allergies": [],
        "total_medications": len(medications),
        "interaction_count": 0,
        "severe_interaction_count": 0,
    }
