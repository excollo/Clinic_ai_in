"""Template library routes for clinical note snippets."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from src.adapters.db.mongo.client import get_database
from src.api.schemas.templates import (
    CreateTemplateRequest,
    ListTemplatesResponse,
    OkResponse,
    RecordTemplateUsageRequest,
    TemplateResponse,
    ToggleTemplateFavoriteResponse,
    UpdateTemplateRequest,
)

router = APIRouter(prefix="/api/templates", tags=["Templates"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    data = dict(doc)
    data.pop("_id", None)
    raw_content = dict(data.get("content") or {})
    data["content"] = {
        "assessment": str(raw_content.get("assessment") or ""),
        "plan": str(raw_content.get("plan") or ""),
        "rx": list(raw_content.get("rx") or []),
        "investigations": list(raw_content.get("investigations") or []),
        "red_flags": list(raw_content.get("red_flags") or []),
        "follow_up_in": str(raw_content.get("follow_up_in") or ""),
        "follow_up_date": str(raw_content.get("follow_up_date") or ""),
        # Backward compatibility with older SOAP template structure.
        "doctor_notes": str(raw_content.get("doctor_notes") or raw_content.get("subjective") or ""),
        "chief_complaint": str(raw_content.get("chief_complaint") or raw_content.get("objective") or ""),
        "data_gaps": list(raw_content.get("data_gaps") or []),
    }
    return data


@router.post("", response_model=TemplateResponse)
def create_template(body: CreateTemplateRequest) -> TemplateResponse:
    db = get_database()
    now = _utc_now()
    template_id = str(uuid4())
    payload = body.model_dump()
    doc = {
        "id": template_id,
        "name": str(payload.get("name") or "").strip(),
        "description": str(payload.get("description") or "").strip(),
        "type": str(payload.get("type") or "personal").strip() or "personal",
        "category": str(payload.get("category") or "General").strip() or "General",
        "specialty": str(payload.get("specialty") or "").strip(),
        "content": dict(payload.get("content") or {}),
        "tags": list(payload.get("tags") or []),
        "appointment_types": list(payload.get("appointment_types") or []),
        "is_favorite": bool(payload.get("is_favorite") or False),
        "author_id": str(payload.get("author_id") or "current_user"),
        "author_name": str(payload.get("author_name") or "You"),
        "usage_count": 0,
        "last_used": None,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
    if not doc["name"]:
        raise HTTPException(status_code=422, detail="Template name is required")
    db.templates.insert_one(doc)
    return TemplateResponse(**_serialize(doc))


@router.get("", response_model=ListTemplatesResponse)
def list_templates(
    type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    specialty: str | None = Query(default=None),
    search: str | None = Query(default=None),
    is_favorite: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> ListTemplatesResponse:
    db = get_database()
    query: dict[str, Any] = {"is_active": {"$ne": False}}
    if type:
        query["type"] = type
    if category:
        query["category"] = category
    if specialty:
        query["specialty"] = specialty
    if is_favorite is not None:
        query["is_favorite"] = is_favorite
    if search and search.strip():
        s = search.strip()
        query["$or"] = [
            {"name": {"$regex": s, "$options": "i"}},
            {"description": {"$regex": s, "$options": "i"}},
            {"tags": {"$elemMatch": {"$regex": s, "$options": "i"}}},
        ]

    skip = (page - 1) * page_size
    cursor = db.templates.find(query).sort("updated_at", -1).skip(skip).limit(page_size)
    items = [_serialize(dict(item)) for item in cursor]
    total = db.templates.count_documents(query)
    return ListTemplatesResponse(
        items=[TemplateResponse(**item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(template_id: str) -> TemplateResponse:
    db = get_database()
    doc = db.templates.find_one({"id": template_id, "is_active": {"$ne": False}})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse(**_serialize(dict(doc)))


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(template_id: str, body: UpdateTemplateRequest) -> TemplateResponse:
    db = get_database()
    existing = db.templates.find_one({"id": template_id, "is_active": {"$ne": False}})
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    patch = body.model_dump(exclude_none=True)
    patch["updated_at"] = _utc_now()
    db.templates.update_one({"id": template_id}, {"$set": patch})
    updated = db.templates.find_one({"id": template_id})
    return TemplateResponse(**_serialize(dict(updated or {})))


@router.delete("/{template_id}", response_model=OkResponse)
def delete_template(template_id: str) -> OkResponse:
    db = get_database()
    result = db.templates.update_one({"id": template_id}, {"$set": {"is_active": False, "updated_at": _utc_now()}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return OkResponse(ok=True)


@router.post("/{template_id}/use", response_model=OkResponse)
def record_template_usage(template_id: str, body: RecordTemplateUsageRequest | None = None) -> OkResponse:
    db = get_database()
    now = _utc_now()
    result = db.templates.update_one(
        {"id": template_id, "is_active": {"$ne": False}},
        {"$inc": {"usage_count": 1}, "$set": {"last_used": now, "updated_at": now}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    if body is not None:
        payload = body.model_dump()
        db.template_usage_events.insert_one(
            {
                "template_id": template_id,
                "visit_id": payload.get("visit_id"),
                "patient_id": payload.get("patient_id"),
                "created_at": now,
            }
        )
    return OkResponse(ok=True)


@router.post("/{template_id}/favorite", response_model=ToggleTemplateFavoriteResponse)
def toggle_template_favorite(template_id: str) -> ToggleTemplateFavoriteResponse:
    db = get_database()
    doc = db.templates.find_one({"id": template_id, "is_active": {"$ne": False}})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    next_value = not bool(doc.get("is_favorite"))
    db.templates.update_one({"id": template_id}, {"$set": {"is_favorite": next_value, "updated_at": _utc_now()}})
    return ToggleTemplateFavoriteResponse(id=template_id, is_favorite=next_value)
