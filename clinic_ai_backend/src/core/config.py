"""Configuration module."""
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv

from src.core.errors import ConfigurationError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


class Settings:
    """Application settings from environment variables."""

    def __init__(self) -> None:
        # Resolve values at instantiation time instead of import time, so
        # restarts pick up current env/.env consistently.
        self.app_name: str = "Clinic AI India Backend"
        self.app_version: str = os.getenv("APP_VERSION", "0.1.0")
        self.api_host: str = os.getenv("API_HOST", "0.0.0.0")
        self.api_port: int = int(os.getenv("API_PORT", "8000"))
        self.mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017/clinic_ai")
        self.mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "clinic_ai")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.whatsapp_access_token: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
        self.whatsapp_api_key: str = os.getenv("WHATSAPP_API_KEY", "")
        self.whatsapp_phone_number_id: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.whatsapp_template_post_visit_recap: str = os.getenv("WHATSAPP_TEMPLATE_POST_VISIT_RECAP", "")
        self.whatsapp_verify_token: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
        self.whatsapp_api_version: str = os.getenv("WHATSAPP_API_VERSION", "v21.0")
        self.whatsapp_intake_template_name: str = os.getenv("WHATSAPP_INTAKE_TEMPLATE_NAME", "opening_msg")
        self.whatsapp_intake_template_lang_en: str = os.getenv("WHATSAPP_INTAKE_TEMPLATE_LANG_EN", "en_US")
        self.whatsapp_intake_template_lang_hi: str = os.getenv("WHATSAPP_INTAKE_TEMPLATE_LANG_HI", "hi")
        self.whatsapp_intake_template_param_count: int = int(os.getenv("WHATSAPP_INTAKE_TEMPLATE_PARAM_COUNT", "1"))
        self.intake_use_llm_message: bool = os.getenv("INTAKE_USE_LLM_MESSAGE", "true").lower() == "true"
        self.intake_require_all_agents: bool = os.getenv("INTAKE_REQUIRE_ALL_AGENTS", "true").lower() == "true"
        self.intake_strict_validation: bool = os.getenv("INTAKE_STRICT_VALIDATION", "true").lower() == "true"
        # Follow-up reminders (post-visit next visit). Defaults to dedicated Meta template `follow_up_1`.
        self.whatsapp_followup_template_name: str = os.getenv("WHATSAPP_FOLLOWUP_TEMPLATE_NAME", "follow_up_1")
        self.whatsapp_followup_template_lang_en: str = os.getenv(
            "WHATSAPP_FOLLOWUP_TEMPLATE_LANG_EN", os.getenv("WHATSAPP_INTAKE_TEMPLATE_LANG_EN", "en_US")
        )
        self.whatsapp_followup_template_lang_hi: str = os.getenv(
            "WHATSAPP_FOLLOWUP_TEMPLATE_LANG_HI", os.getenv("WHATSAPP_INTAKE_TEMPLATE_LANG_HI", "hi")
        )
        self.whatsapp_followup_template_param_count: int = int(os.getenv("WHATSAPP_FOLLOWUP_TEMPLATE_PARAM_COUNT", "1"))
        # If set, POST /workflow/follow-up-reminders/run requires header X-Cron-Secret with this value.
        self.follow_up_reminder_cron_secret: str = os.getenv("FOLLOW_UP_REMINDER_CRON_SECRET", "")
        # Post-visit summary WhatsApp: template body = generated whatsapp_payload. Empty name falls back to intake template only.
        self.whatsapp_post_visit_template_name: str = os.getenv("WHATSAPP_POST_VISIT_TEMPLATE_NAME", "")
        self.whatsapp_post_visit_template_lang_en: str = os.getenv(
            "WHATSAPP_POST_VISIT_TEMPLATE_LANG_EN",
            os.getenv("WHATSAPP_FOLLOWUP_TEMPLATE_LANG_EN", os.getenv("WHATSAPP_INTAKE_TEMPLATE_LANG_EN", "en_US")),
        )
        self.whatsapp_post_visit_template_lang_hi: str = os.getenv(
            "WHATSAPP_POST_VISIT_TEMPLATE_LANG_HI",
            os.getenv("WHATSAPP_FOLLOWUP_TEMPLATE_LANG_HI", os.getenv("WHATSAPP_INTAKE_TEMPLATE_LANG_HI", "hi")),
        )
        self.whatsapp_post_visit_template_param_count: int = int(
            os.getenv("WHATSAPP_POST_VISIT_TEMPLATE_PARAM_COUNT", "1")
        )
        self.azure_speech_key: str = os.getenv("AZURE_SPEECH_KEY", "") or os.getenv(
            "AZURE_SPEECH_SUBSCRIPTION_KEY", ""
        )
        self.azure_speech_region: str = os.getenv("AZURE_SPEECH_REGION", "")
        self.azure_speech_endpoint: str = os.getenv("AZURE_SPEECH_ENDPOINT", "")
        self.azure_speech_batch_transcription_locale: str = os.getenv(
            "AZURE_SPEECH_BATCH_TRANSCRIPTION_LOCALE", "hi-IN"
        )
        self.azure_queue_connection_string: str = os.getenv("AZURE_QUEUE_CONNECTION_STRING", "")
        self.azure_queue_name: str = os.getenv("AZURE_QUEUE_NAME", "")
        self.azure_queue_poison_name: str = os.getenv("AZURE_QUEUE_POISON_NAME", "")
        self.azure_blob_connection_string: str = os.getenv("AZURE_BLOB_CONNECTION_STRING", "")
        self.azure_blob_container: str = os.getenv("AZURE_BLOB_CONTAINER", "")
        self.transcription_confidence_threshold: float = float(
            os.getenv("TRANSCRIPTION_CONFIDENCE_THRESHOLD", "0.75")
        )
        self.transcription_manual_review_ratio_threshold: float = float(
            os.getenv("TRANSCRIPTION_MANUAL_REVIEW_RATIO_THRESHOLD", "0.25")
        )
        self.max_audio_size_mb: int = int(os.getenv("MAX_AUDIO_SIZE_MB", "25"))
        self.allowed_audio_mime_types: list[str] = [
            value.strip()
            for value in os.getenv(
                "ALLOWED_AUDIO_MIME_TYPES",
                "audio/wav,audio/mpeg,audio/mp3,audio/x-wav,audio/mp4,audio/webm,audio/m4a,audio/x-m4a",
            ).split(",")
            if value.strip()
        ]
        self.transcription_max_retries: int = int(os.getenv("TRANSCRIPTION_MAX_RETRIES", "3"))
        # HTTP read/write timeout for a single Azure short-audio REST POST (one chunk).
        self.transcription_timeout_sec: int = int(os.getenv("TRANSCRIPTION_TIMEOUT_SEC", "120"))
        # Wall-clock cap for the whole job in the worker (download + ffmpeg + all chunks). Long visits need this >> single-chunk timeout.
        self.transcription_job_timeout_sec: int = int(os.getenv("TRANSCRIPTION_JOB_TIMEOUT_SEC", "3600"))
        # Azure "short audio" REST processes only the first ~60s; we split longer WAVs into chunks of this many seconds (requires ffmpeg).
        self.transcription_short_audio_max_seconds: float = float(
            os.getenv("TRANSCRIPTION_SHORT_AUDIO_MAX_SECONDS", "55")
        )
        self.transcription_chunk_seconds: float = float(os.getenv("TRANSCRIPTION_CHUNK_SECONDS", "50"))
        # Overlap between consecutive WAV windows sent to Azure (reduces word loss at chunk boundaries; requires ffmpeg).
        self.transcription_chunk_overlap_seconds: float = float(
            os.getenv("TRANSCRIPTION_CHUNK_OVERLAP_SECONDS", "1.5")
        )
        # Retries per chunk for transient HTTP errors or empty STT payloads (same bytes re-posted).
        self.transcription_chunk_max_stt_retries: int = int(os.getenv("TRANSCRIPTION_CHUNK_MAX_STT_RETRIES", "3"))
        # Set to "1" / "true" to log byte sizes and chunk counts at INFO (one line per job).
        self.transcription_debug_bytes: bool = os.getenv("TRANSCRIPTION_DEBUG_BYTES", "").lower() in {
            "1",
            "true",
            "yes",
        }
        # Raw transcript is split into contiguous slices <= this size before OpenAI structuring (ordered merge).
        self.structure_dialogue_max_chunk_chars: int = int(os.getenv("STRUCTURE_DIALOGUE_MAX_CHUNK_CHARS", "12000"))
        self.transcription_worker_concurrency: int = int(os.getenv("TRANSCRIPTION_WORKER_CONCURRENCY", "2"))
        self.transcription_worker_poll_interval_sec: float = float(
            os.getenv("TRANSCRIPTION_WORKER_POLL_INTERVAL_SEC", "1.0")
        )
        self.transcription_worker_heartbeat_interval_sec: int = int(
            os.getenv("TRANSCRIPTION_WORKER_HEARTBEAT_INTERVAL_SEC", "30")
        )
        self.transcription_worker_dead_after_sec: int = int(
            os.getenv("TRANSCRIPTION_WORKER_DEAD_AFTER_SEC", "90")
        )
        self.transcription_worker_id: str = os.getenv("TRANSCRIPTION_WORKER_ID", "clinic-ai-worker")
        # Public base URL used for Azure Speech batch to fetch audio (no trailing slash required).
        self.public_backend_url: str = (os.getenv("PUBLIC_BACKEND_URL", "") or "").strip()
        # HMAC secret for self-hosted signed URLs to /internal/audio; min 32 chars when generating/using URLs.
        self.audio_url_signing_secret: str = os.getenv("AUDIO_URL_SIGNING_SECRET", "") or ""
        # Keep workers on by default so /api/notes/transcribe jobs are actually consumed
        # in standard single-service deployments (e.g., Render web service only).
        self.run_transcription_workers_in_api: bool = (
            os.getenv("RUN_TRANSCRIPTION_WORKERS_IN_API", "true").lower() == "true"
        )
        self.use_local_adapters: bool = os.getenv("USE_LOCAL_ADAPTERS", "false").lower() == "true"
        self.local_audio_storage_path: str = os.getenv("LOCAL_AUDIO_STORAGE_PATH", "/tmp/clinic_audio")
        self.allow_local_audio_fallback: bool = os.getenv("ALLOW_LOCAL_AUDIO_FALLBACK", "false").lower() == "true"
        self.mongo_audio_bucket_name: str = os.getenv("MONGO_AUDIO_BUCKET_NAME", "audio_blobs")
        self.default_note_type: str = os.getenv("DEFAULT_NOTE_TYPE", "india_clinical")
        self.encryption_key: str = os.getenv("ENCRYPTION_KEY", "")
        self.jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expire_hours: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
        self.msg91_api_key: str = os.getenv("MSG91_API_KEY", "")
        self.msg91_template_id: str = os.getenv("MSG91_TEMPLATE_ID", "")
        self.access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
        self.refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
        self.abdm_enabled: bool = os.getenv("ABDM_ENABLED", "false").lower() == "true"

        _tqb = os.getenv("TRANSCRIPTION_QUEUE_BACKEND", "mongo").strip().lower()
        if _tqb not in ("mongo", "azure"):
            raise ConfigurationError(
                f"TRANSCRIPTION_QUEUE_BACKEND must be 'mongo' or 'azure'; got {_tqb!r}. "
                "Use 'mongo' (default/FIFO Mongo collection) or 'azure' (after Sprint 2B Chunk 1)."
            )
        self.transcription_queue_backend: str = _tqb

        _tsb = os.getenv("TRANSCRIPTION_STORAGE_BACKEND", "gridfs").strip().lower()
        if _tsb not in ("gridfs", "azure_blob"):
            raise ConfigurationError(
                f"TRANSCRIPTION_STORAGE_BACKEND must be 'gridfs' or 'azure_blob'; got {_tsb!r}. "
                "Use 'gridfs' (default/GridFS) or 'azure_blob' (after Sprint 2B Chunk 2)."
            )
        self.transcription_storage_backend: str = _tsb


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
