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
import logging
import os
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Any, List
from urllib.parse import urlencode

import logging

import httpx

from app.config.settings import settings

logger = logging.getLogger(__name__)

# OAuth + API endpoints
_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
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

    logger.info(f"[exchange_code] Attempting to exchange code (prefix: {code[:20]}...)")

    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(_TOKEN_URI, data=data)

        if resp.status_code != 200:
            logger.error(f"[exchange_code] Google token error (code prefix: {code[:20]}...): {resp.status_code}")
            logger.error(f"[exchange_code] Response body: {resp.text}")

        resp.raise_for_status()
        tok = resp.json()

    _token_cache["access_token"] = tok.get("access_token")
    _token_cache["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
    profile = _fetch_profile(tok.get("access_token"))
    email = profile.get("email") or "user@gmail.com"
    _token_cache["email"] = email
    _save_tokens({
        "refresh_token": tok.get("refresh_token"),
        "email": email,
        "name": profile.get("name"),
        "picture": profile.get("picture"),
    })
    return {
        "email": email,
        "sub": profile.get("id") or email,  # Google unique ID
        "display_name": profile.get("name"),
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "token_expires_at": datetime.utcnow() + timedelta(seconds=int(tok.get("expires_in", 3600))),
    }


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


def _fetch_profile(access_token: str | None) -> dict[str, str | None]:
    if not access_token:
        return {"email": "user@gmail.com", "name": None, "picture": None}
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "email": data.get("email") or "user@gmail.com",
                "name": data.get("name"),
                "picture": data.get("picture"),
            }
    except Exception:
        return {"email": "user@gmail.com", "name": None, "picture": None}


def _fetch_email(access_token: str | None) -> str:
    return _fetch_profile(access_token).get("email") or "user@gmail.com"


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


def _clean_sender(value: str) -> str:
    """Extract the bare email address from a 'From' header (Name <email>)."""
    from email.utils import parseaddr
    _, addr = parseaddr(value or "")
    return addr or value or "unknown@gmail.com"


def _parse_gmail_date(value: str) -> str:
    """Convert a Gmail RFC-2822 'Date' header to an ISO-8601 string.

    Gmail returns e.g. 'Sun, 07 Jun 2026 09:03:49 +0000' which isn't a valid
    ISO datetime; the API response model needs ISO. Falls back to now on failure.
    """
    if value:
        try:
            return parsedate_to_datetime(value).isoformat()
        except Exception:
            pass
    return datetime.utcnow().isoformat() + "Z"


def _raise_for_gmail(resp: "httpx.Response") -> None:
    """Convert a Gmail API error response into a clean HTTPException with the real reason."""
    if resp.status_code < 400:
        return
    detail = f"Gmail API error {resp.status_code}"
    try:
        err = resp.json().get("error", {})
        msg = err.get("message") if isinstance(err, dict) else str(err)
        if msg:
            detail = f"Gmail API: {msg}"
    except Exception:
        pass
    from fastapi import HTTPException
    # 401/403 = re-auth needed; everything else is an upstream gateway error.
    code = 401 if resp.status_code in (401, 403) else 502
    raise HTTPException(status_code=code, detail=detail)


def _html_to_text(html: str) -> str:
    """Strip HTML to clean plain text for agent (LLM) processing.

    Removes style/script blocks entirely (including CSS @media rules and
    JSON-LD schema blobs) before stripping tags, so the LLM only sees
    the actual readable email content.
    """
    import re
    # Remove style and script blocks entirely (content + tags)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    # Replace block-level tags with newlines before stripping
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</(p|div|li|tr|h[1-6]|blockquote|table|td|th)>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<li[^>]*>', '• ', html, flags=re.IGNORECASE)
    # Remove all remaining tags
    html = re.sub(r'<[^>]+>', '', html)
    # Decode common HTML entities
    html = html.replace('&nbsp;', ' ').replace('&amp;', '&') \
               .replace('&lt;', '<').replace('&gt;', '>') \
               .replace('&quot;', '"').replace('&#39;', "'") \
               .replace('&#160;', ' ')
    # Collapse excessive blank lines
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


