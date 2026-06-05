import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import FRONTEND_ORIGIN
from routes.email_routes import router as email_router
from routes.ai_routes import router as ai_router
from routes.graph_routes import router as graph_router
from routes.evaluation_routes import router as evaluation_router
from app.api.agent_routes import router as agent_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

trace.set_tracer_provider(TracerProvider())

app = FastAPI(
    title="MailMind API",
    description="AI-powered enterprise email triage and drafting backend",
    version="1.0.0",
)

FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(email_router)
app.include_router(ai_router)
app.include_router(graph_router)
app.include_router(evaluation_router)
app.include_router(agent_router)