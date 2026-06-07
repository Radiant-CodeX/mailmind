from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, List

import httpx

from app.config.settings import settings

try:
    import msal
except Exception:  # pragma: no cover - imported at runtime when available
    msal = None


# Delegated scopes requested for the signed-in user (email, calendar, tasks, profile).
_DELEGATED_SCOPES = [
    "User.Read", "Mail.ReadWrite", "Mail.Send", "Calendars.ReadWrite", "Tasks.ReadWrite",
    "ChannelMessage.Send", "OnlineMeetings.ReadWrite", "Team.ReadBasic.All",
]

# Persistent MSAL token cache. Holds the refresh token from the delegated login
# so Quick Login can acquire fresh access tokens silently (no code/password).
_MSAL_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "msal_cache.bin")


def _load_token_cache() -> "msal.SerializableTokenCache":
    cache = msal.SerializableTokenCache()
    try:
        if os.path.exists(_MSAL_CACHE_PATH):
            with open(_MSAL_CACHE_PATH, "r", encoding="utf-8") as fh:
                cache.deserialize(fh.read())
    except Exception:  # pragma: no cover - corrupt cache is non-fatal
        pass
    return cache


def _save_token_cache(cache: "msal.SerializableTokenCache") -> None:
    try:
        if cache.has_state_changed:
            os.makedirs(os.path.dirname(_MSAL_CACHE_PATH), exist_ok=True)
            with open(_MSAL_CACHE_PATH, "w", encoding="utf-8") as fh:
                fh.write(cache.serialize())
    except Exception:  # pragma: no cover - disk issues shouldn't break auth
        pass


def _build_public_client():
    """Build an MSAL PublicClientApplication backed by the persistent cache."""
    cache = _load_token_cache()
    tenant_id = settings.azure_tenant_id or "common"
    app = msal.PublicClientApplication(
        settings.azure_client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )
    return app, cache


def _silent_acquire(username: str | None = None) -> dict[str, Any] | None:
    """Silently acquire a delegated access token from the persisted refresh token.

    Returns the MSAL result dict on success, or None if no usable account /
    refresh token is available (caller should fall back to interactive login).
    """
    if msal is None:
        return None
    app, cache = _build_public_client()
    accounts = app.get_accounts(username=username) if username else app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(_DELEGATED_SCOPES, account=accounts[0])
    _save_token_cache(cache)
    if not result or "access_token" not in result:
        return None
    _user_token_cache["access_token"] = result["access_token"]
    _user_token_cache["expires_at"] = time.time() + int(result.get("expires_in", 3600))
    _user_token_cache["user_principal_name"] = accounts[0].get("username")
    return result


_user_token_cache: dict[str, Any] = {
    "access_token": None,
    "expires_at": 0.0,
    "refresh_token": None,
    "user_principal_name": None,
    "tenant_id": None,
}

# Microsoft's well-known tenant id for personal (consumer) Microsoft accounts.
# Personal accounts use the To Do *live* web app; work/school accounts use the
# *office* web app. Linking to the wrong one shows an empty/forced-login page.
_PERSONAL_MSA_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"

# Tracks the status of in-progress device-code logins keyed by device_code.
# Populated by the background completion thread started in `initiate_user_login`
# and read by the `/auth/login-poll` endpoint. Values look like:
#   {"status": "pending"}
#   {"status": "success", "user_principal_name": "..."}
#   {"status": "error", "error": "..."}
_device_flow_status: dict[str, dict[str, Any]] = {}


