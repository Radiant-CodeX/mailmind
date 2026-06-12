"""
Database engine & session management with graceful no-DB fallback.
==================================================================

Persistence is **optional**. When ``DATABASE_URL`` is unset the engine is None
and ``get_session()`` yields nothing, so the API and workers run fully in
development with results returned inline (never persisted). Setting
``DATABASE_URL`` (e.g. a Supabase/PostgreSQL connection string) transparently
turns on durable storage — no code changes required.

This mirrors the queue's memory↔redis design: zero-dependency in dev, durable
in production.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Iterator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings
from app.db.models import Base

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def is_persistence_enabled() -> bool:
    """True when a database is configured and the engine initialised."""
    return _engine is not None


def _build_engine() -> Optional[Engine]:
    if not settings.persistence_enabled:
        logger.info("DATABASE_URL not set — persistence disabled (inline results only).")
        return None

    url = settings.database_url
    # SQLite (used in tests) does not accept pool sizing kwargs.
    if url.startswith("sqlite"):
        engine = create_engine(url, future=True)
    else:
        engine = create_engine(
            url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,  # transparently recycle dropped connections
            future=True,
        )
    logger.info("Database engine initialised (%s).", url.split("@")[-1] if "@" in url else url)
    return engine


def init_db(create_tables: bool = True) -> bool:
    """
    Initialise the engine + session factory. Optionally create tables.

    Returns True if persistence is active, False if running without a DB.
    Safe to call multiple times (idempotent).
    """
    global _engine, _SessionFactory

    if _engine is None:
        _engine = _build_engine()
        if _engine is None:
            return False
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)

    if create_tables and _engine is not None:
        try:
            Base.metadata.create_all(_engine)
            _run_migrations(_engine)
            logger.info("Database tables ensured.")
        except Exception as exc:
            logger.error("Failed to create tables: %s", exc)
            return False

    return True


@contextlib.contextmanager
def get_session() -> Iterator[Optional[Session]]:
    """
    Context manager yielding a Session, or None when persistence is disabled.

    Usage::

        with get_session() as session:
            if session is None:
                return  # dev mode, nothing to persist
            session.add(row)
            session.commit()

    Commits are the caller's responsibility; on exception we roll back.
    """
    if _SessionFactory is None:
        yield None
        return

    session = _SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run_migrations(engine: Engine) -> None:
    """Apply additive schema migrations that create_all() won't handle.

    Handles v2→v3 transformations:
    - tone_profile: migrate from user_email PK to account_id FK
    - audit_log, processing_metric: add account_id column
    """
    with engine.connect() as conn:
        try:
            # ── Tone Profile v2→v3 Migration ──────────────────────────────────
            # v2: tone_profile(user_email VARCHAR PRIMARY KEY, profile JSON, sample_size INT)
            # v3: tone_profile(account_id VARCHAR FK PRIMARY KEY, profile JSON, sample_size INT)
            #
            # Strategy: rename old table, create new v3 schema, migrate data if possible
            conn.execute(text("""
                ALTER TABLE IF EXISTS tone_profile
                RENAME TO tone_profile_v2
            """))
            conn.commit()
        except Exception:
            pass  # tone_profile_v2 might already exist or not need migration

        try:
            # Create v3 tone_profile if it doesn't exist
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tone_profile (
                    account_id VARCHAR(36) PRIMARY KEY,
                    profile JSON NOT NULL,
                    sample_size INTEGER DEFAULT 0,
                    CONSTRAINT fk_tone_profile_account FOREIGN KEY (account_id)
                        REFERENCES oauth_accounts(id) ON DELETE CASCADE
                )
            """))
            conn.commit()
        except Exception:
            pass  # Already exists

        migrations = [
            # v2 legacy columns — safe to skip if already present
            "ALTER TABLE email_enrichment ADD COLUMN user_email VARCHAR(320)",
            "CREATE INDEX IF NOT EXISTS ix_enrichment_user_email ON email_enrichment(user_email)",
            # v3 additions
            "ALTER TABLE audit_log ADD COLUMN account_id VARCHAR(36)",
            "ALTER TABLE processing_metric ADD COLUMN account_id VARCHAR(36)",
        ]
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column / index already exists — safe to ignore

        # Note: Migrating tone_profile data from v2→v3 requires joining with oauth_accounts
        # to resolve user_email → account_id. This is deferred to a manual migration script
        # or admin command since the mapping depends on which account is "default" for each user.
        logger.info("[Migration] Schema migrations applied (v2→v3).")


def get_db():
    """
    FastAPI dependency — yields a DB Session, or raises 503 if no DB is configured.

    Usage::

        @router.get("/something")
        def handler(db: Session = Depends(get_db)):
            ...
    """
    if _SessionFactory is None:
        from fastapi import HTTPException, status as _status
        raise HTTPException(
            status_code=_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not configured. Set DATABASE_URL to enable this endpoint.",
        )
    session = _SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose and reset the engine (used by tests)."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
