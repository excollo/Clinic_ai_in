# Long audio transcription (10+ minutes)

## Speaker labels on `transcription_results.segments`

### Root cause (Azure short-audio REST)

The worker calls **Speech-to-text REST API for short audio** (`/speech/recognition/{interactive|conversation}/cognitiveservices/v1?format=detailed`). Microsoft’s JSON for this path is essentially **NBest + timing** (`Offset` / `Duration` in 100-ns ticks, `Display` / `Lexical` text). There is **no per-phrase `SpeakerId` or channel** in the payloads we parse (see `tests/fixtures/azure_speech_short_audio_success.json` and `TranscriptionWorker._normalize_azure_response`).

So STT segments are stored with `speaker_label: "unknown"` at the Azure layer. **Doctor / Patient** in the product comes from **OpenAI structuring** (`structure_dialogue_from_transcript_sync`) on the full transcript.

### Fix implemented (Option 1)

After structured dialogue is produced, we run a **deterministic alignment** (`align_segments_with_structured_dialogue` in `src/application/utils/transcript_dialogue.py`): monotone dynamic programming maps each segment’s text to the best-matching dialogue turn by **token overlap**, with `speaker_label` set to **`Doctor` / `Patient` / `Family Member`** when overlap ≥ a small threshold, else **`Unknown`** (same vocabulary as `structured_dialogue` keys). Persisted `transcription_results.segments` then match the dialogue roles when wording overlaps.

### Chunk STT: missing middle content (root cause & mitigations)

**What went wrong historically**

1. **Non-overlapping windows** — Hard splits every `TRANSCRIPTION_CHUNK_SECONDS` can cut words at boundaries; Azure returns one phrase per boundary side, so text at joins was easy to lose.
2. **No per-chunk retries** — A single empty or flaky REST response for a middle chunk still advanced the loop; **no segment rows** were added for that wall-clock slice while the job continued, so `full_transcript_text` and `word_count` could stay far below what ~10+ minutes of speech implies.
3. **Sparse phrase timestamps** — Large gaps in `start_ms` between phrases are normal (silence); they are **not** proof of dropped chunks. Use **`transcription_chunk_stt`** / **`transcription_pipeline_integrity`** logs to verify every chunk index ran.

**What we do now**

- **Overlap** — `TRANSCRIPTION_CHUNK_OVERLAP_SECONDS` (default **1.5**): FFmpeg extracts windows of length `chunk_sec` stepped by `chunk_sec − overlap`. Offsets use **`idx × step`** seconds, not `idx × chunk_sec`.
- **Retries** — `TRANSCRIPTION_CHUNK_MAX_STT_RETRIES` (default **3**) re-posts the same chunk bytes on empty STT or HTTP **429 / 502 / 503**.
- **No silent hard-fail for tiny tails** — If a chunk is small (`payload_bytes < 800_000`, roughly a short tail) and STT is still empty after retries, we log **`transcription_chunk_stt_empty_soft`** and continue; near-full chunks still **raise** so a broken STT path cannot hide.
- **Dedupe** — Overlap can duplicate identical phrases; `dedupe_chunk_overlap_segments` removes time-overlapping near-identical lines before save.
- **Logging** — Every chunk emits **`transcription_chunk_stt`** at INFO (`wall_s`, `payload_bytes`, `segments`, `words`, `http_status`). **`transcription_chunking`** logs `chunk_window_s`, `overlap_s`, and `step_s`.

**Not chosen here (Option 2):** Azure **batch** transcription with diarization — higher quality, larger operational change (blob SAS, polling, SpeakerId → role mapping).

## Root cause (fixed)

The worker called Azure **Speech-to-text REST API for short audio**:

`https://<region>.stt.speech.microsoft.com/speech/recognition/{interactive|conversation}/cognitiveservices/v1`

Microsoft documents a **maximum of about 60 seconds of audio per request** for this endpoint. Sending a full consultation (for example ~12 minutes) still returned HTTP 200, but only the **first portion** of the file was recognized—hence short `audio_duration_seconds`, few words, and misleading “success.”

Implementation: `src/workers/transcription_worker.py` — `_candidate_azure_speech_endpoints` (short-audio URLs) and `_call_azure_speech` (splits longer PCM WAVs with FFmpeg and merges segments).

## What we do now

1. Multipart handler reads the full `UploadFile` into memory once (`tests` and `MAX_AUDIO_SIZE_MB` bound size).
2. **GridFS / local file** stores the same bytes; metadata `size_bytes` is `len(payload)`.
3. Worker downloads the full blob, compares **stored `size_bytes` vs `len(downloaded)`**; on mismatch logs **`transcription_byte_mismatch`** at ERROR.
4. **FFmpeg** transcodes to **16 kHz mono PCM WAV** when `ffmpeg` is on `PATH`.
5. If WAV duration **>** `TRANSCRIPTION_SHORT_AUDIO_MAX_SECONDS` (default **55**) and **ffmpeg** is installed, the WAV is **split in time** into chunks of `TRANSCRIPTION_CHUNK_SECONDS` (default **50** seconds).
6. Each chunk is POSTed to the same short-audio REST API; transcripts are **stitched** with **wall-clock** millisecond offsets (`chunk_index * chunk_sec * 1000`), so segment timelines span the full visit (fixes under-reported `audio_duration_seconds` when a chunk had speech only at the start).
7. After a successful STT path, the worker always emits one **`transcription_pipeline_integrity`** INFO line: stored vs download bytes, transcoded WAV size, `wav_duration_s`, chunked flag, Azure POST count, **sum of HTTP body bytes** sent to Azure, segment count, `max_segment_end_s`, **`speech_span_s`** (sum of phrase durations), **`max_consecutive_gap_ms`** (largest gap between consecutive phrase intervals by `start_ms`), and **`chunk_wall_span_s`** when chunked (`azure_post_count × chunk_sec`, i.e. full wall time sent to STT).
8. With **`TRANSCRIPTION_DEBUG_BYTES=true`** and chunked STT, an extra **`transcription_chunk_wall_audit`** line states that **large gaps between phrase `start_ms` values are expected** when the next phrase is in a later time chunk: offsets are **wall-clock** (`chunk_index × chunk_sec × 1000`), while Azure only returns times **inside** each chunk. A jump from ~17 s to ~50 s usually means **silence until the next chunk boundary**, not dropped audio. Compare `chunk_wall_span_s` to `wav_duration_s` and `azure_post_count` to `ceil(wav_duration / TRANSCRIPTION_CHUNK_SECONDS)` to confirm every slice was posted.

