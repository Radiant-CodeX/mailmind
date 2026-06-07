"""Gmail / Google connector — mirrors GraphClient so the app works for Google
accounts with full parity (inbox/sent/drafts/spam/trash, send, reply, trash,
restore).

Auth: OAuth 2.0 authorization-code flow with a backend redirect callback and a
persisted refresh token (so Quick Login resumes silently). When
`settings.use_mock_graph` is True everything returns deterministic mock data, so
the whole experience works with zero Google config.
"""
from __future__ import annotations

import base64
import json
import os
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any, List
from urllib.parse import urlencode

import httpx

from app.config.settings import settings

# OAuth + API endpoints
_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# Persistent Google token store (holds the refresh token). gitignored.
_GOOGLE_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "google_token.json")

# In-flight OAuth states keyed by `state`, populated by the callback:
#   {"status": "pending" | "success" | "error", "email": ..., "error": ...}
google_auth_status: dict[str, dict[str, Any]] = {}

# Cached live token (mirrors the Microsoft _user_token_cache pattern).
_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0, "email": None}


# ── Token persistence ─────────────────────────────────────────────────────────
def _load_tokens() -> dict[str, Any]:
    try:
        if os.path.exists(_GOOGLE_TOKEN_PATH):
            with open(_GOOGLE_TOKEN_PATH, "r", encoding="utf-8") as fh:
                return json.load(fh)
    except Exception:  # pragma: no cover - corrupt store is non-fatal
        pass
    return {}


