"""Generate legacy SOAP note use case."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.repositories.audio_repository import AudioRepository
from src.adapters.db.mongo.repositories.clinical_note_repository import ClinicalNoteRepository
from src.adapters.services.soap_generation_service import SoapGenerationService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GenerateSoapNoteUseCase:
    """Minimal SOAP generation for backward compatibility endpoint."""

    def __init__(self) -> None:
        self.db = get_database()
        self.audio_repo = AudioRepository()
        self.note_repo = ClinicalNoteRepository()
        self.service = SoapGenerationService()

    def execute(
        self,
        *,
        patient_id: str,
        visit_id: str | None = None,
        transcription_job_id: str | None = None,
    ) -> dict:
        """Generate and persist a minimal legacy SOAP note."""
        if transcription_job_id:
            job = self.audio_repo.get_job(transcription_job_id)
        else:
            query: dict[str, object] = {"patient_id": patient_id, "status": "completed"}
            if visit_id:
                query["visit_id"] = visit_id
            job = self.db.transcription_jobs.find_one(
                query,
                sort=[("completed_at", -1), ("updated_at", -1)],
            )
        if not job:
            raise ValueError("No completed transcription job found for SOAP generation")
        if visit_id and str(job.get("visit_id") or "") != str(visit_id):
            raise ValueError("Transcription job does not belong to this visit")
        transcript = self.audio_repo.get_result(str(job.get("job_id"))) or {}
        effective_visit = visit_id or job.get("visit_id")
        if effective_visit:
            previsit = (
                self.db.pre_visit_summaries.find_one(
                    {"patient_id": patient_id, "visit_id": effective_visit},
                    sort=[("updated_at", -1)],
                )
                or {}
            )
        else:
            previsit = self.db.pre_visit_summaries.find_one({"patient_id": patient_id}, sort=[("updated_at", -1)]) or {}
        chief = ((previsit.get("sections") or {}).get("chief_complaint") or {}).get("reason_for_visit")
        soap_payload = self.service.generate(
            transcript_text=str(transcript.get("full_transcript_text", "") or ""),
            chief_complaint=chief,
        )
        india_compatible_payload = {
            "assessment": soap_payload.get("assessment", ""),
            "plan": soap_payload.get("plan", ""),
            "rx": [],
            "investigations": [],
            "red_flags": [],
            "follow_up_in": "7 days",
            "follow_up_date": None,
            "doctor_notes": (
                f"subjective: {soap_payload.get('subjective', '')}\n"
                f"objective: {soap_payload.get('objective', '')}"
            ).strip(),
            "chief_complaint": chief,
            "data_gaps": [],
        }
        version = self._next_version(patient_id=patient_id, visit_id=visit_id, note_type="soap")
        note_doc = {
            "note_id": str(uuid4()),
            "patient_id": patient_id,
            "visit_id": visit_id or job.get("visit_id"),
            "note_type": "soap",
            "source_job_id": str(job.get("job_id")),
            "status": "fallback_generated",
            "version": version,
            "created_at": _utc_now(),
            "payload": india_compatible_payload,
            "legacy": True,
        }
        created = self.note_repo.create_note(note_doc)
        created.pop("_id", None)
        return created

    def _next_version(self, *, patient_id: str, visit_id: str | None, note_type: str) -> int:
        latest = self.note_repo.find_latest(patient_id=patient_id, visit_id=visit_id, note_type=note_type)
        if not latest:
            return 1
        return int(latest.get("version", 1)) + 1
