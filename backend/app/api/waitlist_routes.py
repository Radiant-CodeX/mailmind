"""
Waitlist + private-beta access control.
=======================================

Public:
  POST /api/waitlist              Join the waitlist (email + name + use-case).

Admin (X-Admin-Token header):
  GET  /api/admin/waitlist        List all waitlist entries, newest first.
  POST /api/admin/waitlist/approve  Approve an email (status → approved).
  POST /api/admin/waitlist/reject   Reject an email (status → rejected).
  GET  /api/admin/feedback        View all submitted product feedback.

The ``waitlist`` table doubles as the allow-list: an ``approved`` row is what
``_finish_oauth_connect`` checks before issuing a session. Approval is therefore
a single status change made through the admin endpoints.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.config.settings import settings
from app.db.base import get_session, is_persistence_enabled

logger = logging.getLogger(__name__)

router = APIRouter(tags=["waitlist"])


def _validate_admin_token(token: str | None) -> None:
    """Gate the /api/admin/* endpoints. Raises 401/403 on failure."""
    if not token:
        raise HTTPException(status_code=401, detail="Missing admin token")
    if settings.admin_token == "change-me-admin-token":
        raise HTTPException(
            status_code=503,
            detail="Admin access is not configured. Set ADMIN_TOKEN in the backend environment.",
        )
    if token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


def _require_db():
    """Waitlist requires real persistence — there's no JSON fallback for access control."""
    if not is_persistence_enabled():
        raise HTTPException(status_code=503, detail="Waitlist storage is unavailable (no database configured).")


def _row_to_dict(r) -> dict:
    return {
        "id": r.id,
        "email": r.email,
        "name": r.name,
        "use_case": r.use_case,
        "status": r.status,
        "source": r.source,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
    }


# ── Public: join the waitlist ────────────────────────────────────────────────


class WaitlistJoinPayload(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=256)
    use_case: str | None = Field(default=None, max_length=2000)


@router.post("/waitlist")
def join_waitlist(payload: WaitlistJoinPayload) -> dict:
    """
    Join the private-beta waitlist. Idempotent on email — re-submitting updates
    the stored name/use-case but never downgrades an already-approved entry.
    """
    _require_db()
    from app.db.models import Waitlist

    email = str(payload.email).strip().lower()
    with get_session() as session:
        if session is None:
            raise HTTPException(status_code=503, detail="Waitlist storage is unavailable.")
        existing = session.query(Waitlist).filter(Waitlist.email == email).first()
        if existing:
            # Refresh context but preserve approval state.
            if payload.name:
                existing.name = payload.name
            if payload.use_case:
                existing.use_case = payload.use_case
            session.commit()
            return {"ok": True, "status": existing.status, "already_joined": True}

        entry = Waitlist(
            email=email,
            name=payload.name,
            use_case=payload.use_case,
            status="pending",
            source="signup",
        )
        session.add(entry)
        session.commit()
        logger.info("[waitlist] new signup: %s", email)
        return {"ok": True, "status": "pending", "already_joined": False}


# ── Admin: review + approve ──────────────────────────────────────────────────


class EmailActionPayload(BaseModel):
    email: EmailStr


@router.get("/admin/waitlist")
def admin_list_waitlist(x_admin_token: str | None = Header(default=None)) -> dict:
    """List every waitlist entry, newest first, with simple status counts."""
    _validate_admin_token(x_admin_token)
    _require_db()
    from app.db.models import Waitlist

    with get_session() as session:
        if session is None:
            raise HTTPException(status_code=503, detail="Waitlist storage is unavailable.")
        rows = session.query(Waitlist).order_by(Waitlist.created_at.desc()).all()
        entries = [_row_to_dict(r) for r in rows]
        counts = {"pending": 0, "approved": 0, "rejected": 0}
        for e in entries:
            counts[e["status"]] = counts.get(e["status"], 0) + 1
        return {"count": len(entries), "counts": counts, "entries": entries}


def _set_status(email: str, status: str) -> dict:
    from app.db.models import Waitlist

    email = email.strip().lower()
    with get_session() as session:
        if session is None:
            raise HTTPException(status_code=503, detail="Waitlist storage is unavailable.")
        row = session.query(Waitlist).filter(Waitlist.email == email).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"No waitlist entry for {email}")
        row.status = status
        row.approved_at = datetime.now(tz=timezone.utc) if status == "approved" else None
        session.commit()
        logger.info("[waitlist] %s → %s", email, status)
        return _row_to_dict(row)


@router.post("/admin/waitlist/approve")
def admin_approve(payload: EmailActionPayload, x_admin_token: str | None = Header(default=None)) -> dict:
    """Approve an email — grants login access immediately."""
    _validate_admin_token(x_admin_token)
    _require_db()
    return {"ok": True, "entry": _set_status(str(payload.email), "approved")}


def _revoke_user_sessions(email: str) -> int:
    """
    Kill all active sessions + quick-login tokens for the user behind ``email``,
    so a rejected user is signed out immediately rather than lingering until their
    24h session cookie expires. Returns the number of sessions revoked.
    """
    from app.db.models import OAuthAccount, QuickLoginToken, User, UserSession

    email_l = email.strip().lower()
    revoked = 0
    with get_session() as session:
        if session is None:
            return 0
        # Resolve every user that owns this email (primary, legacy, or via an
        # OAuth account) so no session slips through.
        user_ids = {
            u.id for u in session.query(User).filter(
                (User.primary_email == email_l) | (User.email == email_l)
            ).all()
        }
        for acc in session.query(OAuthAccount).filter(OAuthAccount.account_email == email_l).all():
            user_ids.add(acc.user_id)
        if not user_ids:
            return 0
        revoked = (
            session.query(UserSession)
            .filter(UserSession.user_id.in_(user_ids))
            .delete(synchronize_session=False)
        )
        session.query(QuickLoginToken).filter(
            QuickLoginToken.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        session.commit()
    logger.info("[waitlist] revoked %d session(s) for rejected email %s", revoked, email_l)
    return revoked


@router.post("/admin/waitlist/reject")
def admin_reject(payload: EmailActionPayload, x_admin_token: str | None = Header(default=None)) -> dict:
    """Reject an email — revokes future access AND signs out any active sessions."""
    _validate_admin_token(x_admin_token)
    _require_db()
    entry = _set_status(str(payload.email), "rejected")
    revoked = _revoke_user_sessions(str(payload.email))
    return {"ok": True, "entry": entry, "sessions_revoked": revoked}


# ── Admin: view feedback ─────────────────────────────────────────────────────


@router.get("/admin/feedback")
def admin_list_feedback(x_admin_token: str | None = Header(default=None)) -> dict:
    """View all product feedback via the admin secret (no user session needed)."""
    _validate_admin_token(x_admin_token)
    _require_db()
    from app.db.models import Feedback

    with get_session() as session:
        if session is None:
            raise HTTPException(status_code=503, detail="Feedback storage is unavailable.")
        rows = session.query(Feedback).order_by(Feedback.created_at.desc()).all()
        return {
            "count": len(rows),
            "entries": [
                {
                    "id": r.id,
                    "rating": r.rating,
                    "category": r.category,
                    "message": r.message,
                    "user_email": r.user_email,
                    "role": r.role,
                    "timestamp": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
        }


# ── Shared helper used by the login gate ─────────────────────────────────────


def is_email_allowed(email: str) -> bool:
    """
    True if the email may sign in: either a bootstrap owner email, or an
    ``approved`` waitlist row. Safe to call with persistence disabled (dev) —
    returns True so local development isn't blocked.
    """
    if not email:
        return False
    email_l = email.strip().lower()
    if email_l in settings.bootstrap_allowed_set:
        return True
    if not is_persistence_enabled():
        return True  # dev mode without a DB — don't gate
    from app.db.models import Waitlist

    with get_session() as session:
        if session is None:
            return True
        row = session.query(Waitlist).filter(Waitlist.email == email_l).first()
        return bool(row and row.status == "approved")


def ensure_pending_entry(email: str, name: str | None = None) -> None:
    """
    Auto-add an un-approved sign-in attempt to the waitlist as ``pending`` so the
    owner sees who's trying to get in. Best-effort — never raises.
    """
    if not is_persistence_enabled() or not email:
        return
    from app.db.models import Waitlist

    email_l = email.strip().lower()
    try:
        with get_session() as session:
            if session is None:
                return
            existing = session.query(Waitlist).filter(Waitlist.email == email_l).first()
            if existing:
                return
            session.add(Waitlist(
                email=email_l,
                name=name,
                status="pending",
                source="login",
            ))
            session.commit()
            logger.info("[waitlist] auto-added pending from login attempt: %s", email_l)
    except Exception as e:
        logger.warning("[waitlist] ensure_pending_entry failed for %s: %s", email_l, e)
