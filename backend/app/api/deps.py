"""
Shared FastAPI dependencies for MailMind API routes.
"""
from __future__ import annotations

from typing import Any

from fastapi import Cookie, Header, HTTPException, status

from app.services.identity import get_session

SESSION_COOKIE = "mailmind_session"


def get_current_session(
    mailmind_session: str | None = Cookie(default=None),
    x_mailmind_session: str | None = Header(default=None),
) -> dict[str, Any]:
    """
    FastAPI dependency — resolves the caller's session or raises 401.

    The HttpOnly cookie is the primary transport (immune to XSS token theft);
    the X-MailMind-Session header is a transitional fallback for clients that
    haven't picked up the cookie yet.

    Returns {user_id, provider, email} so routes can scope every read/write.
    """
    token = mailmind_session or x_mailmind_session
    session = get_session(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please sign in.",
        )
    if not session.get("email"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has no user identity. Please sign in again.",
        )
    return session


def get_current_user(
    mailmind_session: str | None = Cookie(default=None),
    x_mailmind_session: str | None = Header(default=None),
) -> str:
    """
    FastAPI dependency — returns the active user's email or raises 401.

    Every endpoint that touches user data (emails, triage, drafts, calendar,
    RAG) must declare this dependency so unauthenticated or cross-user requests
    are rejected at the boundary before any data is read or written.
    """
    session = get_current_session(mailmind_session, x_mailmind_session)
    return session["email"]
