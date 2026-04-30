"""Tests for patient/visit ID value objects and opaque codec."""
from __future__ import annotations

import re

import pytest

from src.application.utils.patient_id_crypto import decode_patient_id, encode_patient_id
from src.domain.value_objects.patient_id import PatientId
from src.domain.value_objects.visit_id import VisitId


def test_patient_id_generate_cleans_and_formats() -> None:
    value = PatientId.generate("John", "+1 (555) 123-4567")
    assert value == "john_15551234567"


def test_patient_id_generate_rejects_empty_clean_name() -> None:
    with pytest.raises(ValueError):
        PatientId.generate("!!!", "+1 555 1234")


def test_patient_id_generate_rejects_empty_clean_phone() -> None:
    with pytest.raises(ValueError):
        PatientId.generate("John", "abc")


def test_visit_id_generate_matches_expected_regex() -> None:
    value = VisitId.generate()
    assert re.fullmatch(r"^CONSULT-\d{8}-\d{3}$", value) is not None


def test_encode_decode_roundtrip() -> None:
    internal = "john_15551234567"
    token = encode_patient_id(internal)
    assert token != internal
    assert decode_patient_id(token) == internal
