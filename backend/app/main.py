"""
MailMind FastAPI Backend
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_routes import router as agent_router
from app.api.compliance_routes import router as compliance_router
from app.api.monitoring_routes import router as monitoring_router
from app.api.routes import router
from app.config.settings import settings
from app.db.base import init_db
from app.middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    SessionContextMiddleware,
)
from app.observability import init_observability
from app.queue.queue import EmailQueue

def _configure_logging() -> None:
    """Set up structured logging with a dedicated audit trail.

    The ``mailmind.audit`` logger emits security-relevant events (login, logout,
    session create/expire/revoke, token refresh, rate-limit hits) to its own
    handler so they can be routed to a separate sink (file, CloudWatch, Datadog)
    without noise from debug logs. In development it writes to stderr alongside
    the main log; in production, swap the handler for your log-shipping solution.
    """
    log_level = logging.DEBUG if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" else logging.INFO

    fmt = logging.Formatter("%(asctime)s %(levelname)-8s [%(name)s] %(message)s")
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(log_level)
    if not root.handlers:
        root.addHandler(handler)

    # Dedicated audit logger — propagates to root by default (so audit events
    # appear in the main log stream), but you can attach a separate FileHandler
    # or log-shipping handler here to get an isolated audit sink.
    audit_logger = logging.getLogger("mailmind.audit")
    audit_logger.setLevel(logging.DEBUG)  # capture all audit levels

    audit_log_path = os.getenv("AUDIT_LOG_FILE")
    if audit_log_path:
        try:
            os.makedirs(os.path.dirname(audit_log_path), exist_ok=True)
            audit_handler = logging.FileHandler(audit_log_path, encoding="utf-8")
            audit_handler.setFormatter(fmt)
            audit_logger.addHandler(audit_handler)
            audit_logger.propagate = False  # don't double-emit to root
        except Exception as e:
            logging.warning("Could not open AUDIT_LOG_FILE=%s: %s — audit events go to root log", audit_log_path, e)


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.email_queue = EmailQueue()

    # Initialise persistence (no-op when DATABASE_URL is unset / dev mode).
    try:
        init_db()
    except Exception as _e:
        logging.warning(f"Database init skipped: {_e}")

    # Tone DNA profiles are built on demand via POST /api/tone-dna/build — not
    # on startup — because we don't have a user identity at boot time.
    try:
        import spacy
        spacy.load("en_core_web_sm")
    except Exception as e:
        logging.warning(f"spaCy 'en_core_web_sm' not loaded: {e}")
    yield


app = FastAPI(
    title="MailMind API",
    description="AI-powered enterprise email triage and drafting backend",
    version="2.0.0",
    lifespan=lifespan,
)


# Structured logging + global exception handlers + optional Sentry.
init_observability(app)

# ── Security & rate-limit middleware ──────────────────────────────────────────
# NOTE: middleware runs in reverse registration order, so the security headers
# wrap the rate-limiter which wraps the app.
app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
app.add_middleware(SecurityHeadersMiddleware)
# Registered last → runs first (outermost), so the session ContextVar is bound
# before any downstream middleware or route handler runs.
app.add_middleware(SessionContextMiddleware)

# Build an explicit allow-list of origins (no wildcards alongside credentials).
_allowed_origins = list(dict.fromkeys(filter(None, [
    settings.frontend_origin,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
])))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    # Explicit header list — the CORS spec forbids "*" when credentials are allowed.
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Approval-Token", "X-MailMind-Session"],
)

logger = logging.getLogger(__name__)

logger.info(
    "is_production=%s frontend_origin=%s",
    settings.is_production,
    settings.frontend_origin,
)

app.include_router(router)
app.include_router(agent_router)
app.include_router(monitoring_router, prefix="/api")
app.include_router(compliance_router)
