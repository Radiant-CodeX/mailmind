import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

logger = logging.getLogger(__name__)
from fastapi.responses import HTMLResponse, PlainTextResponse

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
    EmailPage,
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
from app.services.mail_provider import (
    active_email,
    active_provider,
    clear_provider,
    get_mail_client,
    is_active,
    set_provider,
)
from app.services.rag import PrecedentInjector, RAGIndexFactory, RetrievalService, mask_pii
from app.services.scorers import (
    ActionTypeScorer,
    CompositeAggregator,
    DeadlineScorer,
    SenderAuthorityScorer,
    SentimentScorer,
    ThreadAgeDecayScorer,
)
from app.services.tone_dna import ToneDNAService, load_profile as _load_tone_profile
from app.services.tools import CalendarFetcher, ThreadFetcher

router = APIRouter(prefix="/api")

# In-memory rate limit store keyed by client IP address.
rate_limit_store: dict[str, list[datetime]] = {}


from app.api.deps import get_current_user

# Cache of evaluation predictions keyed by email text — the golden dataset is
# fixed, so after the first run every re-run is instant.
_eval_prediction_cache: dict[str, str] = {}


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
    """Ensure the approval token matches the configured secret.

    In mock/demo mode the approval token is not enforced — the frontend and
    backend may run with different defaults, and there is no real action being
    authorised, so requiring a matching token only blocks the demo flow
    (e.g. confirming a commitment to the calendar). Live mode still enforces it.
    """
    if settings.use_mock_graph:
        return

    if settings.approval_token == "secret-approval-token":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default approval token cannot be used in Live Mode. Please configure APPROVAL_TOKEN in settings."
        )
    if token != settings.approval_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid approval token")


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    """Liveness probe — process is up and serving."""
    queue = request.app.state.email_queue
    return {
        "status": "ok",
        "version": "2.0.0",
        "queue_size": queue.size(),
        "mode": "mock" if settings.use_mock_graph else "live",
    }


@router.get("/ready")
def ready() -> dict[str, Any]:
    """Readiness probe — reports whether external dependencies are configured.

    Returns 200 with per-dependency booleans. In live mode, missing Graph or
    OpenAI configuration is surfaced so orchestrators can gate traffic.
    """
    graph_ready = settings.use_mock_graph or bool(
        settings.azure_client_id and settings.azure_tenant_id
    )
    llm_ready = bool(settings.azure_openai_api_key and settings.azure_openai_base_endpoint) or bool(
        settings.openai_api_key
    )
    checks = {
        "graph": graph_ready,
        "llm": llm_ready,
    }
    overall = all(checks.values()) if not settings.use_mock_graph else True
    return {"ready": overall, "checks": checks, "mode": "mock" if settings.use_mock_graph else "live"}


@router.get("/mailbox", response_model=EmailPage)
def get_mailbox(
    folder: str = "inbox", limit: int = 50, page_token: str | None = None, q: str | None = None,
    _user: str = Depends(get_current_user),
) -> dict[str, Any]:
    """Paginated listing for any folder, with optional server-side search."""
    client = get_mail_client()
    try:
        return client.list_emails(folder=folder, limit=limit, page_token=page_token, query=q)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to list {folder}: {str(e)}")


@router.get("/inbox/poll")
def poll_new_email(_user: str = Depends(get_current_user)) -> dict[str, Any]:
    """
    Lightweight new-email check for both Microsoft and Google accounts.

    Fetches only the single most recent email and returns its id + received_at.
    The frontend compares this id against what it currently shows — if different,
    a new email has arrived and the inbox should refresh.

    Cost: 1 Graph/Gmail API call, no LLM, no DB write.
    """
    try:
        client = get_mail_client()
        # Fetch only 1 email — just the header fields, no body needed
        page = client.list_emails(folder="inbox", limit=1)
        emails = page.get("emails") or []
        if not emails:
            return {"has_new": False, "latest_id": None, "received_at": None}
        latest = emails[0]
        return {
            "has_new": True,
            "latest_id": latest.get("email_id") or latest.get("id"),
            "received_at": latest.get("received_at"),
            "subject": latest.get("subject", ""),
        }
    except Exception as e:
        logger.warning("[poll] New email check failed: %s", e)
        return {"has_new": False, "latest_id": None, "error": str(e)}


