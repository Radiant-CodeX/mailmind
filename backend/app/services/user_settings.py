"""
Per-user settings: bring-your-own AI key + campus profile.
==========================================================

Stored in ``user_preferences`` (one row per user). The AI API key is
Fernet-encrypted with TOKEN_ENCRYPTION_KEY — the same key that protects OAuth
tokens — and is never returned to the client, only a masked hint.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
from typing import Any
from urllib.parse import urlparse

from app.db.base import get_session
from app.services.llm_provider import (
    PROVIDER_PRESETS,
    AIConfig,
    build_config,
    invalidate_user_config,
    mask_key,
)

logger = logging.getLogger(__name__)
audit = logging.getLogger("mailmind.audit")

CAMPUS_ROLES = ("student", "faculty", "staff")


class SettingsError(ValueError):
    """Invalid settings input, or the server can't store them safely."""


# ─────────────────────────────────────────────────────────────────────────────
# Encryption
# ─────────────────────────────────────────────────────────────────────────────


def _encrypt_key(raw: str) -> str:
    from app.services.token_encryption import _get_fernet

    f = _get_fernet()
    if f is None:
        # Unlike OAuth tokens in local dev, a student's personal API key must
        # never be written to the database in plaintext.
        raise SettingsError(
            "The server cannot store API keys securely: TOKEN_ENCRYPTION_KEY is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return f.encrypt(raw.encode()).decode()


def _decrypt_key(enc: str | None) -> str:
    if not enc:
        return ""
    from app.services.token_encryption import _get_fernet

    f = _get_fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(enc.encode()).decode()
    except Exception:
        logger.error("[settings] stored AI key could not be decrypted (key rotated?)")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Reads
# ─────────────────────────────────────────────────────────────────────────────


def _get_row(session, user_id: str):
    from app.db.models import UserPreferences

    return session.get(UserPreferences, user_id)


def load_ai_config(user_id: str) -> AIConfig | None:
    """The user's own AI config (decrypted), or None if they haven't set one."""
    with get_session() as session:
        if session is None:
            return None
        row = _get_row(session, user_id)
        if row is None or not row.ai_provider:
            return None
        return build_config(
            provider=row.ai_provider,
            api_key=_decrypt_key(row.ai_api_key_enc),
            base_url=row.ai_base_url,
            chat_model=row.ai_chat_model,
            triage_model=row.ai_triage_model,
            embedding_model=row.ai_embedding_model,
            source="user",
        )


def get_ai_settings_view(user_id: str) -> dict[str, Any]:
    """What the settings page shows: the user's config (key masked) + effective model."""
    from app.services.llm_provider import server_default_config

    own: dict[str, Any] | None = None
    with get_session() as session:
        row = _get_row(session, user_id) if session is not None else None
        if row is not None and row.ai_provider:
            own = {
                "provider": row.ai_provider,
                "base_url": row.ai_base_url or PROVIDER_PRESETS.get(row.ai_provider, {}).get("base_url", ""),
                "api_key_hint": mask_key(_decrypt_key(row.ai_api_key_enc)),
                "has_api_key": bool(row.ai_api_key_enc),
                "chat_model": row.ai_chat_model,
                "triage_model": row.ai_triage_model,
                "embedding_model": row.ai_embedding_model,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
    server = server_default_config()
    if own:
        effective = {"source": "user", "provider": own["provider"],
                     "chat_model": own["chat_model"], "triage_model": own["triage_model"]}
    elif server:
        effective = {"source": "server", "provider": server.provider,
                     "chat_model": server.chat_model, "triage_model": server.triage_model}
    else:
        effective = {"source": "rules", "provider": None, "chat_model": None, "triage_model": None}
    return {
        "own": own,
        "server_default_available": server is not None,
        "effective": effective,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Writes
# ─────────────────────────────────────────────────────────────────────────────


def validate_ai_input(payload: dict[str, Any], existing_key: str = "") -> AIConfig:
    """Turn a settings-form payload into an AIConfig (raises SettingsError)."""
    provider = str(payload.get("provider") or "").strip().lower()
    if provider not in PROVIDER_PRESETS:
        raise SettingsError(f"Unknown provider '{provider}'. Choose one of: {', '.join(PROVIDER_PRESETS)}.")
    base_url = str(payload.get("base_url") or "").strip()
    if provider == "custom" and not base_url:
        raise SettingsError("A base URL is required for a custom provider.")
    validate_base_url(base_url or PROVIDER_PRESETS[provider]["base_url"])
    # An omitted key on update means "keep the one already saved".
    api_key = str(payload.get("api_key") or "").strip() or existing_key
    requires_key = PROVIDER_PRESETS[provider].get("requires_key", True)
    if requires_key and not api_key:
        raise SettingsError("An API key is required for this provider.")
    cfg = build_config(
        provider=provider,
        api_key=api_key,
        base_url=base_url or None,
        chat_model=payload.get("chat_model"),
        triage_model=payload.get("triage_model"),
        embedding_model=payload.get("embedding_model"),
        source="user",
    )
    if not cfg.chat_model:
        raise SettingsError("A chat model id is required.")
    return cfg


def validate_base_url(url: str) -> None:
    """Reject endpoints that would let a user point the server at itself.

    The server calls the configured base URL on the user's behalf, so an
    unrestricted URL is a server-side request forgery vector (cloud metadata,
    internal admin ports). Only public https endpoints are allowed unless the
    operator opts in to local models with ALLOW_LOCAL_LLM_ENDPOINTS=true (e.g.
    a self-hosted deployment running Ollama next to the backend).
    """
    from app.config.settings import settings

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("https", "http") or not host:
        raise SettingsError("Base URL must be a full URL, e.g. https://openrouter.ai/api/v1")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
        addresses = {ipaddress.ip_address(info[4][0]) for info in infos}
    except (socket.gaierror, ValueError):
        raise SettingsError(f"Could not resolve the host '{host}'. Check the base URL.")
    internal = any(
        a.is_private or a.is_loopback or a.is_link_local or a.is_reserved or a.is_multicast
        or a.is_unspecified for a in addresses
    )
    if internal:
        if not settings.allow_local_llm_endpoints:
            raise SettingsError(
                "Local / private-network endpoints are disabled on this server. Use a hosted "
                "provider, or run MailMind yourself with ALLOW_LOCAL_LLM_ENDPOINTS=true for Ollama."
            )
        return
    if parsed.scheme != "https":
        raise SettingsError("Base URL must use https://")


def existing_api_key(user_id: str) -> str:
    with get_session() as session:
        row = _get_row(session, user_id) if session is not None else None
        return _decrypt_key(row.ai_api_key_enc) if row is not None else ""


def save_ai_settings(user_id: str, cfg: AIConfig) -> None:
    from app.db.models import UserPreferences

    with get_session() as session:
        if session is None:
            raise SettingsError("Settings need a database (DATABASE_URL is not configured).")
        row = _get_row(session, user_id)
        if row is None:
            row = UserPreferences(user_id=user_id)
            session.add(row)
        row.ai_provider = cfg.provider
        row.ai_base_url = cfg.base_url
        row.ai_api_key_enc = _encrypt_key(cfg.api_key) if cfg.api_key else None
        row.ai_chat_model = cfg.chat_model
        row.ai_triage_model = cfg.triage_model
        row.ai_embedding_model = cfg.embedding_model or None
        session.commit()
    invalidate_user_config(user_id)
    audit.info("AI_SETTINGS_SAVED user_id=%s provider=%s model=%s", user_id, cfg.provider, cfg.chat_model)


def clear_ai_settings(user_id: str) -> None:
    with get_session() as session:
        if session is None:
            return
        row = _get_row(session, user_id)
        if row is not None:
            row.ai_provider = None
            row.ai_base_url = None
            row.ai_api_key_enc = None
            row.ai_chat_model = None
            row.ai_triage_model = None
            row.ai_embedding_model = None
            session.commit()
    invalidate_user_config(user_id)
    audit.info("AI_SETTINGS_CLEARED user_id=%s", user_id)


# ─────────────────────────────────────────────────────────────────────────────
# Campus profile
# ─────────────────────────────────────────────────────────────────────────────

_PROFILE_TTL = 60.0
_profile_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_profile_lock = threading.Lock()

DEFAULT_PROFILE: dict[str, Any] = {"role": "student", "department": None, "year_of_study": None}


def load_campus_profile(user_id: str | None) -> dict[str, Any]:
    """The user's campus profile (cached briefly). Defaults to a student."""
    if not user_id:
        return dict(DEFAULT_PROFILE)
    now = time.monotonic()
    with _profile_lock:
        hit = _profile_cache.get(user_id)
        if hit and hit[0] > now:
            return dict(hit[1])
    profile = dict(DEFAULT_PROFILE)
    try:
        with get_session() as session:
            row = _get_row(session, user_id) if session is not None else None
            if row is not None:
                profile = {
                    "role": row.campus_role or "student",
                    "department": row.department,
                    "year_of_study": row.year_of_study,
                }
    except Exception as exc:
        logger.debug("[settings] campus profile lookup failed: %s", exc)
    with _profile_lock:
        _profile_cache[user_id] = (now + _PROFILE_TTL, profile)
    return dict(profile)


def save_campus_profile(user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from app.db.models import UserPreferences

    role = str(payload.get("role") or "student").strip().lower()
    if role not in CAMPUS_ROLES:
        raise SettingsError(f"role must be one of: {', '.join(CAMPUS_ROLES)}")
    department = (str(payload.get("department") or "").strip() or None)
    if department and len(department) > 128:
        raise SettingsError("department is too long (max 128 characters)")
    year = payload.get("year_of_study")
    if year in ("", None):
        year = None
    else:
        try:
            year = int(year)
        except (TypeError, ValueError):
            raise SettingsError("year_of_study must be a number between 1 and 6")
        if not 1 <= year <= 6:
            raise SettingsError("year_of_study must be a number between 1 and 6")
    if role != "student":
        year = None

    with get_session() as session:
        if session is None:
            raise SettingsError("Settings need a database (DATABASE_URL is not configured).")
        row = _get_row(session, user_id)
        if row is None:
            row = UserPreferences(user_id=user_id)
            session.add(row)
        row.campus_role = role
        row.department = department
        row.year_of_study = year
        session.commit()
    with _profile_lock:
        _profile_cache.pop(user_id, None)
    return {"role": role, "department": department, "year_of_study": year}
