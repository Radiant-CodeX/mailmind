"""
Legacy mail-client factory (v2 compatibility shim).

v3 path: use AccountService.get_adapter(account) instead.
v2 path: a few deep service call-sites (Tone DNA inside the draft service) still
call get_mail_client(); it returns a GmailClient bound to the process-level
token cache populated at login (or mock data when USE_MOCK_MAIL is on).
"""
from __future__ import annotations


def get_mail_client():
    """Return the Gmail client (the only supported provider)."""
    from app.services.gmail import GmailClient
    return GmailClient()
