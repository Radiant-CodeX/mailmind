"""
Shared FastAPI dependencies for MailMind API routes.
"""
from __future__ import annotations

from fastapi import HTTPException, status

from app.services.mail_provider import active_email, is_active


def get_current_user() -> str:
    """
    FastAPI dependency — returns the active user's email or raises 401.

    Every endpoint that touches user data (emails, triage, drafts, calendar,
    RAG) must declare this dependency so unauthenticated or cross-user requests
    are rejected at the boundary before any data is read or written.
    """
    if not is_active():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please sign in.",
        )
    email = active_email()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has no user identity. Please sign in again.",
        )
    return email
