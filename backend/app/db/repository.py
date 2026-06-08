"""
Repository functions — the only place that reads/writes the database.
=====================================================================

Keeping all persistence behind these functions means the rest of the codebase
never imports SQLAlchemy directly, and every call is a safe no-op when running
without a database (dev mode). Each function returns a plain dict (or None) so
callers are decoupled from ORM objects.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import delete, select

from app.config.settings import settings
from app.db.base import get_session, is_persistence_enabled
from app.db.models import AuditLog, EmailEnrichment, ProcessingMetric

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
    status: str = "complete",
    enrichment_source: str = "agentic",
    error: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Insert or update the enrichment row for ``email_id`` from a pipeline state.

    Returns the persisted record as a dict, or None when persistence is off.
    """
    if not is_persistence_enabled():
        return None

    with get_session() as session:
        if session is None:
            return None
        row = session.get(EmailEnrichment, email_id)
        if row is None:
            row = EmailEnrichment(email_id=email_id, sender=state.get("sender", "unknown"))
            session.add(row)

        for field in _ENRICHMENT_FIELDS:
            if field in state and state[field] is not None:
                setattr(row, field, state[field])

        row.status = status
        row.enrichment_source = enrichment_source
        row.error = error
        session.commit()
        return _row_to_dict(row)


def get_enrichment(email_id: str) -> Optional[dict[str, Any]]:
    """Fetch one enrichment record, or None if missing / persistence off."""
    if not is_persistence_enabled():
        return None
    with get_session() as session:
        if session is None:
            return None
        row = session.get(EmailEnrichment, email_id)
        return _row_to_dict(row) if row else None


def list_enrichments(
    *, priority: Optional[str] = None, limit: int = 100, offset: int = 0
) -> list[dict[str, Any]]:
    """List enrichment records, optionally filtered by priority (newest first)."""
    if not is_persistence_enabled():
        return []
    with get_session() as session:
        if session is None:
            return []
        stmt = select(EmailEnrichment).order_by(EmailEnrichment.created_at.desc())
        if priority:
            stmt = stmt.where(EmailEnrichment.priority == priority)
        stmt = stmt.limit(limit).offset(offset)
        return [_row_to_dict(r) for r in session.scalars(stmt).all()]


def delete_enrichment(email_id: str) -> bool:
    """
    Hard-delete an email's enrichment record (GDPR right-to-erasure).

    Returns True if a row was deleted. Always writes an audit entry.
    """
    if not is_persistence_enabled():
        return False
    with get_session() as session:
        if session is None:
            return False
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
) -> None:
    """
    Append a compliance audit entry. Never store raw PII in ``details`` —
    only categories/counts/metadata.
    """
    if not (settings.audit_log_enabled and is_persistence_enabled()):
        return
    with get_session() as session:
        if session is None:
            return
        session.add(AuditLog(email_id=email_id, action=action, actor=actor, details=details))
        session.commit()


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
) -> None:
    """Persist a per-stage processing metric for SLA reporting."""
    if not is_persistence_enabled():
        return
    with get_session() as session:
        if session is None:
            return
        session.add(ProcessingMetric(
            email_id=email_id, stage=stage, duration_ms=duration_ms,
            success=success, sla_met=sla_met,
        ))
        session.commit()


def purge_expired(retention_days: Optional[int] = None) -> int:
    """
    Delete enrichment rows older than the retention window (data minimisation).

    Returns the number of rows deleted. Intended to be run on a schedule.
    """
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
        write_audit(None, "retention_purge", actor="scheduler", details={"deleted": deleted, "older_than_days": days})
    return deleted
