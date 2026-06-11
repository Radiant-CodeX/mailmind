"""Provider-aware mail routing + session activity.

Tracks which provider the current session uses (Microsoft or Google), whether
the session is *active* (logged in vs logged out), and routes to the matching
mail client. Persisted to disk so an active session survives a backend restart —
but a logout deactivates it so the login screen no longer bounces back.
"""
from __future__ import annotations

import json
import os
from typing import Any, Literal

Provider = Literal["microsoft", "google"]

_PROVIDER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "active_provider.json")


def _load() -> dict[str, Any]:
    try:
        if os.path.exists(_PROVIDER_PATH):
            with open(_PROVIDER_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if data.get("provider") in ("microsoft", "google"):
                    return {
                        "provider": data["provider"],
                        "email": data.get("email"),
                        "active": bool(data.get("active", False)),
                    }
    except Exception:
        pass
    return {"provider": "microsoft", "email": None, "active": False}


def _save() -> None:
    try:
        os.makedirs(os.path.dirname(_PROVIDER_PATH), exist_ok=True)
        with open(_PROVIDER_PATH, "w", encoding="utf-8") as fh:
            json.dump(_provider_session, fh)
    except Exception:
        pass


# Active provider for the current session, restored from disk on startup.
_provider_session: dict[str, Any] = _load()


# Session storage lives in app.services.identity (DB-backed with file
# fallback). Thin wrappers are kept here so existing imports keep working.


def create_session(provider: Provider, email: str | None) -> str:
    """Create a browser session token (delegates to the identity service)."""
    from app.services import identity
    token = identity.create_session(provider, email)
    set_provider(provider, email)
    return token


def get_session(token: str | None) -> dict[str, Any] | None:
    """Resolve a session token to {user_id, provider, email} or None."""
    from app.services import identity
    session = identity.get_session(token)
    if not session:
        return None
    # Transitional: sync the legacy active-provider hint only when it actually
    # changed, so provider singletons keep working until they are per-request.
    if (
        _provider_session.get("provider") != session["provider"]
        or _provider_session.get("email") != session.get("email")
    ):
        set_provider(session["provider"], session.get("email"))
    return session


def revoke_session(token: str | None) -> None:
    from app.services import identity
    identity.revoke_session(token)


def set_provider(provider: Provider, email: str | None = None) -> None:
    """Mark a session active for a provider (called on login / resume)."""
    previous_email = _provider_session.get("email")
    _provider_session["provider"] = provider
    _provider_session["email"] = email
    _provider_session["active"] = True
    _save()

    # Clear in-memory caches whenever the active user changes so the incoming
    # user cannot see data cached for a previous user in the same process.
    if email != previous_email:
        try:
            from app.services.cache import clear_all_user_caches
            clear_all_user_caches()
        except Exception:
            pass


def deactivate() -> None:
    """Log out: mark the session inactive but keep the provider/email hint."""
    _provider_session["active"] = False
    _save()


def clear_provider() -> None:
    """Fully reset the session (logout)."""
    _provider_session["provider"] = "microsoft"
    _provider_session["email"] = None
    _provider_session["active"] = False
    _save()


def is_active() -> bool:
    return bool(_provider_session.get("active"))


def active_provider() -> str:
    return _provider_session.get("provider") or "microsoft"


def active_email() -> str | None:
    return _provider_session.get("email")


def get_mail_client(session: dict[str, Any] | None = None):
    """Return a mail client for the requesting user.

    Resolution order:
      1. Explicit ``session`` argument (DI-style call), else
      2. the request-scoped session ContextVar (set by SessionContextMiddleware),
         else
      3. the legacy active-provider hint (single-user / un-migrated paths).

    When a session resolves to a stored OAuth account (requires a database),
    the returned client is *account-bound* — it talks only to that user's
    mailbox, so concurrent requests for different users never collide. Without
    a database, or for unauthenticated calls, it falls back to a legacy client
    backed by the process-global token cache.
    """
    from app.services.request_context import get_current_session

    session = session or get_current_session()
    provider = (session or {}).get("provider") or active_provider()

    # Try to bind the client to the user's stored OAuth account (DB-backed).
    account = None
    if session and session.get("user_id"):
        try:
            from app.db.base import is_persistence_enabled
            if is_persistence_enabled():
                from app.services import identity
                account = identity.get_oauth_account(session["user_id"], provider)
        except Exception:
            account = None

    if provider == "google":
        from app.services.gmail import GmailClient

        return GmailClient(account=account)
    from app.services.graph import GraphClient

    return GraphClient(account=account)
