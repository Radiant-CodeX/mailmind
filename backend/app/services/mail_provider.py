"""Provider-aware mail routing.

Tracks which email provider the current session is using (Microsoft or Google)
and hands back the matching mail client. Mail endpoints call `get_mail_client()`
instead of instantiating a specific client, so the whole app works identically
for an Outlook or a Gmail account.

The active provider is persisted to disk so it survives a backend restart — when
combined with the persisted refresh tokens, the session resumes automatically.
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
                    return {"provider": data["provider"], "email": data.get("email")}
    except Exception:
        pass
    return {"provider": "microsoft", "email": None}


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
    _provider_session["provider"] = provider
    _provider_session["email"] = email
    _save()


def clear_provider() -> None:
    _provider_session["provider"] = "microsoft"
    _provider_session["email"] = None
    _save()


def active_provider() -> str:
    return _provider_session.get("provider") or "microsoft"


def active_email() -> str | None:
    return _provider_session.get("email")


def get_mail_client():
    """Return the mail client for the active provider."""
    if _provider_session.get("provider") == "google":
        from app.services.gmail import GmailClient

        return GmailClient()
    from app.services.graph import GraphClient

    return GraphClient()
