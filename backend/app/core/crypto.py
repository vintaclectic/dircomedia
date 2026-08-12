"""
Credential encryption at rest — Fernet (AES-128-CBC + HMAC-SHA256).

Every OAuth access/refresh token stored in `platform_credentials` is encrypted
with CREDENTIAL_ENCRYPTION_KEY before it touches the database, and decrypted
only in the moment a platform client needs to sign a request. The database file
on disk never contains a usable token.

WHY THIS EXISTS (the threat we're actually defending against): dircomedia.db is
a plain SQLite file. It gets copied into backups, rsynced to the D drive, and
opened by `sqlite3` for debugging. Every one of those is a place a plaintext
posting token would leak from — and a leaked posting token is somebody else
tweeting as Vinta. Encryption at rest makes the DB copy worthless on its own.

FAIL-CLOSED: if CREDENTIAL_ENCRYPTION_KEY is missing or malformed, encryption
raises rather than silently storing plaintext. A token that "saved fine" but sat
unencrypted is worse than a save that failed loudly.

NEVER log the output of decrypt(). Nothing in this module prints a token, and
nothing that calls it should either.

Council build 2026-08-12 (YH9AE4D, helios-fusion).
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class CredentialCryptoError(RuntimeError):
    """Raised when the encryption key is absent/invalid or a blob won't decrypt."""


@lru_cache
def _fernet() -> Fernet:
    key = (os.environ.get("CREDENTIAL_ENCRYPTION_KEY") or "").strip()
    if not key:
        raise CredentialCryptoError(
            "CREDENTIAL_ENCRYPTION_KEY is not set. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"\n"
            "and add it to backend/.env. Refusing to store credentials in plaintext."
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:  # malformed key -> fail closed, never fall back
        raise CredentialCryptoError(
            f"CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key ({e.__class__.__name__}). "
            "It must be a 32-byte urlsafe-base64 key from Fernet.generate_key()."
        ) from e


def crypto_available() -> bool:
    """True when a usable key is configured. Used by health/status surfaces so
    the UI can say 'encryption not configured' instead of throwing at save time."""
    try:
        _fernet()
        return True
    except CredentialCryptoError:
        return False


def encrypt(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a secret for storage. None/'' round-trips as None (a NULL column
    is the honest representation of 'this platform has no refresh token')."""
    if plaintext is None or plaintext == "":
        return None
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt a stored secret. Returns None for NULL/empty columns.

    Raises CredentialCryptoError on a blob this key cannot open — which almost
    always means the key was rotated or replaced. We surface that loudly so the
    dashboard can tell Vinta to reconnect, instead of a platform client failing
    later with an inscrutable 401.
    """
    if ciphertext is None or ciphertext == "":
        return None
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise CredentialCryptoError(
            "Stored credential could not be decrypted with the current "
            "CREDENTIAL_ENCRYPTION_KEY (key rotated or blob corrupt). "
            "Reconnect this platform to store a fresh token."
        ) from e


def redact(secret: Optional[str]) -> str:
    """Safe-for-logs rendering of a secret: last 4 chars only, never the head.

    The tail is enough to tell two tokens apart when debugging; the head is what
    an attacker would need to guess the rest. Use this ANY time a credential is
    near a log line.
    """
    if not secret:
        return "<none>"
    if len(secret) <= 4:
        return "*" * len(secret)
    return "*" * 8 + secret[-4:]
