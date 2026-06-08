"""Persistence layer for MailMind (SQLAlchemy + PostgreSQL/Supabase)."""

from app.db.base import get_session, init_db, is_persistence_enabled
from app.db.models import AuditLog, Base, EmailEnrichment, ProcessingMetric

__all__ = [
    "Base",
    "EmailEnrichment",
    "AuditLog",
    "ProcessingMetric",
    "get_session",
    "init_db",
    "is_persistence_enabled",
]
