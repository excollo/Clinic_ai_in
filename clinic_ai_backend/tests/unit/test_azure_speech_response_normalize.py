"""Regression: document Azure short-audio REST shape vs our normalized segments."""
from __future__ import annotations

import json
from pathlib import Path

from src.workers.transcription_worker import TranscriptionWorker

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "azure_speech_short_audio_success.json"


def test_fixture_matches_documented_short_audio_shape() -> None:
    raw = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    assert raw.get("RecognitionStatus") == "Success"
    assert "NBest" in raw
    assert isinstance(raw["NBest"], list) and raw["NBest"]


def test_normalize_azure_response_yields_single_unknown_speaker_segment() -> None:
    raw = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    out = TranscriptionWorker._normalize_azure_response(raw, "en-IN")
    segs = out["segments"]
    assert len(segs) == 1
    assert segs[0]["speaker_label"] == "Unknown"
    assert "throat" in segs[0]["text"].lower()


def test_segments_to_structured_collapses_unknown_to_patient_turn() -> None:
    """When all segments are unknown, bundle-style merge is one Patient blob — why we OpenAI-structure visits."""
    from src.application.utils.transcript_dialogue import segments_to_structured_dialogue

    raw = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    out = TranscriptionWorker._normalize_azure_response(raw, "en-IN")
    structured = segments_to_structured_dialogue(out["segments"])
    assert len(structured) == 1
    assert "Patient" in structured[0]
