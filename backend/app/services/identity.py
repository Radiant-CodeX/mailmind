"""
Multi-tenant identity: users, OAuth accounts, and browser sessions.
===================================================================

This module is the single source of truth for "who is making this request".
It replaces the process-global ``_provider_session`` model (one active user
per backend process) with per-session identity so any number of users can be
signed in concurrently.

Storage follows the codebase's optional-persistence pattern:
  * ``DATABASE_URL`` set   → users / oauth_accounts / user_sessions tables.
  * ``DATABASE_URL`` unset → JSON file fallback (dev only, single machine).

Session tokens are random 256-bit values. In the DB only their SHA-256 hash
is stored, so a leaked dump cannot be replayed. Sessions slide: activity
extends expiry, but writes are throttled to at most one per hour per session.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.base import get_session as db_session, is_persistence_enabled
from app.services import crypto

logger = logging.getLogger(__name__)
# Dedicated audit logger — route to a separate handler/sink in production to
# get a clean, queryable trail of auth and credential events without mixing
# them with debug noise from the main application logger.
audit = logging.getLogger("mailmind.audit")

SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "30"))
# Throttle sliding-renewal writes: touch last_seen at most this often.
_TOUCH_INTERVAL_SECONDS = 3600

# ── Dev file fallback ─────────────────────────────────────────────────────────

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_SESSIONS_PATH = os.path.join(_DATA_DIR, "auth_sessions.json")


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _file_user_id(email: str) -> str:
    """Deterministic user id in dev mode (no users table to assign one)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mailmind:{email.lower()}"))


def _load_file_sessions() -> dict[str, dict[str, Any]]:
    try:
        if os.path.exists(_SESSIONS_PATH):
            with open(_SESSIONS_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                cutoff = time.time() - SESSION_TTL_DAYS * 86400
                return {
                    tok: s for tok, s in data.items()
                    if isinstance(s, dict) and s.get("email")
                    and s.get("created_at", cutoff + 1) > cutoff
                }
    except Exception:
        pass
    return {}


def _save_file_sessions(sessions: dict[str, dict[str, Any]]) -> None:
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_SESSIONS_PATH, "w", encoding="utf-8") as fh:
            json.dump(sessions, fh)
    except Exception:
        pass


_file_sessions: dict[str, dict[str, Any]] = _load_file_sessions()


# ── Users ─────────────────────────────────────────────────────────────────────

def get_or_create_user(email: str, display_name: str | None = None) -> str:
    """Return the internal user id for an email, creating the user on first login."""
    if not email:
        raise ValueError("email is required to resolve a user")
    email = email.strip().lower()

    if not is_persistence_enabled():
        uid = _file_user_id(email)
        audit.info("USER_RESOLVED store=file user_id=%s email=%s", uid, email)
        return uid

    from app.db.models import User
    with db_session() as s:
        if s is None:
            uid = _file_user_id(email)
            audit.info("USER_RESOLVED store=file_fallback user_id=%s email=%s", uid, email)
            return uid
        user = s.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(id=str(uuid.uuid4()), email=email, display_name=display_name)
            s.add(user)
            audit.info("USER_CREATED store=db user_id=%s email=%s", user.id, email)
        else:
            audit.debug("USER_FOUND store=db user_id=%s email=%s", user.id, email)
        user.last_login_at = _utcnow()
        s.commit()
        return user.id


# ── OAuth accounts ────────────────────────────────────────────────────────────

