import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider

from app.config import FRONTEND_ORIGIN
from routes.email_routes import router as email_router
from routes.ai_routes import router as ai_router
from routes.graph_routes import router as graph_router
from routes.evaluation_routes import router as evaluation_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
trace.set_tracer_provider(TracerProvider())


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.email_queue = EmailQueue()
    # Check if spaCy en_core_web_sm model is available
    try:
        import spacy
        spacy.load("en_core_web_sm")
    except Exception as e:
        logging.warning(
            "spaCy model 'en_core_web_sm' is not installed or failed to load. "
            "Relative date extraction will fall back to regex mode. "
            f"Error: {e}"
        )
    yield


app = FastAPI(
    title="MailMind API",
    description="AI-powered enterprise email triage and drafting backend",
    version="2.0.0",
    lifespan=lifespan,
)

FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(email_router)
app.include_router(ai_router)
app.include_router(graph_router)
app.include_router(evaluation_router)
