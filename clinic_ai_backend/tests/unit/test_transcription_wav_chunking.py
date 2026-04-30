"""WAV duration parsing and ffmpeg chunking used for Azure short-audio REST limits."""
from __future__ import annotations

import io
import shutil
import wave
from types import SimpleNamespace

import pytest

from src.workers.transcription_worker import TranscriptionWorker


def _pcm_wav_bytes(duration_sec: float, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        n = int(duration_sec * sample_rate)
        wf.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


def test_pcm_wav_duration_seconds_matches_written_length() -> None:
    wav = _pcm_wav_bytes(2.5)
    dur = TranscriptionWorker._pcm_wav_duration_seconds(wav)
    assert dur is not None
    assert abs(dur - 2.5) < 0.05


def test_pcm_wav_duration_returns_none_for_non_wav() -> None:
    assert TranscriptionWorker._pcm_wav_duration_seconds(b"not a wav file") is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_split_wav_into_time_chunks_multiple_segments() -> None:
    """Long PCM WAV is split into time windows under Azure short-audio REST limits."""
    worker = TranscriptionWorker()
    wav = _pcm_wav_bytes(42.0)
    chunks, _step = worker._split_wav_into_time_chunks(wav, 15.0, 0.0)
    assert len(chunks) >= 3
    for piece in chunks:
        d = TranscriptionWorker._pcm_wav_duration_seconds(piece)
        assert d is not None
        assert d <= 16.0, "each chunk should be ~chunk_sec seconds"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_split_short_wav_returns_single_chunk() -> None:
    worker = TranscriptionWorker()
    wav = _pcm_wav_bytes(3.0)
    chunks, _step = worker._split_wav_into_time_chunks(wav, 50.0, 0.0)
    assert len(chunks) == 1
    assert chunks[0] == wav


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_long_silent_wav_chunks_cover_full_duration() -> None:
    """Regression: multi-minute silent PCM must split so summed chunk durations ~= source (STT path coverage)."""
    worker = TranscriptionWorker()
    total_sec = 185.0
    wav = _pcm_wav_bytes(total_sec)
    chunk_sec = 50.0
    chunks, step_sec = worker._split_wav_into_time_chunks(wav, chunk_sec, 0.0)
    assert len(chunks) >= 3
    decoded_sum = 0.0
    stt_bytes = 0
    for piece in chunks:
        stt_bytes += len(piece)
        d = TranscriptionWorker._pcm_wav_duration_seconds(piece)
        assert d is not None
        decoded_sum += d
    assert abs(decoded_sum - total_sec) < 2.0, "chunk WAV durations should cover the full visit length"
    assert stt_bytes > len(wav) * 0.5, "each chunk is a full WAV file; total bytes sent to STT is sum of chunks"
    assert abs(step_sec - chunk_sec) < 0.01


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_split_wav_overlap_reduces_step_between_windows() -> None:
    worker = TranscriptionWorker()
    wav = _pcm_wav_bytes(120.0)
    chunks, step = worker._split_wav_into_time_chunks(wav, chunk_sec=50.0, overlap_sec=2.0)
    assert len(chunks) >= 3
    assert abs(step - 48.0) < 0.05
    last_start = (len(chunks) - 1) * step
    assert last_start + 50.0 >= 120.0 - 0.5, "overlapped windows should cover full source duration"


def test_stt_chunk_retries_soft_skip_exhausted_no_segments() -> None:
    worker = TranscriptionWorker.__new__(TranscriptionWorker)
    worker.settings = SimpleNamespace(transcription_chunk_max_stt_retries=2)

    def _fake_short_audio_recognize_one_payload(**_kwargs):
        return (None, None, None, None, "exhausted_no_segments")

    worker._short_audio_recognize_one_payload = _fake_short_audio_recognize_one_payload  # type: ignore[attr-defined]

    result = worker._stt_recognize_chunk_with_retries(
        audio_payload=_pcm_wav_bytes(40.0),
        content_type="audio/wav",
        primary_locale="en-IN",
        job_id="job-1",
        chunk_idx=0,
        chunk_total=5,
        wall_start_s=0.0,
        wall_end_s=40.0,
    )

    assert result["language_detected"] == "en-IN"
    assert result["segments"] == []