def _save_tokens(data: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(_GOOGLE_TOKEN_PATH), exist_ok=True)
        existing = _load_tokens()
        existing.update({k: v for k, v in data.items() if v is not None})
        with open(_GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as fh:
            json.dump(existing, fh)
    except Exception:  # pragma: no cover
        pass


def sign_out_google() -> None:
    """Clear only the in-memory access token (keeps the refresh token on disk so
    Quick Login can resume). Use this on logout."""
    _token_cache["access_token"] = None
    _token_cache["expires_at"] = 0.0


def clear_google_tokens() -> None:
    """Fully forget the Google account (removes the refresh token)."""
    _token_cache.update({"access_token": None, "expires_at": 0.0, "email": None})
    try:
        if os.path.exists(_GOOGLE_TOKEN_PATH):
            os.remove(_GOOGLE_TOKEN_PATH)
    except Exception:  # pragma: no cover
        pass


# ── OAuth flow ────────────────────────────────────────────────────────────────
def build_auth_url(state: str) -> str:
    """Build the Google consent URL for the authorization-code flow."""
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",       # needed to receive a refresh token
        "prompt": "consent",
        "state": state,
        "include_granted_scopes": "true",
    }
    return f"{_AUTH_URI}?{urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an auth code for tokens and persist the refresh token."""
    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(_TOKEN_URI, data=data)
        resp.raise_for_status()
        tok = resp.json()

    _token_cache["access_token"] = tok.get("access_token")
    _token_cache["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
    email = _fetch_email(tok.get("access_token"))
    _token_cache["email"] = email
    _save_tokens({"refresh_token": tok.get("refresh_token"), "email": email})
    return {"email": email}


def _refresh_access_token() -> str | None:
    """Get a fresh access token from the stored refresh token (silent)."""
    stored = _load_tokens()
    refresh_token = stored.get("refresh_token")
    if not refresh_token:
        return None
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(_TOKEN_URI, data=data)
            resp.raise_for_status()
            tok = resp.json()
    except Exception:
        return None
    _token_cache["access_token"] = tok.get("access_token")
    _token_cache["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
    _token_cache["email"] = stored.get("email")
    return _token_cache["access_token"]


def _get_access_token() -> str:
    now = time.time()
    if _token_cache["access_token"] and now < (_token_cache["expires_at"] - 60):
        return _token_cache["access_token"]
    refreshed = _refresh_access_token()
    if not refreshed:
        # Clean 401 (not a 500) so the frontend can redirect to login gracefully.
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Google session expired. Please sign in again.")
    return refreshed


def has_google_session() -> bool:
    """True if a usable Google session (cached or refreshable) exists."""
    if _token_cache["access_token"] and time.time() < (_token_cache["expires_at"] - 60):
        return True
    return bool(_load_tokens().get("refresh_token"))


def current_google_email() -> str | None:
    return _token_cache.get("email") or _load_tokens().get("email")


def _fetch_email(access_token: str | None) -> str:
    if not access_token:
        return "user@gmail.com"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json().get("email", "user@gmail.com")
    except Exception:
        return "user@gmail.com"


# ── Gmail message parsing helpers ─────────────────────────────────────────────
def _header(headers: list[dict[str, str]], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body(payload: dict[str, Any]) -> str:
    """Pull a text/plain body out of a Gmail message payload."""
    if not payload:
        return ""
    body = payload.get("body", {})
    if body.get("data"):
        return _decode_part(body["data"])
    for part in payload.get("parts", []) or []:
        mime = part.get("mimeType", "")
        if mime == "text/plain" and part.get("body", {}).get("data"):
            return _decode_part(part["body"]["data"])
        # Recurse into multipart containers.
        nested = _extract_body(part)
        if nested:
            return nested
    return ""


class GmailClient:
    """Gmail client with the same surface as GraphClient (mock + live)."""

    def __init__(self, settings_obj=settings):
        self.settings = settings_obj
        self.use_mock = bool(self.settings.use_mock_graph)

    # ── helpers ──
    def _request(self, method: str, path: str, **kwargs) -> Any:
        token = _get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Accept", "application/json")
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, f"{_GMAIL_API}{path}", headers=headers, **kwargs)
        resp.raise_for_status()
        if resp.status_code in (202, 204) or not resp.content:
            return None
        return resp.json()

    def _list_formatted(self, label: str, limit: int, date_field: str = "received_at") -> List[dict[str, Any]]:
        data = self._request("GET", f"/messages?labelIds={label}&maxResults={limit}")
        ids = [m["id"] for m in (data or {}).get("messages", [])]
        out: list[dict[str, Any]] = []
        for mid in ids:
            msg = self._request("GET", f"/messages/{mid}?format=full")
            if not msg:
                continue
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            out.append({
                "email_id": msg.get("id", ""),
                "sender": _header(headers, "From") or "unknown@gmail.com",
                "subject": _header(headers, "Subject"),
                "body": _extract_body(payload) or msg.get("snippet", ""),
                "received_at": _header(headers, "Date") or "",
            })
        return out

    # ── mock data ──
    def _mock_inbox(self) -> List[dict[str, Any]]:
        now = datetime.utcnow()
        return [
            {
                "email_id": "gmail-1",
                "sender": "notifications@github.com",
                "subject": "[GitHub] Your CI run failed on main",
                "body": "The workflow 'CI' failed on the latest push to main. Review the logs and re-run.",
                "received_at": (now - timedelta(minutes=12)).isoformat() + "Z",
            },
            {
                "email_id": "gmail-2",
                "sender": "team@notion.so",
                "subject": "Weekly digest: 4 pages updated",
                "body": "Here's what changed in your workspace this week. 4 pages were updated by your team.",
                "received_at": (now - timedelta(hours=3)).isoformat() + "Z",
            },
            {
                "email_id": "gmail-3",
                "sender": "ravi.kumar@gmail.com",
                "subject": "Lunch next week?",
                "body": "Hey! Are you free for lunch sometime next week? Let me know what day works.",
                "received_at": (now - timedelta(hours=20)).isoformat() + "Z",
            },
        ]

    # ── public surface (mirrors GraphClient) ──
    def get_inbox_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        if self.use_mock:
            return self._mock_inbox()[:limit]
        return self._list_formatted("INBOX", limit)

    def fetch_sent_emails(self, days: int = 30) -> List[dict[str, Any]]:
        if self.use_mock:
            return [
                {"id": f"gmail-sent-{i}", "subject": f"Re: project sync {i}",
                 "body": f"Thanks, I'll handle item {i} by end of week.",
                 "sentDateTime": datetime.utcnow().isoformat() + "Z"}
                for i in range(5)
            ]
        return self._list_formatted("SENT", 50, date_field="sentDateTime")

    def get_draft_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        if self.use_mock:
            return []
        return self._list_formatted("DRAFT", limit)

    def get_spam_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        if self.use_mock:
            return []
        return self._list_formatted("SPAM", limit)

    def get_trash_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        if self.use_mock:
            return []
        return self._list_formatted("TRASH", limit)

    def send_reply(self, email_id: str, comment: str) -> None:
        if self.use_mock:
            print(f"[MOCK GMAIL] Reply to {email_id}: {comment}")
            return
        # Look up thread + recipient to thread the reply correctly.
        original = self._request("GET", f"/messages/{email_id}?format=metadata")
        headers = (original or {}).get("payload", {}).get("headers", [])
        to_addr = _header(headers, "From")
        subject = _header(headers, "Subject")
        thread_id = (original or {}).get("threadId")
        raw = self._build_raw(to_addr, f"Re: {subject}", comment)
        self._request("POST", "/messages/send", json={"raw": raw, "threadId": thread_id})

    def send_new_email(self, to: str, subject: str, body: str, cc: str | None = None, bcc: str | None = None) -> None:
        if self.use_mock:
            print(f"[MOCK GMAIL] Send to={to} subject={subject}")
            return
        raw = self._build_raw(to, subject, body, cc, bcc)
        self._request("POST", "/messages/send", json={"raw": raw})

    def move_to_trash(self, email_id: str) -> None:
        if self.use_mock:
            print(f"[MOCK GMAIL] Trash {email_id}")
            return
        self._request("POST", f"/messages/{email_id}/trash")

    def restore_from_trash(self, email_id: str) -> None:
        if self.use_mock:
            print(f"[MOCK GMAIL] Untrash {email_id}")
            return
        self._request("POST", f"/messages/{email_id}/untrash")

    # ── Calendar / Tasks parity (used by commitment confirmation) ────────────
    def _authed(self, method: str, url: str, **kwargs) -> Any:
        token = _get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else None

    def create_calendar_event(self, email_id: str, commitment: str, deadline: Any = None) -> str:
        """Create a Google Calendar event for a commitment; returns its link."""
        if self.use_mock:
            return "https://calendar.google.com/calendar/r/eventedit?mock=1"
        if isinstance(deadline, datetime):
            start = deadline.isoformat()
            if deadline.tzinfo is None:
                start += "Z"
        elif isinstance(deadline, str) and deadline:
            start = deadline
        else:
            start = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
        body = {"summary": commitment, "start": {"dateTime": start}, "end": {"dateTime": start}}
        res = self._authed(
            "POST", "https://www.googleapis.com/calendar/v3/calendars/primary/events", json=body
        )
        return (res or {}).get("htmlLink", "https://calendar.google.com/")

    def create_todo(self, email_id: str, commitment: str) -> str:
        """Create a Google Tasks item for a commitment; returns its link."""
        if self.use_mock:
            return "https://tasks.google.com/task?mock=1"
        res = self._authed(
            "POST", "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks", json={"title": commitment}
        )
        return (res or {}).get("selfLink", "https://tasks.google.com/")

    def get_calendar_events(self, start_time: datetime, end_time: datetime) -> List[dict[str, Any]]:
        """Calendar events in a window, normalized to {title, start_time, end_time, organizer}."""
        if self.use_mock:
            now = datetime.utcnow()
            return [
                {"title": "Standup with Eng", "start_time": now + timedelta(hours=1),
                 "end_time": now + timedelta(hours=1, minutes=30), "organizer": "team@gmail.com"},
                {"title": "1:1 with Manager", "start_time": now + timedelta(days=1, hours=2),
                 "end_time": now + timedelta(days=1, hours=3), "organizer": "manager@gmail.com"},
                {"title": "Product Review", "start_time": now + timedelta(days=2, hours=4),
                 "end_time": now + timedelta(days=2, hours=5), "organizer": "pm@gmail.com"},
            ]
        params = {
            "timeMin": start_time.isoformat() + ("" if start_time.tzinfo else "Z"),
            "timeMax": end_time.isoformat() + ("" if end_time.tzinfo else "Z"),
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        try:
            res = self._authed(
                "GET", "https://www.googleapis.com/calendar/v3/calendars/primary/events", params=params
            )
        except Exception:
            return []

        def _parse(node: dict[str, Any], fallback: datetime) -> datetime:
            val = node.get("dateTime") or node.get("date")
            if not val:
                return fallback
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                return fallback

        events = []
        for item in (res or {}).get("items", []):
            events.append({
                "title": item.get("summary", "Untitled event"),
                "start_time": _parse(item.get("start", {}), start_time),
                "end_time": _parse(item.get("end", {}), end_time),
                "organizer": (item.get("organizer") or {}).get("email", "unknown@gmail.com"),
            })
        return events

    def list_tasks(self, limit: int = 20) -> List[dict[str, Any]]:
        """Return Google Tasks, normalized to {id, title, status, due}."""
        if self.use_mock:
            now = datetime.utcnow()
            return [
                {"id": "gtask-1", "title": "Reply to recruiter", "status": "needsAction",
                 "due": (now + timedelta(days=1)).isoformat() + "Z"},
                {"id": "gtask-2", "title": "Send invoice to client", "status": "needsAction",
                 "due": (now + timedelta(days=2)).isoformat() + "Z"},
            ]
        try:
            res = self._authed(
                "GET", f"https://tasks.googleapis.com/tasks/v1/lists/@default/tasks?maxResults={limit}"
            )
        except Exception:
            return []
        return [
            {"id": t.get("id", ""), "title": t.get("title", ""), "status": t.get("status", "needsAction"),
             "due": t.get("due", "")}
            for t in (res or {}).get("items", [])
        ]

    def get_thread_messages(self, thread_id: str) -> List[dict[str, Any]]:
        # Thread context isn't required for confirmation; safe empty default.
        return []

    def fetch_sent_email(self, email_id: str) -> dict[str, Any] | None:
        if self.use_mock:
            return {"id": email_id, "subject": "Mock", "body": "Mock re-index body."}
        try:
            return self._request("GET", f"/messages/{email_id}?format=full")
        except Exception:
            return None

    def _build_raw(self, to: str, subject: str, body: str, cc: str | None = None, bcc: str | None = None) -> str:
        msg = EmailMessage()
        msg["To"] = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc
        msg.set_content(body)
        return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
