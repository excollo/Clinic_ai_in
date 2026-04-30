"""Transcription worker for Azure Speech pipeline."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.adapters.db.mongo.client import get_database
from src.adapters.db.mongo.repositories.audio_repository import AudioRepository
from src.adapters.db.mongo.repositories.visit_transcription_repository import VisitTranscriptionRepository
from src.adapters.transcription.factory import get_audio_storage_adapter, get_queue_adapter
from src.adapters.transcription.storage.gridfs_audio_adapter import GridFsAudioStorageAdapter
from src.adapters.transcription.types import TranscriptionQueueJob
from src.application.services.dialogue_pii import scrub_dialogue_turns
from src.application.services.structure_dialogue import structure_dialogue_from_transcript_sync
from src.application.use_cases.generate_india_clinical_note import GenerateIndiaClinicalNoteUseCase
from src.application.utils.transcript_dialogue import (
    align_segments_with_structured_dialogue,
    audio_duration_from_segments_ms,
    dedupe_chunk_overlap_segments,
    segment_gap_audit,
    segments_to_structured_dialogue,
    structured_dialogue_segment_coverage_ratio,
)
from src.core.config import get_settings

logger = logging.getLogger(__name__)

_BACKGROUND_TASKS: list[asyncio.Task] = []
_STOP_EVENT: asyncio.Event | None = None


class TranscriptionWorker:
    """Worker that processes transcription queue jobs."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.repo = AudioRepository()
        self.db = get_database()

    def process_next(self) -> bool:
        """Sync wrapper used by tests/CLI."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.process_next_async())
        # If we're already inside an event loop, the sync wrapper isn't safe.
        raise RuntimeError("Use process_next_async() when an event loop is already running")

    async def process_next_async(self) -> bool:
        """Process one queued message (async-friendly for local demo mode)."""
        queue_adapter = get_queue_adapter()
        stale_job_ids = self.repo.requeue_stale_processing_jobs(
            max_processing_sec=self.settings.transcription_timeout_sec
        )
        for stale_job_id in stale_job_ids:
            await queue_adapter.enqueue(TranscriptionQueueJob(job_id=stale_job_id))

        dequeued = await queue_adapter.dequeue(visibility_timeout=600)
        if not dequeued:
            return False

        job_id = dequeued.job.job_id
        try:
            job = self.repo.get_job(job_id)
            if not job:
                return True

            if not self._has_previsit(job):
                self.repo.mark_failed(
                    job_id,
                    error_code="PREVISIT_MISSING",
                    error_message="Pre-visit summary not found at processing time",
                )
                self._sync_visit_failed(job, "Pre-visit summary not found at processing time")
                await self._purge_stored_audio(job)
                return True

            audio_doc = self.repo.get_audio_by_id(job["audio_id"])
            if not audio_doc:
                self.repo.mark_failed(
                    job_id,
                    error_code="AUDIO_MISSING",
                    error_message="Audio metadata not found for transcription job",
                )
                self._sync_visit_failed(job, "Audio metadata not found for transcription job")
                return True

            self.repo.mark_processing(job_id)
            self._sync_visit_processing(job)
            try:
                speech_response = await asyncio.wait_for(
                    asyncio.to_thread(self._call_azure_speech, job=job, audio_doc=audio_doc),
                    timeout=max(
                        float(self.settings.transcription_job_timeout_sec),
                        float(self.settings.transcription_timeout_sec),
                    ),
                )

                normalized = self._normalize_segments(speech_response.get("segments", []))
                if not normalized:
                    raise RuntimeError("No transcript segments returned by speech provider")

                review_count = sum(1 for segment in normalized if segment["needs_manual_review"])
                review_ratio = review_count / len(normalized)
                full_text = " ".join(segment["text"] for segment in normalized if segment["text"]).strip()
                avg_confidence = sum(segment["confidence"] for segment in normalized) / len(normalized)
                if self.settings.use_local_adapters:
                    requires_manual_review = False
                else:
                    requires_manual_review = (
                        review_ratio >= self.settings.transcription_manual_review_ratio_threshold
                    )

                structured = self._visit_structured_dialogue(job, full_text=full_text, normalized=normalized)
                segments_to_store = align_segments_with_structured_dialogue(normalized, structured)
                self.repo.save_result(
                    {
                        "job_id": job["job_id"],
                        "patient_id": job["patient_id"],
                        "visit_id": job.get("visit_id"),
                        "language_detected": speech_response.get("language_detected", "unknown"),
                        "overall_confidence": round(avg_confidence, 4),
                        "requires_manual_review": requires_manual_review,
                        "full_transcript_text": full_text,
                        "segments": segments_to_store,
                    }
                )
                self._sync_visit_completed(
                    job,
                    full_text=full_text,
                    normalized=segments_to_store,
                    structured_dialogue=structured,
                )
                self.repo.mark_completed(job_id)
                self._auto_generate_default_note(job=job)
                await self._purge_stored_audio(job)
            except Exception as exc:  # noqa: BLE001
                if "NON_RETRIABLE_NO_TEXT" in str(exc):
                    err_msg = str(exc).replace("NON_RETRIABLE_NO_TEXT: ", "")
                    self.repo.mark_failed(
                        job_id,
                        error_code="TRANSCRIPTION_FAILED",
                        error_message=err_msg,
                    )
                    self._sync_visit_failed(job, err_msg)
                    await self._purge_stored_audio(job)
                    return True
                refreshed = self.repo.increment_retry(
                    job_id,
                    error_code="TRANSCRIPTION_FAILED_RETRY",
                    error_message=str(exc),
                )
                retry_count = refreshed["retry_count"] if refreshed else job.get("retry_count", 0) + 1
                max_retries = refreshed["max_retries"] if refreshed else job.get("max_retries", 0)
                if retry_count >= max_retries:
                    self.repo.mark_failed(
                        job_id,
                        error_code="TRANSCRIPTION_FAILED",
                        error_message=str(exc),
                    )
                    self._sync_visit_failed(job, str(exc))
                    await self._purge_stored_audio(job)
                else:
                    await queue_adapter.enqueue(TranscriptionQueueJob(job_id=job_id))
        finally:
            await queue_adapter.acknowledge(dequeued.job.job_id, dequeued.receipt)

        return True

    def _auto_generate_default_note(self, *, job: dict) -> None:
        """Generate default India note after successful transcription completion."""
        if self.settings.default_note_type != "india_clinical":
            return
        try:
            GenerateIndiaClinicalNoteUseCase().execute(
                patient_id=str(job.get("patient_id")),
                visit_id=job.get("visit_id"),
                transcription_job_id=str(job.get("job_id")),
                force_regenerate=False,
            )
        except Exception:
            # Do not fail transcription completion if note generation errors.
            return

    def _has_previsit(self, job: dict) -> bool:
        patient_id = str(job.get("patient_id"))
        visit_id = self._visit_id(job)
        query: dict[str, object] = {"patient_id": patient_id}
        if visit_id:
            query["visit_id"] = visit_id
        return self.db.pre_visit_summaries.find_one(query, sort=[("updated_at", -1)]) is not None

    @staticmethod
    def _visit_id(job: dict) -> str | None:
        raw = job.get("visit_id")
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    def _sync_visit_processing(self, job: dict) -> None:
        visit_id = self._visit_id(job)
        if not visit_id:
            return
        VisitTranscriptionRepository().mark_processing(
            patient_id=str(job["patient_id"]),
            visit_id=visit_id,
        )

    def _visit_structured_dialogue(
        self,
        job: dict,
        *,
        full_text: str,
        normalized: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """
        Visit dialogue for the API: prefer OpenAI Doctor/Patient turns when configured.

        Short-audio Azure Speech REST (`/speech/recognition/.../v1`) typically returns one
        `NBest` phrase with no speaker diarization — see `tests/fixtures/azure_speech_short_audio_success.json`.
        `segments_to_structured_dialogue` collapses unknown speakers to Patient-only turns for bundle-style output.
        When `OPENAI_API_KEY` is set, we restructure the full transcript; persisted segments are then aligned to
        those turns via `align_segments_with_structured_dialogue` before `save_result`.
        """
        baseline = segments_to_structured_dialogue(normalized)
        if not (self.settings.openai_api_key or "").strip():
            return baseline
        if not (full_text or "").strip():
            return baseline
        try:
            language_mix = str(job.get("language_mix") or "en")
            speaker_mode = str(job.get("speaker_mode") or "two_speakers")
            structured = structure_dialogue_from_transcript_sync(
                raw_transcript=full_text,
                language=language_mix,
                speaker_mode=speaker_mode,
            )
            if structured:
                cleaned = scrub_dialogue_turns(structured)
                coverage = structured_dialogue_segment_coverage_ratio(normalized, cleaned)
                # If LLM omitted too many lines, keep complete baseline instead of a partial summary-like dialogue.
                if coverage < 0.75:
                    logger.warning(
                        "structured_dialogue_low_coverage job_id=%s coverage=%.3f turns=%s segments=%s fallback=baseline",
                        job.get("job_id"),
                        coverage,
                        len(cleaned),
                        len(normalized),
                    )
                    return baseline
                return cleaned
        except Exception:
            return baseline
        return baseline

    def _sync_visit_completed(
        self,
        job: dict,
        *,
        full_text: str,
        normalized: list[dict[str, Any]],
        structured_dialogue: list[dict[str, str]],
    ) -> None:
        visit_id = self._visit_id(job)
        if not visit_id:
            return
        duration = audio_duration_from_segments_ms(normalized)
        word_count = len(full_text.split()) if full_text else 0
        VisitTranscriptionRepository().mark_completed(
            patient_id=str(job["patient_id"]),
            visit_id=visit_id,
            transcript=full_text,
            structured_dialogue=structured_dialogue,
            word_count=word_count,
            audio_duration_seconds=duration,
        )

    def _sync_visit_failed(self, job: dict, message: str) -> None:
        visit_id = self._visit_id(job)
        if not visit_id:
            return
        VisitTranscriptionRepository().mark_failed(
            patient_id=str(job["patient_id"]),
            visit_id=visit_id,
            error_message=message,
        )

    @staticmethod
    def _storage_ref_from_audio_doc(audio_doc: dict) -> str:
        return str(
            audio_doc.get("storage_ref")
            or audio_doc.get("blob_url")
            or audio_doc.get("blob_path")
            or ""
        ).strip()

    async def _purge_stored_audio(self, job: dict) -> None:
        """Delete stored upload bytes via configured storage backend (best-effort)."""
        doc = self.repo.get_audio_by_id(str(job.get("audio_id", "") or ""))
        if not doc:
            return
        ref = self._storage_ref_from_audio_doc(doc)
        if not ref:
            return
        adapter = get_audio_storage_adapter()
        if isinstance(adapter, GridFsAudioStorageAdapter):
            await asyncio.to_thread(adapter.delete_blocking, ref)
            return None
        await adapter.delete_blob(ref)
        return None

    @staticmethod
    def _pcm_wav_duration_seconds(wav_bytes: bytes) -> float | None:
        """Decode duration from a PCM RIFF/WAVE blob (e.g. ffmpeg 16 kHz mono output)."""
        if len(wav_bytes) < 44 or wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
            return None
        pos = 12
        byte_rate: int | None = None
        while pos + 8 <= len(wav_bytes):
            chunk_id = wav_bytes[pos : pos + 4]
            chunk_size = int.from_bytes(wav_bytes[pos + 4 : pos + 8], "little")
            chunk_start = pos + 8
            if chunk_id == b"fmt " and chunk_size >= 16:
                br_offset = chunk_start + 8
                if br_offset + 4 <= len(wav_bytes):
                    byte_rate = int.from_bytes(wav_bytes[br_offset : br_offset + 4], "little")
            elif chunk_id == b"data" and byte_rate and byte_rate > 0:
                return chunk_size / byte_rate
            pos = chunk_start + chunk_size + (chunk_size % 2)
        return None

    @staticmethod
    def _ffprobe_duration_seconds(path: str) -> float | None:
        ffprobe = TranscriptionWorker._resolve_ffprobe_bin()
        if not ffprobe:
            return None
        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if proc.returncode != 0:
                return None
            val = float((proc.stdout or "").strip() or 0.0)
            return val if val > 0 else None
        except (ValueError, subprocess.TimeoutExpired):
            return None

    def _split_wav_into_time_chunks(
        self, wav_bytes: bytes, chunk_sec: float, overlap_sec: float = 0.0
    ) -> tuple[list[bytes], float]:
        """
        Split PCM WAV into <= chunk_sec windows for Azure short-audio REST (≈60s max per request).

        Returns ``(chunk_wav_bytes_list, step_sec)`` where ``step_sec = chunk_sec - overlap_sec`` is the
        advance along the source timeline between windows (overlap reduces boundary word loss).
        """
        if chunk_sec < 10:
            chunk_sec = 50.0
        overlap_sec = max(0.0, float(overlap_sec or 0.0))
        overlap_sec = min(overlap_sec, chunk_sec * 0.45)
        step_sec = max(0.5, chunk_sec - overlap_sec)
        ffmpeg_bin = self._resolve_ffmpeg_bin()
        if not ffmpeg_bin:
            return [wav_bytes], chunk_sec
        dur = self._pcm_wav_duration_seconds(wav_bytes)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.wav"
            src.write_bytes(wav_bytes)
            if dur is None:
                dur = self._ffprobe_duration_seconds(str(src)) or 0.0
            if dur <= chunk_sec + 0.1:
                return [wav_bytes], chunk_sec
            chunks: list[bytes] = []
            start = 0.0
            idx = 0
            while start < dur - 0.05:
                out = Path(tmp) / f"chunk_{idx:05d}.wav"
                cmd = [
                    ffmpeg_bin,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-ss",
                    f"{start:.3f}",
                    "-i",
                    str(src),
                    "-t",
                    f"{chunk_sec:.3f}",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "pcm_s16le",
                    str(out),
                ]
                proc = subprocess.run(cmd, capture_output=True, timeout=900, check=False)
                if proc.returncode != 0 or not out.is_file() or out.stat().st_size < 200:
                    raise RuntimeError(
                        "ffmpeg chunk split failed at "
                        f"offset={start:.2f}s: "
                        f"{(proc.stderr or b'').decode('utf-8', errors='replace')[:400]}"
                    )
                chunks.append(out.read_bytes())
                start += step_sec
                idx += 1
            return (chunks if chunks else [wav_bytes]), step_sec

    def _short_audio_recognize_one_payload(
        self, *, audio_payload: bytes, content_type: str, primary_locale: str
    ) -> tuple[dict | None, HTTPError | None, dict | None, int | None, str | None]:
        """
        One full pass over locales/endpoints for Azure short-audio REST.

        Returns ``(normalized, last_404, last_raw, http_status, detail)``.
        ``detail`` is an HTTP body snippet, ``"exhausted_no_segments"``, or ``None`` when segments exist.
        """
        last_404: HTTPError | None = None
        last_raw: dict | None = None
        best_normalized: dict | None = None
        best_status: int | None = None
        best_words = -1
        http_timeout = max(30, int(self.settings.transcription_timeout_sec))
        for locale in self._candidate_locales(primary_locale):
            for endpoint in self._candidate_azure_speech_endpoints(locale):
                try:
                    req = Request(endpoint, data=audio_payload, method="POST")
                    req.add_header("Ocp-Apim-Subscription-Key", self.settings.azure_speech_key)
                    req.add_header("Accept", "application/json;text/xml")
                    req.add_header("Content-Type", content_type)
                    with urlopen(req, timeout=http_timeout) as response:
                        raw_bytes = response.read()
                        status = getattr(response, "status", None)
                        if status is None:
                            status = response.getcode()
                        raw = json.loads(raw_bytes.decode("utf-8"))
                    if isinstance(raw, list):
                        raw = next((item for item in raw if isinstance(item, dict)), {})
                    if not isinstance(raw, dict):
                        continue
                    normalized = self._normalize_azure_response(raw, locale)
                    segs = normalized.get("segments") or []
                    if segs:
                        words = sum(len(str(s.get("text", "")).split()) for s in segs)
                        if words > best_words:
                            best_words = words
                            best_normalized = normalized
                            best_status = int(status or 200)
                    last_raw = raw if isinstance(raw, dict) else last_raw
                except HTTPError as exc:
                    err_body = ""
                    try:
                        err_body = exc.read().decode("utf-8", errors="replace")[:800]
                    except Exception:
                        err_body = str(exc)[:800]
                    if exc.code == 404:
                        last_404 = exc
                        continue
                    if exc.code in (429, 502, 503):
                        return None, last_404, last_raw, exc.code, err_body
                    raise RuntimeError(
                        f"Azure Speech HTTP {exc.code} for short-audio STT: {err_body[:300]}"
                    ) from exc
        if best_normalized and (best_normalized.get("segments") or []):
            return best_normalized, last_404, last_raw, best_status, None
        return None, last_404, last_raw, None, "exhausted_no_segments"

    def _stt_recognize_chunk_with_retries(
        self,
        *,
        audio_payload: bytes,
        content_type: str,
        primary_locale: str,
        job_id: str,
        chunk_idx: int,
        chunk_total: int,
        wall_start_s: float,
        wall_end_s: float,
    ) -> dict:
        """POST one chunk to Azure with retries; raises if no segments after all attempts."""
        attempts = max(1, int(self.settings.transcription_chunk_max_stt_retries))
        last_detail = "exhausted_no_segments"
        last_status: int | None = None
        for attempt in range(attempts):
            normalized, _l404, _lraw, status, detail = self._short_audio_recognize_one_payload(
                audio_payload=audio_payload,
                content_type=content_type,
                primary_locale=primary_locale,
            )
            last_detail = detail or last_detail
            last_status = status
            segs = (normalized or {}).get("segments") or []
            if normalized and segs:
                wc = sum(len(str(s.get("text", "")).split()) for s in segs)
                logger.info(
                    "transcription_chunk_stt job_id=%s chunk=%s/%s attempt=%s/%s wall_s=%.2f-%.2f "
                    "payload_bytes=%s segments=%s words=%s http_status=%s",
                    job_id,
                    chunk_idx + 1,
                    chunk_total,
                    attempt + 1,
                    attempts,
                    wall_start_s,
                    wall_end_s,
                    len(audio_payload),
                    len(segs),
                    wc,
                    status,
                )
                return normalized
            retryable = status in (429, 502, 503) or detail == "exhausted_no_segments"
            if attempt < attempts - 1 and retryable:
                logger.warning(
                    "transcription_chunk_stt_retry job_id=%s chunk=%s/%s attempt=%s http=%s detail=%s",
                    job_id,
                    chunk_idx + 1,
                    chunk_total,
                    attempt + 1,
                    status,
                    (detail or "")[:200],
                )
                time.sleep(0.5 * (attempt + 1))
                continue
            break
        chunk_dur = self._pcm_wav_duration_seconds(audio_payload) or 0.0
        logger.error(
            "transcription_chunk_stt_failed job_id=%s chunk=%s/%s attempts=%s http=%s chunk_dur_s=%.2f "
            "payload_bytes=%s detail=%s",
            job_id,
            chunk_idx + 1,
            chunk_total,
            attempts,
            last_status,
            chunk_dur,
            len(audio_payload),
            (last_detail or "")[:300],
        )
        # Silent/no-speech windows are valid in real consultations (pauses, waiting periods, background prep).
        # Keep chunk processing resilient by skipping this chunk; if *all* chunks are empty,
        # _call_azure_speech still raises a clear NON_RETRIABLE_NO_TEXT failure for the full job.
        if last_detail == "exhausted_no_segments":
            logger.warning(
                "transcription_chunk_stt_empty_soft job_id=%s chunk=%s/%s bytes=%s (treating as no-speech window)",
                job_id,
                chunk_idx + 1,
                chunk_total,
                len(audio_payload),
            )
            return {"language_detected": primary_locale, "segments": []}
        raise RuntimeError(
            f"Azure STT produced no segments for chunk {chunk_idx + 1}/{chunk_total} "
            f"(wall ~{wall_start_s:.1f}-{wall_end_s:.1f}s, ~{chunk_dur:.1f}s of audio) after {attempts} attempts. "
            f"last_http={last_status} detail={last_detail!r}"
        )

    def _raise_azure_recognition_failure(
        self,
        *,
        last_404: HTTPError | None,
        last_raw: dict | None,
        audio_doc: dict,
        transcode_error: str | None,
    ) -> None:
        if last_404 is not None:
            raise RuntimeError(
                "Azure Speech endpoint not found (404). Check AZURE_SPEECH_REGION/ENDPOINT and resource region."
            ) from last_404
        if last_raw is not None:
            status = str(last_raw.get("RecognitionStatus", "unknown"))
            mime_type = str(audio_doc.get("mime_type", "unknown") or "unknown")
            if not self._resolve_ffmpeg_bin():
                ffmpeg_hint = (
                    "Install ffmpeg on the server (see deployments/docker/Dockerfile.api) so audio can be "
                    "converted to 16 kHz mono PCM WAV before Azure recognition."
                )
            elif transcode_error:
                ffmpeg_hint = (
                    f"FFmpeg failed while normalizing audio ({transcode_error}). "
                    "Fix the source file or install codecs; Azure then received the original bytes only."
                )
            else:
                ffmpeg_hint = (
                    "FFmpeg normalized WAV was tried first; if this persists, the source may be silent, "
                    "not speech, or the language hint may not match the spoken language."
                )
            raise RuntimeError(
                "NON_RETRIABLE_NO_TEXT: "
                "Azure Speech returned no transcript text. "
                f"RecognitionStatus={status}. "
                f"Input MIME={mime_type}. "
                "Azure treated the request as successful but found no words. "
                "Common causes: silent/corrupt audio, wrong language vs speech, or compressed audio Azure could not decode. "
                f"{ffmpeg_hint}"
            )
        raise RuntimeError("Azure Speech transcription failed without response")

    def _log_transcription_pipeline_integrity(
        self,
        *,
        job: dict,
        audio_doc: dict,
        download_bytes: int,
        transcoded_wav_bytes: int | None,
        wav_duration_s: float | None,
        azure_post_count: int,
        stt_request_bytes_total: int,
        segment_count: int,
        merged_segments: list[dict[str, Any]],
        use_chunked_stt: bool,
        chunk_sec: float | None = None,
        chunk_step_sec: float | None = None,
        chunk_overlap_sec: float | None = None,
    ) -> None:
        """
        One INFO line per successful STT path: stored vs downloaded bytes, WAV duration, and STT wire volume.

        STT bodies are usually **transcoded PCM WAV** (or original bytes for the short-audio fallback path),
        so ``stt_request_bytes_total`` may legitimately differ from the upload when the doctor sent MP3/M4A.
        """
        raw_meta = audio_doc.get("size_bytes")
        meta_int: int | None
        try:
            meta_int = int(raw_meta) if raw_meta is not None else None
        except (TypeError, ValueError):
            meta_int = None
        stored_eq_download = meta_int is None or meta_int == download_bytes
        if not stored_eq_download:
            logger.error(
                "transcription_byte_mismatch job_id=%s audio_id=%s stored_size_bytes=%s download_bytes=%s",
                job.get("job_id"),
                audio_doc.get("audio_id"),
                raw_meta,
                download_bytes,
            )
        max_end_ms = 0
        for seg in merged_segments:
            try:
                max_end_ms = max(max_end_ms, int(seg.get("end_ms", 0) or 0))
            except (TypeError, ValueError):
                continue
        max_end_s = max_end_ms / 1000.0 if max_end_ms else None
        gap_stats = segment_gap_audit(merged_segments)
        wall_span_s: float | None = None
        if use_chunked_stt and chunk_sec is not None and azure_post_count and chunk_step_sec is not None:
            wall_span_s = round(
                float(azure_post_count - 1) * float(chunk_step_sec) + float(chunk_sec),
                3,
            )
        elif use_chunked_stt and chunk_sec is not None and azure_post_count:
            wall_span_s = round(float(azure_post_count) * float(chunk_sec), 3)
        if wav_duration_s and max_end_s and wav_duration_s > 60:
            drift = abs(max_end_s - wav_duration_s) / wav_duration_s
            if drift > 0.15:
                logger.warning(
                    "transcription_segment_timeline_vs_wav job_id=%s wav_duration_s=%s max_segment_end_s=%s "
                    "drift_pct=%.1f",
                    job.get("job_id"),
                    round(wav_duration_s, 2),
                    round(max_end_s, 2),
                    drift * 100.0,
                )
        if wav_duration_s and wav_duration_s >= 300 and self.settings.transcription_debug_bytes:
            logger.info(
                "transcription_long_visit_hint job_id=%s wav_duration_s=%s (expect minutes-scale for long visits)",
                job.get("job_id"),
                round(wav_duration_s, 1),
            )
        logger.info(
            "transcription_pipeline_integrity job_id=%s audio_id=%s stored_bytes=%s download_bytes=%s "
            "stored_eq_download=%s transcoded_wav_bytes=%s wav_duration_s=%s chunked_stt=%s azure_post_count=%s "
            "stt_request_bytes_total=%s segments=%s max_segment_end_s=%s speech_span_s=%s max_consecutive_gap_ms=%s "
            "chunk_wall_span_s=%s chunk_step_s=%s chunk_overlap_s=%s",
            job.get("job_id"),
            audio_doc.get("audio_id"),
            meta_int if meta_int is not None else raw_meta,
            download_bytes,
            stored_eq_download,
            transcoded_wav_bytes,
            round(wav_duration_s, 3) if wav_duration_s is not None else None,
            use_chunked_stt,
            azure_post_count,
            stt_request_bytes_total,
            segment_count,
            round(max_end_s, 3) if max_end_s else None,
            gap_stats["speech_span_s"],
            int(gap_stats["max_consecutive_gap_ms"]),
            wall_span_s,
            round(float(chunk_step_sec), 3) if chunk_step_sec is not None else None,
            round(float(chunk_overlap_sec), 3) if chunk_overlap_sec is not None else None,
        )
        if self.settings.transcription_debug_bytes and use_chunked_stt and wall_span_s is not None and wav_duration_s:
            logger.info(
                "transcription_chunk_wall_audit job_id=%s chunk_sec=%s azure_post_count=%s chunk_wall_span_s=%s "
                "wav_duration_s=%s (STT phrase times are sparse; wall offsets span full file — large inter-phrase "
                "gaps do not imply dropped chunks)",
                job.get("job_id"),
                round(float(chunk_sec), 3) if chunk_sec is not None else None,
                azure_post_count,
                wall_span_s,
                round(wav_duration_s, 3),
            )

    def _call_azure_speech(self, *, job: dict, audio_doc: dict) -> dict:
        if not self.settings.azure_speech_key:
            raise RuntimeError("AZURE_SPEECH_KEY is not configured")
        primary_locale = self._language_hint_to_locale(str(job.get("language_mix", "") or "en"))
        storage_ref = self._storage_ref_from_audio_doc(audio_doc)
        if not storage_ref:
            raise RuntimeError("Audio storage reference not found")
        storage_adapter = get_audio_storage_adapter()
        if isinstance(storage_adapter, GridFsAudioStorageAdapter):
            audio_bytes = storage_adapter.download_blocking(storage_ref)
        else:
            raise RuntimeError(
                "Azure Blob storage adapter downloads are async; Chunk 2 will wire asyncio batch STT orchestration "
                "(current worker path assumes GridFsAudioStorageAdapter / gridfs backend)."
            )
        declared_mime = self._normalize_audio_content_type(str(audio_doc.get("mime_type", "") or "audio/wav"))
        meta_size = audio_doc.get("size_bytes")
        wav_bytes, transcode_error = self._try_transcode_to_wav_pcm16k_mono(audio_bytes, declared_mime)
        wav_duration = self._pcm_wav_duration_seconds(wav_bytes) if wav_bytes else None
        max_short = float(self.settings.transcription_short_audio_max_seconds)
        chunk_sec = float(self.settings.transcription_chunk_seconds)
        overlap_sec_cfg = float(self.settings.transcription_chunk_overlap_seconds)

        if self.settings.transcription_debug_bytes:
            logger.info(
                "transcription_bytes job_id=%s audio_id=%s meta_size_bytes=%s download_bytes=%s "
                "transcoded_wav_bytes=%s wav_duration_s=%s",
                job.get("job_id"),
                audio_doc.get("audio_id"),
                meta_size,
                len(audio_bytes),
                len(wav_bytes) if wav_bytes else None,
                wav_duration,
            )

        use_chunks = (
            bool(wav_bytes)
            and wav_duration is not None
            and wav_duration > max_short
            and self._resolve_ffmpeg_bin() is not None
        )
        if bool(wav_bytes) and wav_duration is not None and wav_duration > max_short and not self._resolve_ffmpeg_bin():
            logger.warning(
                "Audio ~%.1fs exceeds Azure short-audio REST limit (~%ss) but ffmpeg is not installed; "
                "only the first portion will be transcribed. Install ffmpeg for chunked transcription.",
                wav_duration,
                int(max_short),
            )

        merged_segments: list[dict[str, Any]] = []
        merged_lang = primary_locale
        last_404: HTTPError | None = None
        last_raw: dict | None = None

        if use_chunks:
            wav_chunks, step_sec = self._split_wav_into_time_chunks(
                wav_bytes, chunk_sec, overlap_sec_cfg
            )
            stt_total_bytes = sum(len(c) for c in wav_chunks)
            n_chunks = len(wav_chunks)
            logger.info(
                "transcription_chunking job_id=%s chunk_count=%s chunk_window_s=%s overlap_s=%s step_s=%s",
                job.get("job_id"),
                n_chunks,
                round(chunk_sec, 3),
                round(max(0.0, chunk_sec - step_sec), 3),
                round(step_sec, 3),
            )
            for idx, chunk_bytes in enumerate(wav_chunks):
                wall_start_s = float(idx) * float(step_sec)
                wall_end_s = min(float(wav_duration or 0.0), wall_start_s + float(chunk_sec))
                chunk_offset_ms = int(round(wall_start_s * 1000.0))
                normalized = self._stt_recognize_chunk_with_retries(
                    audio_payload=chunk_bytes,
                    content_type="audio/wav",
                    primary_locale=primary_locale,
                    job_id=str(job.get("job_id", "")),
                    chunk_idx=idx,
                    chunk_total=n_chunks,
                    wall_start_s=wall_start_s,
                    wall_end_s=wall_end_s,
                )
                merged_lang = (normalized or {}).get("language_detected") or merged_lang
                segs = (normalized or {}).get("segments") or []
                for seg in segs:
                    merged_segments.append(
                        {
                            **seg,
                            "start_ms": int(seg.get("start_ms", 0)) + chunk_offset_ms,
                            "end_ms": int(seg.get("end_ms", 0)) + chunk_offset_ms,
                        }
                    )
                if self.settings.transcription_debug_bytes:
                    logger.info(
                        "transcription_chunk_merge job_id=%s index=%s chunk_bytes=%s segments=%s chunk_offset_ms=%s",
                        job.get("job_id"),
                        idx,
                        len(chunk_bytes),
                        len(segs),
                        chunk_offset_ms,
                    )
            if max(0.0, chunk_sec - step_sec) > 0.01 and merged_segments:
                before = len(merged_segments)
                merged_segments = dedupe_chunk_overlap_segments(merged_segments)
                removed = before - len(merged_segments)
                if removed:
                    logger.info(
                        "transcription_chunk_overlap_dedupe job_id=%s removed_segments=%s kept=%s",
                        job.get("job_id"),
                        removed,
                        len(merged_segments),
                    )
            if merged_segments:
                self._log_transcription_pipeline_integrity(
                    job=job,
                    audio_doc=audio_doc,
                    download_bytes=len(audio_bytes),
                    transcoded_wav_bytes=len(wav_bytes) if wav_bytes else None,
                    wav_duration_s=wav_duration,
                    azure_post_count=n_chunks,
                    stt_request_bytes_total=stt_total_bytes,
                    segment_count=len(merged_segments),
                    merged_segments=merged_segments,
                    use_chunked_stt=True,
                    chunk_sec=chunk_sec,
                    chunk_step_sec=step_sec,
                    chunk_overlap_sec=max(0.0, chunk_sec - step_sec),
                )
                return {"language_detected": merged_lang, "segments": merged_segments}
            self._raise_azure_recognition_failure(
                last_404=last_404, last_raw=last_raw, audio_doc=audio_doc, transcode_error=transcode_error
            )

        for audio_payload, content_type in self._audio_payload_candidates(audio_bytes, declared_mime, wav_bytes):
            normalized, l404, lraw, status, _detail = self._short_audio_recognize_one_payload(
                audio_payload=audio_payload,
                content_type=content_type,
                primary_locale=primary_locale,
            )
            if l404:
                last_404 = l404
            if lraw:
                last_raw = lraw
            if normalized and normalized.get("segments"):
                segs = normalized.get("segments") or []
                wc = sum(len(str(s.get("text", "")).split()) for s in segs)
                logger.info(
                    "transcription_short_stt job_id=%s payload_bytes=%s segments=%s words=%s http_status=%s",
                    job.get("job_id"),
                    len(audio_payload),
                    len(segs),
                    wc,
                    status,
                )
                self._log_transcription_pipeline_integrity(
                    job=job,
                    audio_doc=audio_doc,
                    download_bytes=len(audio_bytes),
                    transcoded_wav_bytes=len(wav_bytes) if wav_bytes else None,
                    wav_duration_s=wav_duration,
                    azure_post_count=1,
                    stt_request_bytes_total=len(audio_payload),
                    segment_count=len(segs),
                    merged_segments=segs,
                    use_chunked_stt=False,
                )
                return normalized

        self._raise_azure_recognition_failure(
            last_404=last_404, last_raw=last_raw, audio_doc=audio_doc, transcode_error=transcode_error
        )

    def _audio_payload_candidates(
        self, audio_bytes: bytes, declared_mime: str, wav_bytes: bytes | None
    ) -> list[tuple[bytes, str]]:
        """Prefer FFmpeg-normalized WAV for Azure REST compatibility, then original bytes."""
        candidates: list[tuple[bytes, str]] = []
        if wav_bytes:
            candidates.append((wav_bytes, "audio/wav"))
        candidates.append((audio_bytes, declared_mime))
        deduped: list[tuple[bytes, str]] = []
        seen: set[int] = set()
        for payload, mime in candidates:
            key = id(payload)
            if key in seen:
                continue
            seen.add(key)
            deduped.append((payload, mime))
        return deduped

    @staticmethod
    def _resolve_ffmpeg_bin() -> str | None:
        bin_path = shutil.which("ffmpeg")
        if bin_path:
            return bin_path
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            return str(get_ffmpeg_exe())
        except Exception:
            return None

    @staticmethod
    def _resolve_ffprobe_bin() -> str | None:
        bin_path = shutil.which("ffprobe")
        if bin_path:
            return bin_path
        ffmpeg_bin = TranscriptionWorker._resolve_ffmpeg_bin()
        if not ffmpeg_bin:
            return None
        candidate = Path(ffmpeg_bin).with_name("ffprobe")
        if candidate.exists():
            return str(candidate)
        if os.name == "nt":
            candidate_exe = Path(ffmpeg_bin).with_name("ffprobe.exe")
            if candidate_exe.exists():
                return str(candidate_exe)
        return None

    def _try_transcode_to_wav_pcm16k_mono(
        self, audio_bytes: bytes, declared_mime: str
    ) -> tuple[bytes | None, str | None]:
        ffmpeg_bin = self._resolve_ffmpeg_bin()
        if not ffmpeg_bin:
            return None, None
        suffix = self._suffix_for_mime(declared_mime)
        in_path: str | None = None
        out_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
                tmp_in.write(audio_bytes)
                in_path = tmp_in.name
            out_path = f"{in_path}.wav"
            cmd = [
                ffmpeg_bin,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                in_path,
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                out_path,
            ]
            proc = subprocess.run(cmd, check=False, capture_output=True, timeout=120)
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
                return None, err[:500] if err else f"exit code {proc.returncode}"
            with open(out_path, "rb") as wav_file:
                data = wav_file.read()
            if not data:
                return None, "empty WAV output"
            return data, None
        except subprocess.TimeoutExpired:
            return None, "ffmpeg timed out"
        except OSError as exc:
            return None, str(exc)
        finally:
            for path in (in_path, out_path):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    @staticmethod
    def _suffix_for_mime(mime_type: str) -> str:
        mime = str(mime_type or "").strip().lower()
        if "wav" in mime:
            return ".wav"
        if "mpeg" in mime or "mp3" in mime:
            return ".mp3"
        if "mp4" in mime or "m4a" in mime:
            return ".m4a"
        if "webm" in mime:
            return ".webm"
        return ".bin"

    def _speech_host_candidates(self) -> list[str]:
        hosts: list[str] = []
        configured = str(self.settings.azure_speech_endpoint or "").strip().rstrip("/")
        if configured:
            url = configured if "://" in configured else f"https://{configured}"
            parsed = urlparse(url)
            host = (parsed.hostname or "").strip()
            if host:
                if ".api.cognitive.microsoft.com" in host:
                    host = host.replace(".api.cognitive.microsoft.com", ".stt.speech.microsoft.com")
                hosts.append(host)
        if self.settings.azure_speech_region:
            region_host = f"{self.settings.azure_speech_region}.stt.speech.microsoft.com"
            if region_host not in hosts:
                hosts.append(region_host)
        return hosts

    @staticmethod
    def _language_hint_to_locale(language_mix: str) -> str:
        mapping = {
            "en": "en-IN",
            "hi": "hi-IN",
            "ta": "ta-IN",
            "te": "te-IN",
            "bn": "bn-IN",
            "mr": "mr-IN",
            "kn": "kn-IN",
        }
        token = str(language_mix or "").strip().lower().split("-")[0]
        return mapping.get(token, "en-IN")

    def _candidate_azure_speech_endpoints(self, locale: str) -> list[str]:
        """
        Short-audio REST only (~60s max audio per POST; see Microsoft Learn "Speech to text REST API for short audio").

        Longer files are split into WAV time segments in `_call_azure_speech` before calling this path.
        """
        urls: list[str] = []
        for host in self._speech_host_candidates():
            for mode in ("interactive", "conversation"):
                url = (
                    f"https://{host}/speech/recognition/{mode}/cognitiveservices/v1"
                    f"?language={locale}&format=detailed"
                )
                if url not in urls:
                    urls.append(url)
        if not urls:
            raise RuntimeError("Set AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT")
        return urls

    @staticmethod
    def _normalize_azure_response(raw: dict, locale: str) -> dict:
        # Typical short-audio JSON: RecognitionStatus, DisplayText, NBest[0] — no SpeakerId.
        # Fixture: tests/fixtures/azure_speech_short_audio_success.json
        segments = []
        nbest = raw.get("NBest") or []
        best = nbest[0] if isinstance(nbest, list) and nbest else {}
        display_text = str(raw.get("DisplayText") or best.get("Display") or best.get("Lexical") or "").strip()
        if display_text:
            confidence = float(best.get("Confidence", 0.85) or 0.85)
            offset_ticks = int(raw.get("Offset", 0) or 0)
            duration_ticks = int(raw.get("Duration", 0) or 0)
            start_ms = max(0, offset_ticks // 10000)
            end_ms = max(start_ms, start_ms + (duration_ticks // 10000))
            segments.append(
                {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "speaker_label": "Unknown",
                    "text": display_text,
                    "confidence": confidence,
                    "needs_manual_review": False,
                }
            )

        recognized_phrases = raw.get("RecognizedPhrases") or []
        for phrase in recognized_phrases:
            phrase_text = str(phrase.get("Display") or phrase.get("Lexical") or "").strip()
            if not phrase_text:
                continue
            offset_ticks = int(phrase.get("Offset", 0) or 0)
            duration_ticks = int(phrase.get("Duration", 0) or 0)
            start_ms = max(0, offset_ticks // 10000)
            end_ms = max(start_ms, start_ms + (duration_ticks // 10000))
            nbest_phrase = phrase.get("NBest") or []
            best_phrase = nbest_phrase[0] if isinstance(nbest_phrase, list) and nbest_phrase else {}
            confidence = float(best_phrase.get("Confidence", 0.85) or 0.85)
            segments.append(
                {
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "speaker_label": "Unknown",
                    "text": phrase_text,
                    "confidence": confidence,
                    "needs_manual_review": False,
                }
            )

        if not segments:
            combined = raw.get("CombinedRecognizedPhrases") or []
            for phrase in combined:
                text = str(phrase.get("Display") or phrase.get("Lexical") or "").strip()
                if not text:
                    continue
                segments.append(
                    {
                        "start_ms": 0,
                        "end_ms": 0,
                        "speaker_label": "Unknown",
                        "text": text,
                        "confidence": 0.85,
                        "needs_manual_review": False,
                    }
                )

        if not segments:
            deep_texts = TranscriptionWorker._collect_recognition_strings(raw)
            if deep_texts:
                combined = " ".join(dict.fromkeys(deep_texts)).strip()
                if combined:
                    segments.append(
                        {
                            "start_ms": 0,
                            "end_ms": 0,
                            "speaker_label": "Unknown",
                            "text": combined,
                            "confidence": 0.85,
                            "needs_manual_review": False,
                        }
                    )
        return {"language_detected": locale, "segments": segments}

    @staticmethod
    def _collect_recognition_strings(node: Any, depth: int = 0) -> list[str]:
        """Best-effort walk of Azure JSON for any human-readable recognition strings."""
        if depth > 12:
            return []
        found: list[str] = []
        if isinstance(node, dict):
            for key, value in node.items():
                lk = str(key).lower()
                if lk in {"displaytext", "display", "lexical"} and isinstance(value, str):
                    text = value.strip()
                    if text:
                        found.append(text)
                else:
                    found.extend(TranscriptionWorker._collect_recognition_strings(value, depth + 1))
        elif isinstance(node, list):
            for item in node:
                found.extend(TranscriptionWorker._collect_recognition_strings(item, depth + 1))
        return found

    @staticmethod
    def _normalize_audio_content_type(mime_type: str) -> str:
        mime = str(mime_type or "").strip().lower()
        mapping = {
            "audio/x-m4a": "audio/mp4",
            "audio/m4a": "audio/mp4",
            "audio/mp3": "audio/mpeg",
            "audio/x-wav": "audio/wav",
        }
        return mapping.get(mime, mime or "audio/wav")

    @staticmethod
    def _candidate_locales(primary_locale: str) -> list[str]:
        candidates = [primary_locale]
        for locale in ("en-IN", "en-US", "hi-IN"):
            if locale not in candidates:
                candidates.append(locale)
        return candidates

    def _normalize_segments(self, segments: list[dict[str, Any]]) -> list[dict]:
        normalized: list[dict] = []
        for index, raw in enumerate(segments):
            confidence = float(raw.get("confidence", 0.0))
            speaker = self._canonical_speaker(raw.get("speaker_label") or raw.get("speaker"))
            needs_manual_review = bool(raw.get("needs_manual_review", False))
            if not self.settings.use_local_adapters:
                needs_manual_review = confidence < self.settings.transcription_confidence_threshold
            normalized.append(
                {
                    "segment_id": f"seg_{index + 1}",
                    "start_ms": int(raw.get("start_ms", 0)),
                    "end_ms": int(raw.get("end_ms", 0)),
                    "speaker_label": speaker,
                    "text": str(raw.get("text", "")).strip(),
                    "confidence": round(confidence, 4),
                    "needs_manual_review": needs_manual_review,
                }
            )
        return normalized

    @staticmethod
    def _canonical_speaker(value: str | None) -> str:
        """Normalize labels for Mongo/API (aligned with structured_dialogue role names)."""
        if not value:
            return "Unknown"
        speaker = str(value).strip().lower()
        if speaker in {"doctor", "physician", "clinician"}:
            return "Doctor"
        if speaker in {"patient", "speaker_1"}:
            return "Patient"
        if speaker in {"attendant", "caregiver", "speaker_2", "family member"}:
            return "Family Member"
        if speaker in {"unknown"}:
            return "Unknown"
        return "Unknown"


async def _worker_loop(worker_id: int, stop_event: asyncio.Event, poll_interval_sec: float) -> None:
    worker = TranscriptionWorker()
    heartbeat_interval = max(5, int(worker.settings.transcription_worker_heartbeat_interval_sec))
    next_heartbeat = 0.0
    while not stop_event.is_set():
        now = time.time()
        if now >= next_heartbeat:
            worker.db.worker_heartbeats.update_one(
                {"worker_id": f"{worker.settings.transcription_worker_id}-{worker_id}"},
                {
                    "$set": {
                        "worker_id": f"{worker.settings.transcription_worker_id}-{worker_id}",
                        "last_heartbeat": time.time(),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            next_heartbeat = now + heartbeat_interval
        processed = await worker.process_next_async()
        if not processed:
            await asyncio.sleep(poll_interval_sec)


def start_background_workers() -> None:
    """Start background transcription workers once per process."""
    global _BACKGROUND_TASKS, _STOP_EVENT
    if _BACKGROUND_TASKS:
        return
    settings = get_settings()
    _STOP_EVENT = asyncio.Event()
    concurrency = max(1, int(settings.transcription_worker_concurrency))
    poll_interval = max(0.2, float(settings.transcription_worker_poll_interval_sec))
    for i in range(concurrency):
        _BACKGROUND_TASKS.append(asyncio.create_task(_worker_loop(i + 1, _STOP_EVENT, poll_interval)))


async def stop_background_workers() -> None:
    """Stop background transcription workers gracefully."""
    global _BACKGROUND_TASKS, _STOP_EVENT
    if not _BACKGROUND_TASKS:
        return
    if _STOP_EVENT is not None:
        _STOP_EVENT.set()
    await asyncio.gather(*_BACKGROUND_TASKS, return_exceptions=True)
    _BACKGROUND_TASKS = []
    _STOP_EVENT = None
