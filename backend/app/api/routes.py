import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
    ComposeRequest,
    DraftRequest,
    DraftResponse,
    EmailPayload,
    IngestResponse,
    PrecedentItem,
    RAGQuery,
    ReplyRequest,
    TriageResult,
)
from app.queue.queue import QueueMessage
from app.services.alert_scheduler import alert_queue
from app.services.classification import ClassificationService
from app.services.commitments import CommitmentService
from app.services.draft_service import DraftService
from app.services.graph import GraphClient
from app.services.rag import PrecedentInjector, RAGIndexFactory, RetrievalService, mask_pii
from app.services.scorers import (
    ActionTypeScorer,
    CompositeAggregator,
    DeadlineScorer,
    SenderAuthorityScorer,
    SentimentScorer,
    ThreadAgeDecayScorer,
)
from app.services.tone_dna import ToneDNAService
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
    if not settings.use_mock_graph and settings.approval_token == "secret-approval-token":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default approval token cannot be used in Live Mode. Please configure APPROVAL_TOKEN in settings."
        )
    if token != settings.approval_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid approval token")


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    """Health check endpoint reporting current queue depth."""
    queue = request.app.state.email_queue
    return {"status": "ok", "queue_size": queue.size()}


@router.get("/emails", response_model=list[EmailPayload])
def get_emails(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recent emails/messages from the Outlook Inbox."""
    client = GraphClient()
    return client.get_inbox_emails(limit=limit)


@router.get("/emails/sent", response_model=list[EmailPayload])
def get_sent_emails(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recent sent emails/messages from the Outlook Sent Items folder."""
    client = GraphClient()
    raw_emails = client.fetch_sent_emails(days=30)
    
    formatted = []
    for msg in raw_emails[:limit]:
        sender_addr = "unknown@example.com"
        from_obj = msg.get("from") or msg.get("sender")
        if from_obj and "emailAddress" in from_obj:
            sender_addr = from_obj["emailAddress"].get("address", "unknown@example.com")
        
        body_content = ""
        body_obj = msg.get("body")
        if body_obj:
            body_content = body_obj.get("content", "")
        else:
            body_content = msg.get("bodyPreview", "")
            
        formatted.append({
            "email_id": msg.get("id") or msg.get("email_id") or "",
            "sender": sender_addr,
            "subject": msg.get("subject", ""),
            "body": body_content,
            "received_at": msg.get("sentDateTime") or msg.get("received_at") or "",
        })
    return formatted


@router.post("/emails/{email_id}/reply")
def send_email_reply(email_id: str, payload: ReplyRequest) -> dict[str, Any]:
    """Send a reply to the specified email via Microsoft Graph."""
    client = GraphClient()
    client.send_reply(email_id, payload.comment)
    return {"success": True}


@router.post("/emails/compose")
def compose_email(payload: ComposeRequest) -> dict[str, Any]:
    """Compose and send a new email via Microsoft Graph."""
    client = GraphClient()
    client.send_new_email(
        to=payload.to,
        subject=payload.subject,
        body=payload.body,
        cc=payload.cc,
        bcc=payload.bcc
    )
    return {"success": True}




# Global dictionary to temporarily store active device flows
active_device_flows: dict[str, dict[str, Any]] = {}


@router.post("/auth/login-initiate")
def login_initiate() -> dict[str, Any]:
    """Initiate MSAL device code login flow."""
    client = GraphClient()
    if client.use_mock:
        return {
            "status": "mock",
            "message": "App is running in MOCK mode. Login not required."
        }
    try:
        flow = client.initiate_user_login()
        if not flow or "device_code" not in flow:
            raise HTTPException(status_code=500, detail="Failed to initiate device flow")
        
        # Save flow in global dict keyed by device_code
        active_device_flows[flow["device_code"]] = flow
        return {
            "status": "pending",
            "device_code": flow["device_code"],
            "user_code": flow["user_code"],
            "verification_uri": flow["verification_uri"],
            "message": flow["message"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/login-poll")
def login_poll(payload: dict[str, str]) -> dict[str, Any]:
    """Poll MSAL to complete user authentication."""
    device_code = payload.get("device_code")
    if not device_code:
        raise HTTPException(status_code=400, detail="Missing device_code")
    
    flow = active_device_flows.get(device_code)
    if not flow:
        raise HTTPException(status_code=404, detail="Active login session not found")
        
    client = GraphClient()
    try:
        result = client.complete_user_login(flow)
        if not result:
            return {"status": "pending"}
        if "error" in result:
            error_code = result.get("error")
            if error_code == "authorization_pending":
                return {"status": "pending"}
            raise HTTPException(status_code=400, detail=result.get("error_description", error_code))
            
        # Success! Save token details in cache
        import time

        from app.services.graph import _user_token_cache
        _user_token_cache["access_token"] = result.get("access_token")
        _user_token_cache["expires_at"] = time.time() + int(result.get("expires_in", 3600))
        
        # Find logged-in user UPN or mail
        id_token_claims = result.get("id_token_claims", {})
        upn = id_token_claims.get("preferred_username") or id_token_claims.get("upn")
        _user_token_cache["user_principal_name"] = upn
        
        # Clean up flow
        active_device_flows.pop(device_code, None)
        return {
            "status": "success",
            "user_principal_name": upn
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


# Track mock logged-out state globally
_mock_logged_out = True


@router.post("/auth/login-mock")
def login_mock() -> dict[str, Any]:
    """Log in dynamically in mock/demo mode."""
    global _mock_logged_out
    _mock_logged_out = False
    return {
        "status": "mock",
        "authenticated": True,
        "user_principal_name": "mock.user@example.com"
    }


@router.get("/auth/status")
def auth_status() -> dict[str, Any]:
    """Check the current login status and user principal name."""
    from app.services.graph import _user_token_cache
    client = GraphClient()
    
    global _mock_logged_out
    if client.use_mock:
        if _mock_logged_out:
            return {
                "status": "mock_unauthenticated",
                "authenticated": False,
                "user_principal_name": None
            }
        return {
            "status": "mock",
            "authenticated": True,
            "user_principal_name": "mock.user@example.com"
        }
        
    import time
    now = time.time()
    if _user_token_cache["access_token"] and now < (_user_token_cache["expires_at"] - 60):
        return {
            "status": "authenticated",
            "authenticated": True,
            "user_principal_name": _user_token_cache["user_principal_name"] or "authenticated.user@outlook.com"
        }
    return {
        "status": "unauthenticated",
        "authenticated": False,
        "user_principal_name": None
    }


@router.post("/auth/logout")
def auth_logout() -> dict[str, Any]:
    """Log out the current user session by clearing token cache."""
    global _mock_logged_out
    _mock_logged_out = True
    
    from app.services.graph import _user_token_cache
    _user_token_cache["access_token"] = None
    _user_token_cache["expires_at"] = 0.0
    _user_token_cache["user_principal_name"] = None
    return {"status": "logged_out"}


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
    import hashlib

    from app.services.cache import classification_cache
    key = f"classify:{hashlib.sha256(payload.email_text.strip().lower().encode('utf-8')).hexdigest()}"
    cached = classification_cache.get(key)
    if cached is not None:
        return cached

    classifier = ClassificationService()
    masked = mask_pii(payload.email_text)
    result = classifier.classify(masked)
    classification_cache.set(key, result)
    return result


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
    import hashlib

    from app.services.cache import precedents_cache
    key = f"retrieve:{hashlib.sha256(query.email_text.strip().lower().encode('utf-8')).hexdigest()}"
    cached = precedents_cache.get(key)
    if cached is not None:
        return cached

    index = RAGIndexFactory()()
    masked = mask_pii(query.email_text)
    results = RetrievalService(index).retrieve(masked)
    precedents_cache.set(key, results)
    return results


@router.post("/rag/inject")
def rag_inject(query: RAGQuery) -> dict[str, Any]:
    """Create a prompt that injects precedent email context for response drafting."""
    import hashlib

    from app.services.cache import precedents_cache
    key = f"inject:{hashlib.sha256(query.email_text.strip().lower().encode('utf-8')).hexdigest()}"
    cached = precedents_cache.get(key)
    if cached is not None:
        return cached

    index = RAGIndexFactory()()
    masked = mask_pii(query.email_text)
    precedents = RetrievalService(index).retrieve(masked)
    result = PrecedentInjector.inject(masked, precedents)
    precedents_cache.set(key, result)
    return result


@router.post("/rag/draft", response_model=DraftResponse)
def generate_draft(payload: DraftRequest) -> DraftResponse:
    """Generate an email response draft using a selected style (standard, formal, or indepth) and context precedents."""
    import hashlib

    from app.services.cache import precedents_cache
    key = f"draft:{payload.style}:{hashlib.sha256(payload.email_text.strip().lower().encode('utf-8')).hexdigest()}"
    cached = precedents_cache.get(key)
    if cached is not None:
        return cached

    service = DraftService()
    draft, citations = service.generate_draft(
        email_text=payload.email_text,
        style=payload.style,
        sender=payload.sender,
        subject=payload.subject
    )
    result = DraftResponse(draft=draft, precedent_citations=citations)
    precedents_cache.set(key, result)
    return result



@router.post("/commitments/extract", response_model=CommitmentExtractionResponse)
def extract_commitments(payload: CommitmentExtractionRequest) -> CommitmentExtractionResponse:
    """Extract commitment candidates from masked email text."""
    service = CommitmentService(GraphClient())
    commitments = service.extract(payload.masked_email_text, payload.thread_summary or "", payload.email_id)
    return CommitmentExtractionResponse(commitments=commitments)


@router.post("/commitments/confirm", response_model=CommitmentConfirmResponse)
def confirm_commitments(payload: CommitmentApprover, x_approval_token: str | None = Header(None)) -> CommitmentConfirmResponse:
    """Confirm approved commitments and create tasks/calendar events."""
    _validate_approval_token(x_approval_token)
    service = CommitmentService(GraphClient())
    result = service.confirm(payload.email_id, payload.commitments)
    return CommitmentConfirmResponse(**result)


@router.get("/evaluate")
def evaluate_model():
    """Evaluate model performance against a golden dataset."""
    dataset_path = Path("golden_dataset.json")
    if not dataset_path.exists():
        dataset_path = Path("backend/golden_dataset.json")
        if not dataset_path.exists():
            return {"error": "golden_dataset.json not found"}

    with open(dataset_path, "r", encoding="utf-8") as file:
        dataset = json.load(file)

    results = []
    correct = 0
    classifier = ClassificationService()

    for item in dataset:
        email_text = f"Subject: {item['subject']}\nSender: {item['sender']}\nBody: {item['body']}"
        prediction = classifier.classify(email_text)
        
        # Map output to dataset priority labels
        pred_priority = prediction.priority
        if pred_priority == "CRITICAL":
            predicted = "Critical"
        elif pred_priority == "HIGH":
            predicted = "High"
        else:
            predicted = "Normal"

        expected = item["expected_priority"]
        is_correct = expected == predicted
        if is_correct:
            correct += 1

        results.append({
            "subject": item["subject"],
            "expected": expected,
            "predicted": predicted,
            "is_correct": is_correct,
        })

    accuracy = round((correct / len(dataset)) * 100, 2)
    return {
        "accuracy": accuracy,
        "total_samples": len(dataset),
        "correct_predictions": correct,
        "results": results,
    }


@router.post("/triage", response_model=TriageResult)
def triage_email(payload: EmailPayload) -> TriageResult:
    """Calculate the five-axis triage score for an email."""
    from app.services.cache import triage_cache
    key = f"id:{payload.email_id}"
    cached = triage_cache.get(key)
    if cached is not None:
        return cached

    deadline_scorer = DeadlineScorer()
    authority_scorer = SenderAuthorityScorer(GraphClient())
    sentiment_scorer = SentimentScorer()
    decay_scorer = ThreadAgeDecayScorer()
    action_scorer = ActionTypeScorer()
    aggregator = CompositeAggregator()

    body = payload.body
    # Calculate each axis score
    deadline_score = deadline_scorer.score(body, payload.received_at)
    authority_score = authority_scorer.score(str(payload.sender))
    sentiment_score = sentiment_scorer.score(body)
    decay_score = decay_scorer.score(payload.received_at)
    action_score = action_scorer.score(body)

    axes = [deadline_score, authority_score, sentiment_score, decay_score, action_score]
    result = aggregator.aggregate(axes)
    triage_cache.set(key, result)
    return result

# ── Tone DNA routes ───────────────────────────────────────────────────────────


@router.post("/tone-dna/build")
def build_tone_dna() -> dict:
    """DNA-01: Trigger Tone DNA ingestion from sent mail."""
    svc = ToneDNAService(GraphClient())
    profile = svc.ingest_and_build()
    return {
        "status": "built",
        "sample_size": profile.get("sample_size", 0),
        "formality_score": profile["features"]["formality_score"],
        "generated_at": profile["generated_at"],
    }

@router.get("/tone-dna/profile")
def get_tone_dna_profile() -> dict:
    """Return current Tone DNA profile (or 404 if not yet built)."""
    from fastapi import HTTPException

    from app.services.tone_dna import load_profile
    profile = load_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="Tone DNA profile not built yet. POST /api/tone-dna/build first.")
    return profile


# ── Alert queue route ─────────────────────────────────────────────────────────


@router.get("/alerts")
def get_alerts() -> list:
    """CMT-06/07: Return queued T-24h and chase draft alerts."""
    return alert_queue

@router.post("/alerts/{idx}/resolve")
def resolve_alert(idx: int) -> dict:
    if idx >= len(alert_queue):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    alert_queue[idx]["resolved"] = True
    return {"status": "resolved"}
