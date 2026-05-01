"""Unit tests for HMAC-signed audio fetch URLs."""

import pytest

from src.application.services.audio_signed_url import generate_audio_access_url, verify_audio_access_token
from src.core.config import get_settings
from src.core.errors import ConfigurationError


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    yield
    get_settings.cache_clear()


def test_generate_and_verify_roundtrip(monkeypatch):
    monkeypatch.setenv(
        "AUDIO_URL_SIGNING_SECRET",
        "x" * 32,
    )
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://api.example.test")
    get_settings.cache_clear()
    aid = "a1b2c3d4-e5f6-7890-abcd-ef0123456789"
    url = generate_audio_access_url(audio_id=aid, expires_in_seconds=3600)
    assert "/internal/audio/" in url
    assert aid in url
    assert "token=" in url
    token = url.split("token=", 1)[1]
    v = verify_audio_access_token(audio_id=aid, token=token)
    assert v.audio_id == aid


def test_generate_requires_public_url(monkeypatch):
    monkeypatch.setenv("AUDIO_URL_SIGNING_SECRET", "y" * 32)
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError, match="PUBLIC_BACKEND_URL"):
        generate_audio_access_url(audio_id="aid", expires_in_seconds=60)


def test_generate_requires_secret_length(monkeypatch):
    monkeypatch.setenv("AUDIO_URL_SIGNING_SECRET", "short")
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://api.example.test")
    get_settings.cache_clear()
    with pytest.raises(ConfigurationError, match="AUDIO_URL_SIGNING_SECRET"):
        generate_audio_access_url(audio_id="aid", expires_in_seconds=60)


def test_verify_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("AUDIO_URL_SIGNING_SECRET", "z" * 32)
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://api.example.test")
    get_settings.cache_clear()
    aid = "00000000-0000-0000-0000-000000000001"
    token = generate_audio_access_url(audio_id=aid, expires_in_seconds=3600).split("token=", 1)[1]
    monkeypatch.setenv("AUDIO_URL_SIGNING_SECRET", "b" * 32)
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        verify_audio_access_token(audio_id=aid, token=token)


def test_verify_rejects_path_audio_mismatch(monkeypatch):
    monkeypatch.setenv("AUDIO_URL_SIGNING_SECRET", "w" * 32)
    monkeypatch.setenv("PUBLIC_BACKEND_URL", "https://api.example.test")
    get_settings.cache_clear()
    aid = "11111111-1111-1111-1111-111111111111"
    url = generate_audio_access_url(audio_id=aid, expires_in_seconds=3600)
    token = url.split("token=", 1)[1]
    with pytest.raises(ValueError, match="audio_id_mismatch"):
        verify_audio_access_token(audio_id="22222222-2222-2222-2222-222222222222", token=token)