def _extract_body(payload: dict[str, Any]) -> tuple[str, str]:
    """Extract email body, returning (html_body, plain_text).

    Prefers text/html for display; also returns a plain-text version
    for agent processing. Falls back to text/plain if no HTML present.
    Returns ('', '') on failure.
    """
    if not payload:
        return '', ''

    html_body = ''
    plain_body = ''

    def _walk(node: dict[str, Any]) -> None:
        nonlocal html_body, plain_body
        mime = node.get("mimeType", "")
        data = (node.get("body") or {}).get("data", "")
        if mime == "text/html" and data and not html_body:
            html_body = _decode_part(data)
        elif mime == "text/plain" and data and not plain_body:
            plain_body = _decode_part(data)
        for part in node.get("parts", []) or []:
            _walk(part)

    _walk(payload)

    if html_body:
        # Use HTML for display; derive plain text for agents
        agent_text = _html_to_text(html_body)
        return html_body, agent_text
    # Plain text only — same value for both
    return '', plain_body


def _refresh_google_token(refresh_token: str) -> dict[str, Any] | None:
    """Exchange a refresh token for a new access token. Pure — no global state.

    Returns ``{access_token, expires_in}`` or None on failure. Used by
    account-bound clients so a refresh only ever updates that one account.
    """
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
            return resp.json()
    except Exception:
        return None


