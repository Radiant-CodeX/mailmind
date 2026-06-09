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
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.observability import init_observability
from app.queue.queue import EmailQueue
from routes.ai_routes import router as ai_router
from routes.email_routes import router as email_router
from routes.evaluation_routes import router as evaluation_router
from routes.graph_routes import router as graph_router

# api_bridge.py is no longer included — app/api/routes.py handles all /api/* routes
# (including auth, emails, commitments, triage, drafts, etc.)
api_bridge_router = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


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
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Approval-Token"],
)

app.include_router(router)
app.include_router(agent_router)
app.include_router(monitoring_router, prefix="/api")
app.include_router(compliance_router)
app.include_router(email_router)
app.include_router(ai_router)
app.include_router(graph_router)
app.include_router(evaluation_router)

# api_bridge_router is disabled — routes.py supersedes it