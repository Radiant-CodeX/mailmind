from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from app.config.settings import settings
from app.models.schemas import (
    CalendarEvent,
    ClassificationResult,
    CommitmentApprover,
    CommitmentConfirmResponse,
    CommitmentExtractionRequest,
    CommitmentExtractionResponse,
    EmailPayload,
    IngestResponse,
    PrecedentItem,
    RAGQuery,
)
from app.queue.queue import QueueMessage
from app.services.classification import ClassificationService
from app.services.commitments import CommitmentService
from app.services.graph import GraphClient
from app.services.rag import PrecedentInjector, RAGIndexFactory, RetrievalService
from app.services.tools import CalendarFetcher, ThreadFetcher

router = APIRouter(prefix="/api")

# In-memory rate limit store keyed by client IP address.
rate_limit_store: dict[str, list[datetime]] = {}


def _rate_limit(request: Request) -> None:
    """Simple per-IP rate limiting for the ingest endpoint."""
    client_ip = request.client.host if request.client else "unknown"
    window = timedelta(minutes=1)
    now = datetime.now(tz=timezone.utc)
    entries = rate_limit_store.setdefault(client_ip, [])
    # Remove old timestamps outside the current window.
    entries[:] = [timestamp for timestamp in entries if now - timestamp < window]
    if len(entries) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    entries.append(now)


def _validate_approval_token(token: str | None) -> None:
    """Ensure the approval token matches the configured secret."""
    if token != settings.approval_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid approval token")


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    """Health check endpoint reporting current queue depth."""
    queue = request.app.state.email_queue
    return {"status": "ok", "queue_size": queue.size()}


@router.get("/webhook", response_class=PlainTextResponse)
def graph_webhook_validation(validationToken: str | None = None):
    """Validate Microsoft Graph webhook subscriptions."""
    if not validationToken:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing validationToken")
    return PlainTextResponse(validationToken)


@router.post("/webhook")
async def graph_webhook_receive(request: Request) -> dict[str, Any]:
    """Receive Graph webhook notifications and enqueue email preview payloads."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    queue = request.app.state.email_queue
    notifications = body.get("value", [])
    if not isinstance(notifications, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid notification format")

    for notification in notifications:
        data = notification.get("resourceData", {})
        if not data:
            continue
        message = QueueMessage(
            email_id=str(data.get("id", "")),
            sender=str(data.get("sender", "unknown@example.com")),
            subject=str(data.get("subject", "Webhook notification")),
            body=str(data.get("bodyPreview", "")),
            received_at=data.get("receivedDateTime", datetime.now(tz=timezone.utc)),
        )
        queue.enqueue(message)

    return {"status": "received", "count": len(notifications)}


@router.post("/ingest", response_model=IngestResponse)
def ingest_email(payload: EmailPayload, request: Request, _: None = Depends(_rate_limit)) -> IngestResponse:
    """Ingest a validated email payload and place it onto the processing queue."""
    message = QueueMessage(
        email_id=payload.email_id,
        sender=str(payload.sender),
        subject=payload.subject,
        body=payload.body,
        received_at=payload.received_at,
    )
    request.app.state.email_queue.enqueue(message)
    return IngestResponse()


@router.post("/classify", response_model=ClassificationResult)
def classify_text(payload: RAGQuery) -> ClassificationResult:
    """Classify email text to assign priority, category, and confidence."""
    classifier = ClassificationService()
    return classifier.classify(payload.email_text)


@router.get("/thread/{thread_id}")
def fetch_thread(thread_id: str) -> list[dict[str, Any]]:
    """Fetch recent messages for a given thread from the Graph stub client."""
    fetcher = ThreadFetcher(GraphClient())
    return fetcher.fetch(thread_id)


@router.get("/calendar", response_model=list[CalendarEvent])
def fetch_calendar(days: int = 3) -> list[CalendarEvent]:
    """Fetch upcoming calendar events from the Graph stub client."""
    fetcher = CalendarFetcher(GraphClient())
    return fetcher.fetch_next_events(days=days)


@router.post("/rag/retrieve", response_model=list[PrecedentItem])
def rag_retrieve(query: RAGQuery) -> list[PrecedentItem]:
    """Retrieve precedent emails similar to the provided email text."""
    index = RAGIndexFactory()()
    results = RetrievalService(index).retrieve(query.email_text)
    return results


@router.post("/rag/inject")
def rag_inject(query: RAGQuery) -> dict[str, Any]:
    """Create a prompt that injects precedent email context for response drafting."""
    index = RAGIndexFactory()()
    precedents = RetrievalService(index).retrieve(query.email_text)
    return PrecedentInjector.inject(query.email_text, precedents)


@router.post("/commitments/extract", response_model=CommitmentExtractionResponse)
def extract_commitments(payload: CommitmentExtractionRequest) -> CommitmentExtractionResponse:
    """Extract commitment candidates from masked email text."""
    service = CommitmentService(GraphClient())
    commitments = service.extract(payload.masked_email_text, payload.thread_summary or "")
    return CommitmentExtractionResponse(commitments=commitments)


@router.post("/commitments/confirm", response_model=CommitmentConfirmResponse)
def confirm_commitments(payload: CommitmentApprover, x_approval_token: str | None = Header(None)) -> CommitmentConfirmResponse:
    """Confirm approved commitments and create tasks/calendar events."""
    _validate_approval_token(x_approval_token)
    service = CommitmentService(GraphClient())
    result = service.confirm(payload.email_id, payload.commitments)
    return CommitmentConfirmResponse(**result)
