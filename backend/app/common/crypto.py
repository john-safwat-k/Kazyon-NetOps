"""Symmetric AES-GCM / Fernet credential encryption helper using `Settings.encryption_key`."""

from __future__ import annotations

import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.common.config import get_settings


def _get_fernet() -> Fernet:
    raw_key = get_settings().encryption_key.encode("utf-8")
    digest = hashlib.sha256(raw_key).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain_text: str) -> str:
    """Encrypt a plaintext credential string into a URL-safe Fernet token."""
    cleaned = plain_text.strip()
    if not cleaned:
        return ""
    return _get_fernet().encrypt(cleaned.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher_text: Optional[str]) -> str:
    """Decrypt a Fernet token back to plaintext; returns empty string if missing or invalid."""
    if not cipher_text:
        return ""
    try:
        return _get_fernet().decrypt(cipher_text.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
