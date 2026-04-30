"""Generate India clinical note use case."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from uuid import uuid4

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.repositories.audio_repository import AudioRepository
from src.adapters.db.mongo.repositories.clinical_note_repository import ClinicalNoteRepository
from src.adapters.external.ai.openai_client import OpenAIQuestionClient
from src.core.config import get_settings


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GenerateIndiaClinicalNoteUseCase:
    """Compose context, generate note payload, persist clinical note."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_database()
        self.audio_repo = AudioRepository()
        self.note_repo = ClinicalNoteRepository()
        self.openai = OpenAIQuestionClient()

    def execute(
        self,
        *,
        patient_id: str,
        visit_id: str | None = None,
        transcription_job_id: str | None = None,
        force_regenerate: bool = False,
        follow_up_date: date | None = None,
    ) -> dict:
        """Generate India note and save as canonical default artifact."""
        job = self._resolve_transcription_job(
            patient_id=patient_id,
            visit_id=visit_id,
            transcription_job_id=transcription_job_id,
        )
        source_job_id = str(job.get("job_id"))
        if not force_regenerate:
            existing = self.note_repo.find_by_source_job(
                source_job_id=source_job_id,
                note_type="india_clinical",
            )
            if existing:
                existing.pop("_id", None)
                return existing

        context = self._build_context(patient_id=patient_id, visit_id=visit_id, job=job)
        if follow_up_date is not None:
            context["staff_confirmed_follow_up_date"] = follow_up_date.isoformat()
        payload = self._generate_payload(context)
        if follow_up_date is not None:
            payload["follow_up_date"] = follow_up_date.isoformat()
            payload["follow_up_in"] = None
            payload = self._normalize_payload(payload, context=context)
        version = self._next_version(patient_id=patient_id, visit_id=visit_id, note_type="india_clinical")
        note_doc = {
            "note_id": str(uuid4()),
            "patient_id": patient_id,
            "visit_id": visit_id or job.get("visit_id"),
            "note_type": "india_clinical",
            "source_job_id": source_job_id,
            "status": "generated",
            "version": version,
            "created_at": _utc_now(),
            "payload": payload,
        }
        created = self.note_repo.create_note(note_doc)
        created.pop("_id", None)
        return created

    def _resolve_transcription_job(
        self,
        *,
        patient_id: str,
        visit_id: str | None,
        transcription_job_id: str | None,
    ) -> dict:
        if transcription_job_id:
            job = self.audio_repo.get_job(transcription_job_id)
            if not job:
                session = self.db.visit_transcription_sessions.find_one(
                    {"patient_id": patient_id, "visit_id": visit_id},
                    sort=[("updated_at", -1)],
                )
                if session and str(session.get("transcription_status") or "").lower() == "completed":
                    session_job_id = str(session.get("job_id") or "").strip()
                    if session_job_id:
                        job = {
                            "job_id": session_job_id,
                            "patient_id": patient_id,
                            "visit_id": visit_id,
                            "status": "completed",
                            "_session_transcript": str(session.get("transcript") or ""),
                        }
        else:
            query: dict[str, object] = {"patient_id": patient_id, "status": "completed"}
            if visit_id:
                query["visit_id"] = visit_id
            job = self.db.transcription_jobs.find_one(
                query,
                sort=[("completed_at", -1), ("updated_at", -1)],
            )
            if not job:
                session = self.db.visit_transcription_sessions.find_one(
                    {"patient_id": patient_id, "visit_id": visit_id},
                    sort=[("updated_at", -1)],
                )
                if session and str(session.get("transcription_status") or "").lower() == "completed":
                    session_job_id = str(session.get("job_id") or "").strip() or str(session.get("transcription_id") or "").strip()
                    if session_job_id:
                        job = {
                            "job_id": session_job_id,
                            "patient_id": patient_id,
                            "visit_id": visit_id,
                            "status": "completed",
                            "_session_transcript": str(session.get("transcript") or ""),
                        }
        if not job:
            raise ValueError("No completed transcription job found")
        if str(job.get("patient_id")) != patient_id:
            raise ValueError("Transcription job does not belong to patient")
        if visit_id and str(job.get("visit_id") or "") != str(visit_id):
            raise ValueError("Transcription job does not belong to this visit")
        if job.get("status") != "completed":
            raise ValueError("Transcription job must be completed before note generation")
        return job

    def _build_context(self, *, patient_id: str, visit_id: str | None, job: dict) -> dict:
        transcript = self.audio_repo.get_result(str(job.get("job_id"))) or {}
        if not transcript and str(job.get("_session_transcript") or "").strip():
            transcript = {"full_transcript_text": str(job.get("_session_transcript") or "")}
        effective_visit = visit_id or job.get("visit_id")
        if effective_visit:
            previsit = (
                self.db.pre_visit_summaries.find_one(
                    {"patient_id": patient_id, "visit_id": effective_visit},
                    sort=[("updated_at", -1)],
                )
                or {}
            )
            intake = (
                self.db.intake_sessions.find_one(
                    {"patient_id": patient_id, "visit_id": effective_visit},
                    sort=[("updated_at", -1)],
                )
                or {}
            )
            vitals = (
                self.db.patient_vitals.find_one(
                    {"patient_id": patient_id, "visit_id": effective_visit},
                    sort=[("submitted_at", -1)],
                )
                or {}
            )
        else:
            previsit = self.db.pre_visit_summaries.find_one({"patient_id": patient_id}, sort=[("updated_at", -1)]) or {}
            intake = self.db.intake_sessions.find_one({"patient_id": patient_id}, sort=[("updated_at", -1)]) or {}
            vitals = self.db.patient_vitals.find_one({"patient_id": patient_id}, sort=[("submitted_at", -1)]) or {}
        patient = self.db.patients.find_one({"patient_id": patient_id}) or {}

        medication_images = self._extract_medication_images(intake)
        data_gaps: list[str] = []
        if not transcript:
            data_gaps.append("transcript_missing")
        if not previsit:
            data_gaps.append("intake_empty")
        if not vitals:
            data_gaps.append("vitals_missing")
        if not medication_images:
            data_gaps.append("medication_images_missing")

        return {
            "patient_id": patient_id,
            "visit_id": visit_id or job.get("visit_id"),
            "transcription_job_id": job.get("job_id"),
            "transcript_text": transcript.get("full_transcript_text", ""),
            "transcript_segments": transcript.get("segments", []),
            "previsit_sections": previsit.get("sections", {}),
            "intake_answers": intake.get("answers", []),
            "patient_demographics": {
                "name": patient.get("name"),
                "age": patient.get("age"),
                "gender": patient.get("gender"),
                "preferred_language": patient.get("preferred_language"),
            },
            "latest_vitals": vitals.get("values", {}),
            "medication_images": medication_images,
            "data_gaps": data_gaps,
        }

    @staticmethod
    def _extract_medication_images(intake_session: dict) -> list[dict]:
        images: list[dict] = []
        for answer in intake_session.get("answers", []):
            if not isinstance(answer, dict):
                continue
            url = answer.get("image_url") or answer.get("media_url") or answer.get("attachment_url")
            if not url:
                continue
            images.append(
                {
                    "url": str(url),
                    "caption": str(answer.get("answer", "") or ""),
                    "source_topic": str(answer.get("topic", "") or ""),
                }
            )
        return images

    def _generate_payload(self, context: dict) -> dict:
        try:
            generated = self.openai.generate_india_clinical_note(context=context)
            payload = self._normalize_payload(generated, context=context)
        except Exception:
            payload = self._fallback_payload(context=context)
        return payload

    def _normalize_payload(self, generated: dict, *, context: dict) -> dict:
        payload = deepcopy(generated) if isinstance(generated, dict) else {}
        payload.setdefault("assessment", "Clinical assessment pending detailed review.")
        payload.setdefault("plan", "Correlate with examination findings and proceed with OPD management.")
        payload.setdefault("rx", [])
        payload.setdefault("investigations", [])
        payload.setdefault("red_flags", [])
        payload.setdefault("doctor_notes", None)
        payload.setdefault("chief_complaint", self._chief_complaint(context=context))

        normalized_rx = []
        for item in payload.get("rx") or []:
            if not isinstance(item, dict):
                continue
            normalized_rx.append(
                {
                    "medicine_name": str(item.get("medicine_name") or "<medicine_name>"),
                    "dose": str(item.get("dose") or "<dose>"),
                    "frequency": str(item.get("frequency") or "<frequency>"),
                    "duration": str(item.get("duration") or "<duration>"),
                    "route": str(item.get("route") or "<route>"),
                    "food_instruction": str(item.get("food_instruction") or "<food_instruction>"),
                    "generic_available": item.get("generic_available") if isinstance(item.get("generic_available"), bool) else None,
                }
            )
        payload["rx"] = normalized_rx

        normalized_investigations = []
        for item in payload.get("investigations") or []:
            if not isinstance(item, dict):
                continue
            urgency = str(item.get("urgency") or "routine").strip().lower()
            if urgency not in {"routine", "urgent", "stat"}:
                urgency = "routine"
            normalized_investigations.append(
                {
                    "test_name": str(item.get("test_name") or "<test_name>"),
                    "urgency": urgency,
                    "preparation_instructions": str(item.get("preparation_instructions") or "") or None,
                    "routing_note": str(item.get("routing_note") or "") or None,
                }
            )
        payload["investigations"] = normalized_investigations

        payload["red_flags"] = [str(x).strip() for x in (payload.get("red_flags") or []) if str(x).strip()]
        payload["data_gaps"] = sorted(
            set([*(payload.get("data_gaps") or []), *(context.get("data_gaps") or [])])
        )
        has_follow_up_in = bool((payload.get("follow_up_in") or "").strip())
        has_follow_up_date = bool(payload.get("follow_up_date"))
        if has_follow_up_in == has_follow_up_date:
            payload["follow_up_in"] = "7 days"
            payload["follow_up_date"] = None
        if payload.get("follow_up_date") and isinstance(payload["follow_up_date"], (datetime, date)):
            payload["follow_up_date"] = payload["follow_up_date"].isoformat()
        return payload

    def _fallback_payload(self, *, context: dict) -> dict:
        return {
            "assessment": "Assessment is based on available transcript and intake context; correlation with physical examination is advised.",
            "plan": "Proceed with symptom-focused OPD management, safety-net counseling, and reassessment on follow-up.",
            "rx": [],
            "investigations": [],
            "red_flags": [
                "Persistent high fever",
                "Breathlessness at rest",
                "Worsening chest pain",
            ],
            "follow_up_in": "7 days",
            "follow_up_date": None,
            "doctor_notes": None,
            "chief_complaint": self._chief_complaint(context=context),
            "data_gaps": context.get("data_gaps", []),
        }

    @staticmethod
    def _chief_complaint(*, context: dict) -> str | None:
        sections = context.get("previsit_sections") or {}
        chief = sections.get("chief_complaint") if isinstance(sections, dict) else None
        if isinstance(chief, dict):
            reason = str(chief.get("reason_for_visit", "") or "").strip()
            return reason or None
        return None

    def _next_version(self, *, patient_id: str, visit_id: str | None, note_type: str) -> int:
        latest = self.note_repo.find_latest(patient_id=patient_id, visit_id=visit_id, note_type=note_type)
        if not latest:
            return 1
        return int(latest.get("version", 1)) + 1
