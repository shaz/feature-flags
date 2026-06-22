"""SDK credential generation. We store only a SHA-256 hash of each key; the
plaintext is shown once at creation and never again.
"""
from __future__ import annotations

import hashlib
import secrets

_KIND_CODE = {"server": "srv", "client": "cli", "mobile": "mob"}


def generate(kind: str, env_key: str) -> tuple[str, str, str]:
    """Return (plaintext_key, key_prefix, key_hash)."""
    prefix = f"{_KIND_CODE[kind]}-{env_key}-"
    plaintext = prefix + secrets.token_urlsafe(24)
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, prefix, key_hash


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()
