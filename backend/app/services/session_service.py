"""
Session management for MailMind v3.

Two token types:
  mm_session   — Short-lived (24h). Validated on every request.
  mm_quick     — Long-lived (7d). Rotated on use to restore a session.

Both tokens are stored as SHA-256 hashes in the DB. Raw tokens live only in
HttpOnly cookies — never in JS-accessible storage or DB plaintext.

SessionBackend is a protocol so DB can be swapped for Redis later without
changing SessionService or any caller.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _hash(token: str) -> str:
    """SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_token(nbytes: int = 32) -> str:
    """Cryptographically secure URL-safe random token."""
    return secrets.token_urlsafe(nbytes)


def _device_fingerprint(user_agent: str, accept_language: str) -> str:
    """Stable fingerprint from request headers for device identification."""
    raw = f"{user_agent}|{accept_language}".lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _device_name(user_agent: str) -> str:
    """Human-readable device name derived from User-Agent."""
    ua = user_agent.lower()
    browser = "Browser"
    if "chrome" in ua and "edg" not in ua:
        browser = "Chrome"
    elif "firefox" in ua:
        browser = "Firefox"
    elif "safari" in ua and "chrome" not in ua:
        browser = "Safari"
    elif "edg" in ua:
        browser = "Edge"

    os_name = "Unknown OS"
    if "windows" in ua:
        os_name = "Windows"
    elif "macintosh" in ua or "mac os" in ua:
        os_name = "macOS"
    elif "iphone" in ua or "ipad" in ua:
        os_name = "iOS"
    elif "android" in ua:
        os_name = "Android"
    elif "linux" in ua:
        os_name = "Linux"

    return f"{os_name} {browser}"


# ─────────────────────────────────────────────────────────────────────────────
# SessionBackend Protocol  (swap DB → Redis by implementing this)
# ─────────────────────────────────────────────────────────────────────────────


@runtime_checkable
class SessionBackend(Protocol):
    def create_session(self, user_id: str, ttl_seconds: int) -> str:
        """Store a new session, return the raw token."""
        ...

    def get_user_id(self, raw_token: str) -> str | None:
        """Validate token, bump last_seen_at, return user_id or None."""
        ...

    def invalidate_session(self, raw_token: str) -> None:
        """Delete the session."""
        ...

    def create_quick_login(
        self, user_id: str, device_id: str, ttl_seconds: int
    ) -> str:
        """Store a new quick-login token, return raw token."""
        ...

    def validate_and_rotate_quick_login(
        self, raw_token: str, new_ttl_seconds: int
    ) -> tuple[str, str] | None:
        """
        Validate token (ACTIVE, not expired), atomically replace with a new
        token (rotation prevents replay). Returns (user_id, new_raw_token) or None.
        """
        ...

    def logout_quick_login(self, raw_token: str) -> None:
        """Mark as LOGGED_OUT (keep row for 7d audit, do not delete)."""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# DB-backed implementation
# ─────────────────────────────────────────────────────────────────────────────


