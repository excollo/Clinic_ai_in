"""FastAPI application factory module.

Canonical backend ASGI entry point:
`uvicorn src.app:create_app --reload --factory`
"""
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import (
    auth,
    contextai,
    frontend_contract,
    followthrough,
    health,
    internal_audio,
    notes,
    patient_chat,
    patients,
    templates,
    transcription,
    visits,
    vitals,
    whatsapp,
    workflow,
)
from src.middleware.dpdp_audit_middleware import DPDPAuditMiddleware
from src.core.config import get_settings
from src.workers.transcription_worker import start_background_workers, stop_background_workers


def _build_cors_origins() -> list[str]:
    """Merge configured origins with safe local-development defaults."""
    configured = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    # Keep localhost/loopback available for local frontend testing even when
    # Render env sets CORS_ORIGINS to production domains only.
    dev_defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
    merged: list[str] = []
    for origin in [*configured, *dev_defaults]:
        if origin not in merged:
            merged.append(origin)
    return merged


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start/stop background transcription workers with app lifecycle."""
    settings = get_settings()
    if settings.run_transcription_workers_in_api:
        start_background_workers()
    try:
        yield
    finally:
        if settings.run_transcription_workers_in_api:
            await stop_background_workers()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(title="Clinic AI India Backend", version="0.1.0", lifespan=lifespan)
    cors_origins = _build_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(DPDPAuditMiddleware)
    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(internal_audio.router)
    app.include_router(patients.router)
    app.include_router(vitals.router)
    app.include_router(whatsapp.router)
    app.include_router(workflow.router)
    app.include_router(transcription.router)
    app.include_router(visits.router)
    app.include_router(patient_chat.router)
    app.include_router(contextai.router)
    app.include_router(frontend_contract.router)
    app.include_router(templates.router)
    app.include_router(notes.router)
    app.include_router(followthrough.router)
    return app


app = create_app()
