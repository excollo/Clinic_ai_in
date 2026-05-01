"""HMAC-signed, time-limited URLs for Azure Speech batch to fetch audio from this backend (GridFS)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from typing import NamedTuple

from src.core.config import get_settings
from src.core.errors import ConfigurationError


class VerifiedAudioToken(NamedTuple):
    audio_id: str
    expires_at: int
    nonce: str


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def generate_audio_access_url(*, audio_id: str, expires_in_seconds: int = 86400) -> str:
    """Build a public URL Azure Speech can GET to retrieve audio bytes."""
    settings = get_settings()
    if not settings.public_backend_url:
        raise ConfigurationError("PUBLIC_BACKEND_URL is required to generate audio fetch URLs for batch transcription.")
    if len(settings.audio_url_signing_secret) < 32:
        raise ConfigurationError(
            "AUDIO_URL_SIGNING_SECRET must be at least 32 characters. "
            "Generate a strong random secret for production."
        )
    expires_at = int(time.time()) + int(expires_in_seconds)
    nonce = secrets.token_urlsafe(16)
    payload = f"{audio_id}|{expires_at}|{nonce}"
    signature = hmac.new(
        settings.audio_url_signing_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    token = _b64url_encode(f"{payload}|{signature}".encode("utf-8"))
    base = settings.public_backend_url.rstrip("/")
    return f"{base}/internal/audio/{audio_id}?token={token}"


def verify_audio_access_token(*, audio_id: str, token: str) -> VerifiedAudioToken:
    """Validate token shape, expiry, HMAC, and path/audio_id match."""
    settings = get_settings()
    if len(settings.audio_url_signing_secret) < 32:
        raise ConfigurationError("AUDIO_URL_SIGNING_SECRET is not configured")
    try:
        inner = _b64url_decode(token).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid_token_encoding") from exc
    parts = inner.split("|")
    if len(parts) != 4:
        raise ValueError("invalid_token_shape")
    tid, exp_s, nonce, sig = parts
    if tid != audio_id:
        raise ValueError("audio_id_mismatch")
    try:
        expires_at = int(exp_s)
    except ValueError as exc:
        raise ValueError("invalid_expiry") from exc
    if int(time.time()) > expires_at:
        raise ValueError("token_expired")
    payload = f"{tid}|{expires_at}|{nonce}"
    expected = hmac.new(
        settings.audio_url_signing_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("invalid_signature")
    return VerifiedAudioToken(audio_id=tid, expires_at=expires_at, nonce=nonce)


def token_fingerprint(token: str) -> str:
    """Stable id for single-use tracking (do not log raw token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
