import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config.settings import settings
from app.api.routes import router
from app.queue.queue import EmailQueue


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

app.include_router(router)
