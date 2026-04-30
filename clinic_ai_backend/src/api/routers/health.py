"""Health routes module."""
from datetime import datetime, timezone
import socket

from fastapi import APIRouter

from src.adapters.db.mongo.client import get_database
from src.core.config import get_settings

router = APIRouter(prefix="/health", tags=["Health"])


def _check_mongodb() -> str:
    try:
        db = get_database()
        db.command("ping")
        return "connected"
    except Exception:
        return "disconnected"


def _check_azure_speech() -> str:
    settings = get_settings()
    if not settings.azure_speech_key or not (settings.azure_speech_region or settings.azure_speech_endpoint):
        return "not_configured"
    host = (
        settings.azure_speech_endpoint.replace("https://", "").replace("http://", "").split("/")[0]
        if settings.azure_speech_endpoint
        else f"{settings.azure_speech_region}.stt.speech.microsoft.com"
    )
    try:
        socket.gethostbyname(host)
        return "reachable"
    except OSError:
        return "unreachable"


def _check_azure_queue() -> str:
    settings = get_settings()
    if not settings.azure_queue_connection_string or not settings.azure_queue_name or not settings.azure_queue_poison_name:
        return "not_configured"
    return "configured"


def _check_azure_blob() -> str:
    settings = get_settings()
    if not settings.azure_blob_connection_string or not settings.azure_blob_container:
        return "not_configured"
    return "configured"


def _worker_heartbeat() -> dict:
    settings = get_settings()
    try:
        db = get_database()
        row = db.worker_heartbeats.find_one(sort=[("updated_at", -1)])
        if not row:
            return {"status": "missing", "last_heartbeat": None}
        last = row.get("updated_at")
        if not isinstance(last, datetime):
            return {"status": "missing", "last_heartbeat": None}
        now = datetime.now(timezone.utc)
        last_utc = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        age = (now - last_utc).total_seconds()
        return {
            "status": "alive" if age <= settings.transcription_worker_dead_after_sec else "stale",
            "last_heartbeat": last_utc.isoformat(),
        }
    except Exception:
        return {"status": "unknown", "last_heartbeat": None}


@router.get("")
def health() -> dict:
    """Health check endpoint with dependency and worker state."""
    settings = get_settings()
    worker = _worker_heartbeat()

    return {
        "status": "ok",
        "mongodb": _check_mongodb(),
        "azure_speech": _check_azure_speech(),
        "azure_queue": _check_azure_queue(),
        "azure_blob": _check_azure_blob(),
        "worker_status": worker["status"],
        "worker_last_heartbeat": worker["last_heartbeat"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": settings.app_version,
    }