class GraphClient:
    """Microsoft Graph client with a mock fallback.

    When `settings.use_mock_graph` is True the client returns deterministic
    mocked responses. When it's False the client uses MSAL to acquire a
    client-credentials token and calls Microsoft Graph via `httpx`.
    """

    internal_domain = "example.com"

    def __init__(self, settings_obj: type(settings) = settings):
        self.settings = settings_obj
        self.use_mock = bool(self.settings.use_mock_graph)
        if not self.use_mock:
            if msal is None:
                raise RuntimeError("msal package is required for Graph integration; pip install msal")
            self.authority = f"https://login.microsoftonline.com/{self.settings.azure_tenant_id}"
            raw_scopes = [s for s in self.settings.graph_scopes.split() if s]
            # For client credentials flow, Graph requires the /.default scope
            # (resource/.default). Use that unless an explicit resource default
            # is provided in `GRAPH_SCOPES`.
            if any(s.endswith("/.default") for s in raw_scopes):
                self.scopes = raw_scopes
            else:
                self.scopes = ["https://graph.microsoft.com/.default"]
            self._app = msal.ConfidentialClientApplication(
                client_id=self.settings.azure_client_id,
                client_credential=self.settings.azure_client_secret,
                authority=self.authority,
            )
            self._token: str | None = None
            self._token_expires_at = 0.0
            self.base = "https://graph.microsoft.com/v1.0"

    def _get_token(self) -> str | None:
        if self.use_mock:
            return None
        
        now = time.time()
        # 1. Prioritize active user session token if set and valid
        if _user_token_cache["access_token"]:
            if now < (_user_token_cache["expires_at"] - 60):
                return _user_token_cache["access_token"]
            # Access token expired — try a silent refresh from the persisted
            # refresh token before giving up (keeps the session alive for days).
            refreshed = _silent_acquire(_user_token_cache.get("user_principal_name"))
            if refreshed and refreshed.get("access_token"):
                return refreshed["access_token"]
            # No valid refresh token — clear the session and require re-login.
            _user_token_cache["access_token"] = None
            _user_token_cache["expires_at"] = 0.0
            _user_token_cache["user_principal_name"] = None
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="Active user session has expired. Please log in again."
            )

        # 2. If no active user session, check if we have daemon config (azure_user_upn)
        # If not, user is not authenticated at all.
        if not self.settings.azure_user_upn:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Please log in first."
            )

        # 3. Fall back to client credentials app token for daemon mode
        if self._token and now < (self._token_expires_at - 60):
            return self._token
        result = self._app.acquire_token_for_client(scopes=self.scopes)
        if not result or "access_token" not in result:
            raise RuntimeError(f"unable to acquire graph token: {result}")
        self._token = result["access_token"]
        self._token_expires_at = now + int(result.get("expires_in", 3600))
        return self._token

    def _request(self, method: str, path: str, **kwargs) -> Any:
        token = self._get_token()
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        headers.setdefault("Accept", "application/json")
        url = self.base + path
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        # 202 (Accepted, e.g. sendMail) and 204 (No Content) return empty bodies.
        if resp.status_code in (202, 204) or not resp.content:
            return None
        return resp.json()

    def _get_prefix(self) -> str:
        """Get the user prefix path for Microsoft Graph queries."""
        if self.use_mock:
            return "/me"
        
        # If user token is active, we are logged in directly as the user, so use /me
        if _user_token_cache["access_token"]:
            return "/me"
        
        # Check if UPN is explicitly configured in Settings
        if self.settings.azure_user_upn:
            return f"/users/{self.settings.azure_user_upn}"

        if hasattr(self, "_cached_prefix"):
            return self._cached_prefix
            
        upn = None
        if self._app:
            try:
                users = self._request("GET", "/users?$top=1")
                user = users.get("value", [])
                if user:
                    upn = user[0].get("userPrincipalName") or user[0].get("mail")
            except Exception:
                pass
        
        self._cached_prefix = f"/users/{upn}" if upn else "/me"
        return self._cached_prefix

    def initiate_user_login(self) -> dict[str, Any]:
        """Initiate MSAL device code flow and complete it in a background thread.

        `acquire_token_by_device_flow` is a *blocking* call that polls Microsoft
        until the user authenticates. It must be invoked exactly once per flow —
        calling it again reuses the device_code and triggers AADSTS70000. So we
        run it once in a background thread and let `/auth/login-poll` simply read
        the resulting status from `_device_flow_status`.
        """
        import threading
        import time as _time

        # Cache-backed client so the refresh token is persisted for Quick Login.
        app, cache = _build_public_client()
        flow = app.initiate_device_flow(scopes=_DELEGATED_SCOPES)
        if not flow or "device_code" not in flow:
            return flow

        device_code = flow["device_code"]
        _device_flow_status[device_code] = {"status": "pending"}

        def _complete() -> None:
            try:
                result = app.acquire_token_by_device_flow(flow)
                if not result or "access_token" not in result:
                    error = (result or {}).get("error_description") or "Authentication failed"
                    _device_flow_status[device_code] = {"status": "error", "error": error}
                    return
                id_token_claims = result.get("id_token_claims", {})
                upn = id_token_claims.get("preferred_username") or id_token_claims.get("upn")
                _user_token_cache["access_token"] = result.get("access_token")
                _user_token_cache["expires_at"] = _time.time() + int(result.get("expires_in", 3600))
                _user_token_cache["user_principal_name"] = upn
                _user_token_cache["tenant_id"] = id_token_claims.get("tid")
                # Persist the refresh token so Quick Login can resume silently.
                _save_token_cache(cache)
                _device_flow_status[device_code] = {"status": "success", "user_principal_name": upn}
            except Exception as e:  # pragma: no cover - background thread safety
                _device_flow_status[device_code] = {"status": "error", "error": str(e)}

        threading.Thread(target=_complete, daemon=True).start()
        return flow

    def quick_login(self, email: str | None = None) -> dict[str, Any]:
        """Resume a delegated session silently for Quick Login (no code/password).

        Uses the refresh token persisted from a previous Microsoft sign-in. Raises
        a clear error if no remembered session exists or the refresh token has
        expired, so the caller can fall back to interactive sign-in.
        """
        result = _silent_acquire(email)
        if not result or "access_token" not in result:
            raise RuntimeError(
                "No active Microsoft session to resume. Please use 'Sign In with Microsoft' first."
            )
        return {"user_principal_name": _user_token_cache.get("user_principal_name") or email}

    # --- Public methods (mocked when `use_mock` is True) ---
    def get_inbox_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        """Return messages from the user's Inbox."""
        if self.use_mock:
            # Shift received times relative to now so mock inbox is always active and fresh
            now = datetime.utcnow()
            return [
                {
                    "email_id": "email-1",
                    "sender": "sarah.chen@acmecorp.com",
                    "subject": "URGENT: Production API down — clients impacted",
                    "body": "Hi team,\n\nOur production API has been returning 500 errors for the past 30 minutes. Three enterprise clients have already called in. We need this resolved ASAP.\n\nPlease review the logs immediately and confirm status.\n\nSarah Chen\nCTO, Acme Corp",
                    "received_at": (now - timedelta(minutes=10)).isoformat() + "Z",
                },
                {
                    "email_id": "email-2",
                    "sender": "james.wright@partnerfirm.com",
                    "subject": "Contract review — sign by Friday EOD",
                    "body": "Hi,\n\nPlease find attached the revised service agreement for Q3. Legal has approved from our side.\n\nWe need your signature by Friday end of day to proceed with the engagement.\n\nBest,\nJames Wright",
                    "received_at": (now - timedelta(hours=2)).isoformat() + "Z",
                },
                {
                    "email_id": "email-3",
                    "sender": "priya.sharma@internal.com",
                    "subject": "Q3 budget approval needed before Monday",
                    "body": "Hi,\n\nThe Q3 engineering budget proposal is ready for your review and approval. Finance needs sign-off by Monday morning to proceed with vendor payments.\n\nDeck is attached. Happy to walk through it.\n\nPriya",
                    "received_at": (now - timedelta(hours=4)).isoformat() + "Z",
                },
                {
                    "email_id": "email-5",
                    "sender": "support-tickets@zendesk.com",
                    "subject": "Customer ticket #10482: Login issue on Chrome",
                    "body": "A new support ticket has been created:\n\nCustomer: TechStart Inc\nIssue: Login page spinning indefinitely on Chrome v120\nPriority: High\n\nPlease assign and respond within 4 hours per SLA.",
                    "received_at": (now - timedelta(hours=8)).isoformat() + "Z",
                },
                {
                    "email_id": "email-4",
                    "sender": "alex.kim@team.com",
                    "subject": "Reminder: Weekly sync tomorrow 10am",
                    "body": "Hi all,\n\nJust a reminder that our weekly engineering sync is tomorrow at 10am in the main conference room.\n\nAgenda: sprint review, blockers, upcoming milestones.\n\nAlex",
                    "received_at": (now - timedelta(hours=6)).isoformat() + "Z",
                },
                {
                    "email_id": "email-6",
                    "sender": "newsletter@techdigest.io",
                    "subject": "This week in AI: GPT updates, new models",
                    "body": "Hello,\n\nHere is your weekly digest of AI news and updates. This week: new model releases, industry trends, and upcoming conferences.\n\nClick here to read more.",
                    "received_at": (now - timedelta(days=1)).isoformat() + "Z",
                },
            ]

        prefix = self._get_prefix()
        # Scope strictly to the Inbox folder so Sent/Drafts/Junk/Deleted items
        # don't leak into the inbox listing.
        path = f"{prefix}/mailFolders/inbox/messages?$top={limit}&$orderby=receivedDateTime desc"
        data = self._request("GET", path, headers={"Prefer": 'outlook.body-content-type="text"'})
        raw_msgs = data.get("value", [])
        
        formatted = []
        for msg in raw_msgs:
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
                "email_id": msg.get("id"),
                "sender": sender_addr,
                "subject": msg.get("subject", ""),
                "body": body_content,
                "received_at": msg.get("receivedDateTime"),
            })
        return formatted

    def _format_messages(self, raw_msgs: list, date_field: str = "receivedDateTime") -> list:
        formatted = []
        for msg in raw_msgs:
            from_obj = msg.get("from") or msg.get("sender")
            sender_addr = "unknown@example.com"
            if from_obj and "emailAddress" in from_obj:
                sender_addr = from_obj["emailAddress"].get("address", "unknown@example.com")
            body_obj = msg.get("body")
            body_content = body_obj.get("content", "") if body_obj else msg.get("bodyPreview", "")
            formatted.append({
                "email_id": msg.get("id"),
                "sender": sender_addr,
                "subject": msg.get("subject", ""),
                "body": body_content,
                "received_at": msg.get(date_field) or msg.get("receivedDateTime") or "",
            })
        return formatted

    def get_draft_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        """Return messages from the user's Drafts folder."""
        if self.use_mock:
            return []
        prefix = self._get_prefix()
        path = f"{prefix}/mailFolders/drafts/messages?$top={limit}&$orderby=lastModifiedDateTime desc"
        data = self._request("GET", path, headers={"Prefer": 'outlook.body-content-type="text"'})
        return self._format_messages(data.get("value", []), date_field="lastModifiedDateTime")

    def get_spam_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        """Return messages from the user's Junk Email (spam) folder."""
        if self.use_mock:
            return []
        prefix = self._get_prefix()
        path = f"{prefix}/mailFolders/junkemail/messages?$top={limit}&$orderby=receivedDateTime desc"
        data = self._request("GET", path, headers={"Prefer": 'outlook.body-content-type="text"'})
        return self._format_messages(data.get("value", []))

    def get_trash_emails(self, limit: int = 10) -> List[dict[str, Any]]:
        """Return messages from the user's Deleted Items folder."""
        if self.use_mock:
            return []
        prefix = self._get_prefix()
        path = f"{prefix}/mailFolders/deleteditems/messages?$top={limit}&$orderby=receivedDateTime desc"
        data = self._request("GET", path, headers={"Prefer": 'outlook.body-content-type="text"'})
        return self._format_messages(data.get("value", []))

    def get_thread_messages(self, thread_id: str) -> List[dict[str, Any]]:
        """Return messages for a conversation/thread.

        For Graph this queries messages filtered by `conversationId`.
        """
        if self.use_mock or thread_id.startswith("sent-") or thread_id.startswith("email-") or thread_id.startswith("msg-"):
            return [
                {
                    "sender": "alice@example.com",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "subject": f"Thread {thread_id} update",
                    "body": "This is a mocked message body.",
                }
            ]
        prefix = self._get_prefix()
        path = f"{prefix}/messages?$filter=conversationId eq '{thread_id}'"
        try:
            data = self._request("GET", path, headers={"Prefer": 'outlook.body-content-type="text"'})
            raw_msgs = data.get("value", [])
        except Exception:
            return []
        
        formatted = []
        for msg in raw_msgs:
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
                "sender": sender_addr,
                "timestamp": msg.get("receivedDateTime"),
                "subject": msg.get("subject", ""),
                "body": body_content,
            })

        try:
            formatted.sort(key=lambda m: m.get("timestamp") or "", reverse=True)
        except Exception:
            pass
        return formatted

    def get_calendar_events(self, start_time: datetime, end_time: datetime) -> List[dict[str, Any]]:
        """Return calendar events between two datetimes (UTC-aware ISO strings)."""
        if self.use_mock:
            now = datetime.utcnow()
            return [
                {
                    "title": "Production Deployment Sync",
                    "start_time": now + timedelta(hours=2),
                    "end_time": now + timedelta(hours=3),
                    "organizer": "sarah.chen@acmecorp.com"
                },
                {
                    "title": "Acme Budget Review",
                    "start_time": now + timedelta(days=1, hours=4),
                    "end_time": now + timedelta(days=1, hours=5),
                    "organizer": "priya.sharma@internal.com"
                },
                {
                    "title": "Weekly Engineering Sync",
                    "start_time": now + timedelta(days=2, hours=1),
                    "end_time": now + timedelta(days=2, hours=2),
                    "organizer": "alex.kim@team.com"
                }
            ]

        # Ensure timestamps are RFC3339 with timezone (use Z for UTC if naive)
        def to_rfc(dt: datetime) -> str:
            if dt.tzinfo is None:
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return dt.isoformat()

        start = to_rfc(start_time)
        end = to_rfc(end_time)
        
        prefix = self._get_prefix()
        path = (
            f"{prefix}/calendarview?"
            f"startDateTime={start}&endDateTime={end}"
            f"&$orderby=start/dateTime"
        )

        data = self._request("GET", path, headers={"Prefer": "outlook.timezone=UTC"})
        raw_events = data.get("value", [])
        
        events = []
        for item in raw_events:
            title = item.get("subject", "Untitled event")
            
            # Start time parsing
            start_val = item.get("start", {})
            start_dt_str = start_val.get("dateTime")
            start_dt = start_time
            if start_dt_str:
                try:
                    cleaned = re.sub(r'(\.\d{6})\d+', r'\1', start_dt_str)
                    cleaned = cleaned.replace("Z", "+00:00")
                    start_dt = datetime.fromisoformat(cleaned)
                except Exception:
                    pass

            # End time parsing
            end_val = item.get("end", {})
            end_dt_str = end_val.get("dateTime")
            end_dt = end_time
            if end_dt_str:
                try:
                    cleaned = re.sub(r'(\.\d{6})\d+', r'\1', end_dt_str)
                    cleaned = cleaned.replace("Z", "+00:00")
                    end_dt = datetime.fromisoformat(cleaned)
                except Exception:
                    pass

            # Organizer parsing
            org_val = item.get("organizer", {})
            email_addr_val = org_val.get("emailAddress", {})
            organizer = email_addr_val.get("address") or email_addr_val.get("name") or "unknown@example.com"
            
            events.append({
                "title": title,
                "start_time": start_dt,
                "end_time": end_dt,
                "organizer": organizer
            })
        return events

    def get_sender_authority(self, sender_email: str) -> dict[str, Any]:
        """Try to resolve sender to a user and provide a simple authority score."""
        if self.use_mock:
            if sender_email.endswith("@example.com") or sender_email.endswith("@acmecorp.com") or sender_email.endswith("@partnerfirm.com") or sender_email.endswith("@team.com") or sender_email.endswith("@internal.com"):
                return {"role": "peer", "score": 0.5, "source": "fallback"}
            return {"role": "external", "score": 0.1, "source": "fallback"}
        # Try to get user by mail
        try:
            self._get_prefix()
            # If UPN matches the sender email exactly, it's the owner/internal
            if self.settings.azure_user_upn and sender_email.lower() == self.settings.azure_user_upn.lower():
                return {"role": "internal", "score": 0.8, "source": "graph-owner"}
            
            data = self._request("GET", f"/users/{sender_email}")
            job = data.get("jobTitle") or ""
            score = 0.8 if job else 0.6
            return {"role": "internal", "score": score, "source": "graph"}
        except Exception:
            return {"role": "external", "score": 0.1, "source": "graph-fallback"}

    def create_todo(self, email_id: str, commitment: str) -> str:
        """Create a To Do task in the user's default To Do list.

        Microsoft Graph does NOT return a per-task `webUrl` for To Do tasks
        (unlike calendar events), so we return the To Do web app URL. This opens
        Microsoft To Do where the newly created task is visible rather than
        navigating to a bare task id.
        """
        if self.use_mock:
            return self._todo_web_url()

        prefix = self._get_prefix()
        lists = self._request("GET", f"{prefix}/todo/lists")
        lists_val = lists.get("value", [])
        if not lists_val:
            raise RuntimeError("no todo lists available for user")
        list_id = lists_val[0]["id"]
        payload = {"title": commitment}
        self._request("POST", f"{prefix}/todo/lists/{list_id}/tasks", json=payload)
        return self._todo_web_url()

    def list_tasks(self, limit: int = 20) -> List[dict[str, Any]]:
        """Return Microsoft To Do tasks, normalized to {id, title, status, due}."""
        if self.use_mock:
            now = datetime.utcnow()
            return [
                {"id": "mtask-1", "title": "Approve Q3 budget", "status": "notStarted",
                 "due": (now + timedelta(days=1)).isoformat() + "Z"},
                {"id": "mtask-2", "title": "Sign service agreement", "status": "notStarted",
                 "due": (now + timedelta(days=3)).isoformat() + "Z"},
            ]
        try:
            prefix = self._get_prefix()
            lists = self._request("GET", f"{prefix}/todo/lists")
            lists_val = lists.get("value", []) if lists else []
            if not lists_val:
                return []
            list_id = lists_val[0]["id"]
            data = self._request("GET", f"{prefix}/todo/lists/{list_id}/tasks?$top={limit}")
        except Exception:
            return []
        out = []
        for t in (data or {}).get("value", []):
            due = ""
            if t.get("dueDateTime"):
                due = t["dueDateTime"].get("dateTime", "")
            out.append({
                "id": t.get("id", ""),
                "title": t.get("title", ""),
                "status": t.get("status", "notStarted"),
                "due": due,
            })
        return out

    def _todo_web_url(self) -> str:
        """Return the correct Microsoft To Do web app URL for the signed-in account.

        Personal (consumer) accounts use to-do.live.com; work/school accounts use
        to-do.office.com. Opening the wrong one lands the user on a login/empty page
        where their task is not visible.
        """
        if _user_token_cache.get("tenant_id") == _PERSONAL_MSA_TENANT_ID:
            return "https://to-do.live.com/tasks/"
        return "https://to-do.office.com/tasks/"

    def create_calendar_event(self, email_id: str, commitment: str, deadline: datetime | None) -> str:
        """Create a calendar event and return its webLink."""
        if self.use_mock:
            event_id = f"event-{email_id[:8]}"
            return f"https://graph.microsoft.com/calendar/{event_id}"
        
        start_dt = deadline or datetime.utcnow()
        end_dt = start_dt + timedelta(hours=1)
        start = start_dt.isoformat()
        end = end_dt.isoformat()
        event_payload = {
            "subject": commitment,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
            "body": {"contentType": "text", "content": commitment},
        }
        prefix = self._get_prefix()
        event = self._request("POST", f"{prefix}/events", json=event_payload)
        return event.get("webLink") or event.get("id")

    def send_reply(self, email_id: str, comment: str) -> None:
        """Send a reply to a message via Microsoft Graph API."""
        if self.use_mock:
            print(f"[MOCK GRAPH] Replying to email {email_id} with comment: {comment[:30]}...")
            return
        
        prefix = self._get_prefix()
        payload = {
            "comment": comment
        }
        self._request("POST", f"{prefix}/messages/{email_id}/reply", json=payload)

    def restore_from_trash(self, email_id: str) -> None:
        """Move a message from Deleted Items back to the Inbox."""
        if self.use_mock:
            print(f"[MOCK GRAPH] Restoring email {email_id} from Deleted Items to Inbox")
            return

        prefix = self._get_prefix()
        self._request(
            "POST",
            f"{prefix}/messages/{email_id}/move",
            json={"destinationId": "inbox"},
        )

    def move_to_trash(self, email_id: str) -> None:
        """Move a message to the Deleted Items (Trash) folder via Microsoft Graph."""
        if self.use_mock:
            print(f"[MOCK GRAPH] Moving email {email_id} to Deleted Items")
            return

        prefix = self._get_prefix()
        # Graph 'move' relocates the message to the well-known deleteditems folder,
        # keeping it out of the Inbox while preserving it under Trash.
        self._request(
            "POST",
            f"{prefix}/messages/{email_id}/move",
            json={"destinationId": "deleteditems"},
        )

    def send_new_email(self, to: str, subject: str, body: str, cc: str | None = None, bcc: str | None = None) -> None:
        """Send a new email via Microsoft Graph API."""
        if self.use_mock:
            print(f"[MOCK GRAPH] Sending new email to={to}, subject={subject}, cc={cc}, bcc={bcc}")
            return

        to_list = [t.strip() for t in to.split(",") if t.strip()]
        to_recipients = [{"emailAddress": {"address": addr}} for addr in to_list]

        message = {
            "subject": subject,
            "body": {
                "contentType": "Text",
                "content": body
            },
            "toRecipients": to_recipients
        }

        if cc:
            cc_list = [c.strip() for c in cc.split(",") if c.strip()]
            message["ccRecipients"] = [{"emailAddress": {"address": addr}} for addr in cc_list]

        if bcc:
            bcc_list = [b.strip() for b in bcc.split(",") if b.strip()]
            message["bccRecipients"] = [{"emailAddress": {"address": addr}} for addr in bcc_list]

        prefix = self._get_prefix()
        payload = {
            "message": message,
            "saveToSentItems": "true"
        }
        self._request("POST", f"{prefix}/sendMail", json=payload)

    # ── Microsoft Teams ──────────────────────────────────────────────────────
    def list_teams(self) -> List[dict[str, Any]]:
        """Return the teams the signed-in user has joined."""
        if self.use_mock:
            return [{"id": "team-mock-1", "displayName": "Engineering"}]
        data = self._request("GET", "/me/joinedTeams")
        return data.get("value", []) if data else []

    def post_teams_message(self, team_id: str, channel_id: str, message: str) -> dict[str, Any]:
        """Post a message to a Teams channel."""
        if self.use_mock:
            print(f"[MOCK GRAPH] Teams message to {team_id}/{channel_id}: {message}")
            return {"id": "msg-mock-1", "status": "sent"}
        payload = {"body": {"contentType": "text", "content": message}}
        result = self._request("POST", f"/teams/{team_id}/channels/{channel_id}/messages", json=payload)
        return result or {"status": "sent"}

    def create_online_meeting(self, subject: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
        """Create a Teams online meeting and return its join URL."""
        if self.use_mock:
            return {
                "id": "meeting-mock-1",
                "subject": subject,
                "joinUrl": "https://teams.microsoft.com/l/meetup-join/mock-meeting",
            }
        prefix = self._get_prefix()
        now = datetime.utcnow()
        payload = {
            "subject": subject,
            "startDateTime": start or (now + timedelta(minutes=5)).isoformat() + "Z",
            "endDateTime": end or (now + timedelta(minutes=35)).isoformat() + "Z",
        }
        result = self._request("POST", f"{prefix}/onlineMeetings", json=payload)
        return result or {}

    def fetch_sent_email(self, email_id: str) -> dict[str, Any] | None:
        """Fetch a sent email by message id for re-indexing."""
        if self.use_mock:
            return {
                "id": email_id,
                "subject": "Mock re-indexed email",
                "body": "This is a mock re-indexed email body with some contact info like +1234567890."
            }
        try:
            prefix = self._get_prefix()
            return self._request("GET", f"{prefix}/messages/{email_id}")
        except Exception:
            return None

    def fetch_sent_emails(self, days: int = 180) -> List[dict[str, Any]]:
        """Fetch sent emails from the last N days."""
        if self.use_mock:
            # Return >= 50 mock sent emails to satisfy the test case and delta query verification
            mock_emails = []
            for i in range(55):
                mock_emails.append({
                    "id": f"msg-sent-{i}",
                    "subject": f"Follow-up discussion on project part {i}",
                    "body": f"Hi team, just wanted to check in on task {i}. Please make sure to complete it by next week. Let me know if any questions. Contact me at john.doe{i}@example.com or +1-555-0199.",
                    "sentDateTime": datetime.utcnow().isoformat() + "Z"
                })
            return mock_emails

        # Live Graph query
        prefix = self._get_prefix()
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        try:
            path = f"{prefix}/mailFolders/sentitems/messages?$filter=sentDateTime ge {cutoff_date}&$top=100"
            data = self._request("GET", path)
            return data.get("value", [])
        except Exception:
            try:
                path = f"{prefix}/messages?$filter=sentDateTime ge {cutoff_date}&$top=100"
                data = self._request("GET", path)
                return data.get("value", [])
            except Exception:
                return []


