"""Shared language normalization and routing helpers."""
from __future__ import annotations

import re
from collections.abc import Iterable

DEFAULT_INTAKE_LANGUAGE = "en"
SUPPORTED_INTAKE_LANGUAGE_CODES = (
    "en",
    "hi",
    "hi-eng",
    "ta",
    "te",
    "bn",
    "mr",
    "kn",
)

INTAKE_LANGUAGE_ALIASES = {
    "english": "en",
    "en-in": "en",
    "en_us": "en",
    "en-us": "en",
    "hindi": "hi",
    "hinglish": "hi-eng",
    "hi_en": "hi-eng",
    "hi en": "hi-eng",
}


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_intake_language(language: str) -> str:
    """Normalize persisted/requested language codes for intake prompt/validation."""
    normalized = _normalize_text(language)
    normalized = INTAKE_LANGUAGE_ALIASES.get(normalized, normalized)
    return normalized if normalized in SUPPORTED_INTAKE_LANGUAGE_CODES else DEFAULT_INTAKE_LANGUAGE


def is_supported_intake_language(language: str) -> bool:
    normalized = _normalize_text(language)
    return normalized in SUPPORTED_INTAKE_LANGUAGE_CODES or normalized in INTAKE_LANGUAGE_ALIASES


def intake_language_validation_message(
    field_name: str = "preferred_language",
    *,
    extra_values: Iterable[str] = (),
) -> str:
    values = [*SUPPORTED_INTAKE_LANGUAGE_CODES, *[str(value) for value in extra_values if str(value).strip()]]
    return f"{field_name} must be one of: {', '.join(values)}"


def uses_hindi_template_family(language: str) -> bool:
    """Meta template routing currently distinguishes Hindi from all other languages."""
    return normalize_intake_language(language) == "hi"


def build_template_language_candidates(
    preferred_language: str,
    *,
    hindi_codes: Iterable[str],
    english_codes: Iterable[str],
) -> list[str]:
    selected = list(hindi_codes) if uses_hindi_template_family(preferred_language) else list(english_codes)
    out: list[str] = []
    for code in selected:
        value = str(code or "").strip()
        if value and value not in out:
            out.append(value)
    return out
