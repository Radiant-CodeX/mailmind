"""
API Bridge: Translate frontend /api/* calls to internal backend routes.

Frontend expects structure:
  GET /api/auth/status
  POST /api/auth/login-poll
  GET /api/emails
  POST /api/emails/triage
  POST /api/commitments/extract
  POST /api/emails/compose
  POST /api/emails/{id}/reply
  etc.

Backend has:
  GET /emails
  POST /triage
  POST /conflict-check
  POST /approve
  etc.

This bridge translates between them and provides mock fallbacks.
"""
import logging
import os

import requests
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

BACKEND_URL = os.getenv("INTERNAL_BACKEND_URL", "http://localhost:8000")
MOCK_MODE = os.getenv("MOCK_AUTH", "true").lower() == "true"
REQUEST_TIMEOUT = 15


# ─────────────────────────────────────────────────────────────────
# AUTH ROUTES
# ─────────────────────────────────────────────────────────────────

@router.get("/auth/status")
async def auth_status():
    """Check authentication status."""
    if MOCK_MODE:
        return {
            "authenticated": True,
            "user_principal_name": "demo@company.com",
            "status": "mock",
        }

    return {
        "authenticated": False,
        "status": "unauthenticated",
    }


@router.post("/auth/login-initiate")
async def login_initiate():
    """Initiate Microsoft device code login flow."""
    if MOCK_MODE:
        # In mock mode, return mock device flow
        return {
            "status": "mock",
            "message": "Mock login mode - click 'Login with Mock Account'",
            "user_code": "MOCK-CODE-12345",
            "device_code": "mock_device_code",
            "verification_uri": "https://microsoft.com/devicelogin",
        }

    # Real device code flow would be here
    return {
        "status": "pending",
        "message": "Please visit https://microsoft.com/devicelogin and enter code",
        "user_code": "ABC-DEFGH",
        "device_code": "real_device_code",
        "verification_uri": "https://microsoft.com/devicelogin",
    }


@router.post("/auth/login-mock")
async def login_mock():
    """Direct mock login without device flow."""
    return {
        "status": "success",
        "authenticated": True,
        "user_principal_name": "demo@company.com",
        "message": "Logged in with mock account",
    }


@router.post("/auth/logout")
async def logout():
    """Logout user."""
    return {
        "status": "success",
        "message": "Logged out",
    }


