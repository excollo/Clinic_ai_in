"""LLM-based structuring of raw transcript into Doctor/Patient JSON (OpenAI API)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib import request

from src.core.config import get_settings

logger = logging.getLogger(__name__)


def chunk_transcript_for_structure(text: str, max_chars: int) -> list[str]:
    """
    Split a long transcript into contiguous slices that rejoin losslessly.

    Breaks prefer paragraph/newline boundaries near the tail of each window so clauses
    are not split mid-line when possible.
    """
    raw = text or ""
    if not raw:
        return []
    limit = max(2000, int(max_chars))
    if len(raw) <= limit:
        return [raw]
    chunks: list[str] = []
    start = 0
    n = len(raw)
    lookback = min(800, limit // 4)
    while start < n:
        if start + limit >= n:
            chunks.append(raw[start:])
            break
        end = start + limit
        slice_lo = max(start, end - lookback)
        break_at = -1
        for sep in ("\n\n", "\n", ". "):
            pos = raw.rfind(sep, slice_lo, end)
            if pos != -1:
                break_at = pos + len(sep)
                break
        if break_at <= start:
            break_at = end
        chunk = raw[start:break_at]
        if not chunk:
            break_at = min(n, start + limit)
            chunk = raw[start:break_at]
        chunks.append(chunk)
        start = break_at
    return chunks


def _extract_dialogue_array(content: str) -> list[dict[str, str]] | None:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("dialogue"), list):
            parsed = parsed["dialogue"]
        if isinstance(parsed, list):
            normalized: list[dict[str, str]] = []
            for item in parsed:
                if isinstance(item, dict) and len(item) == 1:
                    k, v = next(iter(item.items()))
                    normalized.append({str(k): str(v)})
            return normalized or None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[\s*\{[\s\S]*\}\s*\]", text)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [dict(t) for t in arr if isinstance(t, dict) and len(t) == 1]  # type: ignore[misc]
        except json.JSONDecodeError:
            return None
    return None


def _dedupe_adjacent_dialogue_turns(turns: list[dict[str, str]]) -> list[dict[str, str]]:
    """Remove obvious boundary duplicates when stitching chunk-level LLM outputs."""
    if len(turns) < 2:
        return turns
    out: list[dict[str, str]] = [turns[0]]
    for turn in turns[1:]:
        if not isinstance(turn, dict) or len(turn) != 1:
            continue
        sk, sv = next(iter(turn.items()))
        prev = out[-1]
        pk, pv = next(iter(prev.items()))
        s_clean = sv.strip()
        p_clean = pv.strip()
        if not s_clean:
            continue
        if sk == pk and s_clean.lower() == p_clean.lower():
            continue
        if sk == pk and (s_clean.startswith(p_clean) or p_clean.startswith(s_clean)):
            merged_text = s_clean if len(s_clean) >= len(p_clean) else p_clean
            out[-1] = {pk: merged_text}
            continue
        out.append({sk: sv})
    return out


def _structure_one_chunk_openai(
    *,
    raw_transcript: str,
    language: str,
    chunk_index: int,
    chunk_total: int,
    output_language: str,
    speaker_mode: str = "two_speakers",
) -> list[dict[str, str]]:
    settings = get_settings()
    normalized_mode = str(speaker_mode or "two_speakers").strip().lower()
    if normalized_mode == "three_speakers":
        speaker_instruction = (
            "The consultation uses three roles: Doctor, Patient, and Family Member. "
            "Preserve Family Member turns when a caregiver/attendant speaks for or about the patient. "
            "Do not collapse Family Member speech into Patient."
        )
    else:
        speaker_instruction = (
            "Use only Doctor and Patient roles for this consultation; map third-party caregiver lines to Patient."
        )
    system = (
        "You are a medical dialogue analyst. Convert the raw consultation transcript into a JSON array. "
        "Each element must be a single-key object: {\"Doctor\": \"text\"} or {\"Patient\": \"text\"} "
        "or {\"Family Member\": \"text\"} when applicable. "
        f"{speaker_instruction} "
        "Remove direct identifiers (names used as people, phone numbers, emails, SSN-style numbers). "
        "Do NOT remove medication names, vitals, lab values, timelines, or clinical terms. "
        "Do NOT summarize away complaints, history, exam findings, counseling, or plan items — "
        "every clinically relevant phase in this fragment must appear as one or more turns. "
        "Do NOT merge multiple distinct clinical sentences into one short turn; prefer more, shorter turns "
        "so multi-step exams, medication lists, and counseling blocks stay complete. "
        "Verbatim wording is strongly preferred over paraphrase; do not invent lines not in the fragment. "
        f"Write spoken text in {output_language}. "
        "Return ONLY valid JSON array, no markdown."
    )
    if chunk_total > 1:
        user = (
            f"This transcript is split into {chunk_total} sequential parts for processing. "
            f"You are processing PART {chunk_index + 1} of {chunk_total} only.\n"
            "Include every spoken/clinical line from this part; do not invent content from other parts.\n\n"
            f"TRANSCRIPT (part {chunk_index + 1}):\n{raw_transcript}\n\nReturn ONLY the JSON array."
        )
    else:
        user = f"TRANSCRIPT:\n{raw_transcript}\n\nReturn ONLY the JSON array."

    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.05,
    }
    req = request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"] or ""
    parsed = _extract_dialogue_array(content)
    if not parsed:
        raise RuntimeError("STRUCTURE_DIALOGUE_PARSE_FAILED")
    return parsed


def structure_dialogue_from_transcript_sync(
    *,
    raw_transcript: str,
    language: str = "en",
    speaker_mode: str = "two_speakers",
) -> list[dict[str, str]]:
    """
    Call OpenAI chat completions to produce [{Doctor: ...}, {Patient: ...}, ...].

    Uses OPENAI_API_KEY / OPENAI_MODEL from Settings (public OpenAI, not Azure OpenAI).

    Long transcripts are split into ordered chunks; each chunk is structured independently
    and results are concatenated with light boundary deduplication.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if not (raw_transcript or "").strip():
        return []

    lang = (language or "en").strip().lower()
    output_language = "Spanish" if lang in {"sp", "es", "es-es", "es-mx", "spanish", "español"} else "English"

    max_chars = max(2000, int(settings.structure_dialogue_max_chunk_chars))
    chunks = chunk_transcript_for_structure(raw_transcript, max_chars)
    if len(chunks) > 1:
        logger.info(
            "structure_dialogue_chunked total_chars=%s chunks=%s max_chunk_chars=%s",
            len(raw_transcript),
            len(chunks),
            max_chars,
        )

    merged: list[dict[str, str]] = []
    for idx, piece in enumerate(chunks):
        part = _structure_one_chunk_openai(
            raw_transcript=piece,
            language=language,
            chunk_index=idx,
            chunk_total=len(chunks),
            output_language=output_language,
            speaker_mode=speaker_mode,
        )
        merged.extend(part)

    return _dedupe_adjacent_dialogue_turns(merged)

