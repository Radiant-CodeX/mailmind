"""
SQLAlchemy ORM models for MailMind persistence.
================================================

Three tables capture everything needed to operate, audit, and report on the
pipeline in production:

  * ``email_enrichment`` — the canonical result of processing one email
    (triage scores, commitments, conflicts, draft). One row per email.
  * ``audit_log``        — an append-only trail of privacy/compliance-relevant
    events (PII masked, triaged, enriched, restored, deleted). Never stores
    raw PII — only categories/counts.
  * ``processing_metric``— per-stage latency + SLA outcome, used for SLA
    reporting and capacity planning.

All models use JSON columns for nested structures so the schema is portable
across PostgreSQL (production) and SQLite (tests).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all MailMind ORM models."""


class EmailEnrichment(Base):
    """Canonical processed-email record. One row per email_id."""

    __tablename__ = "email_enrichment"

    email_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    sender: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    masked_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Triage ──────────────────────────────────────────────────────────────
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    email_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    axes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    dynamic_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    triage_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Commitments / calendar ──────────────────────────────────────────────
    commitments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    commitment_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── RAG / draft ─────────────────────────────────────────────────────────
    draft_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    precedents: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ── Lifecycle ───────────────────────────────────────────────────────────
    # enrichment_source: "agentic" (full pipeline) | "fast_triage" (triage only)
    enrichment_source: Mapped[str] = mapped_column(String(32), default="agentic")
    # status: "triaged" | "enriching" | "complete" | "failed"
    status: Mapped[str] = mapped_column(String(20), default="triaged", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_enrichment_priority", "priority"),
        Index("ix_enrichment_created_at", "created_at"),
        Index("ix_enrichment_user_email", "user_email"),
    )


class AuditLog(Base):
    """Append-only compliance audit trail. Never contains raw PII."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    # action: "pii_masked" | "triaged" | "enriched" | "pii_restored" | "deleted" | "exported"
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    # details holds non-sensitive metadata only (e.g. {"PERSON": 2, "EMAIL": 1}).
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class ToneProfile(Base):
    """
    Stylometric profile built from a user's sent-mail history (Tone DNA).

    One row per user — upserted whenever the profile is rebuilt.
    The ``profile`` JSON column stores the full feature dict produced by
    ``tone_dna.build_profile()``.
    """

    __tablename__ = "tone_profile"

    user_email: Mapped[str] = mapped_column(String(320), primary_key=True)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ProcessingMetric(Base):
    """Per-stage latency and SLA outcome for one email's processing."""

    __tablename__ = "processing_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    # stage: "triage" | "enrichment"
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    sla_met: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
