"""
SQLAlchemy ORM models for MailMind v3.
=======================================

Identity layer (v3):
  users              — MailMind identity. Email is metadata, not identity.
  oauth_accounts     — One per connected Gmail/Outlook account. Tokens stored
                       encrypted at rest. Multiple per user.
  user_sessions      — Short-lived authenticated sessions (24h). Validated on
                       every request via mm_session cookie.
  devices            — Trusted devices for Quick Login (browser fingerprint).
  quick_login_tokens — Long-lived (7d) tokens for session auto-resume.
                       Status: ACTIVE | LOGGED_OUT | REVOKED | EXPIRED.

Pipeline layer (unchanged from v2, scoped to account_id in v3):
  email_enrichment   — Canonical triage/commitment/draft result per message.
  audit_log          — Append-only compliance trail (no raw PII).
  processing_metric  — Per-stage latency for SLA reporting.
  tone_profile       — Stylometric profile, now keyed by account_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Declarative base for all MailMind ORM models."""


# ─────────────────────────────────────────────────────────────────────────────
# IDENTITY LAYER
# ─────────────────────────────────────────────────────────────────────────────


class User(Base):
    """
    MailMind identity. One row per person, regardless of how many email
    accounts they connect. primary_email is display metadata only — it is NOT
    unique and NOT the identity anchor. user.id (UUID) is the identity.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Display metadata — not unique, can change, can be None.
    primary_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    accounts: Mapped[list[OAuthAccount]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", cascade="all, delete-orphan")
    devices: Mapped[list[Device]] = relationship(back_populates="user", cascade="all, delete-orphan")
    quick_login_tokens: Mapped[list[QuickLoginToken]] = relationship(back_populates="user", cascade="all, delete-orphan")


class OAuthAccount(Base):
    """
    One connected email account. A user can have many.

    Deduplication key: (provider, provider_account_id) — Google sub / MS
    object_id. These are stable and immutable even if the email address changes.

    Tokens are Fernet-encrypted at rest via TokenEncryptionService.
    """

    __tablename__ = "oauth_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Provider identity — dedup anchor, never changes
    provider: Mapped[str] = mapped_column(String(32), nullable=False)           # "google" | "microsoft"
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)  # Google sub / MS object_id
    account_email: Mapped[str] = mapped_column(String(320), nullable=False)

    # Encrypted OAuth tokens (v2 Supabase uses _enc suffix, v3 uses _encrypted)
    access_token_encrypted: Mapped[str | None] = mapped_column("access_token_enc", Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column("refresh_token_enc", Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # User-defined account metadata (Change #2)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)     # "Personal", "SRM"
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)         # "#6366f1"
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="accounts")
    tone_profile: Mapped[ToneProfile | None] = relationship(back_populates="account", uselist=False, cascade="all, delete-orphan")
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    given_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True
    )

    family_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True
    )

    picture_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )
    __table_args__ = (
        # Deduplication: same provider account can only be connected once globally.
        UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
        Index("ix_oauth_accounts_user_id", "user_id"),
    )


class UserSession(Base):
    """
    Short-lived authenticated session (default 24h).
    Only the SHA-256 hash of the raw token is stored — never the token itself.
    The raw token lives in the mm_session HttpOnly cookie.

    Note: In v2 Supabase, token_hash is the PK (no separate id column).
    """

    __tablename__ = "user_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # v2 legacy columns (required NOT NULL in Supabase)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="google")
    email: Mapped[str] = mapped_column(String(320), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    user: Mapped[User] = relationship(back_populates="sessions")

    __table_args__ = (
        Index("ix_user_sessions_user_id", "user_id"),
        Index("ix_user_sessions_token_hash", "token_hash"),
    )


class Device(Base):
    """
    A trusted browser/device for Quick Login.
    Identified by a fingerprint derived from User-Agent + Accept-Language headers.
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)              # sha256 of User-Agent + Accept-Language
    user_agent: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    accept_language: Mapped[str | None] = mapped_column(String(256), nullable=True)

    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    user: Mapped[User] = relationship(back_populates="devices")
    quick_login_tokens: Mapped[list[QuickLoginToken]] = relationship(back_populates="device", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "fingerprint", name="uq_device_user_fingerprint"),
        Index("ix_devices_user_id", "user_id"),
    )


class QuickLoginToken(Base):
    """
    Long-lived token (default 7d) for automatic session restoration.
    Stored as SHA-256 hash. Raw token lives in mm_quick HttpOnly cookie.

    Lifecycle:
      ACTIVE     — valid, can restore a session
      LOGGED_OUT — user explicitly logged out; kept for 7d for audit
      REVOKED    — admin/security revocation
      EXPIRED    — past expires_at (soft state, filtered in queries)

    Token is rotated on every use (validate_and_rotate) to detect replay attacks.
    """

    __tablename__ = "quick_login_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE", nullable=False)
    # ACTIVE | LOGGED_OUT | REVOKED | EXPIRED

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    user: Mapped[User] = relationship(back_populates="quick_login_tokens")
    device: Mapped[Device] = relationship(back_populates="quick_login_tokens")

    __table_args__ = (
        Index("ix_quick_login_user_id", "user_id"),
        Index("ix_quick_login_token_hash", "token_hash"),
        Index("ix_quick_login_status", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE LAYER (scoped to account_id in v3)
# ─────────────────────────────────────────────────────────────────────────────


class EmailEnrichment(Base):
    """Canonical processed-email record. One row per global_message_id."""

    __tablename__ = "email_enrichment"

    # v3: email_id uses global format "provider:account_id:native_id"
    email_id: Mapped[str] = mapped_column(String(512), primary_key=True)
    # account_id scopes this record to a specific connected account
    account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("oauth_accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )

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
    enrichment_source: Mapped[str] = mapped_column(String(32), default="agentic")
    status: Mapped[str] = mapped_column(String(20), default="triaged", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_enrichment_priority", "priority"),
        Index("ix_enrichment_created_at", "created_at"),
        Index("ix_enrichment_account_id", "account_id"),
    )


class AuditLog(Base):
    """Append-only compliance audit trail. Never contains raw PII."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[str | None] = mapped_column(String(512), index=True, nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class ToneProfile(Base):
    """
    Stylometric profile built from a user's sent-mail history (Tone DNA).

    v3: keyed by account_id — each connected email account has its own
    writing style profile. Personal Gmail vs SRM Outlook have different tones.
    """

    __tablename__ = "tone_profile"

    # v3: primary key is account_id, not user_email
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("oauth_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationship
    account: Mapped[OAuthAccount] = relationship(back_populates="tone_profile")


class Feedback(Base):
    """User-submitted product feedback (rating + category + message)."""

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class TriagePriorityOverride(Base):
    """
    A user-supplied correction to an email's triage priority.

    Each row is one override event ("this CRITICAL email is actually DONE").
    Beyond updating the single email, these rows form a feedback loop: future
    emails from the same sender can be short-circuited to the learned priority,
    making triage both faster and more aligned with the user's judgment.
    """

    __tablename__ = "triage_priority_override"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # account scope (legacy: primary_email) used to match the triage path's key
    account_id: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    email_id: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    original_priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # CRITICAL / HIGH / MEDIUM / LOW / DONE
    override_priority: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    __table_args__ = (
        Index("ix_override_account_sender", "account_id", "sender"),
    )


class ProcessingMetric(Base):
    """Per-stage latency and SLA outcome for one email's processing."""

    __tablename__ = "processing_metric"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_id: Mapped[str | None] = mapped_column(String(512), index=True, nullable=True)
    account_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    sla_met: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
