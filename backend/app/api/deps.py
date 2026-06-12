"""
FastAPI dependencies for MailMind v3.

Every route that touches user data declares get_current_user() as a dependency.
Cookie-based authentication: mm_session (24h) → mm_quick auto-rotation (7d).

Flow:
  1. Read mm_session cookie → validate via SessionService
  2. If expired/missing → try mm_quick rotation → issue new mm_session + mm_quick
  3. If both fail → 401
"""

from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db.database import get_db


def _session_service(db: Session):
    """Build a SessionService backed by the request-scoped DB session."""
    from app.services.session_service import DBSessionBackend, SessionService
    return SessionService(DBSessionBackend(db))


def get_current_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    mm_session: str | None = Cookie(default=None),
    mm_quick: str | None = Cookie(default=None),
):
    print("=" * 50)
    print("PATH:", request.url.path)
    print("COOKIES:", request.cookies)
    print("mm_session:", mm_session)
    print("mm_quick:", mm_quick)
    print("=" * 50)
    """
    FastAPI dependency — returns the authenticated User ORM object or raises 401.

    Tries mm_session first. If that's expired or absent, attempts quick-login
    rotation via mm_quick. On rotation, sets fresh mm_session + mm_quick cookies
    so the user doesn't have to log in again.
    """
    from app.db.models import User
    from app.config.settings import settings

    svc = _session_service(db)

    # ── 1. Try primary session cookie ────────────────────────────────────────
    if mm_session:
        user_id = svc.get_user_id_from_session(mm_session)
        if user_id:
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                return user

    # ── 2. Try quick-login rotation ──────────────────────────────────────────
    if mm_quick:
        result = svc.try_quick_login(mm_quick)
        if result:
            user_id, new_quick_token = result
            user = db.query(User).filter_by(id=user_id).first()
            if user:
                # Issue a fresh mm_session
                new_session_token = svc.create_session(user_id)
                _set_session_cookie(response, new_session_token, settings.session_ttl_seconds)
                _set_quick_cookie(response, new_quick_token, settings.quick_login_ttl_seconds)
                db.commit()
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Please sign in.",
        headers={"WWW-Authenticate": "Cookie"},
    )


def get_default_account(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency — returns the current user's default OAuthAccount or raises 404.

    Used by routes that need a specific account context (e.g. Tone DNA, RAG) but
    don't accept an explicit account_id from the caller.
    """
    from app.db.models import OAuthAccount

    account = (
        db.query(OAuthAccount)
        .filter_by(user_id=current_user.id, is_default=True)
        .first()
    )
    if not account:
        # Fall back to any account for this user
        account = db.query(OAuthAccount).filter_by(user_id=current_user.id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected account found. Please connect an email account first.",
        )
    return account


def get_current_account(
    account_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FastAPI dependency — validates that `account_id` (path/query param) belongs
    to the authenticated user. Returns the OAuthAccount or raises 403.

    Usage in routes:
        @router.get("/accounts/{account_id}/emails")
        async def list_emails(account=Depends(get_current_account)):
            ...
    """
    from app.db.models import OAuthAccount

    account = (
        db.query(OAuthAccount)
        .filter_by(id=account_id, user_id=current_user.id)
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not found or does not belong to your user.",
        )
    return account


# ─────────────────────────────────────────────────────────────────────────────
# Cookie helpers — centralise SameSite/Secure/HttpOnly settings
# ─────────────────────────────────────────────────────────────────────────────


def _set_session_cookie(response: Response, token: str, max_age: int) -> None:
    from app.config.settings import settings
    response.set_cookie(
        key="mm_session",
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def _set_quick_cookie(response: Response, token: str, max_age: int) -> None:
    from app.config.settings import settings
    response.set_cookie(
        key="mm_quick",
        value=token,
        max_age=max_age,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookies(response: Response, clear_quick: bool = False) -> None:
    """Clear authentication cookies. By default only clears mm_session to preserve quick login."""
    response.delete_cookie("mm_session", path="/")
    if clear_quick:
        response.delete_cookie("mm_quick", path="/")
