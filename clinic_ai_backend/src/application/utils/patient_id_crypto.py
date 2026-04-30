"""Opaque patient ID codec using Fernet symmetric encryption."""
from __future__ import annotations

import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = (get_settings().encryption_key or "").strip()
    if not key:
        key = Fernet.generate_key().decode("utf-8")
        logger.warning("ENCRYPTION_KEY missing; using ephemeral key for this process")
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Invalid ENCRYPTION_KEY for Fernet") from exc


def encode_patient_id(internal_id: str) -> str:
    raw = str(internal_id or "").strip()
    if not raw:
        raise ValueError("internal_id cannot be empty")
    return _get_fernet().encrypt(raw.encode("utf-8")).decode("utf-8")


def decode_patient_id(opaque_token: str) -> str:
    token = str(opaque_token or "").strip()
    if not token:
        raise ValueError("patient_id cannot be empty")
    try:
        return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid patient_id token") from exc


def resolve_internal_patient_id(patient_id: str, *, allow_raw_fallback: bool = True) -> str:
    token = str(patient_id or "").strip()
    if not token:
        raise ValueError("patient_id cannot be empty")
    try:
        return decode_patient_id(token)
    except ValueError:
        if allow_raw_fallback:
            return token
        raise