Without ffmpeg, long files still **truncate**; the worker logs a warning.

### Byte accounting (what “equal” means)

| Stage | Meaning |
|--------|--------|
| Upload | `multipart_bytes` in **`transcription_upload_accepted`** (INFO, API). |
| Optional verify | If `TRANSCRIPTION_DEBUG_BYTES=true`, API re-reads storage and logs **`transcription_upload_storage_roundtrip_ok`** or **`transcription_upload_storage_mismatch`**. |
| Worker | **`transcription_pipeline_integrity`**: `stored_bytes` / `download_bytes` / `stored_eq_download`. |
| STT wire | **`stt_request_bytes_total`**: sum of per-chunk WAV bodies in chunked mode, or the single winning payload in short mode. This is usually **PCM WAV**, so it can legitimately differ from the original upload when the doctor sent MP3/M4A/WebM. |

Decoded duration: use **`wav_duration_s`** from the worker log and **`max_segment_end_s`**; after the wall-clock offset fix they should track within ~15% for long files; otherwise **`transcription_segment_timeline_vs_wav`** is logged at WARNING.

## Doctor/Patient dialogue (LLM)

Raw STT text is structured with OpenAI in `src/application/services/structure_dialogue.py`.

- Prompts require **no summarization away** of clinical phases; long transcripts are split with **`chunk_transcript_for_structure`** (contiguous, lossless rejoin) and processed **in order**, then concatenated with light boundary deduplication (`_dedupe_adjacent_dialogue_turns`).
- Chunk size: **`STRUCTURE_DIALOGUE_MAX_CHUNK_CHARS`** (default **12000**).

## PII scrub (`dialogue_pii.py`)

Phone patterns are constrained to **NANP-style** numbers and **India +91 / 91** mobile forms so plain 10-digit clinical IDs are not rewritten. SSN scrub uses a **narrow dashed** pattern to reduce false positives.

## Operator checklist

| Item | Notes |
|------|--------|
| **ffmpeg** (and **ffprobe** optional) | Required on the worker host for chunking. Render: ensure it is in the Docker image or buildpack. |
| `TRANSCRIPTION_JOB_TIMEOUT_SEC` | Default **3600**. Must exceed `(chunk_count × per-chunk latency)` for long visits. |
| `TRANSCRIPTION_TIMEOUT_SEC` | Per **HTTP POST** to Azure (one chunk). Default **120** is usually enough. |
| `MAX_AUDIO_SIZE_MB` | Upload limit in the API; independent of Azure’s **duration** limit. |
| `TRANSCRIPTION_DEBUG_BYTES=true` | Extra per-chunk logs + **upload round-trip** byte verify on the API. |
| `STRUCTURE_DIALOGUE_MAX_CHUNK_CHARS` | Lower if OpenAI context errors; raise only if model window allows. |

## Validating on Render (10+ minute generic clip)

Use a **non-PHI** clip (silence + TTS, or a licensed generic consultation sample). No real patient audio in automated tests.

1. Build/deploy worker image with **ffmpeg** on `PATH` (see `deployments/docker/Dockerfile.worker` if present).
2. Set `TRANSCRIPTION_DEBUG_BYTES=true` temporarily for one validation run.
3. Upload via `POST /notes/transcribe` under the normal size cap; poll until completed.
4. In logs, confirm:
   - **`transcription_upload_accepted`** `multipart_bytes` matches audio file size on disk.
   - **`transcription_pipeline_integrity`**: `stored_eq_download=true`, `chunked_stt=true` for long files, `azure_post_count` ≈ `ceil(duration / TRANSCRIPTION_CHUNK_SECONDS)`, `wav_duration_s` in the **multi-minute** range.
5. Fetch dialogue / transcript and confirm markers from early **and** late in the clip appear (no “collapsed” middle).

## Automated tests

- `tests/unit/test_segment_dialogue_alignment.py` — segment `speaker_label` alignment to structured Doctor/Patient turns.
- `tests/unit/test_transcription_wav_chunking.py` — PCM duration parsing, ffmpeg split, **long silent WAV chunk duration sum** (regression for partial coverage).
- `tests/unit/test_structure_dialogue_chunking.py` — lossless chunking of long text; mocked multi-chunk OpenAI **ordered merge**.
- `tests/unit/test_dialogue_pii.py` — vitals/doses preserved; phone/email/SSN-style scrubbed.

## Alternatives not implemented (larger change)

- **Batch transcription** (blob SAS + polling) — best for very long files; needs durable blob URLs.
- **Speech SDK continuous recognition** — WebSocket/long session; heavier dependency and process model.
