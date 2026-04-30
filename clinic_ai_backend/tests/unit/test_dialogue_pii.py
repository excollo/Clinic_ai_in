"""PII scrub must not strip clinically relevant non-PII text."""
from __future__ import annotations

from src.application.services.dialogue_pii import scrub_dialogue_turns, scrub_text


def test_scrub_preserves_bp_and_doses() -> None:
    text = "BP 120 over 80. Metformin 500 mg twice daily. HbA1c 7.2 percent."
    assert scrub_text(text) == text


def test_scrub_preserves_plain_ten_digit_not_phone() -> None:
    # Generic 10-digit runs (e.g. local IDs) should not be rewritten by the old broad rule.
    text = "Sample ID 1234567890 for lab correlation only."
    assert scrub_text(text) == text


def test_scrub_nanp_phone() -> None:
    text = "Callback +1 (415) 555-2671 tomorrow."
    out = scrub_text(text)
    assert "[PHONE]" in out
    assert "415" not in out or "[PHONE]" in out


def test_scrub_india_mobile_with_country_code() -> None:
    text = "WhatsApp on +91 9876543210 for logistics."
    out = scrub_text(text)
    assert "[PHONE]" in out


def test_scrub_email_and_ssn_style() -> None:
    text = "Email drx@clinic.example and SSN 078-05-1120 are not for notes."
    out = scrub_text(text)
    assert "[EMAIL]" in out
    assert "[SSN]" in out


def test_scrub_dialogue_turns_shape() -> None:
    d = scrub_dialogue_turns([{"Doctor": "Reach me at +1 212-555-0199."}])
    assert d[0]["Doctor"] == "Reach me at [PHONE]."
