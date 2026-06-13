"""
Repository functions — the only place that reads/writes the database.
=====================================================================

v3: EmailEnrichment is scoped by account_id (FK to oauth_accounts.id),
not user_email. All public functions accept account_id; the legacy
user_email parameter is kept as an alias so call-sites don't all have
to change at once, but internally we use account_id.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, select

from app.config.settings import settings
from app.db.base import get_session, is_persistence_enabled
from app.db.models import AuditLog, EmailEnrichment, ProcessingMetric, ToneProfile, TriagePriorityOverride

logger = logging.getLogger(__name__)

# Fields copied from pipeline state into the enrichment row.
_ENRICHMENT_FIELDS = (
    "sender", "subject", "masked_body", "priority", "composite_score",
    "email_type", "approval_mode", "axes", "dynamic_weights", "triage_reasoning",
    "commitments", "commitment_reasoning", "conflict_summary", "draft_reply",
    "precedents",
)


def _row_to_dict(row: EmailEnrichment) -> dict[str, Any]:
    return {
        "email_id": row.email_id,
        "account_id": row.account_id,
        # Legacy compat key — callers that still read user_email get account_id value
        "user_email": row.account_id,
        "sender": row.sender,
        "subject": row.subject,
        "masked_body": row.masked_body,
        "priority": row.priority,
        "composite_score": row.composite_score,
        "email_type": row.email_type,
        "approval_mode": row.approval_mode,
        "axes": row.axes,
        "dynamic_weights": row.dynamic_weights,
        "triage_reasoning": row.triage_reasoning,
        "commitments": row.commitments,
        "commitment_reasoning": row.commitment_reasoning,
        "conflict_summary": row.conflict_summary,
        "draft_reply": row.draft_reply,
        "precedents": row.precedents,
        "enrichment_source": row.enrichment_source,
        "status": row.status,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def upsert_enrichment(
    email_id: str,
    state: dict[str, Any],
    *,
    account_id: Optional[str] = None,
    # Legacy alias — callers passing user_email still work
    user_email: Optional[str] = None,
    status: str = "complete",
    enrichment_source: str = "agentic",
    error: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Insert or update the enrichment row for email_id from a pipeline state."""
    if not is_persistence_enabled():
        return None

    # Resolve account_id — prefer explicit, fall back to legacy alias
    resolved_account_id = account_id or user_email or None

    with get_session() as session:
        if session is None:
            return None

        row = session.get(EmailEnrichment, email_id)

        if row is None:
            row = EmailEnrichment(
                email_id=email_id,
                account_id=resolved_account_id,
                sender=state.get("sender", "unknown"),
            )
            session.add(row)
        else:
            if resolved_account_id and not row.account_id:
                row.account_id = resolved_account_id

        for field in _ENRICHMENT_FIELDS:
            if field in state and state[field] is not None:
                setattr(row, field, state[field])

        row.status = status
        row.enrichment_source = enrichment_source
        row.error = error
        session.commit()
        return _row_to_dict(row)