class GmailClient:
    """Gmail client with the same surface as GraphClient (mock + live)."""

    def __init__(self, settings_obj=settings, *, access_token: str | None = None, refresh_token: str | None = None):
        self.settings = settings_obj
        self.use_mock = bool(self.settings.use_mock_graph)
        # When tokens are injected at construction (v3 AccountService path),
        # they take precedence over the global process-level cache.
        self._injected_access_token = access_token
        self._injected_refresh_token = refresh_token

    def _get_token(self) -> str:
        """Return the active access token: injected first, then global cache."""
        if self._injected_access_token:
            return self._injected_access_token
        return _get_access_token()

    def _refresh_injected_token(self) -> str | None:
        """
        Refresh an injected (DB-sourced) access token using the injected refresh token.
        Updates self._injected_access_token so subsequent _get_token() calls use the
        fresh token. Falls back to the global _refresh_access_token() if no injected
        refresh token is available.
        """
        if self._injected_refresh_token:
            resp = httpx.post(
                _TOKEN_URI,
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "refresh_token": self._injected_refresh_token,
                    "grant_type": "refresh_token",
                },
                timeout=15.0,
            )
            tok = resp.json() if resp.status_code == 200 else {}
            new_token = tok.get("access_token")
            if new_token:
                self._injected_access_token = new_token
                logger.info("[gmail] Injected access token refreshed via injected refresh token")
                return new_token
            logger.warning("[gmail] Injected refresh token exchange failed: %s", tok.get("error"))

        # Fall back to global refresh (file-based token store)
        refreshed = _refresh_access_token()
        if refreshed:
            self._injected_access_token = refreshed
        return refreshed

    # ── identity ──────────────────────────────────────────────────────────────

    def _own_email(self) -> str | None:
        """Return the authenticated user's email address (best-effort)."""
        if self._injected_access_token:
            try:
                profile = self._request("GET", "/profile") or {}
                return profile.get("emailAddress")
            except Exception:
                pass
        return _token_cache.get("email") or _load_tokens().get("email")

    def get_user_profile(self) -> dict[str, str | None]:
        """Return the signed-in Google profile for display in the app shell."""
        if self.use_mock:
            return {
                "email": self._own_email() or "user@gmail.com",
                "display_name": "Google User",
                "photo_url": None,
            }
        stored = _load_tokens()
        profile = {
            "email": self._own_email(),
            "display_name": stored.get("name"),
            "photo_url": stored.get("picture"),
        }
        try:
            live = _fetch_profile(self._get_token())
            profile["email"] = live.get("email") or profile["email"]
            profile["display_name"] = live.get("name") or profile["display_name"]
            profile["photo_url"] = live.get("picture") or profile["photo_url"]
            _save_tokens({
                "email": profile["email"],
                "name": profile["display_name"],
                "picture": profile["photo_url"],
            })
        except Exception:
            pass
        return profile

    # ── helpers ──
    def _request(self, method: str, path: str, **kwargs) -> Any:
        token = self._get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Accept", "application/json")
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, f"{_GMAIL_API}{path}", headers=headers, **kwargs)

        # On 401, the access token was rejected by Google — it may have been revoked
        # or expired server-side (happens after session logout + quick login where the
        # DB-injected token is stale). Refresh and retry once regardless of whether
        # the token was injected or came from the global cache.
        if resp.status_code == 401:
            logger.info("[gmail] 401 received — refreshing token and retrying")
            # Clear global cache so _get_access_token() forces a real refresh
            _token_cache["access_token"] = None
            _token_cache["expires_at"] = 0.0
            refreshed = self._refresh_injected_token()
            if refreshed:
                headers["Authorization"] = f"Bearer {refreshed}"
                with httpx.Client(timeout=30.0) as client:
                    resp = client.request(method, f"{_GMAIL_API}{path}", headers=headers, **kwargs)

        _raise_for_gmail(resp)
        if resp.status_code in (202, 204) or not resp.content:
            return None
        return resp.json()

    def _has_attachment(self, payload: dict[str, Any]) -> bool:
        for part in payload.get("parts", []) or []:
            if part.get("filename"):
                return True
            if self._has_attachment(part):
                return True
        return False

    def _extract_attachments(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Collect attachment metadata (filename, mime, size, attachmentId).

        The actual bytes are fetched lazily via GET /messages/{id}/attachments/{attId}
        only when the user clicks download.
        """
        out: list[dict[str, Any]] = []

        def _walk(node: dict[str, Any]) -> None:
            for part in node.get("parts", []) or []:
                filename = part.get("filename") or ""
                body = part.get("body") or {}
                att_id = body.get("attachmentId")
                # Real attachments have a filename AND an attachmentId
                if filename and att_id:
                    out.append({
                        "attachment_id": att_id,
                        "filename": filename,
                        "mime_type": part.get("mimeType", "application/octet-stream"),
                        "size": body.get("size", 0),
                    })
                _walk(part)

        _walk(payload)
        return out

    def list_attachments(self, message_id: str) -> list[dict[str, Any]]:
        """Return attachment metadata for a Gmail message (id, filename, mime_type, size).

        Fetches the message envelope (no body bytes) and walks the MIME tree to
        collect every part that has a filename and attachmentId. The actual bytes
        are only fetched when the user clicks download via get_attachment().
        """
        if self.use_mock:
            return []
        msg = self._request("GET", f"/messages/{message_id}?format=metadata&metadataHeaders=Subject")
        if not msg:
            return []
        return self._extract_attachments(msg.get("payload") or {})

    def get_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any] | None:
        """Fetch raw attachment bytes (base64url) for download."""
        if self.use_mock:
            return None
        return self._request("GET", f"/messages/{message_id}/attachments/{attachment_id}")

    def _list_formatted(self, label: str, limit: int, date_field: str = "received_at") -> List[dict[str, Any]]:
        data = self._request("GET", f"/messages?labelIds={label}&maxResults={limit}")
        ids = [m["id"] for m in (data or {}).get("messages", [])]
        return self._fetch_many(ids)

    # ── Mail actions (label-based) ──
    def mark_read(self, email_id: str, read: bool = True) -> None:
        if self.use_mock:
            return
        body = {"removeLabelIds": ["UNREAD"]} if read else {"addLabelIds": ["UNREAD"]}
        self._request("POST", f"/messages/{email_id}/modify", json=body)

    def archive(self, email_id: str) -> None:
        if self.use_mock:
            return
        self._request("POST", f"/messages/{email_id}/modify", json={"removeLabelIds": ["INBOX"]})

    def report_spam(self, email_id: str) -> None:
        if self.use_mock:
            return
        self._request(
            "POST", f"/messages/{email_id}/modify",
            json={"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
        )

    def forward_email(self, email_id: str, to: str, comment: str = "") -> None:
        if self.use_mock:
            print(f"[MOCK GMAIL] Forward {email_id} to {to}")
            return
        original = self._request("GET", f"/messages/{email_id}?format=full")
        payload = (original or {}).get("payload", {})
        headers = payload.get("headers", [])
        subject = _header(headers, "Subject")
        _html, orig_body = _extract_body(payload)
        orig_body = orig_body or (original or {}).get("snippet", "")
        fwd_body = f"{comment}\n\n---------- Forwarded message ----------\n{orig_body}"
        raw = self._build_raw(to, f"Fwd: {subject}", fwd_body)
        self._request("POST", "/messages/send", json={"raw": raw})

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
                "is_read": False, "has_attachments": False,
            },
            {
                "email_id": "gmail-2",
                "sender": "team@notion.so",
                "subject": "Weekly digest: 4 pages updated",
                "body": "Here's what changed in your workspace this week. 4 pages were updated by your team.",
                "received_at": (now - timedelta(hours=3)).isoformat() + "Z",
                "is_read": True, "has_attachments": True,
            },
            {
                "email_id": "gmail-3",
                "sender": "ravi.kumar@gmail.com",
                "subject": "Lunch next week?",
                "body": "Hey! Are you free for lunch sometime next week? Let me know what day works.",
                "received_at": (now - timedelta(hours=20)).isoformat() + "Z",
                "is_read": False, "has_attachments": False,
            },
        ]

    _LABELS = {"inbox": "INBOX", "sent": "SENT", "drafts": "DRAFT", "spam": "SPAM", "trash": "TRASH"}

    def list_emails(self, folder: str = "inbox", limit: int = 50,
                    page_token: str | None = None, query: str | None = None) -> dict[str, Any]:
        """Unified paginated listing for any folder with optional search."""
        label = self._LABELS.get(folder, "INBOX")
        if self.use_mock:
            source = self._mock_inbox() if folder == "inbox" else []
            if query:
                q = query.lower()
                source = [m for m in source if q in m["subject"].lower() or q in m["sender"].lower()]
            return {"emails": source[:limit], "next_page_token": None, "total": len(source)}

        params = [f"maxResults={limit}", f"labelIds={label}"]
        if page_token:
            params.append(f"pageToken={page_token}")
        if query:
            from urllib.parse import quote
            params.append(f"q={quote(query)}")
        data = self._request("GET", f"/messages?{'&'.join(params)}") or {}
        ids = [m["id"] for m in data.get("messages", [])]
        emails = self._fetch_many(ids)
        return {
            "emails": emails,
            "next_page_token": data.get("nextPageToken"),
            "total": int(data.get("resultSizeEstimate", len(emails))),
        }

    # ── Delta sync (users.history.list) ───────────────────────────────────────

    def list_inbox_delta(self, history_id: str | None = None, folder: str = "inbox") -> dict[str, Any]:
        """
        True Gmail delta sync via users.history.list.

        history_id=None  → first-time backfill: snapshot + capture current historyId.
        history_id=str   → incremental: replay changes since that historyId.

        Returns { upserts, removed, delta_cursor (new historyId), truncated }.
        delta_cursor is stored in mailbox_sync_state.delta_cursor by SyncService.
        """
        if self.use_mock:
            page = self.list_emails(folder=folder, limit=50)
            return {"upserts": page.get("emails", []), "removed": [],
                    "delta_cursor": "mock-history-1", "truncated": False}

        label = self._LABELS.get(folder, "INBOX")
        if not history_id:
            return self._gmail_snapshot_with_cursor(label)
        return self._gmail_history_delta(history_id, label)

    def _gmail_snapshot_with_cursor(self, label: str) -> dict[str, Any]:
        """Full snapshot + capture the current historyId for future delta calls."""
        try:
            current_history_id = (self._request("GET", "/profile") or {}).get("historyId")
        except Exception:
            current_history_id = None

        all_emails: list[dict] = []
        page_token: str | None = None
        pages = 0
        truncated = False

        while pages < 10:  # max 500 messages on backfill
            params = ["maxResults=50", f"labelIds={label}"]
            if page_token:
                params.append(f"pageToken={page_token}")
            data = self._request("GET", f"/messages?{'&'.join(params)}") or {}
            ids = [m["id"] for m in data.get("messages", [])]
            if ids:
                all_emails.extend(self._fetch_many(ids))
            page_token = data.get("nextPageToken")
            pages += 1
            if not page_token:
                break
        else:
            truncated = True

        return {
            "upserts": all_emails,
            "removed": [],
            "delta_cursor": current_history_id,
            "truncated": truncated,
        }

    def _gmail_history_delta(self, history_id: str, label: str) -> dict[str, Any]:
        """Replay Gmail history since history_id; returns upserts + removed ids."""
        upsert_ids: set[str] = set()
        removed_ids: set[str] = set()
        new_history_id = history_id
        page_token: str | None = None
        pages = 0

        while pages < 20:
            params = [
                f"startHistoryId={history_id}",
                "historyTypes=messageAdded",
                "historyTypes=messageDeleted",
                "historyTypes=labelAdded",
                "historyTypes=labelRemoved",
                f"labelId={label}",
                "maxResults=500",
            ]
            if page_token:
                params.append(f"pageToken={page_token}")

            try:
                data = self._request("GET", f"/history?{'&'.join(params)}") or {}
            except Exception as exc:
                # historyId is too old (Gmail purges after ~30 days) → full re-snapshot
                logger.warning("[gmail] historyId %s too old (%s) — falling back to snapshot", history_id, exc)
                return self._gmail_snapshot_with_cursor(label)

            new_history_id = data.get("historyId", new_history_id)

            for record in data.get("history", []):
                for item in record.get("messagesAdded", []):
                    mid = (item.get("message") or {}).get("id")
                    if mid:
                        upsert_ids.add(mid)
                        removed_ids.discard(mid)

                for item in record.get("messagesDeleted", []):
                    mid = (item.get("message") or {}).get("id")
                    if mid:
                        removed_ids.add(mid)
                        upsert_ids.discard(mid)

                # INBOX label added → message moved back into inbox
                for item in record.get("labelsAdded", []):
                    if label in (item.get("labelIds") or []):
                        mid = (item.get("message") or {}).get("id")
                        if mid:
                            upsert_ids.add(mid)
                            removed_ids.discard(mid)

                # INBOX label removed → archived or trashed
                for item in record.get("labelsRemoved", []):
                    if label in (item.get("labelIds") or []):
                        mid = (item.get("message") or {}).get("id")
                        if mid:
                            removed_ids.add(mid)
                            upsert_ids.discard(mid)

            page_token = data.get("nextPageToken")
            pages += 1
            if not page_token:
                break

        upserts = self._fetch_many(list(upsert_ids)) if upsert_ids else []
        return {
            "upserts": upserts,
            "removed": list(removed_ids),
            "delta_cursor": new_history_id,
            "truncated": pages >= 20,
        }

    # ── Push notifications (Cloud Pub/Sub watch) ──────────────────────────────

    def watch_inbox(self, topic_name: str) -> dict[str, Any]:
        """
        Register a Gmail push watch on the INBOX label.

        Gmail publishes a notification to ``topic_name`` (a Cloud Pub/Sub topic)
        whenever the mailbox changes. Returns {historyId, expiration} where
        expiration is epoch-millis (~7 days out). Must be re-called before it
        lapses — Gmail enforces a 7-day max and stops silently after that.
        """
        if self.use_mock:
            return {"historyId": "mock-history-1",
                    "expiration": str(int((time.time() + 7 * 86400) * 1000))}
        body = {
            "topicName": topic_name,
            "labelIds": ["INBOX"],
            "labelFilterBehavior": "INCLUDE",
        }
        return self._request("POST", "/watch", json=body) or {}

    def stop_watch(self) -> None:
        """Stop all Gmail push notifications for this account (best-effort)."""
        if self.use_mock:
            return
        try:
            self._request("POST", "/stop")
        except Exception as e:
            logger.debug("[gmail] stop watch failed: %s", e)

    def _fetch_many(self, ids: list[str]) -> list[dict[str, Any]]:
        """Fetch + format many messages concurrently (Gmail has no batch GET, so
        parallel requests turn ~50 sequential round-trips into a few batches)."""
        if not ids:
            return []
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(self._format_one, ids))
        return [e for e in results if e]

    def _format_one(self, mid: str) -> dict[str, Any] | None:
        msg = self._request("GET", f"/messages/{mid}?format=full")
        if not msg:
            return None
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        label_ids = msg.get("labelIds", [])
        html_body, plain_body = _extract_body(payload)
        snippet = msg.get("snippet", "")
        # Plain-text body for agents: prefer extracted plain → HTML-stripped → snippet
        agent_body = plain_body or (_html_to_text(html_body) if html_body else snippet)
        attachments = self._extract_attachments(payload)
        return {
            "email_id": msg.get("id", ""),
            "sender": _clean_sender(_header(headers, "From")),
            "subject": _header(headers, "Subject"),
            # html_body: sent to frontend for display (preserves formatting + images)
            # body: plain text sent to agents for LLM processing (no HTML tags)
            "html_body": html_body or None,
            "body": agent_body,
            "received_at": _parse_gmail_date(_header(headers, "Date")),
            "is_read": "UNREAD" not in label_ids,
            "has_attachments": bool(attachments),
            "attachments": attachments,
        }

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

    def reply_all(self, email_id: str, comment: str) -> None:
        if self.use_mock:
            print(f"[MOCK GMAIL] Reply-all to {email_id}: {comment}")
            return
        original = self._request("GET", f"/messages/{email_id}?format=metadata")
        headers = (original or {}).get("payload", {}).get("headers", [])
        thread_id = (original or {}).get("threadId")
        subject = _header(headers, "Subject")
        # Recipients = original sender + everyone on To/Cc (excluding self).
        recipients = {_clean_sender(_header(headers, "From"))}
        for field in ("To", "Cc"):
            for addr in (_header(headers, field) or "").split(","):
                clean = _clean_sender(addr)
                if "@" in clean:
                    recipients.add(clean)
        recipients.discard(self._own_email())
        to = ", ".join(sorted(r for r in recipients if r))
        raw = self._build_raw(to, f"Re: {subject}", comment)
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
        token = self._get_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, url, headers=headers, **kwargs)
        _raise_for_gmail(resp)
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
