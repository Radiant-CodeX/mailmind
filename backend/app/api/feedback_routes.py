"""
Feedback collection endpoint.
==============================

  POST /api/feedback   Submit a star-rating + category + message (auth required)
  GET  /api/feedback   Return all submitted feedback entries (auth required)

Storage: the ``feedback`` DB table is the primary store. When persistence is
disabled (no DATABASE_URL, dev mode) entries fall back to a local JSON file
(backend/feedback_store.json) — same memory↔durable pattern as the queue.

The submitter identity always comes from the authenticated session — the
client cannot spoof another user's email.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.db.base import get_session, is_persistence_enabled

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback"])

_STORE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "feedback_store.json")


# ── JSON-file fallback (dev mode only) ───────────────────────────────────────


def _file_load() -> list[dict]:
    if not os.path.exists(_STORE_PATH):
        return []
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return []


def _file_save(entries: list[dict]) -> None:
    try:
        os.makedirs(os.path.dirname(_STORE_PATH), exist_ok=True)
        with open(_STORE_PATH, "w", encoding="utf-8") as fh:
            json.dump(entries, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass  # best-effort — don't crash the request


class FeedbackPayload(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    category: str = Field(..., max_length=64)
    message: str = Field(..., max_length=2000)
    role: str | None = Field(default=None, max_length=64)


@router.post("/feedback")
def submit_feedback(payload: FeedbackPayload, current_user=Depends(get_current_user)) -> dict:
    """Persist a feedback submission (DB primary, JSON file fallback)."""
    entry_id = str(uuid.uuid4())

    if is_persistence_enabled():
        from app.db.models import Feedback

        with get_session() as session:
            if session is not None:
                session.add(Feedback(
                    id=entry_id,
                    user_id=current_user.id,
                    user_email=current_user.primary_email,
                    rating=payload.rating,
                    category=payload.category,
                    message=payload.message,
                    role=payload.role,
                ))
                session.commit()
                return {"ok": True, "id": entry_id, "store": "db"}

    # Dev fallback — no DATABASE_URL configured
    entries = _file_load()
    entries.append({
        "id": entry_id,
        "rating": payload.rating,
        "category": payload.category,
        "message": payload.message,
        "user_email": current_user.primary_email,
        "role": payload.role,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    })
    _file_save(entries)
    return {"ok": True, "id": entry_id, "store": "file"}


@router.get("/feedback")
def list_feedback(current_user=Depends(get_current_user)) -> dict:
    """Return all collected feedback entries, newest first."""
    if is_persistence_enabled():
        from app.db.models import Feedback

        with get_session() as session:
            if session is not None:
                rows = (
                    session.query(Feedback)
                    .order_by(Feedback.created_at.desc())
                    .all()
                )
                return {
                    "count": len(rows),
                    "store": "db",
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

    entries = _file_load()
    return {
        "count": len(entries),
        "store": "file",
        "entries": sorted(entries, key=lambda e: e.get("timestamp", ""), reverse=True),
    }
