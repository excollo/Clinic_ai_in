"""Pre-visit summary generation use case."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.adapters.db.mongo.client import get_database
from src.adapters.external.ai.openai_client import OpenAIQuestionClient


class GeneratePreVisitSummaryUseCase:
    """Generate and persist doctor-facing pre-visit summary."""

    def __init__(self) -> None:
        self.db = get_database()
        self.openai = OpenAIQuestionClient()

    def execute(self, patient_id: str, visit_id: str) -> dict[str, Any]:
        """Create pre-visit summary from the intake session for this visit."""
        session = self.db.intake_sessions.find_one(
            {"patient_id": patient_id, "visit_id": visit_id},
            sort=[("updated_at", -1)],
        )
        if not session:
            raise ValueError("No intake session found for patient and visit")

        answers = session.get("answers", [])
        if not answers:
            raise ValueError("Intake answers are empty")

        language = session.get("language", "en")
        summary = self._fallback_summary(answers)
        try:
            ai_summary = self.openai.generate_pre_visit_summary(language=language, intake_answers=answers)
            if isinstance(ai_summary, dict):
                summary = ai_summary
        except Exception:
            pass

        now = datetime.now(timezone.utc)
        doc = {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "intake_session_id": str(session.get("_id")),
            "language": language,
            "status": session.get("status", "in_progress"),
            "sections": summary,
            "updated_at": now,
        }
        self.db.pre_visit_summaries.update_one(
            {"patient_id": patient_id, "visit_id": visit_id, "intake_session_id": str(session.get("_id"))},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        return doc

    @staticmethod
    def _fallback_summary(answers: list[dict[str, Any]]) -> dict[str, Any]:
        """Build safe fallback summary without model dependency."""
        illness = "Not provided"
        associated = []
        severity = "Not provided"
        impact = "Not provided"
        meds = "Not provided"
        history = "Not provided"
        allergies = "Not provided"
        red_flags: list[str] = []

        for item in answers:
            q = str(item.get("question", "")).lower()
            a = str(item.get("answer", "")).strip()
            if not a:
                continue
            if q == "illness":
                illness = a
            if any(k in q for k in ["pain", "discomfort", "symptom", "issue"]):
                associated.append(a)
            if any(k in q for k in ["worse", "constant", "on and off", "severity"]):
                severity = a
            if any(k in q for k in ["daily", "routine", "work", "sleep"]):
                impact = a
            if any(k in q for k in ["medicine", "medicines", "home remed"]):
                meds = a
            if any(k in q for k in ["history", "past", "condition", "surgery"]):
                history = a
            if "allerg" in q:
                allergies = a
            if any(k in a.lower() for k in ["breath", "bleed", "confusion", "chest pain", "high fever"]):
                red_flags.append(a)

        return {
            "chief_complaint": {
                "reason_for_visit": illness,
                "symptom_duration_or_onset": "Not provided",
            },
            "hpi": {
                "associated_symptoms": associated or ["Not provided"],
                "symptom_severity_or_progression": severity,
                "impact_on_daily_life": impact,
            },
            "current_medication": {
                "medications_or_home_remedies": meds,
            },
            "past_medical_history_allergies": {
                "past_medical_history": history,
                "allergies": allergies,
            },
            "red_flag_indicators": red_flags or ["No explicit red flags reported"],
        }