class DBSessionBackend:
    """SQLAlchemy implementation of SessionBackend."""

    def __init__(self, db) -> None:
        self._db = db

    def create_session(self, user_id: str, ttl_seconds: int) -> str:
        from app.db.models import UserSession, OAuthAccount
        token = _generate_token()

        # Get default account for provider/email (v2 legacy fields in user_sessions)
        account = self._db.query(OAuthAccount).filter_by(user_id=user_id, is_default=True).first()
        if not account:
            account = self._db.query(OAuthAccount).filter_by(user_id=user_id).first()

        provider = account.provider if account else "google"
        email = account.account_email if account else ""

        row = UserSession(
            user_id=user_id,
            token_hash=_hash(token),
            provider=provider,
            email=email,
            expires_at=_now() + timedelta(seconds=ttl_seconds),
        )
        self._db.add(row)
        self._db.flush()
        return token

    def get_user_id(self, raw_token: str) -> str | None:
        from app.db.models import UserSession
        h = _hash(raw_token)
        row = (
            self._db.query(UserSession)
            .filter_by(token_hash=h)
            .first()
        )
        if not row:
            return None
        if row.expires_at < _now():
            self._db.delete(row)
            self._db.flush()
            return None
        row.last_seen_at = _now()
        self._db.flush()
        return row.user_id

    def invalidate_session(self, raw_token: str) -> None:
        from app.db.models import UserSession
        row = (
            self._db.query(UserSession)
            .filter_by(token_hash=_hash(raw_token))
            .first()
        )
        if row:
            self._db.delete(row)
            self._db.flush()

    def create_quick_login(
        self, user_id: str, device_id: str, ttl_seconds: int
    ) -> str:
        from app.db.models import QuickLoginToken
        token = _generate_token()
        row = QuickLoginToken(
            user_id=user_id,
            device_id=device_id,
            token_hash=_hash(token),
            status="ACTIVE",
            expires_at=_now() + timedelta(seconds=ttl_seconds),
        )
        self._db.add(row)
        self._db.flush()
        return token

    def validate_and_rotate_quick_login(
        self, raw_token: str, new_ttl_seconds: int
    ) -> tuple[str, str] | None:
        from app.db.models import QuickLoginToken
        row = (
            self._db.query(QuickLoginToken)
            .filter_by(token_hash=_hash(raw_token), status="ACTIVE")
            .first()
        )
        if not row:
            return None
        if row.expires_at < _now():
            row.status = "EXPIRED"
            self._db.flush()
            return None

        user_id = row.user_id

        # Rotate: replace old token with a new one atomically
        new_token = _generate_token()
        row.token_hash = _hash(new_token)
        row.expires_at = _now() + timedelta(seconds=new_ttl_seconds)
        self._db.flush()

        return user_id, new_token

    def logout_quick_login(self, raw_token: str) -> None:
        from app.db.models import QuickLoginToken
        row = (
            self._db.query(QuickLoginToken)
            .filter_by(token_hash=_hash(raw_token))
            .first()
        )
        if row:
            row.status = "LOGGED_OUT"
            self._db.flush()


# ─────────────────────────────────────────────────────────────────────────────
# SessionService  (high-level, used by routes and deps)
# ─────────────────────────────────────────────────────────────────────────────


class SessionService:
    """
    Orchestrates session + quick-login lifecycle on top of a SessionBackend.
    Routes call this; they don't touch the backend directly.
    """

    def __init__(self, backend: SessionBackend) -> None:
        self._b = backend

    # ── Session ───────────────────────────────────────────────────────────────

    def create_session(self, user_id: str) -> str:
        from app.config.settings import settings
        return self._b.create_session(user_id, settings.session_ttl_seconds)

    def get_user_id_from_session(self, raw_token: str) -> str | None:
        return self._b.get_user_id(raw_token)

    def invalidate_session(self, raw_token: str) -> None:
        self._b.invalidate_session(raw_token)

    # ── Quick Login ───────────────────────────────────────────────────────────

    def create_quick_login(self, user_id: str, device_id: str) -> str:
        from app.config.settings import settings
        return self._b.create_quick_login(
            user_id, device_id, settings.quick_login_ttl_seconds
        )

    def try_quick_login(self, raw_token: str) -> tuple[str, str] | None:
        """
        Validate quick-login token and rotate it.
        Returns (user_id, new_quick_token) or None if invalid/expired.
        Caller must set the new quick token as a cookie AND create a new session.
        """
        from app.config.settings import settings
        result = self._b.validate_and_rotate_quick_login(
            raw_token, settings.quick_login_ttl_seconds
        )
        if result is None:
            return None
        user_id, new_quick_token = result
        return user_id, new_quick_token

    def logout(self, session_token: str | None, quick_token: str | None) -> None:
        if session_token:
            self._b.invalidate_session(session_token)
        if quick_token:
            self._b.logout_quick_login(quick_token)

    # ── Device ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_device(db, user_id: str, user_agent: str, accept_language: str = "") -> str:
        """Return existing device_id or create a new Device row. Returns device_id."""
        from app.db.models import Device
        fp = _device_fingerprint(user_agent, accept_language)
        device = db.query(Device).filter_by(user_id=user_id, fingerprint=fp).first()
        if device:
            device.last_used = _now()
            db.flush()
            return device.id
        device = Device(
            user_id=user_id,
            fingerprint=fp,
            user_agent=user_agent,
            accept_language=accept_language,
        )
        db.add(device)
        db.flush()
        return device.id
