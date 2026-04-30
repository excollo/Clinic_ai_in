"""Align STT segments to structured Doctor/Patient turns (Azure REST has no diarization)."""
from __future__ import annotations

from src.application.utils.transcript_dialogue import (
    align_segments_with_structured_dialogue,
    dedupe_chunk_overlap_segments,
    segment_gap_audit,
    structured_dialogue_segment_coverage_ratio,
)


def test_aligns_two_segments_to_alternating_doctor_patient() -> None:
    structured = [
        {"Doctor": "Open wide and say ah."},
        {"Patient": "Ah. My jaw clicks when I do that."},
    ]
    segments = [
        {"segment_id": "seg_1", "start_ms": 0, "end_ms": 900, "speaker_label": "unknown", "text": "Open wide say ah", "confidence": 0.9},
        {
            "segment_id": "seg_2",
            "start_ms": 1000,
            "end_ms": 2500,
            "speaker_label": "unknown",
            "text": "Ah my jaw clicks when I do that",
            "confidence": 0.88,
        },
    ]
    out = align_segments_with_structured_dialogue(segments, structured)
    assert out[0]["speaker_label"] == "Doctor"
    assert out[1]["speaker_label"] == "Patient"


def test_single_segment_maps_to_best_overlapping_turn_not_all_unknown() -> None:
    structured = [{"Doctor": "Tell me more."}, {"Patient": "My throat hurts badly since yesterday."}]
    segments = [
        {
            "segment_id": "seg_1",
            "start_ms": 0,
            "end_ms": 2000,
            "speaker_label": "unknown",
            "text": "Doctor, my throat hurts since yesterday.",
            "confidence": 0.9,
        }
    ]
    out = align_segments_with_structured_dialogue(segments, structured)
    assert out[0]["speaker_label"] == "Patient"


def test_low_overlap_keeps_unknown() -> None:
    structured = [{"Doctor": "Completely unrelated clinical boilerplate text alpha beta gamma."}]
    segments = [
        {
            "segment_id": "seg_1",
            "start_ms": 0,
            "end_ms": 500,
            "speaker_label": "unknown",
            "text": "Zebra quartz volcano xyzzy plugh",
            "confidence": 0.5,
        }
    ]
    out = align_segments_with_structured_dialogue(segments, structured)
    assert out[0]["speaker_label"] == "Unknown"


def test_segment_gap_audit_sums_spans_and_max_gap() -> None:
    segments = [
        {"start_ms": 0, "end_ms": 1000, "text": "a"},
        {"start_ms": 50000, "end_ms": 51000, "text": "b"},
    ]
    stats = segment_gap_audit(segments)
    assert stats["speech_span_s"] == 2.0
    assert stats["max_consecutive_gap_ms"] == 49000.0


def test_family_member_turn_maps_to_attendant_slug() -> None:
    structured = [{"Family Member": "She has been dizzy since Tuesday morning."}]
    segments = [
        {
            "segment_id": "seg_1",
            "start_ms": 0,
            "end_ms": 800,
            "speaker_label": "unknown",
            "text": "dizzy since Tuesday morning",
            "confidence": 0.85,
        }
    ]
    out = align_segments_with_structured_dialogue(segments, structured)
    assert out[0]["speaker_label"] == "Family Member"


def test_dedupe_chunk_overlap_removes_duplicate_time_text() -> None:
    segs = [
        {"start_ms": 47000, "end_ms": 48000, "text": "same phrase", "speaker_label": "Unknown"},
        {"start_ms": 47200, "end_ms": 47800, "text": "same phrase", "speaker_label": "Unknown"},
    ]
    out = dedupe_chunk_overlap_segments(segs)
    assert len(out) == 1


def test_structured_dialogue_coverage_ratio_flags_sparse_dialogue() -> None:
    segments = [
        {"text": "history and exam line one"},
        {"text": "medication counseling line two"},
        {"text": "follow up and safety net line three"},
        {"text": "procedure consent line four"},
    ]
    sparse = [{"Doctor": "history and exam line one"}, {"Patient": "line three"}]
    rich = [
        {"Doctor": "history and exam line one"},
        {"Patient": "medication counseling line two"},
        {"Doctor": "follow up and safety net line three"},
        {"Patient": "procedure consent line four"},
    ]
    assert structured_dialogue_segment_coverage_ratio(segments, sparse) < 0.75
    assert structured_dialogue_segment_coverage_ratio(segments, rich) >= 0.75
