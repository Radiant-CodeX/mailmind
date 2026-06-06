from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, List
import time
import re

from app.config.settings import settings

import httpx

try:
    import msal
except Exception:  # pragma: no cover - imported at runtime when available
    msal = None


_user_token_cache: dict[str, Any] = {
    "access_token": None,
    "expires_at": 0.0,
    "refresh_token": None,
    "user_principal_name": None,
}


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
        if _user_token_cache["access_token"] and now < (_user_token_cache["expires_at"] - 60):
            return _user_token_cache["access_token"]

        # 2. Fall back to client credentials app token
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
        if resp.status_code == 204:
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
        """Initiate MSAL device code flow for user authentication."""
        client_id = self.settings.azure_client_id
        tenant_id = self.settings.azure_tenant_id or "common"
        # Request standard delegated permissions for email, calendar, tasks and profile
        scopes = ["User.Read", "Mail.ReadWrite", "Calendars.ReadWrite", "Tasks.ReadWrite"]
        app = msal.PublicClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}"
        )
        flow = app.initiate_device_flow(scopes=scopes)
        return flow

    def complete_user_login(self, flow: dict[str, Any]) -> dict[str, Any]:
        """Poll and acquire token by device flow."""
        client_id = self.settings.azure_client_id
        tenant_id = self.settings.azure_tenant_id or "common"
        app = msal.PublicClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}"
        )
        result = app.acquire_token_by_device_flow(flow)
        return result

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
        path = f"{prefix}/messages?$top={limit}&$orderby=receivedDateTime desc"
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

    def get_thread_messages(self, thread_id: str) -> List[dict[str, Any]]:
        """Return messages for a conversation/thread.

        For Graph this queries messages filtered by `conversationId`.
        """
        if self.use_mock:
            return [
                {
                    "sender": "alice@example.com",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "subject": f"Thread {thread_id} update",
                    "body": "This is a mocked message body.",
                }
            ]
        prefix = self._get_prefix()
        path = f"{prefix}/messages?$filter=conversationId eq '{thread_id}'&$orderby=receivedDateTime desc"
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
                "sender": sender_addr,
                "timestamp": msg.get("receivedDateTime"),
                "subject": msg.get("subject", ""),
                "body": body_content,
            })
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
            prefix = self._get_prefix()
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
        """Create a To Do task in the user's default To Do list and return its webUrl."""
        if self.use_mock:
            return f"https://graph.microsoft.com/todo/{email_id}/{commitment[:10]}"
        
        prefix = self._get_prefix()
        lists = self._request("GET", f"{prefix}/todo/lists")
        lists_val = lists.get("value", [])
        if not lists_val:
            raise RuntimeError("no todo lists available for user")
        list_id = lists_val[0]["id"]
        payload = {"title": commitment}
        task = self._request("POST", f"{prefix}/todo/lists/{list_id}/tasks", json=payload)
        return task.get("webUrl") or task.get("id")

    def create_calendar_event(self, email_id: str, commitment: str, deadline: datetime | None) -> str:
        """Create a calendar event and return its webLink."""
        if self.use_mock:
            event_id = f"event-{email_id[:8]}"
            return f"https://graph.microsoft.com/calendar/{event_id}"
        
        start = (deadline or datetime.utcnow()).isoformat()
        end = (deadline or datetime.utcnow() + timedelta(hours=1)).isoformat()
        event_payload = {
            "subject": commitment,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
            "body": {"contentType": "text", "content": commitment},
        }
        prefix = self._get_prefix()
        event = self._request("POST", f"{prefix}/events", json=event_payload)
        return event.get("webLink") or event.get("id")

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


