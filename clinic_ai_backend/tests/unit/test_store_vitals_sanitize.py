"""Vitals field sanitization and submit validation."""
from __future__ import annotations

from src.application.use_cases.store_vitals import StoreVitalsUseCase


def test_sanitize_dedupes_and_caps_fields() -> None:
    raw = [
        {"key": "temperature_c", "label": "Temp", "field_type": "number", "unit": "C", "required": True, "reason": "fever"},
        {"key": "temperature_c", "label": "Dup", "field_type": "number", "unit": "C", "required": True, "reason": "x"},
        {"key": "BAD KEY!", "label": "x", "field_type": "number", "unit": None, "required": True, "reason": "y"},
    ]
    out = StoreVitalsUseCase._sanitize_vitals_fields(raw)
    assert len(out) == 1
    assert out[0]["key"] == "temperature_c"


def test_sanitize_invalid_field_type_becomes_text() -> None:
    raw = [
        {
            "key": "note",
            "label": "Note",
            "field_type": "weird",
            "unit": None,
            "required": False,
            "reason": "r",
        }
    ]
    out = StoreVitalsUseCase._sanitize_vitals_fields(raw)
    assert out[0]["field_type"] == "text"


def test_contextual_vitals_excludes_weight_bp_and_caps_at_three() -> None:
    """
    Simulates ONE possible LLM response for a visit where the model judged several
    extras relevant (e.g. respiratory symptoms). Production extras are not this fixed
    list — the LLM picks which fields and how many (1–3); we only strip weight/BP
    duplicates and enforce max three contextual rows.
    """
    raw_simulating_llm_for_one_respiratory_style_visit = [
        # Model must not send these — server adds canonical weight/BP — included here to assert they are dropped.
        {"key": "weight_kg", "label": "Weight", "field_type": "number", "unit": "kg", "required": True, "reason": "x"},
        {"key": "blood_pressure", "label": "BP", "field_type": "text", "unit": None, "required": True, "reason": "x"},
        # Illustrative contextual picks (would differ for e.g. rash-only vs UTI vs injury).
        {"key": "temperature_c", "label": "Temp", "field_type": "number", "unit": "C", "required": True, "reason": "fever"},
        {"key": "spo2_percent", "label": "SpO2", "field_type": "number", "unit": "%", "required": True, "reason": "cough"},
        {"key": "heart_rate_bpm", "label": "HR", "field_type": "number", "unit": "bpm", "required": True, "reason": "tachy"},
        {"key": "respiratory_rate", "label": "RR", "field_type": "number", "unit": "/min", "required": True, "reason": "work of breathing"},
    ]
    out = StoreVitalsUseCase._sanitize_contextual_vitals_fields(
        raw_simulating_llm_for_one_respiratory_style_visit,
        max_count=3,
    )
    keys = [f["key"] for f in out]
    assert keys == ["temperature_c", "spo2_percent", "heart_rate_bpm"]
    assert "weight_kg" not in keys
    assert "blood_pressure" not in keys


def test_contextual_vitals_llm_can_return_fewer_than_three() -> None:
    """When the model only needs one extra measure, the form keeps just that (plus fixed vitals at merge time)."""
    raw_one_contextual_from_llm = [
        {"key": "pain_score_0_10", "label": "Pain 0–10", "field_type": "number", "unit": None, "required": True, "reason": "knee injury intake"},
    ]
    out = StoreVitalsUseCase._sanitize_contextual_vitals_fields(raw_one_contextual_from_llm, max_count=3)
    assert len(out) == 1
    assert out[0]["key"] == "pain_score_0_10"


def test_contextual_vitals_drops_non_numeric_fields_dynamically() -> None:
    raw = [
        {"key": "pain_score_0_10", "label": "Pain", "field_type": "number", "unit": None, "required": True, "reason": "injury"},
        {"key": "associated_symptoms", "label": "Associated symptoms", "field_type": "text", "unit": None, "required": True, "reason": "narrative"},
        {"key": "red_flag_present", "label": "Red flags", "field_type": "boolean", "unit": None, "required": True, "reason": "screening"},
    ]
    out = StoreVitalsUseCase._sanitize_contextual_vitals_fields(raw, max_count=3)
    assert [f["key"] for f in out] == ["pain_score_0_10"]
    assert all(f["field_type"] == "number" for f in out)


def test_fixed_common_vitals_prepended_order() -> None:
    fixed = StoreVitalsUseCase._fixed_common_vitals_fields()
    assert [f["key"] for f in fixed] == ["body_weight_kg", "blood_pressure_mmhg"]
    ctx = StoreVitalsUseCase._sanitize_contextual_vitals_fields(
        [{"key": "temperature_c", "label": "T", "field_type": "number", "unit": "C", "required": True, "reason": "r"}],
        max_count=3,
    )
    merged = fixed + ctx
    assert len(merged) == 3
    assert merged[0]["key"] == "body_weight_kg"
