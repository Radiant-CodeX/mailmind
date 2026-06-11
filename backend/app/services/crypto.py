"""
Encryption-at-rest for OAuth credential material.
=================================================

Refresh tokens and MSAL cache blobs are long-lived credentials to a user's
entire mailbox, so they are never written to the database in plaintext.

Key management:
  * ``TOKEN_ENCRYPTION_KEY`` env var — a Fernet key (44-char urlsafe base64).
    Generate one with:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  * When unset in development, values are stored with a ``plain:`` prefix and
    a loud warning is logged. Production (APP_ENV=production) refuses to start
    without a key rather than silently downgrading.

Values are prefixed (``enc:`` / ``plain:``) so the two formats coexist during
key rollout and ``decrypt`` can always tell what it is looking at.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_ENC_PREFIX = "enc:"
_PLAIN_PREFIX = "plain:"

_fernet = None
_key_checked = False


def _get_fernet():
    """Lazily build the Fernet instance; None when no key is configured."""
    global _fernet, _key_checked
    if _key_checked:
        return _fernet
    _key_checked = True

    key = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    if not key:
        from app.config.settings import settings
        if settings.is_production:
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY must be set in production — refusing to "
                "store OAuth tokens in plaintext."
            )
        logger.warning(
            "TOKEN_ENCRYPTION_KEY not set — OAuth tokens will be stored "
            "UNENCRYPTED (dev mode only). Set the env var before deploying."
        )
        return None

    try:
        from cryptography.fernet import Fernet
        _fernet = Fernet(key.encode("ascii"))
    except Exception as exc:
        raise RuntimeError(f"TOKEN_ENCRYPTION_KEY is not a valid Fernet key: {exc}") from exc
    return _fernet


def encrypt(value: str | None) -> str | None:
    """Encrypt a credential string for storage. None passes through."""
    if value is None:
        return None
    f = _get_fernet()
    if f is None:
        return _PLAIN_PREFIX + value
    return _ENC_PREFIX + f.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(stored: str | None) -> str | None:
    """Decrypt a stored credential string. None passes through."""
    if stored is None:
        return None
    if stored.startswith(_PLAIN_PREFIX):
        return stored[len(_PLAIN_PREFIX):]
    if stored.startswith(_ENC_PREFIX):
        f = _get_fernet()
        if f is None:
            raise RuntimeError(
                "Encrypted token found but TOKEN_ENCRYPTION_KEY is not set — "
                "cannot decrypt stored credentials."
            )
        return f.decrypt(stored[len(_ENC_PREFIX):].encode("ascii")).decode("utf-8")
    # Legacy/unprefixed value written before this module existed.
    return stored
