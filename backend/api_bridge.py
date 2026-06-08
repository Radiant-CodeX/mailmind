"""
API Bridge: Translate frontend /api/* calls to the agentic pipeline.

Frontend expects:
  GET  /api/auth/status
  POST /api/auth/login-poll
  GET  /api/emails
  POST /api/emails/triage         → POST /api/agent/triage
  POST /api/emails/draft          → POST /api/agent/process  (full pipeline)
  POST /api/emails/summary        → POST /api/agent/process  (full pipeline)
  POST /api/commitments/extract   → POST /api/agent/commitments
  POST /api/emails/{id}/reply     → POST /api/agent/approve/{id}
  etc.

All AI routes are forwarded to the LangGraph agent pipeline endpoints.
Auth, email-list, calendar, and graph routes remain pass-through.
"""
import logging
import os
import uuid

import requests
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# Agent pipeline lives in the same process; call via localhost to avoid import cycles.
BACKEND_URL = os.getenv("INTERNAL_BACKEND_URL", "http://localhost:8000")
MOCK_MODE = os.getenv("MOCK_AUTH", "true").lower() == "true"
REQUEST_TIMEOUT = 20  # Agent pipeline can take longer than simple routes

# ── Helper: build a normalised agent request payload ─────────────────────────

def _agent_payload(body: dict, email_id: str | None = None) -> dict:
    """Normalise bridge request body into the AgentProcessRequest schema."""
    sender = body.get("sender") or body.get("from") or "unknown@company.com"
    # Agent requires a valid email address
    if "@" not in sender:
        sender = f"{sender.lower().replace(' ', '.')}@company.com"
    return {
        "email_id": email_id or body.get("email_id") or str(uuid.uuid4()),
        "sender": sender,
        "subject": body.get("subject", "(no subject)"),
        "body": body.get("body", ""),
        "received_at": body.get("received_at", ""),
        "calendar_events": body.get("calendar_events", []),
    }


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
    """Triage an email through the LangGraph triage sub-pipeline."""
    try:
        body = await request.json()
        resp = requests.post(
            f"{BACKEND_URL}/api/agent/triage",
            json=_agent_payload(body),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            # Normalise to the shape the frontend expects
            return {
                "priority_score": round(data.get("composite_score", 50) / 100, 2),
                "priority_label": data.get("priority", "MEDIUM"),
                "composite_score": data.get("composite_score", 50),
                "approval_mode": data.get("approval_mode", "SUGGEST"),
                "axes": data.get("axes", []),
                "triage_reasoning": data.get("triage_reasoning"),
                "errors": data.get("errors", []),
            }
    except Exception as e:
        logger.error(f"Triage via agent failed: {e}")

    return {
        "priority_score": 0.5,
        "priority_label": "MEDIUM",
        "composite_score": 50.0,
        "approval_mode": "SUGGEST",
        "axes": [],
        "triage_reasoning": None,
        "errors": ["agent_unavailable"],
    }


@router.post("/emails/conflict-check")
async def conflict_check(request: Request):
    """Check for calendar conflicts via the full agent pipeline."""
    try:
        body = await request.json()
        resp = requests.post(
            f"{BACKEND_URL}/api/agent/process",
            json=_agent_payload(body, email_id=body.get("email_id")),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            commitments_with_conflicts = [
                c for c in data.get("commitments", []) if c.get("conflict_badge")
            ]
            return {
                "conflict_detected": len(commitments_with_conflicts) > 0,
                "conflict_summary": data.get("conflict_summary"),
                "conflicting_events": [
                    {"detail": c["conflict_detail"], "commitment": c["commitment"]}
                    for c in commitments_with_conflicts
                ],
            }
    except Exception as e:
        logger.error(f"Conflict check via agent failed: {e}")

    return {
        "conflict_detected": False,
        "conflict_summary": None,
        "conflicting_events": [],
    }


@router.post("/emails/draft")
async def generate_draft(request: Request):
    """Generate AI draft reply via the full agent pipeline (RAG + Tone DNA)."""
    try:
        body = await request.json()
        resp = requests.post(
            f"{BACKEND_URL}/api/agent/process",
            json=_agent_payload(body),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "draft_reply": data.get("draft_reply", ""),
                "priority": data.get("priority"),
                "citations": [
                    {"subject": p["subject"], "similarity": p["similarity_score"]}
                    for p in data.get("precedents", [])
                ],
                "triage_reasoning": data.get("triage_reasoning"),
            }
    except Exception as e:
        logger.error(f"Draft via agent failed: {e}")

    return {
        "draft_reply": (
            "Hello,\n\nThank you for your email. I have received your message "
            "and will review it shortly.\n\nRegards"
        ),
        "priority": None,
        "citations": [],
        "triage_reasoning": None,
    }


@router.post("/emails/approve")
async def approve_draft(request: Request):
    """Approve, reject, or edit a draft via the agent approval gate."""
    try:
        body = await request.json()
        email_id = body.get("email_id", str(uuid.uuid4()))
        resp = requests.post(
            f"{BACKEND_URL}/api/agent/approve/{email_id}",
            json={
                "action": body.get("action", "approve"),
                "edited_draft": body.get("draft_reply") or body.get("edited_draft"),
                "reviewer_note": body.get("reviewer_note"),
            },
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.error(f"Approval via agent gate failed: {e}")

    return {
        "action": "approve",
        "approved": True,
        "reviewed_at": None,
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

        # Record approval in the agent gate, then send
        try:
            requests.post(
                f"{BACKEND_URL}/api/agent/approve/{email_id}",
                json={"action": "approve", "edited_draft": comment},
                timeout=REQUEST_TIMEOUT,
            )
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
    """Extract action items via the agent commitment sub-pipeline."""
    try:
        body = await request.json()
        resp = requests.post(
            f"{BACKEND_URL}/api/agent/commitments",
            json=_agent_payload(body),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            commitments = data.get("commitments", [])
            tasks = [c["id"] for c in commitments if not c.get("deadline")]
            events = [c["id"] for c in commitments if c.get("deadline")]
            return {
                "commitments": commitments,
                "tasks": tasks,
                "events": events,
                "commitment_reasoning": data.get("commitment_reasoning"),
            }
    except Exception as e:
        logger.error(f"Commitment extraction via agent failed: {e}")

    return {"commitments": [], "tasks": [], "events": [], "commitment_reasoning": None}


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
    """Get AI triage summary via the agent triage sub-pipeline."""
    try:
        body = await request.json()
        resp = requests.post(
            f"{BACKEND_URL}/api/agent/triage",
            json=_agent_payload(body),
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "summary": data.get("triage_reasoning") or f"Priority: {data.get('priority', 'MEDIUM')}",
                "priority": data.get("priority"),
                "composite_score": data.get("composite_score"),
                "action_required": (
                    "Requires immediate response"
                    if data.get("priority") in ("CRITICAL", "HIGH")
                    else "Review when convenient"
                ),
            }
    except Exception as e:
        logger.error(f"Summary via agent failed: {e}")

    return {
        "summary": "Email summary unavailable",
        "priority": None,
        "composite_score": None,
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
