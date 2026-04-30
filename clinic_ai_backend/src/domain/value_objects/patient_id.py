"""Patient ID value object."""
from __future__ import annotations

import re


class PatientId:
    """Deterministic patient ID: ``{clean_name}_{clean_phone}``."""

    _name_pattern = re.compile(r"[^a-zA-Z0-9]+")
    _format_pattern = re.compile(r"^[a-z0-9]+_[0-9]+$")

    @staticmethod
    def generate(first_name: str, mobile: str) -> str:
        clean_name = PatientId._name_pattern.sub("", str(first_name or "")).lower()
        clean_phone = "".join(ch for ch in str(mobile or "") if ch.isdigit())
        if not clean_name:
            raise ValueError("first_name must contain at least one alphanumeric character")
        if not clean_phone:
            raise ValueError("mobile must contain at least one digit")
        return f"{clean_name}_{clean_phone}"

    @staticmethod
    def validate(value: str) -> str:
        normalized = str(value or "").strip()
        if not PatientId._format_pattern.fullmatch(normalized):
            raise ValueError("patient_id must match format <clean_name>_<digits>")
        return normalized
