"""
Drop-in replacement for backend/app/main.py
OBS-03: Jaeger exporter configured
OBS-01/02: Custom spans per agent step with triage axis attributes
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

try:
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
except Exception:
    JaegerExporter = None

from app.api.agent_routes import router as agent_router
from app.api.routes import router
from app.config.settings import settings
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.observability import init_observability
from app.queue.queue import EmailQueue
from routes.ai_routes import router as ai_router
from routes.email_routes import router as email_router
from routes.evaluation_routes import router as evaluation_router
from routes.graph_routes import router as graph_router

# API Bridge: Translate frontend /api/* calls to internal routes
try:
    from api_bridge import router as api_bridge_router
except ImportError:
    logging.warning("api_bridge.py not found; /api/* routes will not be available")
    api_bridge_router = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ── OBS-03: Jaeger exporter ────────────────────────────────────────────────────
_provider = TracerProvider()


_jaeger_endpoint = os.getenv(
    "OTEL_EXPORTER_JAEGER_ENDPOINT", "http://localhost:14268/api/traces"
)
try:
    if JaegerExporter is not None:
        _jaeger_exporter = JaegerExporter(collector_endpoint=_jaeger_endpoint)
        _provider.add_span_processor(BatchSpanProcessor(_jaeger_exporter))
        logging.info(f"Jaeger exporter configured: {_jaeger_endpoint}")
    else:
        logging.warning("Jaeger exporter thrift protocol not supported/available in this environment.")
except Exception as _e:
    logging.warning(f"Jaeger exporter not available: {_e}")

trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("mailmind.v2")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.email_queue = EmailQueue()
    app.state.tracer = tracer

    # DNA-01: Build Tone DNA profile on startup if not yet present
    from app.services.graph import GraphClient
    from app.services.tone_dna import ToneDNAService, load_profile
    if not load_profile():
        try:
            ToneDNAService(GraphClient()).ingest_and_build()
        except Exception as _e:
            logging.warning(f"Tone DNA build skipped on startup: {_e}")
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

FastAPIInstrumentor.instrument_app(app)

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
app.include_router(email_router)
app.include_router(ai_router)
app.include_router(graph_router)
app.include_router(evaluation_router)

# Include API Bridge for frontend /api/* routes
if api_bridge_router:
    app.include_router(api_bridge_router)


# ── OBS-01/02: Helper for custom spans ────────────────────────────────────────
def span_triage(email_id: str, axes: list, composite_score: float, priority: str):
    """Call after triage to emit a custom span with all 5 axis attributes."""
    with tracer.start_as_current_span("mailmind.triage") as span:
        span.set_attribute("email.id", email_id)
        span.set_attribute("triage.composite_score", composite_score)
        span.set_attribute("triage.priority", priority)
        for axis in axes:
            name = axis.get("axis") or getattr(axis, "axis", "unknown")
            score = axis.get("raw_score") or getattr(axis, "raw_score", 0.0)
            span.set_attribute(f"triage.axis.{name}", score)