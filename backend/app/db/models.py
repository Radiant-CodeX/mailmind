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


class User(Base):
    """
    Internal MailMind identity. One row per human, regardless of how many
    mail accounts they connect.

    The user's primary email is whichever address they first signed in with —
    it is a label, not the identity. ``id`` is the identity; everything else
    (oauth accounts, sessions, caches) hangs off it.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid4 hex-with-dashes
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthAccount(Base):
    """
    One connected mailbox (Gmail or Outlook) belonging to a user.

    Deliberately one-to-many from users: the schema supports a user connecting
    several accounts even though the UI is single-account today.

    Token columns are stored encrypted (see ``app.services.crypto``). For
    Microsoft we store the serialized MSAL token cache blob rather than raw
    tokens — MSAL owns refresh/rotation, which avoids re-implementing AAD's
    token semantics. For Google we store the refresh/access token pair.
    """

    __tablename__ = "oauth_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # "google" | "microsoft"
    # The provider's stable account identifier (Google `sub` / AAD object id),
    # falling back to the account email when the provider id is unavailable.
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_email: Mapped[str] = mapped_column(String(320), nullable=False)

    # ── Encrypted credential material ────────────────────────────────────────
    access_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    msal_cache_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        # A given provider account can only be linked once, to one user.
        Index("uq_oauth_provider_account", "provider", "provider_account_id", unique=True),
        Index("ix_oauth_user_provider", "user_id", "provider"),
    )


class UserSession(Base):
    """
    Browser session. The token travels as an HttpOnly cookie (with the
    X-MailMind-Session header kept as a transitional fallback).

    Only a SHA-256 hash of the token is stored — a leaked DB dump cannot be
    replayed as live sessions.
    """

    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


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
