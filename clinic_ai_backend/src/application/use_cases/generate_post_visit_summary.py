"""Generate post-visit summary use case."""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.repositories.audio_repository import AudioRepository
from src.adapters.db.mongo.repositories.clinical_note_repository import ClinicalNoteRepository
from src.adapters.services.post_visit_summary_service import PostVisitSummaryService
from src.application.use_cases.schedule_follow_up_reminders import schedule_follow_up_after_post_visit
from src.application.utils.follow_up_dates import parse_next_visit_at


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


LANGUAGE_NAMES = {
    "en": "English",
    "en_us": "English",
    "hi": "Hindi",
}


class GeneratePostVisitSummaryUseCase:
    """Generate and persist patient-friendly post-visit summary note."""

    def __init__(self) -> None:
        self.db = get_database()
        self.audio_repo = AudioRepository()
        self.note_repo = ClinicalNoteRepository()
        self.summary_service = PostVisitSummaryService()

    def execute(
        self,
        *,
        patient_id: str,
        visit_id: str | None = None,
        transcription_job_id: str | None = None,
        preferred_language: str | None = None,
        follow_up_date: date | None = None,
    ) -> dict:
        """Generate summary with India-note-first strategy and transcript fallback."""
        patient = self.db.patients.find_one({"patient_id": patient_id}) or {}
        resolved_language = self._resolve_language(
            patient_preferred_language=patient.get("preferred_language"),
            request_language=preferred_language,
        )
        if not resolved_language:
            raise ValueError("preferred_language missing in both patient profile and request")

        india_note = self.note_repo.find_latest(
            patient_id=patient_id,
            visit_id=visit_id,
            note_type="india_clinical",
        )
        job: dict | None = None
        transcript: dict = {}
        if transcription_job_id or not india_note:
            job = self._resolve_transcription_job(
                patient_id=patient_id,
                visit_id=visit_id,
                transcription_job_id=transcription_job_id,
            )
            transcript = self.audio_repo.get_result(str(job.get("job_id"))) or {}
            if not transcript and str(job.get("_session_transcript") or "").strip():
                transcript = {"full_transcript_text": str(job.get("_session_transcript") or "")}

        if not india_note and not transcript:
            raise ValueError("No India clinical note or completed transcription available")

        context = self._build_context(india_note=india_note, transcript=transcript)
        language_name = LANGUAGE_NAMES.get(resolved_language, resolved_language)
        payload = self._generate_payload(context=context, language_name=language_name)
        if follow_up_date is not None:
            parsed_staff = parse_next_visit_at(follow_up_date)
            if parsed_staff:
                payload["next_visit_date"] = parsed_staff.date().isoformat()
        whatsapp_payload = self._build_whatsapp_payload(payload=payload)

        version = self._next_version(patient_id=patient_id, visit_id=visit_id, note_type="post_visit_summary")
        note_doc = {
            "note_id": str(uuid4()),
            "patient_id": patient_id,
            "visit_id": visit_id or (india_note or {}).get("visit_id") or (job or {}).get("visit_id"),
            "note_type": "post_visit_summary",
            "source_job_id": str((india_note or {}).get("source_job_id") or (job or {}).get("job_id") or ""),
            "status": "generated",
            "version": version,
            "created_at": _utc_now(),
            "payload": payload,
            "whatsapp_payload": whatsapp_payload,
        }
        created = self.note_repo.create_note(note_doc)
        created.pop("_id", None)
        schedule_follow_up_after_post_visit(
            db=self.db,
            patient_id=patient_id,
            visit_id=str(created.get("visit_id") or ""),
            note_id=str(created.get("note_id") or ""),
            payload=payload,
            patient=patient,
            preferred_language=resolved_language,
        )
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
        return job

    def _build_context(self, *, india_note: dict | None, transcript: dict) -> dict:
        india_payload = (india_note or {}).get("payload") or {}
        return {
            "india_clinical_note": india_payload,
            "transcript_text": str(transcript.get("full_transcript_text", "") or ""),
            "input_priority": "india_clinical_note_first_transcript_fallback",
        }

    def _generate_payload(self, *, context: dict, language_name: str) -> dict:
        try:
            generated = self.summary_service.generate(context=context, language_name=language_name)
            return self._normalize_payload(generated)
        except Exception:
            return self._fallback_payload(context=context)

    @staticmethod
    def _normalize_payload(generated: dict) -> dict:
        payload = dict(generated or {})
        payload.setdefault("visit_reason", "Visit reason was discussed during consultation.")
        payload.setdefault("what_doctor_found", "Doctor findings were explained during consultation.")
        payload["medicines_to_take"] = [str(item).strip() for item in (payload.get("medicines_to_take") or []) if str(item).strip()]
        payload["tests_recommended"] = [str(item).strip() for item in (payload.get("tests_recommended") or []) if str(item).strip()]
        payload["self_care"] = [str(item).strip() for item in (payload.get("self_care") or []) if str(item).strip()]
        payload["warning_signs"] = [str(item).strip() for item in (payload.get("warning_signs") or []) if str(item).strip()]
        payload.setdefault("follow_up", "Follow your doctor's advice for the next review.")
        nd = payload.get("next_visit_date")
        parsed = parse_next_visit_at(nd)
        if parsed:
            payload["next_visit_date"] = parsed.date().isoformat()
        else:
            payload.pop("next_visit_date", None)
        return payload

    @staticmethod
    def _fallback_payload(*, context: dict) -> dict:
        india_payload = context.get("india_clinical_note") or {}
        meds = []
        for item in india_payload.get("rx", []) or []:
            if isinstance(item, dict):
                line = " ".join(
                    str(v).strip()
                    for v in [
                        item.get("medicine_name"),
                        item.get("dose"),
                        item.get("frequency"),
                        item.get("duration"),
                        item.get("food_instruction"),
                    ]
                    if str(v or "").strip()
                )
                if line:
                    meds.append(line)
        tests = []
        for item in india_payload.get("investigations", []) or []:
            if isinstance(item, dict) and str(item.get("test_name") or "").strip():
                tests.append(str(item.get("test_name")).strip())
        fu_raw = india_payload.get("follow_up_date")
        next_visit_iso: str | None = None
        if fu_raw not in (None, ""):
            p = parse_next_visit_at(fu_raw)
            if p:
                next_visit_iso = p.date().isoformat()
        out = {
            "visit_reason": str(india_payload.get("chief_complaint") or "Your concern discussed during this visit."),
            "what_doctor_found": str(india_payload.get("assessment") or "Findings based on doctor consultation."),
            "medicines_to_take": meds,
            "tests_recommended": tests,
            "self_care": ["Drink enough fluids", "Take adequate rest"],
            "warning_signs": [str(x).strip() for x in (india_payload.get("red_flags") or []) if str(x).strip()],
            "follow_up": str(
                india_payload.get("follow_up_in")
                or india_payload.get("follow_up_date")
                or "Follow up as advised by your doctor."
            ),
        }
        if next_visit_iso:
            out["next_visit_date"] = next_visit_iso
        return out

    @staticmethod
    def _build_whatsapp_payload(*, payload: dict) -> str:
        medicines = payload.get("medicines_to_take") or []
        tests = payload.get("tests_recommended") or []
        warnings = payload.get("warning_signs") or []
        lines = [
            "Post-visit summary",
            f"🩺 Finding: {payload.get('what_doctor_found', '')}",
            f"💊 Medicines: {', '.join(medicines) if medicines else 'As advised by doctor'}",
            f"🔬 Tests: {', '.join(tests) if tests else 'No additional tests'}",
            f"📅 Follow-up: {payload.get('follow_up', '')}",
            f"⚠️ Warning signs: {', '.join(warnings) if warnings else 'If symptoms worsen, contact your doctor'}",
        ]
        return "\n".join(line.strip() for line in lines if line.strip())

    @staticmethod
    def _resolve_language(*, patient_preferred_language: object, request_language: str | None) -> str | None:
        candidate = str(request_language or patient_preferred_language or "").strip().lower()
        if not candidate:
            return None
        if candidate == "en_us":
            return "en"
        return candidate

    def _next_version(self, *, patient_id: str, visit_id: str | None, note_type: str) -> int:
        latest = self.note_repo.find_latest(patient_id=patient_id, visit_id=visit_id, note_type=note_type)
        if not latest:
            return 1
        return int(latest.get("version", 1)) + 1
