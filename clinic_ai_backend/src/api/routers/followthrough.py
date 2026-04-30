"""Follow-through and lab pipeline routes."""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from urllib import request
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from src.adapters.db.mongo.client import get_database
from src.core.config import get_settings
from src.application.utils.patient_id_crypto import encode_patient_id

router = APIRouter(prefix="/api/follow-through", tags=["Follow-through"])


class CreateLabRecordRequest(BaseModel):
    visit_id: str = Field(min_length=1)
    source: str = Field(default="whatsapp", min_length=1, max_length=50)
    raw_text: str = Field(min_length=1)


class ReviewLabRecordRequest(BaseModel):
    decision: str = Field(default="approved", min_length=1, max_length=50)
    notes: str | None = None


class ContinuityUpdateRequest(BaseModel):
    continuity_summary: str = Field(min_length=1)
    mark_visit_completed: bool = True


def _to_iso(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _extract_numeric_flags(raw_text: str) -> tuple[list[dict], list[str]]:
    values: list[dict] = []
    flags: list[str] = []
    for match in re.finditer(r"([A-Za-z ]{2,30})[:= -]*([0-9]+(?:\.[0-9]+)?)", raw_text):
        label = re.sub(r"\s+", " ", match.group(1)).strip()
        value = float(match.group(2))
        values.append({"label": label, "value": value})
        lowered = label.lower()
        if ("glucose" in lowered or "sugar" in lowered) and value > 200:
            flags.append(f"{label} high ({value})")
        if ("oxygen" in lowered or "spo2" in lowered) and value < 92:
            flags.append(f"{label} low ({value})")
    return values, flags


def _public_lab_record(doc: dict) -> dict:
    patient_id = str(doc.get("patient_id") or "")
    return {
        "record_id": str(doc.get("record_id") or ""),
        "visit_id": str(doc.get("visit_id") or ""),
        "patient_id": encode_patient_id(patient_id) if patient_id else "",
        "source": str(doc.get("source") or "whatsapp"),
        "status": str(doc.get("status") or "received"),
        "raw_text": str(doc.get("raw_text") or ""),
        "ocr_text": str(doc.get("ocr_text") or ""),
        "image_count": int(doc.get("image_count") or 0),
        "extracted_values": doc.get("extracted_values") or [],
        "flags": doc.get("flags") or [],
        "doctor_decision": doc.get("doctor_decision"),
        "doctor_notes": doc.get("doctor_notes"),
        "continuity_summary": doc.get("continuity_summary"),
        "created_at": _to_iso(doc.get("created_at")),
        "updated_at": _to_iso(doc.get("updated_at")),
    }


def _find_visit_for_follow_through(raw_visit_id: str) -> dict | None:
    """Resolve a visit from common ID variants entered by staff."""
    db = get_database()
    normalized = str(raw_visit_id or "").strip()
    if not normalized:
        return None

    direct = (
        db.visits.find_one({"visit_id": normalized})
        or db.visits.find_one({"id": normalized})
        or db.visits.find_one({"appointment_id": normalized})
    )
    if direct:
        return direct

    normalized_lower = normalized.lower()
    for visit in db.visits.find({}):
        for key in ("visit_id", "id", "appointment_id"):
            candidate = str(visit.get(key) or "").strip()
            if candidate and candidate.lower() == normalized_lower:
                return visit
    return None


def _ocr_images_with_openai(image_payloads: list[tuple[bytes, str]]) -> str:
    """Best-effort OCR using OpenAI vision; returns merged plain text."""
    settings = get_settings()
    if not settings.openai_api_key or not image_payloads:
        return ""

    extracted_parts: list[str] = []
    for image_bytes, mime_type in image_payloads:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": settings.openai_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Read this lab report image and return only extracted text lines "
                                "with numbers/units exactly as visible. No explanation."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                    ],
                }
            ],
            "temperature": 0,
        }
        req = request.Request(
            url="https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = str(body["choices"][0]["message"]["content"] or "").strip()
            if text:
                extracted_parts.append(text)
    return "\n\n".join(extracted_parts).strip()


@router.post("/lab-records")
def create_lab_record(payload: CreateLabRecordRequest) -> dict:
    db = get_database()
    visit = _find_visit_for_follow_through(payload.visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    now = datetime.now(timezone.utc)
    record = {
        "record_id": f"LAB-{uuid4()}",
        "visit_id": str(visit.get("visit_id") or visit.get("id") or payload.visit_id),
        "patient_id": str(visit.get("patient_id") or ""),
        "source": payload.source,
        "status": "received",
        "raw_text": payload.raw_text,
        "extracted_values": [],
        "flags": [],
        "doctor_decision": None,
        "doctor_notes": None,
        "continuity_summary": None,
        "created_at": now,
        "updated_at": now,
    }
    db.follow_through_lab_records.insert_one(record)
    return _public_lab_record(record)


@router.post("/lab-records/with-images")
async def create_lab_record_with_images(
    visit_id: str = Form(...),
    source: str = Form(default="whatsapp"),
    raw_text: str = Form(default=""),
    image_files: list[UploadFile] = File(default=[]),
) -> dict:
    db = get_database()
    visit = _find_visit_for_follow_through(visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")

    image_payloads: list[tuple[bytes, str]] = []
    for image_file in image_files:
        mime_type = str(image_file.content_type or "").strip().lower()
        if not mime_type.startswith("image/"):
            continue
        payload = await image_file.read()
        if payload:
            image_payloads.append((payload, mime_type))

    ocr_text = ""
    if image_payloads:
        try:
            ocr_text = _ocr_images_with_openai(image_payloads)
        except Exception:
            ocr_text = ""

    merged_raw_text = str(raw_text or "").strip()
    if ocr_text:
        merged_raw_text = f"{merged_raw_text}\n\n{ocr_text}".strip() if merged_raw_text else ocr_text

    now = datetime.now(timezone.utc)
    record = {
        "record_id": f"LAB-{uuid4()}",
        "visit_id": str(visit.get("visit_id") or visit.get("id") or visit_id),
        "patient_id": str(visit.get("patient_id") or ""),
        "source": source,
        "status": "received",
        "raw_text": merged_raw_text,
        "ocr_text": ocr_text,
        "image_count": len(image_payloads),
        "extracted_values": [],
        "flags": [],
        "doctor_decision": None,
        "doctor_notes": None,
        "continuity_summary": None,
        "created_at": now,
        "updated_at": now,
    }
    db.follow_through_lab_records.insert_one(record)
    return _public_lab_record(record)


@router.get("/lab-queue")
def list_lab_queue(status: str | None = Query(default=None)) -> dict:
    db = get_database()
    query: dict = {}
    if status:
        query["status"] = status
    records = list(db.follow_through_lab_records.find(query, {"_id": 0}))
    records.sort(key=lambda item: item.get("updated_at") or item.get("created_at") or datetime.min, reverse=True)
    return {"items": [_public_lab_record(item) for item in records]}


@router.post("/lab-records/{record_id}/extract")
def extract_lab_record(record_id: str) -> dict:
    db = get_database()
    record = db.follow_through_lab_records.find_one({"record_id": record_id})
    if not record:
        raise HTTPException(status_code=404, detail="Lab record not found")

    source_text = str(record.get("raw_text") or "").strip()
    if not source_text and str(record.get("ocr_text") or "").strip():
        source_text = str(record.get("ocr_text") or "").strip()
    values, flags = _extract_numeric_flags(source_text)
    db.follow_through_lab_records.update_one(
        {"record_id": record_id},
        {
            "$set": {
                "status": "extracted",
                "extracted_values": values,
                "flags": flags,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    updated = db.follow_through_lab_records.find_one({"record_id": record_id}) or {}
    return _public_lab_record(updated)


@router.post("/lab-records/{record_id}/review")
def review_lab_record(record_id: str, payload: ReviewLabRecordRequest) -> dict:
    db = get_database()
    record = db.follow_through_lab_records.find_one({"record_id": record_id})
    if not record:
        raise HTTPException(status_code=404, detail="Lab record not found")

    decision = payload.decision.strip().lower()
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="decision must be approved or rejected")
    status_value = "doctor_reviewed" if decision == "approved" else "review_rejected"
    db.follow_through_lab_records.update_one(
        {"record_id": record_id},
        {
            "$set": {
                "status": status_value,
                "doctor_decision": decision,
                "doctor_notes": payload.notes,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    updated = db.follow_through_lab_records.find_one({"record_id": record_id}) or {}
    return _public_lab_record(updated)


@router.post("/lab-records/{record_id}/continuity-update")
def update_continuity(record_id: str, payload: ContinuityUpdateRequest) -> dict:
    db = get_database()
    record = db.follow_through_lab_records.find_one({"record_id": record_id})
    if not record:
        raise HTTPException(status_code=404, detail="Lab record not found")

    now = datetime.now(timezone.utc)
    db.follow_through_lab_records.update_one(
        {"record_id": record_id},
        {"$set": {"status": "continuity_updated", "continuity_summary": payload.continuity_summary, "updated_at": now}},
    )
    if payload.mark_visit_completed:
        visit_id = str(record.get("visit_id") or "")
        if visit_id:
            db.visits.update_one(
                {"visit_id": visit_id},
                {"$set": {"status": "completed", "actual_end": now, "updated_at": now}},
            )
            db.visits.update_one(
                {"id": visit_id},
                {"$set": {"status": "completed", "actual_end": now, "updated_at": now}},
            )

    updated = db.follow_through_lab_records.find_one({"record_id": record_id}) or {}
    return _public_lab_record(updated)
