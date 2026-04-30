"""Lightweight regex PII scrub for transcript dialogue (subset of Clinic-AI reference)."""
from __future__ import annotations

import re
from typing import Any

# Avoid stripping clinical numbers (e.g. lab IDs, vitals) that match generic 10-digit runs.
# NANP: optional +1, optional parens around area code; do not use ``\b`` before ``+`` (fails after space).
# India: +91 or 91 followed by a 10-digit mobile starting 6–9.
_PHONE = re.compile(
    r"(?<!\d)(?:\+1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    r"|\+91[-.\s]?[6-9]\d{9}\b"
    r"|\b91[-.\s]?[6-9]\d{9}\b",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# US SSN pattern (###-##-####); keep narrow to reduce false positives on clinical triplets.
_SSN = re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")


def scrub_text(text: str) -> str:
    if not text:
        return text
    cleaned = _PHONE.sub("[PHONE]", text)
    cleaned = _EMAIL.sub("[EMAIL]", cleaned)
    cleaned = _SSN.sub("[SSN]", cleaned)
    return cleaned


def scrub_dialogue_turns(dialogue: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for turn in dialogue:
        if not isinstance(turn, dict) or len(turn) != 1:
            continue
        speaker, content = next(iter(turn.items()))
        out.append({str(speaker): scrub_text(str(content))})
    return out
