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


def get_mail_client():
    """Return the mail client for the active provider."""
    if active_provider() == "google":
        from app.services.gmail import GmailClient

        return GmailClient()
    from app.services.graph import GraphClient

    return GraphClient()
