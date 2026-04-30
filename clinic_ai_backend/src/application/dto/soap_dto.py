"""SOAP DTO module for legacy endpoint compatibility."""
from __future__ import annotations

from pydantic import BaseModel


class SoapNoteDTO(BaseModel):
    """Minimal SOAP payload structure."""

    subjective: str
    objective: str
    assessment: str
    plan: str