def get_enrichment(
    email_id: str,
    account_id: Optional[str] = None,
    user_email: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Fetch one enrichment record scoped to account_id, or None if missing."""
    if not is_persistence_enabled():
        return None

    resolved = account_id or user_email or None

    with get_session() as session:
        if session is None:
            return None
        if resolved:
            stmt = (
                select(EmailEnrichment)
                .where(EmailEnrichment.email_id == email_id)
                .where(EmailEnrichment.account_id == resolved)
            )
            row = session.scalars(stmt).first()
        else:
            row = session.get(EmailEnrichment, email_id)
        return _row_to_dict(row) if row else None


def list_enrichments(
    *,
    account_id: Optional[str] = None,
    user_email: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List enrichment records scoped to account_id, optionally filtered by priority."""
    if not is_persistence_enabled():
        return []

    resolved = account_id or user_email or None

    with get_session() as session:
        if session is None:
            return []
        stmt = select(EmailEnrichment).order_by(EmailEnrichment.created_at.desc())
        if resolved:
            stmt = stmt.where(EmailEnrichment.account_id == resolved)
        if priority:
            stmt = stmt.where(EmailEnrichment.priority == priority)
        stmt = stmt.limit(limit).offset(offset)
        return [_row_to_dict(r) for r in session.scalars(stmt).all()]


def delete_enrichment(
    email_id: str,
    account_id: Optional[str] = None,
    user_email: Optional[str] = None,
) -> bool:
    """Hard-delete an email's enrichment record (GDPR right-to-erasure)."""
    if not is_persistence_enabled():
        return False

    resolved = account_id or user_email or None

    with get_session() as session:
        if session is None:
            return False
        if resolved:
            stmt = (
                select(EmailEnrichment)
                .where(EmailEnrichment.email_id == email_id)
                .where(EmailEnrichment.account_id == resolved)
            )
            row = session.scalars(stmt).first()
        else:
            row = session.get(EmailEnrichment, email_id)
        if row is None:
            return False
        session.delete(row)
        session.commit()
    write_audit(email_id, "deleted", actor="gdpr_request")
    return True


def write_audit(
    email_id: Optional[str],
    action: str,
    *,
    actor: str = "system",
    details: Optional[dict[str, Any]] = None,
    account_id: Optional[str] = None,
) -> None:
    """Append a compliance audit entry. Never store raw PII in details."""
    if not (settings.audit_log_enabled and is_persistence_enabled()):
        return
    with get_session() as session:
        if session is None:
            return
        session.add(AuditLog(
            email_id=email_id,
            action=action,
            actor=actor,
            details=details,
            account_id=account_id,
        ))
        session.commit()


def record_priority_override(
    email_id: str,
    sender: str,
    override_priority: str,
    *,
    original_priority: Optional[str] = None,
    user_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Persist a user's triage-priority correction and apply it to the email's
    enrichment row. Returns the override as a dict, or None when persistence
    is disabled.

    The stored row also feeds ``get_sender_priority_hint`` so subsequent emails
    from the same sender can be triaged faster and more accurately.
    """
    if not is_persistence_enabled():
        return None

    norm_sender = (sender or "").strip().lower()
    override_priority = (override_priority or "").strip().upper()

    with get_session() as session:
        if session is None:
            return None

        row = TriagePriorityOverride(
            email_id=email_id,
            sender=norm_sender,
            original_priority=original_priority,
            override_priority=override_priority,
            user_id=user_id,
            account_id=account_id,
        )
        session.add(row)

        # Reflect the override on the canonical enrichment record so the inbox
        # and detail views show the corrected priority immediately.
        enrichment = session.get(EmailEnrichment, email_id)
        if enrichment is not None:
            if override_priority == "DONE":
                enrichment.status = "done"
            else:
                enrichment.priority = override_priority
                enrichment.approval_mode = "GATE" if override_priority == "CRITICAL" else "SUGGEST"

        session.commit()
        result = {
            "id": row.id,
            "email_id": email_id,
            "sender": norm_sender,
            "override_priority": override_priority,
            "original_priority": original_priority,
        }

    write_audit(
        email_id,
        "priority_override",
        actor="user",
        details={"from": original_priority, "to": override_priority},
        account_id=account_id,
    )
    return result


def get_sender_priority_hint(
    sender: str,
    *,
    account_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """
    Return the learned priority for a sender based on prior overrides, or None.

    This is the read side of the triage feedback loop: if the user has recently
    corrected this sender's emails to a consistent priority, future emails can
    skip scoring and adopt that priority directly. We only return a hint when
    the most recent overrides for the sender agree, to avoid acting on noise.
    """
    if not is_persistence_enabled():
        return None

    norm_sender = (sender or "").strip().lower()
    if not norm_sender:
        return None

    with get_session() as session:
        if session is None:
            return None
        stmt = (
            select(TriagePriorityOverride.override_priority)
            .where(TriagePriorityOverride.sender == norm_sender)
        )
        if account_id:
            stmt = stmt.where(TriagePriorityOverride.account_id == account_id)
        elif user_id:
            stmt = stmt.where(TriagePriorityOverride.user_id == user_id)
        stmt = stmt.order_by(TriagePriorityOverride.created_at.desc()).limit(3)
        recent = [r for r in session.scalars(stmt).all()]

    if not recent:
        return None
    # Only act when the latest signals are unanimous.
    if all(p == recent[0] for p in recent):
        return recent[0]
    return None


def get_audit_log(email_id: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return the audit trail for one email (newest first)."""
    if not is_persistence_enabled():
        return []
    with get_session() as session:
        if session is None:
            return []
        stmt = (
            select(AuditLog)
            .where(AuditLog.email_id == email_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": r.id,
                "email_id": r.email_id,
                "action": r.action,
                "actor": r.actor,
                "details": r.details,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in session.scalars(stmt).all()
        ]


def record_metric(
    email_id: Optional[str],
    stage: str,
    duration_ms: float,
    *,
    success: bool = True,
    sla_met: bool = True,
    account_id: Optional[str] = None,
) -> None:
    """Persist a per-stage processing metric for SLA reporting."""
    if not is_persistence_enabled():
        return
    with get_session() as session:
        if session is None:
            return
        session.add(ProcessingMetric(
            email_id=email_id,
            stage=stage,
            duration_ms=duration_ms,
            success=success,
            sla_met=sla_met,
            account_id=account_id,
        ))
        session.commit()


def get_tone_profile(account_id: str) -> Optional[dict[str, Any]]:
    """Return the Tone DNA profile for account_id, or None if not built yet."""
    if not is_persistence_enabled():
        return None
    with get_session() as session:
        if session is None:
            return None
        row = session.get(ToneProfile, account_id)
        return dict(row.profile) if row else None


def save_tone_profile(account_id: str, profile: dict[str, Any]) -> None:
    """Insert or overwrite the Tone DNA profile for account_id."""
    if not is_persistence_enabled():
        return
    with get_session() as session:
        if session is None:
            return
        row = session.get(ToneProfile, account_id)
        if row is None:
            row = ToneProfile(account_id=account_id, profile=profile,
                              sample_size=profile.get("sample_size", 0))
            session.add(row)
        else:
            row.profile = profile
            row.sample_size = profile.get("sample_size", 0)
        session.commit()


def purge_expired(retention_days: Optional[int] = None) -> int:
    """Delete enrichment rows older than the retention window (data minimisation)."""
    if not is_persistence_enabled():
        return 0
    days = retention_days if retention_days is not None else settings.data_retention_days
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    with get_session() as session:
        if session is None:
            return 0
        result = session.execute(
            delete(EmailEnrichment).where(EmailEnrichment.created_at < cutoff)
        )
        session.commit()
        deleted = result.rowcount or 0
    if deleted:
        write_audit(None, "retention_purge", actor="scheduler",
                    details={"deleted": deleted, "older_than_days": days})
    return deleted
