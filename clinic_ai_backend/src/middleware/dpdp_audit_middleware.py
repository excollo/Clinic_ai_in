"""DPDP audit middleware for authenticated API requests."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
import logging

from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware

from src.adapters.db.mongo.client import get_database
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class DPDPAuditMiddleware(BaseHTTPMiddleware):
    """Persist audit entries for authenticated request/response cycles."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        api_key = request.headers.get("X-API-Key")
        doctor_id = request.headers.get("X-Doctor-ID")
        if not api_key or not doctor_id:
            return response

        settings = get_settings()
        try:
            payload = jwt.decode(api_key, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        except JWTError:
            return response

        if payload.get("doctor_id") != doctor_id:
            return response

        action = getattr(request.state, "audit_action", None)
        if not action:
            logger.warning("DPDP audit fallback used for %s %s", request.method, request.url.path)
            action = "api_access"
        resource_type = getattr(request.state, "audit_resource_type", "endpoint")
        resource_id = getattr(request.state, "audit_resource_id", request.url.path)
        patient_id = getattr(request.state, "audit_patient_id", None)
        visit_id = getattr(request.state, "audit_visit_id", None)
        audit_status = getattr(request.state, "audit_status", "success" if response.status_code < 400 else "failure")
        audit_context = getattr(request.state, "audit_context", {})

        db = get_database()
        try:
            db.audit_log.insert_one(
                {
                    "entry_id": f"audit_{uuid4().hex[:16]}",
                    "doctor_id": doctor_id,
                    "patient_id": patient_id,
                    "visit_id": visit_id,
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": str(resource_id),
                    "ip_address": request.client.host if request.client else "",
                    "user_agent": request.headers.get("user-agent", ""),
                    "timestamp": datetime.now(timezone.utc),
                    "status_code": response.status_code,
                    "audit_status": audit_status,
                    "additional_context": {
                        "path": request.url.path,
                        "method": request.method,
                        **(audit_context if isinstance(audit_context, dict) else {}),
                    },
                }
            )
        except AttributeError:
            # Test doubles may not expose audit_log collection.
            pass
        return response

