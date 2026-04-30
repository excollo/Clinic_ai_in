"""Stable patient identity derived from demographics (name + phone)."""
from __future__ import annotations

from src.domain.value_objects.patient_id import PatientId


def normalize_patient_identity(name: str, phone_number: str) -> tuple[str, str]:
    """Return normalized (clean_name, digits-only phone) used for id derivation."""
    generated = PatientId.generate(name, phone_number)
    clean_name, clean_phone = generated.split("_", 1)
    return clean_name, clean_phone


def stable_patient_id(name: str, phone_number: str) -> str:
    """Backward-compatible alias for deterministic patient id generation."""
    return PatientId.generate(name, phone_number)
