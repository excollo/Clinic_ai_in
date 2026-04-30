"""Build structured Doctor/Patient-style turns from diarized segments."""
from __future__ import annotations

import copy
import re
from difflib import SequenceMatcher
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Below this overlap (segment recall), keep Azure as Unknown rather than forcing a role.
_MIN_SPEAKER_ALIGNMENT_OVERLAP = 0.06


def segments_to_structured_dialogue(segments: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Merge consecutive segments from the same clinical speaker into bundle-style turns."""
    label_to_role = {
        "doctor": "Doctor",
        "patient": "Patient",
        "attendant": "Family Member",
        "family member": "Family Member",
        "unknown": "Patient",
    }
    out: list[dict[str, str]] = []
    for seg in segments:
        raw_label = str(seg.get("speaker_label") or "unknown").lower()
        role = label_to_role.get(raw_label, "Patient")
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        if out and role in out[-1]:
            out[-1][role] = f"{out[-1][role]} {text}".strip()
        else:
            out.append({role: text})
    return out


def _token_set(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _word_overlap_ratio(segment_text: str, turn_text: str) -> float:
    """How well segment tokens are explained by a dialogue turn (0–1), plus light substring boost."""
    sa = _token_set(segment_text)
    sb = _token_set(turn_text)
    if not sa:
        return 0.0
    inter = len(sa & sb)
    ratio = inter / len(sa)
    s_norm = re.sub(r"\s+", " ", segment_text.lower()).strip()
    t_norm = re.sub(r"\s+", " ", turn_text.lower()).strip()
    if len(s_norm) >= 8 and len(t_norm) >= 8:
        if s_norm in t_norm or t_norm in s_norm:
            ratio = max(ratio, 0.42)
    return min(1.0, ratio)


def _flatten_structured_turns(structured_dialogue: list[dict[str, str]]) -> list[tuple[str, str]]:
    """(speaker_label, text) in order — labels are Doctor / Patient / Family Member (Mongo + UI)."""
    out: list[tuple[str, str]] = []
    for turn in structured_dialogue:
        if not isinstance(turn, dict):
            continue
        for display_key in ("Doctor", "Patient", "Family Member"):
            raw = turn.get(display_key)
            if raw is None:
                continue
            text = str(raw).strip()
            if text:
                out.append((display_key, text))
    return out


def structured_dialogue_segment_coverage_ratio(
    segments: list[dict[str, Any]],
    structured_dialogue: list[dict[str, str]],
    *,
    min_overlap: float = 0.32,
) -> float:
    """
    Fraction of non-empty STT segments represented in structured dialogue (0..1).

    A segment is counted as covered when any structured turn overlaps its wording by at least
    ``min_overlap`` using the same token-overlap logic as speaker alignment.
    """
    if not segments:
        return 1.0
    turns = _flatten_structured_turns(structured_dialogue)
    if not turns:
        return 0.0
    turn_texts = [t[1] for t in turns]
    considered = 0
    covered = 0
    for seg in segments:
        seg_text = str(seg.get("text") or "").strip()
        if not seg_text:
            continue
        considered += 1
        best = 0.0
        for t in turn_texts:
            best = max(best, _word_overlap_ratio(seg_text, t))
            if best >= min_overlap:
                break
        if best >= min_overlap:
            covered += 1
    if considered == 0:
        return 1.0
    return covered / considered


def align_segments_with_structured_dialogue(
    segments: list[dict[str, Any]],
    structured_dialogue: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """
    Map each STT segment to Doctor / Patient / Family Member using structured dialogue from OpenAI
    (or bundle-style turns), with monotone time-in-dialogue order.

    Azure short-audio REST responses do not include per-phrase speaker ids; STT segments are
    typically all ``unknown``. After structuring, token overlap + dynamic programming assigns roles
    so ``transcription_results.segments`` matches API dialogue when wording overlaps enough.
    """
    if not segments:
        return []
    turns = _flatten_structured_turns(structured_dialogue)
    if not turns:
        return [copy.deepcopy(s) for s in segments]

    turn_texts = [t[1] for t in turns]
    m = len(turns)
    n = len(segments)
    ovl: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        seg_text = str(segments[i].get("text") or "")
        for j in range(m):
            row.append(_word_overlap_ratio(seg_text, turn_texts[j]))
        ovl.append(row)

    # dp[i][j] = best score placing segments 0..i with segment i on turn j (turn index monotone).
    dp: list[list[float]] = [[0.0] * m for _ in range(n)]
    bp: list[list[int]] = [[0] * m for _ in range(n)]

    for j in range(m):
        dp[0][j] = ovl[0][j]

    for i in range(1, n):
        prefix_best = dp[i - 1][0]
        prefix_k = 0
        for j in range(m):
            if dp[i - 1][j] >= prefix_best:
                prefix_best = dp[i - 1][j]
                prefix_k = j
            dp[i][j] = ovl[i][j] + prefix_best
            bp[i][j] = prefix_k

    best_j = max(range(m), key=lambda j: dp[n - 1][j])
    turn_idx = [0] * n
    j = best_j
    for i in range(n - 1, -1, -1):
        turn_idx[i] = j
        if i == 0:
            break
        j = bp[i][j]

    out: list[dict[str, Any]] = []
    for i, seg in enumerate(segments):
        seg_out = copy.deepcopy(seg)
        text = str(seg.get("text") or "").strip()
        if not text:
            seg_out["speaker_label"] = "Unknown"
            out.append(seg_out)
            continue
        tj = turn_idx[i]
        score = ovl[i][tj]
        if score < _MIN_SPEAKER_ALIGNMENT_OVERLAP:
            seg_out["speaker_label"] = "Unknown"
        else:
            seg_out["speaker_label"] = turns[tj][0]
        out.append(seg_out)
    return out


def dedupe_chunk_overlap_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Remove near-duplicate phrases introduced when overlapped chunk windows re-transcribe the same audio.

    Keeps timeline order by ``start_ms``; drops a segment when it overlaps the previous in time and
    matches text (exact or very high sequence similarity).
    """
    if len(segments) < 2:
        return list(segments)
    ordered = sorted(
        segments,
        key=lambda s: (int(s.get("start_ms", 0) or 0), int(s.get("end_ms", 0) or 0)),
    )
    out: list[dict[str, Any]] = []
    for seg in ordered:
        if not out:
            out.append(seg)
            continue
        prev = out[-1]
        try:
            ps = int(prev.get("start_ms", 0) or 0)
            pe = int(prev.get("end_ms", 0) or 0)
            cs = int(seg.get("start_ms", 0) or 0)
            ce = int(seg.get("end_ms", 0) or 0)
        except (TypeError, ValueError):
            out.append(seg)
            continue
        pt = str(prev.get("text", "")).strip().lower()
        ct = str(seg.get("text", "")).strip().lower()
        if not ct:
            out.append(seg)
            continue
        overlap_ms = min(ce, pe) - max(cs, ps)
        if overlap_ms > 0:
            if pt == ct:
                continue
            if min(len(pt), len(ct)) >= 10 and SequenceMatcher(None, pt, ct).ratio() > 0.96:
                continue
        out.append(seg)
    return out


def segment_gap_audit(segments: list[dict[str, Any]]) -> dict[str, float]:
    """
    Sum of per-segment (end_ms - start_ms) and max gap between consecutive segments by start_ms.

    Large gaps often reflect silence or chunk stitching (wall-clock offsets), not dropped audio;
    compare ``speech_span_s`` and ``max_segment_end`` to ``wav_duration_s`` (see long-audio doc).
    """
    pairs: list[tuple[int, int]] = []
    for s in segments:
        try:
            a = int(s.get("start_ms", 0) or 0)
            b = int(s.get("end_ms", 0) or 0)
        except (TypeError, ValueError):
            continue
        pairs.append((a, b))
    if not pairs:
        return {"speech_span_s": 0.0, "max_consecutive_gap_ms": 0.0}
    pairs.sort(key=lambda x: x[0])
    span_ms = sum(max(0, e - st) for st, e in pairs)
    max_gap = 0
    for i in range(1, len(pairs)):
        gap = max(0, pairs[i][0] - pairs[i - 1][1])
        max_gap = max(max_gap, gap)
    return {
        "speech_span_s": round(span_ms / 1000.0, 3),
        "max_consecutive_gap_ms": float(max_gap),
    }


def audio_duration_from_segments_ms(segments: list[dict[str, Any]]) -> float | None:
    if not segments:
        return None
    try:
        end_ms = max(int(s.get("end_ms", 0) or 0) for s in segments)
    except (TypeError, ValueError):
        return None
    if end_ms <= 0:
        return None
    return round(end_ms / 1000.0, 3)
