"""
Legacy mail-client factory (v2 compatibility shim).

v3 path: use AccountService.get_adapter(account) instead.
v2 path (existing mail routes): this function reads from the process-level
in-memory cache populated by exchange_code / exchange_ms_code at login time.

get_mail_client() stays alive until all non-auth routes are migrated to v3
AccountService. The set_provider / clear_provider / is_active / active_email
functions have been removed — session state is now managed by SessionService.
"""
from __future__ import annotations


def get_mail_client():
    """Return the mail client for the active provider (legacy v2 path)."""
    from app.services.graph import _user_token_cache
    from app.services.gmail import _token_cache as _google_cache

    # Detect the active provider from whichever cache has a token.
    if _google_cache.get("access_token"):
        from app.services.gmail import GmailClient
        return GmailClient()

    # Default to GraphClient (also handles mock mode).
    from app.services.graph import GraphClient
    return GraphClient()
