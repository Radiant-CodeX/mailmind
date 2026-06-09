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
    """Apply additive schema migrations that create_all() won't handle."""
    migrations = [
        "ALTER TABLE email_enrichment ADD COLUMN user_email VARCHAR(320)",
        "CREATE INDEX IF NOT EXISTS ix_enrichment_user_email ON email_enrichment(user_email)",
        # tone_profile is created by create_all; no ALTER needed — it's a new table
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column / index already exists — safe to ignore


def reset_engine() -> None:
    """Dispose and reset the engine (used by tests)."""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
