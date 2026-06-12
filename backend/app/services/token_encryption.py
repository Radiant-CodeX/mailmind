"""
Fernet-based encryption for OAuth tokens stored in oauth_accounts.

All access_token and refresh_token values are encrypted before writing to the
database and decrypted on read. The encryption key is TOKEN_ENCRYPTION_KEY in
settings — a URL-safe base64-encoded 32-byte key generated with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

If TOKEN_ENCRYPTION_KEY is not set (dev/test without a DB), encrypt/decrypt
are no-ops so the rest of the code runs unmodified.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet

    from app.config.settings import settings
    key = settings.token_encryption_key
    if not key:
        return None

    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except Exception as exc:
        logger.error("Failed to initialise Fernet: %s", exc)
        return None


def encrypt_token(token: str) -> str:
    """Encrypt a raw OAuth token string. Returns ciphertext as a string."""
    if not token:
        return token
    f = _get_fernet()
    if f is None:
        return token  # no-op in dev/test
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a Fernet ciphertext back to the raw token string."""
    if not encrypted:
        return encrypted
    f = _get_fernet()
    if f is None:
        return encrypted  # no-op in dev/test
    try:
        return f.decrypt(encrypted.encode()).decode()
    except Exception as exc:
        logger.error("Token decryption failed: %s", exc)
        raise ValueError("Failed to decrypt token — key mismatch or corrupted data") from exc