@router.get("/emails/{email_id}/attachments/{attachment_id}")
def download_attachment(email_id: str, attachment_id: str, filename: str = "attachment",
                        _user: str = Depends(get_current_user)):
    """Stream an email attachment for download (Gmail or Microsoft Graph)."""
    import base64
    from fastapi.responses import Response

    client = get_mail_client()
    if not hasattr(client, "get_attachment"):
        raise HTTPException(status_code=501, detail="Attachments not supported for this provider")

    try:
        att = client.get_attachment(email_id, attachment_id)
        if not att:
            raise HTTPException(status_code=404, detail="Attachment not found")
        # Gmail returns base64url-encoded data
        data_b64 = att.get("data") or ""
        raw = base64.urlsafe_b64decode(data_b64 + "=" * (-len(data_b64) % 4))
        return Response(
            content=raw,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("[attachment] Download failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch attachment: {str(e)}")


@router.get("/emails", response_model=list[EmailPayload])
def get_emails(limit: int = 10, _user: str = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Fetch recent inbox messages from the active provider (Outlook or Gmail)."""
    client = get_mail_client()
    return client.get_inbox_emails(limit=limit)


@router.get("/emails/sent", response_model=list[EmailPayload])
def get_sent_emails(limit: int = 10, _user: str = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Fetch recent sent messages from the active provider (Outlook or Gmail)."""
    client = get_mail_client()
    raw_emails = client.fetch_sent_emails(days=30)

    formatted = []
    for msg in raw_emails[:limit]:
        sender_addr = "unknown@example.com"
        from_obj = msg.get("from") or msg.get("sender")
        if isinstance(from_obj, dict) and "emailAddress" in from_obj:
            sender_addr = from_obj["emailAddress"].get("address", "unknown@example.com")
        elif isinstance(from_obj, str) and from_obj:
            sender_addr = from_obj

        # Body may be a Graph dict ({"content": ...}) in live mode or a plain
        # string in mock mode — handle both.
        body_obj = msg.get("body")
        if isinstance(body_obj, dict):
            body_content = body_obj.get("content", "")
        elif isinstance(body_obj, str):
            body_content = body_obj
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


@router.get("/emails/drafts", response_model=list[EmailPayload])
def get_draft_emails(limit: int = 10, _user: str = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Fetch emails from the Drafts folder."""
    client = get_mail_client()
    return client.get_draft_emails(limit=limit)


@router.get("/emails/spam", response_model=list[EmailPayload])
def get_spam_emails(limit: int = 10, _user: str = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Fetch emails from the Junk/Spam folder."""
    client = get_mail_client()
    return client.get_spam_emails(limit=limit)


@router.get("/emails/trash", response_model=list[EmailPayload])
def get_trash_emails(limit: int = 10, _user: str = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Fetch emails from the Deleted Items folder."""
    client = get_mail_client()
    return client.get_trash_emails(limit=limit)


@router.post("/emails/{email_id}/reply")
def send_email_reply(email_id: str, payload: ReplyRequest, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Send a reply to the specified email via the active provider."""
    client = get_mail_client()
    try:
        client.send_reply(email_id, payload.comment)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send reply: {str(e)}")


@router.post("/emails/{email_id}/read")
def set_read_status(email_id: str, payload: dict[str, Any] | None = None, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Mark an email read or unread (default: read)."""
    read = True if payload is None else bool(payload.get("read", True))
    try:
        get_mail_client().mark_read(email_id, read)
        return {"success": True, "is_read": read}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update read status: {str(e)}")


@router.post("/emails/{email_id}/archive")
def archive_email(email_id: str, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Archive an email (out of Inbox, not deleted)."""
    try:
        get_mail_client().archive(email_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to archive: {str(e)}")


@router.post("/emails/{email_id}/spam")
def report_spam(email_id: str, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Report an email as spam (move to Junk/Spam)."""
    try:
        get_mail_client().report_spam(email_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to report spam: {str(e)}")


@router.post("/emails/{email_id}/forward")
def forward_email(email_id: str, payload: dict[str, str], _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Forward an email to another recipient."""
    to = (payload or {}).get("to", "").strip()
    if not to:
        raise HTTPException(status_code=400, detail="'to' recipient is required")
    try:
        get_mail_client().forward_email(email_id, to, (payload or {}).get("comment", ""))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to forward: {str(e)}")


@router.post("/emails/{email_id}/reply-all")
def reply_all_email(email_id: str, payload: ReplyRequest, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Reply to everyone on an email thread."""
    try:
        get_mail_client().reply_all(email_id, payload.comment)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to reply all: {str(e)}")


@router.post("/emails/{email_id}/restore")
def restore_email_from_trash(email_id: str, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Restore the specified email from Trash back to Inbox."""
    client = get_mail_client()
    try:
        client.restore_from_trash(email_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to restore email: {str(e)}")


@router.post("/emails/{email_id}/trash")
def move_email_to_trash(email_id: str, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Move the specified email to the Deleted Items (Trash) folder."""
    client = get_mail_client()
    try:
        client.move_to_trash(email_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to move email to trash: {str(e)}")


@router.post("/emails/compose")
def compose_email(payload: ComposeRequest, _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Compose and send a new email via the active provider."""
    client = get_mail_client()
    try:
        client.send_new_email(
            to=payload.to,
            subject=payload.subject,
            body=payload.body,
            cc=payload.cc,
            bcc=payload.bcc
        )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to compose email: {str(e)}")




# ── Microsoft Teams ───────────────────────────────────────────────────────────


@router.get("/teams")
def list_teams() -> list[dict[str, Any]]:
    """List the Teams the signed-in user belongs to."""
    return GraphClient().list_teams()


@router.post("/teams/message")
def post_teams_message(payload: dict[str, str]) -> dict[str, Any]:
    """Post a message to a Teams channel."""
    team_id = payload.get("team_id")
    channel_id = payload.get("channel_id")
    message = payload.get("message", "")
    if not team_id or not channel_id:
        raise HTTPException(status_code=400, detail="team_id and channel_id are required")
    try:
        result = GraphClient().post_teams_message(team_id, channel_id, message)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to post Teams message: {str(e)}")


@router.post("/teams/meeting")
def create_teams_meeting(payload: dict[str, str]) -> dict[str, Any]:
    """Create a Teams online meeting and return its join URL."""
    subject = payload.get("subject", "MailMind Meeting")
    try:
        result = GraphClient().create_online_meeting(subject, payload.get("start"), payload.get("end"))
        return {"success": True, "join_url": result.get("joinUrl"), "meeting": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create meeting: {str(e)}")


@router.post("/auth/login-initiate")
def login_initiate() -> dict[str, Any]:
    """Initiate MSAL device code login flow.

    The blocking token acquisition is completed in a background thread (see
    `GraphClient.initiate_user_login`); polling only reads its status.
    """
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

        return {
            "status": "pending",
            "device_code": flow["device_code"],
            "user_code": flow["user_code"],
            "verification_uri": flow["verification_uri"],
            "message": flow["message"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/login-poll")
def login_poll(payload: dict[str, str]) -> dict[str, Any]:
    """Read the status of an in-progress device-code login.

    The actual token acquisition happens once in a background thread started by
    `/auth/login-initiate`. This endpoint never calls Microsoft directly, so it
    can be polled freely without reusing the device_code (AADSTS70000).
    """
    device_code = payload.get("device_code")
    if not device_code:
        raise HTTPException(status_code=400, detail="Missing device_code")

    from app.services.graph import _device_flow_status

    state = _device_flow_status.get(device_code)
    if not state:
        return {"status": "pending", "authenticated": False}

    status_val = state.get("status")
    if status_val == "success":
        _device_flow_status.pop(device_code, None)
        set_provider("microsoft", state.get("user_principal_name"))
        return {
            "status": "success",
            "authenticated": True,
            "user_principal_name": state.get("user_principal_name"),
        }
    if status_val == "error":
        _device_flow_status.pop(device_code, None)
        raise HTTPException(status_code=400, detail=state.get("error", "Authentication failed"))

    return {"status": "pending", "authenticated": False}


# ── Microsoft OAuth (authorization-code popup flow) ───────────────────────────


@router.post("/auth/microsoft/login-initiate")
def microsoft_login_initiate() -> dict[str, Any]:
    """Begin Microsoft sign-in via the auth-code popup flow.

    Returns the Microsoft consent URL; the frontend opens it in a popup and polls /auth/microsoft/poll.
    """
    if not settings.azure_client_id:
        raise HTTPException(status_code=500, detail="Microsoft OAuth not configured (AZURE_CLIENT_ID).")
    from app.services.graph import build_ms_auth_url
    auth_url, state = build_ms_auth_url()
    return {"status": "pending", "auth_url": auth_url, "state": state}


def _connected_screen(email: str, dashboard_url: str, provider: str = "microsoft") -> str:
    """Branded 'account connected' screen shown after a successful OAuth redirect."""
    safe_email = (email or "").replace("<", "&lt;").replace(">", "&gt;")
    who = f"<p class='email'>{safe_email}</p>" if safe_email else ""

    if provider == "google":
        gradient = "linear-gradient(135deg, #1a73e8 0%, #0d9488 100%)"
        shadow_color = "rgba(26, 115, 232, .30)"
        email_color = "#1a73e8"
        spin_color = "#1a73e8"
        provider_label = "Google"
        provider_logo = """<div class="provider-logo">
      <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="32" height="32">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
      </svg>
    </div>"""
    else:
        gradient = "linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)"
        shadow_color = "rgba(49, 46, 129, .35)"
        email_color = "#6366F1"
        spin_color = "#6366F1"
        provider_label = "Microsoft"
        provider_logo = """<div class="provider-logo">
      <svg viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg" width="28" height="28">
        <rect x="1" y="1" width="9" height="9" fill="#F25022"/>
        <rect x="11" y="1" width="9" height="9" fill="#7FBA00"/>
        <rect x="1" y="11" width="9" height="9" fill="#00A4EF"/>
        <rect x="11" y="11" width="9" height="9" fill="#FFB900"/>
      </svg>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Connected · MailMind</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background: {gradient}; color: #1e1b2e;
    }}
    .card {{
      background: #fff; border-radius: 20px; padding: 40px 36px; width: 380px; max-width: 90vw;
      text-align: center; box-shadow: 0 24px 60px {shadow_color}; animation: rise .45s ease-out;
    }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(14px); }} to {{ opacity: 1; transform: none; }} }}
    .provider-logo {{
      width: 64px; height: 64px; margin: 0 auto 4px; border-radius: 16px;
      background: #f8f9fa; border: 1px solid #e8eaed;
      display: flex; align-items: center; justify-content: center;
    }}
    .check {{
      width: 32px; height: 32px; margin: 8px auto 16px; border-radius: 50%;
      background: #ecfdf5; display: flex; align-items: center; justify-content: center;
    }}
    .check svg {{ width: 18px; height: 18px; stroke: #10b981; }}
    h2 {{ margin: 0 0 6px; font-size: 20px; font-weight: 700; }}
    .email {{ margin: 0 0 14px; font-size: 13px; font-weight: 600; color: {email_color}; }}
    p.sub {{ margin: 0; font-size: 13px; color: #6b7280; line-height: 1.5; }}
    .spin {{
      margin: 22px auto 0; width: 20px; height: 20px; border-radius: 50%;
      border: 3px solid #e5e7eb; border-top-color: {spin_color}; animation: spin .8s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  </style>
</head>
<body>
  <div class="card">
    {provider_logo}
    <div class="check">
      <svg viewBox="0 0 24 24" fill="none" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <path d="M5 13l4 4L19 7" />
      </svg>
    </div>
    <h2>You're connected to MailMind</h2>
    {who}
    <p class="sub">Your {provider_label} account is securely linked.<br/>Returning you to your workspace…</p>
    <div class="spin"></div>
  </div>
  <script>
    setTimeout(function () {{
      try {{ window.close(); }} catch (e) {{}}
      setTimeout(function () {{ window.location.href = '{dashboard_url}'; }}, 400);
    }}, 1200);
  </script>
</body>
</html>"""


@router.get("/auth/microsoft/callback", response_class=HTMLResponse)
def microsoft_callback(request: Request) -> str:
    """OAuth redirect target — exchanges the code and stores the session."""
    from app.services.graph import exchange_ms_code, ms_auth_status
    params = dict(request.query_params)
    state = params.get("state", "")
    if params.get("error"):
        if state:
            ms_auth_status[state] = {"status": "error", "error": params.get("error_description", params["error"])}
        return f"<html><body><h3>Sign-in failed: {params.get('error')}</h3>You can close this window.</body></html>"
    try:
        info = exchange_ms_code(state, params)
        set_provider("microsoft", info.get("email"))
        ms_auth_status[state] = {"status": "success", "email": info.get("email")}
        dashboard = f"{settings.frontend_origin.rstrip('/')}/dashboard"
        email = info.get("email") or ""
        return _connected_screen(email, dashboard)
    except Exception as e:
        if state:
            ms_auth_status[state] = {"status": "error", "error": str(e)}
        return f"<html><body><h3>Sign-in failed: {str(e)}</h3>You can close this window.</body></html>"


@router.post("/auth/microsoft/poll")
def microsoft_poll(payload: dict[str, str]) -> dict[str, Any]:
    """Poll the status of an in-progress Microsoft sign-in."""
    from app.services.graph import ms_auth_status
    state = payload.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")
    info = ms_auth_status.get(state)
    if not info:
        return {"status": "pending", "authenticated": False}
    if info.get("status") == "success":
        ms_auth_status.pop(state, None)
        return {"status": "success", "authenticated": True, "user_principal_name": info.get("email")}
    if info.get("status") == "error":
        ms_auth_status.pop(state, None)
        raise HTTPException(status_code=400, detail=info.get("error", "Microsoft sign-in failed"))
    return {"status": "pending", "authenticated": False}


# ── Google / Gmail OAuth ──────────────────────────────────────────────────────


@router.post("/auth/google/login-initiate")
def google_login_initiate(payload: dict[str, str] | None = None) -> dict[str, Any]:
    """Begin Google sign-in.

    Mock mode logs in instantly as a Gmail account. Live mode returns the Google
    consent URL; the frontend opens it and polls /auth/google/poll.
    """
    import uuid

    from app.services.gmail import build_auth_url, google_auth_status

    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID/SECRET.")

    state = uuid.uuid4().hex
    google_auth_status[state] = {"status": "pending"}
    return {"status": "pending", "auth_url": build_auth_url(state), "state": state}


@router.get("/auth/google/callback", response_class=HTMLResponse)
def google_callback(code: str | None = None, state: str | None = None, error: str | None = None) -> str:
    """OAuth redirect target — exchanges the code and stores the session."""
    from app.services.gmail import exchange_code, google_auth_status

    if error:
        if state:
            google_auth_status[state] = {"status": "error", "error": error}
        return f"<html><body><h3>Sign-in failed: {error}</h3>You can close this window.</body></html>"
    if not code or not state:
        return "<html><body><h3>Missing code/state</h3></body></html>"
    try:
        info = exchange_code(code)
        set_provider("google", info.get("email"))
        google_auth_status[state] = {"status": "success", "email": info.get("email")}
        dashboard = f"{settings.frontend_origin.rstrip('/')}/dashboard"
        email = info.get("email") or ""
        return _connected_screen(email, dashboard, provider="google")
    except Exception as e:
        google_auth_status[state] = {"status": "error", "error": str(e)}
        return f"<html><body><h3>Sign-in failed: {str(e)}</h3>You can close this window.</body></html>"


@router.post("/auth/google/poll")
def google_poll(payload: dict[str, str]) -> dict[str, Any]:
    """Poll the status of an in-progress Google sign-in."""
    from app.services.gmail import google_auth_status

    state = payload.get("state")
    if not state:
        raise HTTPException(status_code=400, detail="Missing state")
    info = google_auth_status.get(state)
    if not info:
        return {"status": "pending", "authenticated": False}
    if info.get("status") == "success":
        google_auth_status.pop(state, None)
        return {"status": "success", "authenticated": True, "user_principal_name": info.get("email")}
    if info.get("status") == "error":
        google_auth_status.pop(state, None)
        raise HTTPException(status_code=400, detail=info.get("error", "Google sign-in failed"))
    return {"status": "pending", "authenticated": False}


@router.post("/auth/quick-login")
def quick_login(payload: dict[str, str] | None = None) -> dict[str, Any]:
    """One-tap login for a remembered account — no device code / password.

    Uses the persisted refresh token (Microsoft MSAL cache or Google token) to
    resume the session silently without requiring the user to re-authenticate.
    """
    email = (payload or {}).get("email")
    provider = (payload or {}).get("provider") or "microsoft"

    # Live Google: resume silently from the persisted Google refresh token.
    if provider == "google":
        from app.services.gmail import _refresh_access_token, current_google_email, has_google_session
        if not has_google_session() or not _refresh_access_token():
            raise HTTPException(status_code=400, detail="No Google session to resume. Please connect Google again.")
        set_provider("google", current_google_email() or email)
        return {"status": "authenticated", "authenticated": True, "user_principal_name": active_email()}

    # Live Microsoft: resume the delegated session silently via the persisted
    # refresh token. Delegated tokens work with personal accounts and avoid the
    # app-only Conditional Access block (AADSTS53003).
    try:
        info = client.quick_login(email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    set_provider("microsoft", info.get("user_principal_name") or email)
    return {
        "status": "authenticated",
        "authenticated": True,
        "user_principal_name": info.get("user_principal_name") or email,
    }


@router.get("/auth/status")
def auth_status() -> dict[str, Any]:
    """Check the current login status and user principal name."""
    from app.services.graph import _user_token_cache

    # A logged-out session is never authenticated, even if a resumable refresh
    # token still exists on disk (that's only used by Quick Login).
    if not is_active():
        return {
            "status": "unauthenticated",
            "authenticated": False,
            "user_principal_name": None,
            "provider": active_provider(),
        }

    # Live Google session.
    if active_provider() == "google":
        from app.services.gmail import current_google_email, has_google_session
        if has_google_session():
            return {
                "status": "authenticated",
                "authenticated": True,
                "user_principal_name": current_google_email(),
                "provider": "google",
            }
        return {"status": "unauthenticated", "authenticated": False, "user_principal_name": None, "provider": "google"}

    # Live Microsoft session.
    import time
    now = time.time()
    if _user_token_cache["access_token"] and now < (_user_token_cache["expires_at"] - 60):
        return {
            "status": "authenticated",
            "authenticated": True,
            "user_principal_name": _user_token_cache["user_principal_name"] or "authenticated.user@outlook.com",
            "provider": "microsoft",
        }
    return {
        "status": "unauthenticated",
        "authenticated": False,
        "user_principal_name": None,
        "provider": "microsoft",
    }


@router.post("/auth/logout")
def auth_logout() -> dict[str, Any]:
    """Log out the current user session by clearing token cache."""
    from app.services.gmail import sign_out_google
    from app.services.graph import _user_token_cache
    _user_token_cache["access_token"] = None
    _user_token_cache["expires_at"] = 0.0
    _user_token_cache["user_principal_name"] = None
    sign_out_google()  # keeps the refresh token so Quick Login can resume
    clear_provider()   # reset provider + mark the session logged out
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
def classify_text(payload: RAGQuery, current_user: str = Depends(get_current_user)) -> ClassificationResult:
    """Classify email text to assign priority, category, and confidence."""
    import hashlib

    from app.services.cache import classification_cache
    key = f"classify:{current_user}:{hashlib.sha256(payload.email_text.strip().lower().encode('utf-8')).hexdigest()}"
    cached = classification_cache.get(key)
    if cached is not None:
        return cached

    classifier = ClassificationService()
    masked = mask_pii(payload.email_text)
    result = classifier.classify(masked)
    classification_cache.set(key, result)
    return result


@router.get("/thread/{thread_id}")
def fetch_thread(thread_id: str, _user: str = Depends(get_current_user)) -> list[dict[str, Any]]:
    """Fetch recent messages for a given thread from the Graph stub client."""
    fetcher = ThreadFetcher(GraphClient())
    return fetcher.fetch(thread_id)


@router.get("/calendar", response_model=list[CalendarEvent])
def fetch_calendar(days: int = 7, _user: str = Depends(get_current_user)) -> list[CalendarEvent]:
    """Fetch upcoming calendar events from the active provider (Outlook or Google)."""
    try:
        fetcher = CalendarFetcher(get_mail_client())
        return fetcher.fetch_next_events(days=days)
    except Exception as e:
        logger.warning(f"Calendar fetch failed: {str(e)}")
        return []


@router.post("/calendar/event")
def create_calendar_event(payload: dict[str, Any], _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Create a calendar event in the user's Outlook or Google calendar."""
    title = (payload.get("title") or "").strip()
    start = (payload.get("start_time") or "").strip()
    end = (payload.get("end_time") or "").strip()
    description = (payload.get("description") or "").strip()

    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    if not start:
        raise HTTPException(status_code=400, detail="start_time is required")

    client = get_mail_client()
    try:
        from datetime import datetime
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00")) if end else start_dt + __import__('datetime').timedelta(hours=1)
        link = client.create_calendar_event(
            email_id=payload.get("email_id", "manual"),
            commitment=f"{title}\n\n{description}".strip(),
            deadline=start_dt,
        )
        return {
            "success": True,
            "title": title,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "event_url": link,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")


@router.get("/tasks")
def list_tasks(limit: int = 20, _user: str = Depends(get_current_user)) -> list[dict[str, Any]]:
    """List the user's tasks from the active provider (Microsoft To Do or Google Tasks)."""
    return get_mail_client().list_tasks(limit=limit)


@router.post("/tasks")
def create_task(payload: dict[str, str], _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Create a task in the active provider's task list."""
    title = (payload or {}).get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    try:
        url = get_mail_client().create_todo("manual", title)
        return {"success": True, "url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create task: {str(e)}")


@router.post("/rag/retrieve", response_model=list[PrecedentItem])
def rag_retrieve(query: RAGQuery, current_user: str = Depends(get_current_user)) -> list[PrecedentItem]:
    """Retrieve precedent emails similar to the provided email text."""
    import hashlib

    from app.services.cache import precedents_cache
    key = f"retrieve:{current_user}:{hashlib.sha256(query.email_text.strip().lower().encode('utf-8')).hexdigest()}"
    cached = precedents_cache.get(key)
    if cached is not None:
        return cached

    index = RAGIndexFactory()()
    masked = mask_pii(query.email_text)
    results = RetrievalService(index).retrieve(masked)
    precedents_cache.set(key, results)
    return results


@router.post("/rag/inject")
def rag_inject(query: RAGQuery, current_user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Create a prompt that injects precedent email context for response drafting."""
    import hashlib

    from app.services.cache import precedents_cache
    key = f"inject:{current_user}:{hashlib.sha256(query.email_text.strip().lower().encode('utf-8')).hexdigest()}"
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
def generate_draft(payload: DraftRequest, _user: str = Depends(get_current_user)) -> DraftResponse:
    """Generate an email response draft using a selected style (standard, formal, or indepth) and context precedents."""
    import hashlib

    from app.services.cache import precedents_cache
    # Include current_user_email in the cache key — different users get different drafts.
    user_part = (payload.current_user_email or "anon").lower()
    key = f"draft:{payload.style}:{user_part}:{hashlib.sha256(payload.email_text.strip().lower().encode('utf-8')).hexdigest()}"
    cached = precedents_cache.get(key)
    if cached is not None:
        return cached

    service = DraftService()
    draft, citations = service.generate_draft(
        email_text=payload.email_text,
        style=payload.style,
        sender=payload.sender,
        subject=payload.subject,
        current_user_email=payload.current_user_email,
    )
    result = DraftResponse(draft=draft, precedent_citations=citations)
    precedents_cache.set(key, result)
    return result



@router.post("/commitments/extract", response_model=CommitmentExtractionResponse)
def extract_commitments(payload: CommitmentExtractionRequest) -> CommitmentExtractionResponse:
    """Extract commitment candidates from masked email text."""
    service = CommitmentService(get_mail_client())
    commitments = service.extract(payload.get_text(), payload.thread_summary or "", payload.email_id)
    return CommitmentExtractionResponse(commitments=commitments)


@router.get("/rag/stats")
def rag_stats(_user: str = Depends(get_current_user)) -> dict[str, Any]:
    """Return real index statistics: document count, storage size, last indexed time."""
    import os
    from app.config.settings import settings as _s

    index_dir = os.path.abspath(_s.chroma_storage_path)
    index_file = os.path.join(index_dir, "index.json")

    doc_count = 0
    storage_bytes = 0
    last_modified: str | None = None

    if os.path.exists(index_file):
        try:
            import json as _json
            with open(index_file, "r", encoding="utf-8") as fh:
                docs = _json.load(fh)
            doc_count = len(docs)
            storage_bytes = os.path.getsize(index_file)
            ts = os.path.getmtime(index_file)
            from datetime import datetime as _dt, timezone as _tz
            last_modified = _dt.fromtimestamp(ts, tz=_tz.utc).isoformat()
        except Exception as exc:
            logger.warning("[rag/stats] Failed to read index: %s", exc)

    storage_mb = round(storage_bytes / (1024 * 1024), 2)
    return {
        "indexed_emails": doc_count,
        "storage_mb": storage_mb,
        "storage_label": f"{storage_mb} MB" if storage_mb >= 0.01 else f"{round(storage_bytes / 1024, 1)} KB",
        "last_indexed": last_modified,
        "index_path": index_file,
        "similarity_threshold": _s.rag_similarity_threshold,
        "max_index_size": _s.index_max_size,
    }


@router.post("/rag/settings")
def update_rag_settings(payload: dict[str, Any], _user: str = Depends(get_current_user)) -> dict[str, Any]:
    """
    Update retrieval settings at runtime.

    Accepted keys: ``similarity_threshold`` (float 0.0–1.0), ``max_index_size`` (int).
    Changes apply immediately to all subsequent retrieve calls in this process.
    They are not persisted across restarts — set the corresponding env vars
    (RAG_SIMILARITY_THRESHOLD, RAG_INDEX_MAX_SIZE) for durable configuration.
    """
    from app.config.settings import settings as _s

    updated: dict[str, Any] = {}

    threshold = payload.get("similarity_threshold")
    if threshold is not None:
        val = float(threshold)
        if not 0.0 <= val <= 1.0:
            raise HTTPException(status_code=400, detail="similarity_threshold must be between 0.0 and 1.0")
        _s.rag_similarity_threshold = val
        updated["similarity_threshold"] = val

    max_size = payload.get("max_index_size")
    if max_size is not None:
        val_i = int(max_size)
        if val_i < 1:
            raise HTTPException(status_code=400, detail="max_index_size must be at least 1")
        _s.index_max_size = val_i
        updated["max_index_size"] = val_i

    return {"status": "ok", "updated": updated}


@router.post("/commitments/confirm", response_model=CommitmentConfirmResponse)
def confirm_commitments(payload: CommitmentApprover, x_approval_token: str | None = Header(None)) -> CommitmentConfirmResponse:
    """Confirm approved commitments and create tasks/calendar events."""
    _validate_approval_token(x_approval_token)
    service = CommitmentService(get_mail_client())
    try:
        result = service.confirm(payload.email_id, payload.commitments)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to confirm commitments: {str(e)}")
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

    classifier = ClassificationService()

    def _evaluate_one(item: dict) -> dict:
        email_text = f"Subject: {item['subject']}\nSender: {item['sender']}\nBody: {item['body']}"
        predicted = _eval_prediction_cache.get(email_text)
        if predicted is None:
            pred_priority = classifier.classify(email_text).priority
            predicted = {"CRITICAL": "Critical", "HIGH": "High"}.get(pred_priority, "Normal")
            _eval_prediction_cache[email_text] = predicted
        expected = item["expected_priority"]
        return {
            "subject": item["subject"],
            "expected": expected,
            "predicted": predicted,
            "is_correct": expected == predicted,
        }

    # Run rows concurrently so a live LLM-backed eval finishes in seconds
    # instead of (rows × per-call latency). Order is preserved via the index map.
    from concurrent.futures import ThreadPoolExecutor

    workers = 1 if settings.use_mock_graph else min(8, max(2, len(dataset)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_evaluate_one, dataset))

    correct = sum(1 for r in results if r["is_correct"])
    accuracy = round((correct / len(dataset)) * 100, 2) if dataset else 0.0
    return {
        "accuracy": accuracy,
        "total_samples": len(dataset),
        "correct_predictions": correct,
        "results": results,
    }


def _make_scorers() -> dict[str, Any]:
    """Build a reusable set of scorers (shared across a batch to reuse caches)."""
    return {
        "deadline": DeadlineScorer(),
        "authority": SenderAuthorityScorer(GraphClient()),
        "sentiment": SentimentScorer(),
        "decay": ThreadAgeDecayScorer(),
        "action": ActionTypeScorer(),
        "aggregator": CompositeAggregator(),
    }


def _compute_triage(payload: EmailPayload, scorers: dict[str, Any], user_email: str = "") -> TriageResult:
    from app.services.cache import triage_cache
    key = f"id:{user_email}:{payload.email_id}"
    cached = triage_cache.get(key)
    if cached is not None:
        return cached
    body = payload.body
    axes = [
        scorers["deadline"].score(body, payload.received_at),
        scorers["authority"].score(str(payload.sender)),
        scorers["sentiment"].score(body),
        scorers["decay"].score(payload.received_at),
        scorers["action"].score(body),
    ]
    result = scorers["aggregator"].aggregate(axes)
    triage_cache.set(key, result)
    return result


@router.post("/triage", response_model=TriageResult)
def triage_email(payload: EmailPayload, current_user: str = Depends(get_current_user)) -> TriageResult:
    """Calculate the five-axis triage score for an email."""
    return _compute_triage(payload, _make_scorers(), current_user)


@router.post("/triage/batch", response_model=list[TriageResult])
def triage_batch(payloads: list[EmailPayload], current_user: str = Depends(get_current_user)) -> list[TriageResult]:
    """Score many emails in one request (reuses scorers + cache).

    Replaces N separate /triage calls with a single round-trip — drastically
    cutting the number of API calls the client makes per page.
    """
    scorers = _make_scorers()
    return [_compute_triage(p, scorers, current_user) for p in payloads]

# ── Tone DNA routes ───────────────────────────────────────────────────────────


@router.post("/tone-dna/build")
def build_tone_dna(current_user: str = Depends(get_current_user)) -> dict:
    """DNA-01: Trigger Tone DNA ingestion from sent mail (current provider)."""
    svc = ToneDNAService(get_mail_client(), current_user)
    profile = svc.ingest_and_build()
    return {
        "status": "built",
        "sample_size": profile.get("sample_size", 0),
        "formality_score": profile["features"]["formality_score"],
        "generated_at": profile["generated_at"],
    }

@router.get("/tone-dna/profile")
def get_tone_dna_profile(current_user: str = Depends(get_current_user)) -> dict:
    """Return the current user's Tone DNA profile (or 404 if not yet built)."""
    profile = _load_tone_profile(current_user)
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
