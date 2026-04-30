"""SOAP service port module."""
from __future__ import annotations

from abc import ABC, abstractmethod


class SoapService(ABC):
    """Abstract interface for legacy SOAP generation."""

    @abstractmethod
    def generate(self, *, transcript_text: str, chief_complaint: str | None = None) -> dict:
        """Generate SOAP-compatible content."""
