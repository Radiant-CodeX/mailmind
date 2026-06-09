"""
Compliance & data-governance endpoints (GDPR / DPDP-aligned).
=============================================================

MailMind processes personal data, so it exposes the data-subject rights and
operational controls expected of an enterprise system:

  GET    /api/compliance/email/{id}/export   Right to access / portability
  DELETE /api/compliance/email/{id}          Right to erasure ("right to be forgotten")
  GET    /api/compliance/email/{id}/audit    Processing audit trail for one email
  POST   /api/compliance/purge               Run data-retention purge (data minimisation)

Privacy guarantees enforced elsewhere and surfaced here:
  * PII is masked before any LLM call and only restored post-generation
    (see app/services/pii.py).
  * Audit entries never contain raw PII — only categories/counts/metadata.
  * Erasure is a hard delete and is itself audited.

These endpoints require persistence; without a configured database they return
503 so callers know governance features are unavailable in that deployment.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.config.settings import settings
from app.db import repository as repo
from app.db.base import is_persistence_enabled

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


def _require_persistence() -> None:
    if not is_persistence_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Compliance features require a configured database (DATABASE_URL).",
        )


def _db_error_to_503(exc: Exception) -> HTTPException:
    """Convert a DB connectivity/operational error into a clean 503."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Database is temporarily unreachable. "
            "This is expected on restricted networks (e.g. captive portal / VPN required). "
            f"Underlying error: {type(exc).__name__}"
        ),
    )


@router.get("/email/{email_id}/export")
def export_email_data(email_id: str, current_user: str = Depends(get_current_user)) -> dict:
    """
    Data-subject access / portability: return everything stored for an email,
    including its processing audit trail. Also records the export in the audit log.
    """
    _require_persistence()
    try:
        record = repo.get_enrichment(email_id, user_email=current_user)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data for this email_id.")
        audit = repo.get_audit_log(email_id)
        repo.write_audit(email_id, "exported", actor="data_subject_request")
        return {
            "email_id": email_id,
            "enrichment": record,
            "audit_trail": audit,
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _db_error_to_503(exc) from exc


@router.delete("/email/{email_id}")
def erase_email_data(email_id: str, current_user: str = Depends(get_current_user)) -> dict:
    """
    Right to erasure: hard-delete the stored enrichment for an email.

    The deletion itself is written to the audit log (for accountability) before
    the enrichment row is removed.
    """
    _require_persistence()
    try:
        deleted = repo.delete_enrichment(email_id, user_email=current_user)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data for this email_id.")
        return {
            "email_id": email_id,
            "deleted": True,
            "erased_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise _db_error_to_503(exc) from exc


@router.get("/email/{email_id}/audit")
def get_email_audit(email_id: str) -> dict:
    """Return the processing audit trail for one email (no raw PII)."""
    _require_persistence()
    try:
        return {"email_id": email_id, "audit_trail": repo.get_audit_log(email_id)}
    except Exception as exc:
        raise _db_error_to_503(exc) from exc


@router.post("/purge")
def purge_retention(retention_days: int | None = None) -> dict:
    """
    Run the data-retention purge: delete enrichment older than the retention
    window (default ``settings.data_retention_days``). Intended for a scheduler
    or admin action. Data-minimisation control.
    """
    _require_persistence()
    try:
        deleted = repo.purge_expired(retention_days)
        return {
            "deleted": deleted,
            "retention_days": retention_days if retention_days is not None else settings.data_retention_days,
            "purged_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    except Exception as exc:
        raise _db_error_to_503(exc) from exc