def upsert_oauth_account(
    user_id: str,
    provider: str,
    account_email: str,
    provider_account_id: str | None = None,
    *,
    access_token: str | None = None,
    refresh_token: str | None = None,
    msal_cache: str | None = None,
    token_expires_at: datetime | None = None,
) -> None:
    """Create or update the stored credentials for one connected mailbox.

    Pass only the fields the provider returned: ``None`` means "leave the
    stored value unchanged" (Google often omits the refresh token on
    re-consent; overwriting with None would orphan the account).
    """
    if not is_persistence_enabled():
        audit.debug(
            "OAUTH_ACCOUNT_SKIP store=file provider=%s account=%s user_id=%s",
            provider, account_email, user_id,
        )
        return  # dev mode: providers keep their existing file-based caches

    from app.db.models import OAuthAccount
    pid = provider_account_id or account_email.lower()
    with db_session() as s:
        if s is None:
            return
        acct = (
            s.query(OAuthAccount)
            .filter(OAuthAccount.provider == provider, OAuthAccount.provider_account_id == pid)
            .one_or_none()
        )
        is_new = acct is None
        if is_new:
            acct = OAuthAccount(
                id=str(uuid.uuid4()), user_id=user_id, provider=provider,
                provider_account_id=pid, account_email=account_email,
            )
            s.add(acct)
        acct.user_id = user_id
        acct.account_email = account_email
        updated_fields = []
        if access_token is not None:
            acct.access_token_enc = crypto.encrypt(access_token)
            updated_fields.append("access_token")
        if refresh_token is not None:
            acct.refresh_token_enc = crypto.encrypt(refresh_token)
            updated_fields.append("refresh_token")
        if msal_cache is not None:
            acct.msal_cache_enc = crypto.encrypt(msal_cache)
            updated_fields.append("msal_cache")
        if token_expires_at is not None:
            acct.token_expires_at = token_expires_at
            updated_fields.append("token_expires_at")
        s.commit()
        action = "OAUTH_ACCOUNT_CREATED" if is_new else "OAUTH_ACCOUNT_UPDATED"
        audit.info(
            "%s provider=%s account=%s user_id=%s account_id=%s fields=%s",
            action, provider, account_email, user_id, acct.id, ",".join(updated_fields) or "none",
        )


def get_oauth_account(user_id: str, provider: str | None = None) -> dict[str, Any] | None:
    """Fetch (and decrypt) a user's connected account. Newest first if several."""
    if not is_persistence_enabled():
        audit.debug("OAUTH_ACCOUNT_FETCH_SKIP store=file user_id=%s provider=%s", user_id, provider)
        return None

    from app.db.models import OAuthAccount
    with db_session() as s:
        if s is None:
            return None
        q = s.query(OAuthAccount).filter(OAuthAccount.user_id == user_id)
        if provider:
            q = q.filter(OAuthAccount.provider == provider)
        acct = q.order_by(OAuthAccount.updated_at.desc()).first()
        if acct is None:
            audit.warning(
                "OAUTH_ACCOUNT_NOT_FOUND user_id=%s provider=%s",
                user_id, provider,
            )
            return None
        audit.debug(
            "OAUTH_ACCOUNT_FETCHED account_id=%s user_id=%s provider=%s",
            acct.id, user_id, provider,
        )
        return {
            "id": acct.id,
            "user_id": acct.user_id,
            "provider": acct.provider,
            "account_email": acct.account_email,
            "access_token": crypto.decrypt(acct.access_token_enc),
            "refresh_token": crypto.decrypt(acct.refresh_token_enc),
            "msal_cache": crypto.decrypt(acct.msal_cache_enc),
            "token_expires_at": acct.token_expires_at,
        }


def update_account_tokens_locked(
    account_id: str,
    *,
    access_token: str | None = None,
    refresh_token: str | None = None,
    msal_cache: str | None = None,
    token_expires_at: datetime | None = None,
) -> None:
    """Persist refreshed tokens under a row lock.

    ``SELECT ... FOR UPDATE`` serialises concurrent refreshes of the same
    account across workers — without it, two requests can refresh in parallel
    and the loser persists a rotated-out (now invalid) refresh token.
    """
    if not is_persistence_enabled():
        return
    from app.db.models import OAuthAccount
    with db_session() as s:
        if s is None:
            return
        acct = (
            s.query(OAuthAccount)
            .filter(OAuthAccount.id == account_id)
            .with_for_update()
            .one_or_none()
        )
        if acct is None:
            audit.warning("OAUTH_TOKENS_REFRESH_MISS account_id=%s (row not found)", account_id)
            return
        refreshed_fields = []
        if access_token is not None:
            acct.access_token_enc = crypto.encrypt(access_token)
            refreshed_fields.append("access_token")
        if refresh_token is not None:
            acct.refresh_token_enc = crypto.encrypt(refresh_token)
            refreshed_fields.append("refresh_token")
        if msal_cache is not None:
            acct.msal_cache_enc = crypto.encrypt(msal_cache)
            refreshed_fields.append("msal_cache")
        if token_expires_at is not None:
            acct.token_expires_at = token_expires_at
            refreshed_fields.append("token_expires_at")
        s.commit()
        audit.info(
            "OAUTH_TOKENS_REFRESHED account_id=%s fields=%s",
            account_id, ",".join(refreshed_fields) or "none",
        )


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(provider: str, email: str | None) -> str:
    """Create a browser session and return its bearer token."""
    if not email:
        raise ValueError("Cannot create a session without an email")
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    user_id = get_or_create_user(email)

    if is_persistence_enabled():
        from app.db.models import UserSession
        with db_session() as s:
            if s is not None:
                s.add(UserSession(
                    token_hash=_hash_token(token),
                    user_id=user_id,
                    provider=provider,
                    email=email,
                    expires_at=_utcnow() + timedelta(days=SESSION_TTL_DAYS),
                ))
                s.commit()
                audit.info(
                    "SESSION_CREATED store=db provider=%s email=%s user_id=%s ttl_days=%d",
                    provider, email, user_id, SESSION_TTL_DAYS,
                )
                return token

    _file_sessions[token] = {
        "provider": provider, "email": email, "user_id": user_id,
        "created_at": time.time(),
    }
    _save_file_sessions(_file_sessions)
    audit.info(
        "SESSION_CREATED store=file provider=%s email=%s user_id=%s ttl_days=%d",
        provider, email, user_id, SESSION_TTL_DAYS,
    )
    return token