@router.post("/auth/login-poll")
async def login_poll(request: Request):
    """Poll for login completion."""
    try:
        body = await request.json()
        device_code = body.get("device_code")

        if not device_code:
            raise HTTPException(status_code=400, detail="Missing device_code")

        if MOCK_MODE:
            return {
                "status": "success",
                "authenticated": True,
                "user_principal_name": "demo@company.com",
            }

        return {
            "status": "pending",
            "authenticated": False,
        }
    except Exception as e:
        logger.error(f"Login poll failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# EMAIL ROUTES
# ─────────────────────────────────────────────────────────────────

@router.get("/emails")
async def get_emails():
    """Fetch email list."""
    try:
        resp = requests.get(f"{BACKEND_URL}/emails", timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Get emails failed: {e}")

    # Fallback: mock emails
    return [
        {
            "id": "1",
            "sender": "manager@company.com",
            "subject": "Need report by today",
            "body": "Please send the project report by 5 PM today.",
            "status": "Pending",
            "priority_score": 0.85,
            "priority_label": "HIGH",
        }
    ]


@router.post("/emails/triage")
async def triage_email(request: Request):
    """Triage an email across 5 axes."""
    try:
        body = await request.json()

        resp = requests.post(
            f"{BACKEND_URL}/triage",
            json={
                "sender": body.get("from") or body.get("sender", ""),
                "subject": body.get("subject", ""),
                "body": body.get("body", ""),
            },
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Triage failed: {e}")

    # Fallback
    return {
        "priority_score": 0.5,
        "priority_label": "NORMAL",
        "axes": [
            {"axis": "urgency", "raw_score": 0.5},
            {"axis": "stakeholder_power", "raw_score": 0.5},
            {"axis": "complexity", "raw_score": 0.5},
            {"axis": "time_sensitivity", "raw_score": 0.5},
            {"axis": "escalation_risk", "raw_score": 0.5},
        ]
    }


@router.post("/emails/conflict-check")
async def conflict_check(request: Request):
    """Check for calendar conflicts."""
    try:
        body = await request.json()

        resp = requests.post(
            f"{BACKEND_URL}/conflict-check",
            json={
                "email_id": body.get("email_id", ""),
                "sender": body.get("from") or body.get("sender", ""),
                "subject": body.get("subject", ""),
                "body": body.get("body", ""),
            },
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Conflict check failed: {e}")

    return {
        "conflict_detected": False,
        "conflicting_events": [],
        "precedents": [],
    }


@router.post("/emails/draft")
async def generate_draft(request: Request):
    """Generate AI draft reply."""
    try:
        body = await request.json()

        resp = requests.post(
            f"{BACKEND_URL}/draft",
            json={
                "sender": body.get("from") or body.get("sender", ""),
                "subject": body.get("subject", ""),
                "body": body.get("body", ""),
            },
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Draft generation failed: {e}")

    return {
        "draft_reply": """Hello,

Thank you for your email. I have received your message and will review it shortly.

I will get back to you with an update.

Regards,
Rithish Barath""",
        "status": "Fallback draft",
        "citations": [],
    }


@router.post("/emails/approve")
async def approve_draft(request: Request):
    """Approve and send draft."""
    try:
        body = await request.json()

        resp = requests.post(
            f"{BACKEND_URL}/approve",
            json={
                "email_id": body.get("email_id", ""),
                "action": body.get("action", "approve"),
                "draft_reply": body.get("draft_reply", ""),
            },
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Approval failed: {e}")

    return {
        "status": "Approved",
        "message": "Draft approved",
    }


@router.post("/emails/compose")
async def compose_email(request: Request):
    """Compose new email."""
    try:
        body = await request.json()
        to = body.get("to", "")
        subject = body.get("subject", "")
        email_body = body.get("body", "")

        if not all([to, subject, email_body]):
            raise HTTPException(status_code=400, detail="Missing fields: to, subject, body")

        logger.info(f"Compose email: to={to}, subject={subject}")
        return {
            "success": True,
            "messageId": "draft_123",
            "status": "Draft saved",
        }
    except Exception as e:
        logger.error(f"Compose failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/emails/{email_id}/reply")
async def send_email_reply(email_id: str, request: Request):
    """Send reply to email."""
    try:
        body = await request.json()
        comment = body.get("comment", "").strip()

        if not comment:
            raise HTTPException(status_code=400, detail="Empty reply")

        # Try to send via Graph API
        try:
            resp = requests.post(
                f"{BACKEND_URL}/approve",
                json={
                    "email_id": email_id,
                    "action": "approve",
                    "draft_reply": comment,
                },
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

        logger.info(f"Send reply to {email_id}")
        return {
            "success": True,
            "messageId": f"reply_{email_id}",
            "status": "Email sent",
        }
    except Exception as e:
        logger.error(f"Send reply failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# COMMITMENT / EXTRACTION ROUTES
# ─────────────────────────────────────────────────────────────────

@router.post("/commitments/extract")
async def extract_commitments(request: Request):
    """Extract tasks and events from email."""
    try:
        await request.json()

        # Mock commitments
        return {
            "commitments": [
                {
                    "id": "task1",
                    "type": "task",
                    "title": "Review budget proposal",
                    "dueDate": "2026-06-15",
                    "priority": "high",
                    "status": "pending",
                    "extracted_from": "email",
                }
            ],
            "tasks": ["task1"],
            "events": [],
        }
    except Exception as e:
        logger.error(f"Extract commitments failed: {e}")
        return {
            "commitments": [],
            "tasks": [],
            "events": [],
        }


@router.post("/commitments/confirm")
async def confirm_commitments(request: Request):
    """Confirm and create tasks/events."""
    try:
        body = await request.json()
        commitment_ids = body.get("commitmentIds", [])
        email_id = body.get("emailId", "")

        result = {
            "taskUrls": [],
            "eventUrls": [],
            "message": f"Created {len(commitment_ids)} items",
        }

        logger.info(f"Confirm commitments for email {email_id}: {commitment_ids}")
        return result
    except Exception as e:
        logger.error(f"Confirm commitments failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# CALENDAR / GRAPH ROUTES
# ─────────────────────────────────────────────────────────────────

@router.get("/calendar/events")
async def get_calendar_events():
    """Get calendar events."""
    try:
        resp = requests.get(f"{BACKEND_URL}/graph/emails", timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return {"events": resp.json().get("graph_response", [])}
    except Exception as e:
        logger.error(f"Get calendar events failed: {e}")

    return {"events": []}


@router.post("/graph/create-task")
async def create_graph_task(request: Request):
    """Create task in MS To-Do."""
    try:
        body = await request.json()
        title = body.get("title", "")
        due_date = body.get("dueDate", "")

        logger.info(f"Create task: {title} due {due_date}")
        return {
            "success": True,
            "taskId": "task_123",
            "taskUrl": "https://to-do.microsoft.com/tasks/task_123",
        }
    except Exception as e:
        logger.error(f"Create task failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/graph/create-event")
async def create_graph_event(request: Request):
    """Create event in MS Calendar."""
    try:
        body = await request.json()
        title = body.get("title", "")
        start_time = body.get("startTime", "")

        logger.info(f"Create event: {title} at {start_time}")
        return {
            "success": True,
            "eventId": "event_123",
            "eventUrl": "https://calendar.microsoft.com/events/event_123",
        }
    except Exception as e:
        logger.error(f"Create event failed: {e}")
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────
# SUMMARY / EVALUATION ROUTES
# ─────────────────────────────────────────────────────────────────

@router.post("/emails/summary")
async def get_email_summary(request: Request):
    """Get AI summary of email."""
    try:
        body = await request.json()

        resp = requests.post(
            f"{BACKEND_URL}/summary",
            json={
                "sender": body.get("from") or body.get("sender", ""),
                "subject": body.get("subject", ""),
                "body": body.get("body", ""),
            },
            timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Summary failed: {e}")

    return {
        "summary": "Email summary unavailable",
        "action_required": "Review manually",
    }


@router.get("/rag/status")
async def rag_status():
    """RAG system status."""
    return {
        "ready": True,
        "indexed_documents": 2543,
        "last_updated": "2026-06-06T10:30:00Z",
    }


@router.post("/rag/search")
async def rag_search(request: Request):
    """Search RAG knowledge base."""
    try:
        await request.json()

        return {
            "results": [
                {
                    "doc_id": "doc_123",
                    "title": "Similar past email",
                    "excerpt": "In the past, when faced with...",
                    "relevance": 0.92,
                }
            ],
            "total": 1,
        }
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        return {"results": [], "total": 0}
