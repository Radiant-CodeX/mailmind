"""
Repository for the server-side mailbox mirror (inbox sync).
===========================================================

All functions are no-ops (returning empty/defaults) when persistence is
disabled, mirroring the pattern in ``repository.py``. The mirror tables are:

  mailbox_message      — envelope + flags per email
  mailbox_sync_state   — per-account delta cursor + exact count
  graph_subscription   — webhook subscription lifecycle

The read path joins ``mailbox_message`` with ``email_enrichment`` (on email_id)
so any already-computed triage is returned alongside the envelope.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select

from app.db.base import get_session, is_persistence_enabled
from app.db.models import EmailEnrichment, MailboxMessage, MailboxSyncState

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# ── Sync state ───────────────────────────────────────────────────────────────


def get_sync_state(account_id: str, folder: str = "inbox") -> Optional[dict[str, Any]]:
    """Return the sync-state row for an account+folder as a dict, or None."""
    if not is_persistence_enabled():
        return None
    with get_session() as session:
        if session is None:
            return None
        row = session.get(MailboxSyncState, (account_id, folder))
        if row is None:
            return None
        return {
            "account_id": row.account_id,
            "folder": row.folder,
            "delta_cursor": row.delta_cursor,
            "backfill_done": row.backfill_done,
            "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
            "last_status": row.last_status,
            "last_error": row.last_error,
            "message_count": row.message_count,
        }


def set_sync_status(account_id: str, folder: str, status: str, error: str | None = None) -> None:
    """Update only the status/error fields (e.g. 'running' / 'error')."""
    if not is_persistence_enabled():
        return
    with get_session() as session:
        if session is None:
            return
        row = session.get(MailboxSyncState, (account_id, folder))
        if row is None:
            row = MailboxSyncState(account_id=account_id, folder=folder)
            session.add(row)
        row.last_status = status
        row.last_error = error
        session.commit()


def set_sync_cursor(
    account_id: str,
    folder: str,
    *,
    delta_cursor: str | None = None,
    backfill_done: bool | None = None,
    status: str = "idle",
    error: str | None = None,
) -> None:
    """Persist the delta cursor and mark a sync as finished."""
    if not is_persistence_enabled():
        return
    with get_session() as session:
        if session is None:
            return
        row = session.get(MailboxSyncState, (account_id, folder))
        if row is None:
            row = MailboxSyncState(account_id=account_id, folder=folder)
            session.add(row)
        if delta_cursor is not None:
            row.delta_cursor = delta_cursor
        if backfill_done is not None:
            row.backfill_done = backfill_done
        row.last_status = status
        row.last_error = error
        row.last_synced_at = _utcnow()
        session.commit()


def recount(account_id: str, folder: str = "inbox") -> int:
    """Recompute and persist the exact active-message count. Returns it."""
    if not is_persistence_enabled():
        return 0
    with get_session() as session:
        if session is None:
            return 0
        total = session.scalar(
            select(func.count())
            .select_from(MailboxMessage)
            .where(MailboxMessage.account_id == account_id)
            .where(MailboxMessage.folder == folder)
            .where(MailboxMessage.state == "active")
        ) or 0
        row = session.get(MailboxSyncState, (account_id, folder))
        if row is None:
            row = MailboxSyncState(account_id=account_id, folder=folder)
            session.add(row)
        row.message_count = int(total)
        session.commit()
        return int(total)


# ── Message upserts ──────────────────────────────────────────────────────────


def upsert_messages(account_id: str, folder: str, messages: list[dict[str, Any]]) -> tuple[int, int]:
    """
    Insert or update a batch of envelopes. Returns (new_count, updated_count).

    Each message dict uses the envelope shape returned by the provider clients:
      email_id, sender, sender_name, subject, snippet, received_at,
      is_read, is_starred, has_attachments, thread_id
    """
    if not is_persistence_enabled():
        return (0, 0)
    new_count = updated = 0
    with get_session() as session:
        if session is None:
            return (0, 0)
        for m in messages:
            eid = m.get("email_id") or m.get("id")
            if not eid:
                continue
            row = session.get(MailboxMessage, eid)
            received = _parse_dt(m.get("received_at"))
            if row is None:
                session.add(MailboxMessage(
                    email_id=eid,
                    account_id=account_id,
                    folder=folder,
                    thread_id=m.get("thread_id"),
                    sender=m.get("sender") or "unknown@example.com",
                    sender_name=m.get("sender_name"),
                    subject=m.get("subject"),
                    snippet=(m.get("snippet") or m.get("body") or "")[:2000] or None,
                    received_at=received,
                    is_read=bool(m.get("is_read", True)),
                    is_starred=bool(m.get("is_starred", False)),
                    has_attachments=bool(m.get("has_attachments", False)),
                    state="active",
                ))
                new_count += 1
            else:
                row.folder = folder
                row.state = "active"
                row.is_read = bool(m.get("is_read", row.is_read))
                row.is_starred = bool(m.get("is_starred", row.is_starred))
                row.has_attachments = bool(m.get("has_attachments", row.has_attachments))
                if m.get("subject") is not None:
                    row.subject = m.get("subject")
                if received is not None:
                    row.received_at = received
                if m.get("thread_id"):
                    row.thread_id = m.get("thread_id")
                updated += 1
        session.commit()
    return (new_count, updated)


def tombstone_messages(account_id: str, email_ids: list[str]) -> int:
    """Mark messages as deleted (delta @removed). Returns rows affected."""
    if not is_persistence_enabled() or not email_ids:
        return 0
    affected = 0
    with get_session() as session:
        if session is None:
            return 0
        for eid in email_ids:
            row = session.get(MailboxMessage, eid)
            if row is not None and row.account_id == account_id and row.state != "deleted":
                row.state = "deleted"
                affected += 1
        session.commit()
    return affected


def update_flags(email_id: str, *, is_read: bool | None = None, is_starred: bool | None = None,
                 state: str | None = None) -> None:
    """Reflect a local action (read/star/done) on the mirror immediately."""
    if not is_persistence_enabled():
        return
    with get_session() as session:
        if session is None:
            return
        row = session.get(MailboxMessage, email_id)
        if row is None:
            return
        if is_read is not None:
            row.is_read = is_read
        if is_starred is not None:
            row.is_starred = is_starred
        if state is not None:
            row.state = state
        session.commit()


# ── Read path ────────────────────────────────────────────────────────────────


def list_page(
    account_id: str,
    folder: str = "inbox",
    *,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Return one page of the mirror joined with enrichment, newest first.

    Optimization: fetch limit+1 rows to determine if there's a next page without
    a separate COUNT query. If we got more than limit, return only limit and set
    next_page_token. This halves pagination latency (one query instead of two).
    """
    if not is_persistence_enabled():
        return {"emails": [], "total": 0, "next_page_token": None}
    with get_session() as session:
        if session is None:
            return {"emails": [], "total": 0, "next_page_token": None}

        # Fetch limit+1 to detect if there's a next page without a COUNT query
        stmt = (
            select(MailboxMessage, EmailEnrichment)
            .join(EmailEnrichment, EmailEnrichment.email_id == MailboxMessage.email_id, isouter=True)
            .where(MailboxMessage.account_id == account_id)
            .where(MailboxMessage.folder == folder)
            .where(MailboxMessage.state == "active")
            .order_by(MailboxMessage.received_at.desc().nullslast())
            .limit(limit + 1)  # Fetch one extra to detect next page
            .offset(offset)
        )
        all_rows = session.execute(stmt).all()
        has_next = len(all_rows) > limit
        rows = all_rows[:limit]  # Return only limit rows

        emails: list[dict[str, Any]] = []
        for msg, enr in rows:
            emails.append({
                "email_id": msg.email_id,
                "sender": msg.sender,
                "sender_name": msg.sender_name,
                "subject": msg.subject or "",
                "body": msg.snippet or "",
                "snippet": msg.snippet or "",
                "received_at": msg.received_at.isoformat() if msg.received_at else None,
                "is_read": msg.is_read,
                "is_starred": msg.is_starred,
                "has_attachments": msg.has_attachments,
                "thread_id": msg.thread_id,
                # Triage (None until enriched → frontend streams it as a fallback)
                "priority": enr.priority if enr else None,
                "composite_score": enr.composite_score if enr else None,
                "email_type": enr.email_type if enr else None,
                "approval_mode": (enr.approval_mode if enr else None) or "SUGGEST",
                "axes": (enr.axes if enr else None) or [],
            })

        next_token = str(offset + limit) if has_next else None
        return {"emails": emails, "total": 0, "next_page_token": next_token}


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None
