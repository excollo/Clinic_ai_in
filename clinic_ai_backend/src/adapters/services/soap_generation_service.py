"""Legacy SOAP generation service module."""
from __future__ import annotations

from src.application.ports.services.soap_service import SoapService


class SoapGenerationService(SoapService):
    """Minimal legacy SOAP generator kept for endpoint compatibility."""

    def generate(self, *, transcript_text: str, chief_complaint: str | None = None) -> dict:
        summary = transcript_text.strip()
        if len(summary) > 320:
            summary = f"{summary[:317]}..."
        complaint = (chief_complaint or "").strip() or "Not explicitly provided"
        return {
            "subjective": complaint,
            "objective": "Refer transcript and vitals context.",
            "assessment": "Legacy SOAP path is enabled for backward compatibility.",
            "plan": summary or "Clinical correlation advised.",
        }