def get_session(token: str | None) -> dict[str, Any] | None:
    """Resolve a session token to ``{user_id, provider, email}`` or None."""
    if not token:
        return None

    if is_persistence_enabled():
        from app.db.models import UserSession
        with db_session() as s:
            if s is not None:
                row = s.get(UserSession, _hash_token(token))
                if row is None:
                    audit.warning("SESSION_NOT_FOUND store=db token_prefix=%s", token[:8])
                    return None
                now = _utcnow()
                expires_at = row.expires_at
                if expires_at.tzinfo is None:  # SQLite returns naive datetimes
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at < now:
                    s.delete(row)
                    s.commit()
                    audit.info(
                        "SESSION_EXPIRED store=db provider=%s email=%s user_id=%s",
                        row.provider, row.email, row.user_id,
                    )
                    return None
                last_seen = row.last_seen_at
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                # Sliding renewal, throttled to one write per hour.
                if (now - last_seen).total_seconds() > _TOUCH_INTERVAL_SECONDS:
                    row.last_seen_at = now
                    row.expires_at = now + timedelta(days=SESSION_TTL_DAYS)
                    s.commit()
                    audit.info(
                        "SESSION_RENEWED store=db provider=%s email=%s user_id=%s",
                        row.provider, row.email, row.user_id,
                    )
                else:
                    audit.debug(
                        "SESSION_RESOLVED store=db provider=%s email=%s user_id=%s",
                        row.provider, row.email, row.user_id,
                    )
                return {"user_id": row.user_id, "provider": row.provider, "email": row.email}

    session = _file_sessions.get(token)
    if not session:
        audit.warning("SESSION_NOT_FOUND store=file token_prefix=%s", token[:8])
        return None
    audit.debug(
        "SESSION_RESOLVED store=file provider=%s email=%s",
        session.get("provider"), session.get("email"),
    )
    result = dict(session)
    result.setdefault("user_id", _file_user_id(session["email"]))
    return result


def revoke_session(token: str | None) -> None:
    if not token:
        return
    if is_persistence_enabled():
        from app.db.models import UserSession
        with db_session() as s:
            if s is not None:
                row = s.get(UserSession, _hash_token(token))
                if row is not None:
                    audit.info(
                        "SESSION_REVOKED store=db provider=%s email=%s user_id=%s",
                        row.provider, row.email, row.user_id,
                    )
                    s.delete(row)
                    s.commit()
                else:
                    audit.warning("SESSION_REVOKE_MISS store=db token_prefix=%s (not found)", token[:8])
                return
    if token in _file_sessions:
        session = _file_sessions[token]
        audit.info(
            "SESSION_REVOKED store=file provider=%s email=%s",
            session.get("provider"), session.get("email"),
        )
        _file_sessions.pop(token, None)
        _save_file_sessions(_file_sessions)
    else:
        audit.warning("SESSION_REVOKE_MISS store=file token_prefix=%s (not found)", token[:8])
