from __future__ import annotations

import logging
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


def _graph_html_to_text(html: str) -> str:
    """Strip HTML to clean plain text for agent processing (Outlook bodies)."""
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'</(p|div|li|tr|h[1-6]|blockquote|table)>', '\n', html, flags=re.IGNORECASE)
    html = re.sub(r'<li[^>]*>', '• ', html, flags=re.IGNORECASE)
    html = re.sub(r'<[^>]+>', '', html)
    html = (html.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<')
                .replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'"))
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


# Delegated scopes requested for the signed-in user (email, calendar, tasks, profile).
# offline_access is required to receive a refresh token so sessions survive past 1 hour
# without requiring the user to re-authenticate (Azure offline_access permission enabled).
_DELEGATED_SCOPES = [
    "User.Read",
    "Mail.ReadWrite", "Mail.Send",
    "Calendars.ReadWrite",
    "Tasks.ReadWrite",
    "ChannelMessage.Send", "OnlineMeetings.ReadWrite", "Team.ReadBasic.All",
]

# Proactive token refresh: refresh the access token this many seconds before expiry.
# Prevents any 401 mid-request by keeping the token always fresh.
_TOKEN_REFRESH_BUFFER = 300  # 5 minutes

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


def _build_confidential_client():
    """Build an MSAL ConfidentialClientApplication (web app) for the auth-code flow."""
    cache = _load_token_cache()
    tenant_id = settings.azure_tenant_id or "common"
    app = msal.ConfidentialClientApplication(
        settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )
    return app, cache


# In-flight Microsoft auth-code flows, keyed by the flow's own `state`.
ms_auth_status: dict[str, dict[str, Any]] = {}


def build_ms_auth_url() -> tuple[str, str]:
    """Start a Microsoft authorization-code (popup) flow. Returns (auth_url, state)."""
    app, _ = _build_confidential_client()
    flow = app.initiate_auth_code_flow(_DELEGATED_SCOPES, redirect_uri=settings.azure_redirect_uri)
    state = flow["state"]
    ms_auth_status[state] = {"status": "pending", "flow": flow}
    return flow["auth_uri"], state


def exchange_ms_code(state: str, query_params: dict[str, str]) -> dict[str, Any]:
    """Complete the auth-code flow from the redirect query params; store the session.

    With offline_access in scope, MSAL returns a refresh token alongside the
    access token. MSAL's SerializableTokenCache persists it to disk so future
    calls to _silent_acquire() can obtain new access tokens without any user
    interaction — the session survives indefinitely as long as the refresh token
    is not revoked.
    """
    rec = ms_auth_status.get(state)
    if not rec or "flow" not in rec:
        raise RuntimeError("Unknown or expired sign-in state. Please try again.")
    app, cache = _build_confidential_client()
    result = app.acquire_token_by_auth_code_flow(rec["flow"], query_params)
    if not result or "access_token" not in result:
        raise RuntimeError(result.get("error_description") if result else "Authentication failed")
    claims = result.get("id_token_claims", {})
    upn = claims.get("preferred_username") or claims.get("upn") or claims.get("email")
    _user_token_cache["access_token"] = result["access_token"]
    _user_token_cache["expires_at"] = time.time() + int(result.get("expires_in", 3600))
    _user_token_cache["user_principal_name"] = upn
    _user_token_cache["tenant_id"] = claims.get("tid")
    # refresh_token is persisted inside the MSAL cache (not in _user_token_cache)
    # so it survives process restarts via the msal_cache.bin file.
    _save_token_cache(cache)

    # Dual-write the serialized MSAL cache to the per-user oauth_accounts table
    # (encrypted). MSAL owns refresh/rotation semantics, so storing its cache
    # blob per account is safer than extracting raw tokens. No-op without a DB.
    try:
        from app.services import identity
        if upn:
            user_id = identity.get_or_create_user(upn, claims.get("name"))
            identity.upsert_oauth_account(
                user_id, "microsoft", upn,
                provider_account_id=claims.get("oid") or upn,
                msal_cache=cache.serialize(),
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("[auth] Failed to persist oauth account: %s", exc)

    import logging
    logging.getLogger(__name__).info(
        "[auth] Token exchange complete for %s — refresh token persisted (offline_access)", upn
    )
    return {"email": upn}


def _silent_acquire(username: str | None = None) -> dict[str, Any] | None:
    """Silently acquire a delegated access token from the persisted refresh token.

    Tries the confidential client first (auth-code flow stores tokens there),
    then falls back to the public client (device-code flow). Both write to the
    same cache file but MSAL separates accounts by client type, so both must
    be checked for Quick Login to work regardless of which flow was used.

    Returns the MSAL result dict on success, or None if no usable account /
    refresh token is available (caller should fall back to interactive login).
    """
    if msal is None:
        return None

    # Try confidential client first (auth-code flow), then public (device-code).
    for build_fn in (_build_confidential_client, _build_public_client):
        try:
            app, cache = build_fn()
            accounts = app.get_accounts(username=username) if username else app.get_accounts()
            if not accounts:
                continue
            result = app.acquire_token_silent(_DELEGATED_SCOPES, account=accounts[0])
            _save_token_cache(cache)
            if result and "access_token" in result:
                _user_token_cache["access_token"] = result["access_token"]
                _user_token_cache["expires_at"] = time.time() + int(result.get("expires_in", 3600))
                _user_token_cache["user_principal_name"] = accounts[0].get("username")
                return result
        except Exception:
            continue

    return None


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

    def __init__(self, settings_obj: type(settings) = settings, *, access_token: str | None = None, refresh_token: str | None = None):
        self.settings = settings_obj
        self.use_mock = bool(self.settings.use_mock_graph)
        # v3: when tokens are injected at construction, they take precedence
        # over the process-level _user_token_cache.
        self._injected_access_token = access_token
        self._injected_refresh_token = refresh_token
        # Account-bound metadata (msal_cache, account_email, id). Only populated
        # by the legacy account-bound path; the v3 adapter path injects a token
        # directly and leaves this None.
        self.account = None
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

    def _account_token(self) -> str:
        """Acquire a delegated access token for this client's bound account.

        Self-contained: deserializes the account's MSAL cache, silently acquires
        a token for that account, and persists any rotated cache back to the
        same account row. Never reads or writes _user_token_cache.
        """
        if msal is None:
            raise RuntimeError("msal package is required for Graph integration")
        cache = msal.SerializableTokenCache()
        blob = self.account.get("msal_cache")
        if blob:
            try:
                cache.deserialize(blob)
            except Exception:
                pass
        tenant_id = self.settings.azure_tenant_id or "common"
        app = msal.ConfidentialClientApplication(
            self.settings.azure_client_id,
            client_credential=self.settings.azure_client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            token_cache=cache,
        )
        target = self.account.get("account_email")
        accounts = app.get_accounts(username=target) or app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(_DELEGATED_SCOPES, account=accounts[0])
        if not result or "access_token" not in result:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Microsoft session expired. Please reconnect.")
        # Persist rotated refresh tokens back to this account only.
        if cache.has_state_changed:
            try:
                from app.services import identity
                identity.update_account_tokens_locked(self.account["id"], msal_cache=cache.serialize())
            except Exception:
                pass
        return result["access_token"]

    def _get_token(self) -> str | None:
        if self.use_mock:
            return None

        # v3: injected token wins over global cache (AccountService path)
        if self._injected_access_token:
            return self._injected_access_token

        now = time.time()
        # 1. Active user session — proactively refresh _TOKEN_REFRESH_BUFFER seconds
        #    before expiry so no API call ever hits a stale token mid-flight.
        if _user_token_cache["access_token"]:
            if now < (_user_token_cache["expires_at"] - _TOKEN_REFRESH_BUFFER):
                return _user_token_cache["access_token"]
            # Token within refresh window (or expired) — silently acquire a new one
            # using the offline_access refresh token persisted in msal_cache.bin.
            refreshed = _silent_acquire(_user_token_cache.get("user_principal_name"))
            if refreshed and refreshed.get("access_token"):
                import logging
                logging.getLogger(__name__).debug(
                    "[auth] Access token proactively refreshed for %s",
                    _user_token_cache.get("user_principal_name"),
                )
                return refreshed["access_token"]
            # Refresh token revoked or expired — clear and require re-login.
            _user_token_cache["access_token"] = None
            _user_token_cache["expires_at"] = 0.0
            _user_token_cache["user_principal_name"] = None
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="Session expired. Please sign in again.",
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

    def get_user_profile(self) -> dict[str, str | None]:
        """Return the signed-in Microsoft profile for display in the app shell."""
        own_email = self.account.get("account_email") if self.account else None
        if self.use_mock:
            return {
                "email": own_email or _user_token_cache.get("user_principal_name") or self.settings.azure_user_upn or "user@example.com",
                "display_name": "Microsoft User",
                "photo_url": None,
            }

        prefix = self._get_prefix()
        email = own_email or _user_token_cache.get("user_principal_name") or self.settings.azure_user_upn
        display_name = None
        photo_url = None

        try:
            user = self._request("GET", f"{prefix}?$select=displayName,mail,userPrincipalName")
            display_name = (user or {}).get("displayName")
            email = (user or {}).get("mail") or (user or {}).get("userPrincipalName") or email
        except Exception:
            pass

        try:
            token = self._get_token()
            headers = {"Accept": "image/*"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(f"{self.base}{prefix}/photo/$value", headers=headers)
            if resp.status_code == 200 and resp.content:
                import base64
                content_type = resp.headers.get("content-type") or "image/jpeg"
                encoded = base64.b64encode(resp.content).decode("ascii")
                photo_url = f"data:{content_type};base64,{encoded}"
        except Exception:
            photo_url = None

        return {
            "email": email,
            "display_name": display_name,
            "photo_url": photo_url,
        }

    def _get_prefix(self) -> str:
        """Get the user prefix path for Microsoft Graph queries."""
        if self.use_mock:
            return "/me"

        # Account-bound or active user session — we act as the delegated user.
        # The v3 adapter path injects a delegated user token directly, so that
        # also means we should query the signed-in user's own mailbox (/me).
        if self._injected_access_token or self.account or _user_token_cache["access_token"]:
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
            # All times are relative to now so the demo inbox always looks live and fresh.
            now = datetime.utcnow()
            return [
                # ── CRITICAL ────────────────────────────────────────────────────────────
                {
                    "email_id": "email-1",
                    "sender": "victoria.hayes@nexuscapital.com",
                    "sender_name": "Victoria Hayes",
                    "subject": "URGENT: $4.2M wire transfer — authorize before market close today",
                    "body": (
                        "Hi,\n\n"
                        "The Nexus Capital board has approved the Series B tranche. To meet the closing "
                        "conditions your legal team confirmed yesterday, we need the $4.2M wire authorization "
                        "signed and submitted to First Republic before 3:00 PM EST today.\n\n"
                        "Failure to hit this window pushes close to next quarter due to bank blackout dates.\n\n"
                        "Please confirm authorization by replying to this email or calling me directly at "
                        "+1 (212) 555-0192 before 2:30 PM.\n\n"
                        "Victoria Hayes\nManaging Director, Nexus Capital\nvictoria.hayes@nexuscapital.com"
                    ),
                    "received_at": (now - timedelta(minutes=8)).isoformat() + "Z",
                    "is_read": False,
                    "is_starred": True,
                    "has_attachments": True,
                },
                # ── CRITICAL ────────────────────────────────────────────────────────────
                {
                    "email_id": "email-2",
                    "sender": "cto@globalretail.com",
                    "sender_name": "Daniel Park",
                    "subject": "PRODUCTION DOWN — checkout flow returning 500s, revenue impact",
                    "body": (
                        "Team,\n\n"
                        "Our production checkout API has been returning HTTP 500 errors for the last 22 minutes. "
                        "Payment processing is completely offline. Estimated revenue loss is $18K/minute at current "
                        "traffic.\n\n"
                        "Three enterprise clients (RetailMax, FreshCart, StyleHub) have already escalated to their "
                        "account managers. RetailMax is threatening SLA penalties if this exceeds 30 minutes.\n\n"
                        "I need a status update and an ETA for resolution immediately. Do not wait for a postmortem "
                        "— call me now: +1 (415) 555-0847.\n\n"
                        "Daniel Park\nCTO, Global Retail Inc."
                    ),
                    "received_at": (now - timedelta(minutes=22)).isoformat() + "Z",
                    "is_read": False,
                    "is_starred": False,
                    "has_attachments": False,
                },
                # ── HIGH ────────────────────────────────────────────────────────────────
                {
                    "email_id": "email-3",
                    "sender": "james.whitfield@lexpartners.com",
                    "sender_name": "James Whitfield",
                    "subject": "MSA redline — countersignature required by Friday 5 PM",
                    "body": (
                        "Hi,\n\n"
                        "Please find attached the redlined Master Services Agreement incorporating your legal "
                        "team's feedback from the 14th. Our counsel has approved all remaining open points.\n\n"
                        "We need your countersignature by Friday at 5:00 PM GMT to maintain the go-live date "
                        "of the 28th. If we miss Friday, the implementation team cannot hold the slot and we "
                        "will need to reschedule to Q4.\n\n"
                        "Please review Section 8.3 (liability cap) and Section 12 (data processing addendum) "
                        "in particular — those were the substantive changes from our side.\n\n"
                        "Let me know if you need a call to walk through anything.\n\n"
                        "Best regards,\n"
                        "James Whitfield\nSenior Partner, Lex & Partners LLP"
                    ),
                    "received_at": (now - timedelta(hours=1, minutes=45)).isoformat() + "Z",
                    "is_read": False,
                    "is_starred": False,
                    "has_attachments": True,
                },
                # ── HIGH ────────────────────────────────────────────────────────────────
                {
                    "email_id": "email-4",
                    "sender": "priya.nair@internal.acme",
                    "sender_name": "Priya Nair",
                    "subject": "Q3 headcount plan — CFO needs approval by Monday 9 AM",
                    "body": (
                        "Hi,\n\n"
                        "The Q3 headcount proposal is finalised. We're requesting approval for 6 new engineering "
                        "hires (4 senior, 2 mid-level) and 2 product managers — total annualised cost $1.1M.\n\n"
                        "The CFO has a board pre-read call at 9:00 AM Monday and needs your sign-off before then "
                        "so finance can include the headcount numbers in the operating model.\n\n"
                        "Deck is attached. Key slides: 4 (hiring rationale), 7 (cost breakdown), 9 (timeline).\n\n"
                        "Happy to jump on a call Friday afternoon if you want to talk through it first.\n\n"
                        "Priya Nair\nVP Engineering, Acme Corp"
                    ),
                    "received_at": (now - timedelta(hours=3, minutes=10)).isoformat() + "Z",
                    "is_read": False,
                    "is_starred": False,
                    "has_attachments": True,
                },
                # ── HIGH ────────────────────────────────────────────────────────────────
                {
                    "email_id": "email-5",
                    "sender": "security-alerts@crowdstrike.com",
                    "sender_name": "CrowdStrike Falcon",
                    "subject": "[ALERT] Suspicious login attempt — admin panel, Singapore IP",
                    "body": (
                        "Security Alert — Action Required\n\n"
                        "We detected a suspicious login attempt on your admin panel:\n\n"
                        "  Time:        2024-06-17 04:31 UTC\n"
                        "  IP Address:  103.86.xx.xx (Singapore)\n"
                        "  Account:     admin@acme.com\n"
                        "  Result:      BLOCKED (MFA challenge failed)\n\n"
                        "This IP has been associated with credential stuffing campaigns in the past 48 hours "
                        "across 3 other enterprise customers.\n\n"
                        "Recommended actions:\n"
                        "1. Rotate the admin@acme.com password immediately\n"
                        "2. Review audit logs for the past 72 hours\n"
                        "3. Confirm no sessions were opened from this IP\n\n"
                        "If you did not initiate this login, contact our SOC at +1 (888) 555-0123.\n\n"
                        "CrowdStrike Falcon Platform"
                    ),
                    "received_at": (now - timedelta(hours=5)).isoformat() + "Z",
                    "is_read": False,
                    "is_starred": False,
                    "has_attachments": False,
                },
                # ── MEDIUM ──────────────────────────────────────────────────────────────
                {
                    "email_id": "email-6",
                    "sender": "alex.kim@acme.com",
                    "sender_name": "Alex Kim",
                    "subject": "Sprint 24 retro notes + action items",
                    "body": (
                        "Hi team,\n\n"
                        "Notes from today's Sprint 24 retrospective:\n\n"
                        "What went well:\n"
                        "- Shipped the new onboarding flow on schedule\n"
                        "- Zero P1 bugs in production this sprint\n\n"
                        "What to improve:\n"
                        "- PR review turnaround still averaging 3 days — target is 1 day\n"
                        "- Staging environment instability blocked QA twice\n\n"
                        "Action items:\n"
                        "1. @you — schedule staging infrastructure review with DevOps by Wednesday\n"
                        "2. Alex — set up PR review rotation starting next Monday\n"
                        "3. Team — update runbooks for the new deployment process by EOW\n\n"
                        "Please confirm you've seen item 1 — I'll chase if I don't hear back by Thursday.\n\n"
                        "Alex Kim\nEngineering Manager"
                    ),
                    "received_at": (now - timedelta(hours=6, minutes=30)).isoformat() + "Z",
                    "is_read": True,
                    "is_starred": False,
                    "has_attachments": False,
                },
                # ── MEDIUM ──────────────────────────────────────────────────────────────
                {
                    "email_id": "email-7",
                    "sender": "onboarding@stripe.com",
                    "sender_name": "Stripe",
                    "subject": "Action required: complete your Stripe Connect verification",
                    "body": (
                        "Hi there,\n\n"
                        "To continue processing payments above $10,000/month you need to complete identity "
                        "verification for your Stripe Connect account.\n\n"
                        "What you need to submit:\n"
                        "- Government-issued ID for the account owner\n"
                        "- Business registration document\n"
                        "- Bank account statement (last 3 months)\n\n"
                        "Deadline: You have 14 days from today before payouts are paused.\n\n"
                        "Complete verification → https://dashboard.stripe.com/verify\n\n"
                        "Questions? Reply to this email or contact support@stripe.com.\n\n"
                        "The Stripe Team"
                    ),
                    "received_at": (now - timedelta(hours=9)).isoformat() + "Z",
                    "is_read": True,
                    "is_starred": False,
                    "has_attachments": False,
                },
                # ── MEDIUM ──────────────────────────────────────────────────────────────
                {
                    "email_id": "email-8",
                    "sender": "rachel.torres@designstudio.io",
                    "sender_name": "Rachel Torres",
                    "subject": "Brand refresh — 3 concepts ready for feedback",
                    "body": (
                        "Hi,\n\n"
                        "We've completed the first round of brand concepts based on the brief you shared "
                        "on June 10th. Three directions are ready in Figma:\n\n"
                        "  Concept A — 'Precision' (clean, minimal, enterprise)\n"
                        "  Concept B — 'Momentum' (dynamic, gradient-forward, tech)\n"
                        "  Concept C — 'Clarity' (warm, approachable, SaaS-standard)\n\n"
                        "Figma link: https://figma.com/file/demo-brand-refresh\n\n"
                        "I'd love to get your thoughts before we present to the wider team on Thursday. "
                        "Even a quick 'leaning toward A' would help us focus the next iteration.\n\n"
                        "Let me know if you'd like a walkthrough call.\n\n"
                        "Rachel Torres\nCreative Director, Design Studio"
                    ),
                    "received_at": (now - timedelta(hours=11)).isoformat() + "Z",
                    "is_read": True,
                    "is_starred": False,
                    "has_attachments": True,
                },
                # ── LOW ─────────────────────────────────────────────────────────────────
                {
                    "email_id": "email-9",
                    "sender": "newsletter@tldr.tech",
                    "sender_name": "TLDR Newsletter",
                    "subject": "TLDR Tech — Anthropic raises $3B, Apple WWDC recap",
                    "body": (
                        "Good morning!\n\n"
                        "Today's top stories:\n\n"
                        "🤖 AI — Anthropic closes $3B Series E at $18B valuation. Focus: safety research and "
                        "Claude model family expansion.\n\n"
                        "🍎 APPLE — WWDC 2024 recap: Apple Intelligence, iOS 18, macOS Sequoia announced. "
                        "On-device ML models for Mail, Messages, and Photos.\n\n"
                        "⚡ INFRA — Cloudflare announces R2 storage price cuts of 40%. Major win for "
                        "egress-heavy workloads.\n\n"
                        "🔒 SECURITY — Critical CVE in OpenSSH (CVE-2024-6387) allows unauthenticated RCE "
                        "on glibc-based Linux. Patch immediately.\n\n"
                        "Read more at tldr.tech"
                    ),
                    "received_at": (now - timedelta(hours=14)).isoformat() + "Z",
                    "is_read": True,
                    "is_starred": False,
                    "has_attachments": False,
                },
                # ── LOW ─────────────────────────────────────────────────────────────────
                {
                    "email_id": "email-10",
                    "sender": "no-reply@notion.so",
                    "sender_name": "Notion",
                    "subject": "Your Notion workspace usage report — June 2024",
                    "body": (
                        "Hi there,\n\n"
                        "Here's your Notion workspace summary for June 2024:\n\n"
                        "  Pages created:    47\n"
                        "  Edits made:      312\n"
                        "  Team members:     18 active\n"
                        "  Most active page: 'Product Roadmap Q3 2024'\n\n"
                        "Your team is in the top 15% for collaboration activity this month. 🎉\n\n"
                        "Explore your analytics → notion.so/analytics\n\n"
                        "The Notion Team"
                    ),
                    "received_at": (now - timedelta(days=1, hours=2)).isoformat() + "Z",
                    "is_read": True,
                    "is_starred": False,
                    "has_attachments": False,
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
                "is_read": bool(msg.get("isRead", True)),
                "has_attachments": bool(msg.get("hasAttachments", False)),
            })
        return formatted

    _FOLDERS = {"inbox": "inbox", "sent": "sentitems", "drafts": "drafts",
                "spam": "junkemail", "trash": "deleteditems"}

    def list_emails(self, folder: str = "inbox", limit: int = 50,
                    page_token: str | None = None, query: str | None = None) -> dict[str, Any]:
        """Unified paginated listing for any folder with optional search.

        page_token encodes the skip offset (Graph uses $skip-based paging).
        """
        if self.use_mock:
            source = self.get_inbox_emails(limit=50) if folder == "inbox" else []
            if query:
                q = query.lower()
                source = [m for m in source if q in m["subject"].lower() or q in str(m["sender"]).lower()]
            return {"emails": source[:limit], "next_page_token": None, "total": len(source)}

        folder_id = self._FOLDERS.get(folder, "inbox")
        skip = int(page_token) if page_token and page_token.isdigit() else 0
        prefix = self._get_prefix()
        base = f"{prefix}/mailFolders/{folder_id}/messages?$top={limit}&$skip={skip}&$count=true"
        if query:
            from urllib.parse import quote
            path = f'{base}&$search="{quote(query)}"'
        else:
            path = f"{base}&$orderby=receivedDateTime desc"
        # Request HTML body so the frontend can render rich formatting like Gmail.
        data = self._request("GET", path, headers={
            "Prefer": 'outlook.body-content-type="html"', "ConsistencyLevel": "eventual"})
        raw = data.get("value", [])
        emails = []
        for msg in raw:
            from_obj = msg.get("from") or msg.get("sender")
            sender = "unknown@example.com"
            if from_obj and "emailAddress" in from_obj:
                sender = from_obj["emailAddress"].get("address", sender)
            body_obj = msg.get("body") or {}
            content = body_obj.get("content", "")
            content_type = (body_obj.get("contentType") or "").lower()
            if content_type == "html" and content:
                html_body = content
                plain_body = _graph_html_to_text(content)
            else:
                html_body = None
                plain_body = content or msg.get("bodyPreview", "")
            emails.append({
                "email_id": msg.get("id"),
                "sender": sender,
                "subject": msg.get("subject", ""),
                "body": plain_body,         # plain text for agents
                "html_body": html_body,     # rich HTML for display
                "received_at": msg.get("receivedDateTime"),
                "is_read": bool(msg.get("isRead", True)),
                "has_attachments": bool(msg.get("hasAttachments", False)),
                # Attachment metadata is fetched lazily on demand via list_attachments
                "attachments": [],
            })
        total = int(data.get("@odata.count", skip + len(emails)))
        next_token = str(skip + limit) if len(emails) == limit and (skip + limit) < total else None
        return {"emails": emails, "next_page_token": next_token, "total": total}

    def get_message(self, email_id: str) -> dict[str, Any] | None:
        """Fetch a single message fully formatted (rich html_body + attachments).

        Used by the detail view: the mirror stores only a snippet, so opening an
        email fetches the full content on demand.
        """
        if self.use_mock:
            for m in self.get_inbox_emails(limit=50):
                if m.get("email_id") == email_id:
                    return m
            return None
        prefix = self._get_prefix()
        msg = self._request(
            "GET",
            f"{prefix}/messages/{email_id}"
            "?$select=id,subject,from,sender,receivedDateTime,isRead,hasAttachments,body,conversationId",
            headers={"Prefer": 'outlook.body-content-type="html"'},
        )
        if not msg:
            return None
        from_obj = msg.get("from") or msg.get("sender")
        sender = "unknown@example.com"
        if from_obj and "emailAddress" in from_obj:
            sender = from_obj["emailAddress"].get("address", sender)
        body_obj = msg.get("body") or {}
        content = body_obj.get("content", "")
        content_type = (body_obj.get("contentType") or "").lower()
        if content_type == "html" and content:
            html_body = content
            plain_body = _graph_html_to_text(content)
        else:
            html_body = None
            plain_body = content or msg.get("bodyPreview", "")
        attachments = self.list_attachments(email_id) if msg.get("hasAttachments") else []
        return {
            "email_id": msg.get("id"),
            "sender": sender,
            "subject": msg.get("subject", ""),
            "body": plain_body,
            "html_body": html_body,
            "received_at": msg.get("receivedDateTime"),
            "is_read": bool(msg.get("isRead", True)),
            "has_attachments": bool(msg.get("hasAttachments", False)),
            "attachments": attachments,
        }

    def list_inbox_delta(
        self, delta_link: str | None = None, *, folder: str = "inbox", max_pages: int = 40
    ) -> dict[str, Any]:
        """
        Walk the Graph messages *delta* for a folder (the inbox-sync engine).

        - delta_link=None  → start a fresh enumeration (used for backfill).
        - delta_link=<url> → replay an incremental change set.

        Returns { upserts: [...envelopes], removed: [email_id...],
                  delta_cursor: <next @odata.deltaLink or None>, truncated: bool }.

        ``delta_cursor`` is None if we hit ``max_pages`` before Graph emitted a
        deltaLink (very large mailbox); the caller should re-backfill next time.
        """
        if self.use_mock:
            snap = self.get_inbox_emails(limit=25) if folder == "inbox" else []
            return {"upserts": snap, "removed": [], "delta_cursor": None, "truncated": False}

        select = ("id,subject,from,sender,receivedDateTime,isRead,bodyPreview,"
                  "hasAttachments,conversationId,flag")
        folder_id = self._FOLDERS.get(folder, "inbox")
        if delta_link:
            url = delta_link
        else:
            prefix = self._get_prefix()
            url = (f"{self.base}{prefix}/mailFolders/{folder_id}/messages/delta"
                   f"?$select={select}&$top=50")

        upserts: list[dict[str, Any]] = []
        removed: list[str] = []
        delta_cursor: str | None = None
        truncated = False

        token = self._get_token()
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        pages = 0
        with httpx.Client(timeout=30.0) as client:
            while url:
                if pages >= max_pages:
                    truncated = True
                    break
                resp = client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json() if resp.content else {}
                for msg in data.get("value", []):
                    if "@removed" in msg:
                        if msg.get("id"):
                            removed.append(msg["id"])
                        continue
                    upserts.append(self._delta_msg_to_envelope(msg))
                pages += 1
                if data.get("@odata.deltaLink"):
                    delta_cursor = data["@odata.deltaLink"]
                    break
                url = data.get("@odata.nextLink")

        return {"upserts": upserts, "removed": removed,
                "delta_cursor": delta_cursor, "truncated": truncated}

    @staticmethod
    def _delta_msg_to_envelope(msg: dict[str, Any]) -> dict[str, Any]:
        """Map a Graph delta message to the shared envelope shape."""
        from_obj = msg.get("from") or msg.get("sender") or {}
        addr = (from_obj.get("emailAddress") or {}) if isinstance(from_obj, dict) else {}
        flag = (msg.get("flag") or {}) if isinstance(msg.get("flag"), dict) else {}
        return {
            "email_id": msg.get("id"),
            "sender": addr.get("address", "unknown@example.com"),
            "sender_name": addr.get("name"),
            "subject": msg.get("subject", ""),
            "snippet": msg.get("bodyPreview", ""),
            "received_at": msg.get("receivedDateTime"),
            "is_read": bool(msg.get("isRead", True)),
            "is_starred": (flag.get("flagStatus") == "flagged"),
            "has_attachments": bool(msg.get("hasAttachments", False)),
            "thread_id": msg.get("conversationId"),
        }

    # ── Change-notification subscriptions (webhooks) ──────────────────────────

    def create_subscription(self, notification_url: str, client_state: str,
                            resource: str = "/me/mailFolders('inbox')/messages",
                            minutes: int = 4230) -> dict[str, Any]:
        """Create a Graph change-notification subscription. Returns {id, expirationDateTime}."""
        from datetime import datetime, timedelta, timezone
        expires = (datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        body = {
            "changeType": "created,updated,deleted",
            "notificationUrl": notification_url,
            "resource": resource,
            "expirationDateTime": expires,
            "clientState": client_state,
        }
        return self._request("POST", "/subscriptions", json=body) or {}

    def renew_subscription(self, subscription_id: str, minutes: int = 4230) -> dict[str, Any]:
        """Extend a subscription's expiry. Returns the updated subscription."""
        from datetime import datetime, timedelta, timezone
        expires = (datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return self._request("PATCH", f"/subscriptions/{subscription_id}",
                             json={"expirationDateTime": expires}) or {}

    def delete_subscription(self, subscription_id: str) -> None:
        """Remove a subscription (best-effort)."""
        try:
            self._request("DELETE", f"/subscriptions/{subscription_id}")
        except Exception as e:
            logging.getLogger(__name__).debug("[graph] delete subscription %s failed: %s", subscription_id, e)

    def list_attachments(self, message_id: str) -> list[dict[str, Any]]:
        """List attachment metadata for a Graph message."""
        if self.use_mock:
            return []
        prefix = self._get_prefix()
        data = self._request("GET", f"{prefix}/messages/{message_id}/attachments?$select=id,name,contentType,size")
        out = []
        for att in (data or {}).get("value", []):
            out.append({
                "attachment_id": att.get("id"),
                "filename": att.get("name", "attachment"),
                "mime_type": att.get("contentType", "application/octet-stream"),
                "size": att.get("size", 0),
            })
        return out

    def get_attachment(self, message_id: str, attachment_id: str) -> dict[str, Any] | None:
        """Fetch a Graph attachment; returns {data: base64url} to match Gmail's shape."""
        if self.use_mock:
            return None
        prefix = self._get_prefix()
        att = self._request("GET", f"{prefix}/messages/{message_id}/attachments/{attachment_id}")
        if not att:
            return None
        # Graph returns standard base64 in contentBytes; convert to base64url for the
        # shared download endpoint (which uses urlsafe_b64decode).
        import base64
        content_b64 = att.get("contentBytes", "")
        try:
            raw = base64.b64decode(content_b64)
            return {"data": base64.urlsafe_b64encode(raw).decode("ascii")}
        except Exception:
            return {"data": content_b64}

    # ── Mail actions ─────────────────────────────────────────────────────────
    def mark_read(self, email_id: str, read: bool = True) -> None:
        """Mark a message read/unread."""
        if self.use_mock:
            return
        prefix = self._get_prefix()
        self._request("PATCH", f"{prefix}/messages/{email_id}", json={"isRead": read})

    def archive(self, email_id: str) -> None:
        """Move a message to the Archive folder."""
        if self.use_mock:
            return
        prefix = self._get_prefix()
        self._request("POST", f"{prefix}/messages/{email_id}/move", json={"destinationId": "archive"})

    def report_spam(self, email_id: str) -> None:
        """Move a message to the Junk Email folder."""
        if self.use_mock:
            return
        prefix = self._get_prefix()
        self._request("POST", f"{prefix}/messages/{email_id}/move", json={"destinationId": "junkemail"})

    def forward_email(self, email_id: str, to: str, comment: str = "") -> None:
        """Forward a message to a new recipient."""
        if self.use_mock:
            print(f"[MOCK GRAPH] Forward {email_id} to {to}")
            return
        prefix = self._get_prefix()
        to_recipients = [{"emailAddress": {"address": a.strip()}} for a in to.split(",") if a.strip()]
        self._request(
            "POST", f"{prefix}/messages/{email_id}/forward",
            json={"comment": comment, "toRecipients": to_recipients},
        )

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
                # Conflicts with email-1 (wire transfer deadline today ~3 PM)
                {
                    "title": "Investor Relations All-Hands",
                    "start_time": now + timedelta(hours=2),
                    "end_time": now + timedelta(hours=3, minutes=30),
                    "organizer": "victoria.hayes@nexuscapital.com",
                },
                # Conflicts with email-3 (MSA countersignature Friday 5 PM)
                {
                    "title": "Legal Review — Contract Finalization",
                    "start_time": now + timedelta(days=2, hours=3),
                    "end_time": now + timedelta(days=2, hours=4),
                    "organizer": "james.whitfield@lexpartners.com",
                },
                # Conflicts with email-4 (CFO headcount review Monday 9 AM)
                {
                    "title": "CFO Board Pre-Read Call",
                    "start_time": now + timedelta(days=3, hours=9),
                    "end_time": now + timedelta(days=3, hours=10),
                    "organizer": "priya.nair@internal.acme",
                },
                {
                    "title": "Sprint 25 Planning",
                    "start_time": now + timedelta(days=1, hours=10),
                    "end_time": now + timedelta(days=1, hours=11, minutes=30),
                    "organizer": "alex.kim@acme.com",
                },
                {
                    "title": "Brand Refresh Presentation",
                    "start_time": now + timedelta(days=3, hours=14),
                    "end_time": now + timedelta(days=3, hours=15),
                    "organizer": "rachel.torres@designstudio.io",
                },
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

    def reply_all(self, email_id: str, comment: str) -> None:
        """Reply to all recipients of a message via Microsoft Graph API."""
        if self.use_mock:
            print(f"[MOCK GRAPH] Reply-all to email {email_id}")
            return
        prefix = self._get_prefix()
        self._request("POST", f"{prefix}/messages/{email_id}/replyAll", json={"comment": comment})

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
            # Rich sent-mail history for realistic Tone DNA — VP/Director persona, enterprise tech company.
            # Stylistic profile: direct opener, short declarative sentences, numbered action items,
            # "Thanks" sign-off (never "Best regards"), mild formality, no filler phrases.
            now = datetime.utcnow()
            def _days_ago(d: int) -> str:
                return (now - timedelta(days=d)).isoformat() + "Z"

            rich_sent = [
                {
                    "id": "sent-s01",
                    "subject": "Re: Q3 OKR alignment — action items",
                    "body": (
                        "Team,\n\n"
                        "Good session today. Here is what I need from each of you before Friday:\n\n"
                        "1. Engineering — finalise capacity estimate for the auth migration.\n"
                        "2. Product — lock the KR metrics with Priya by Wednesday EOD.\n"
                        "3. Design — share the revised onboarding flow with me for review.\n\n"
                        "I'll consolidate and send the deck to the exec team Thursday morning.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(2),
                },
                {
                    "id": "sent-s02",
                    "subject": "Re: Board pre-read — revenue section",
                    "body": (
                        "Marcus,\n\n"
                        "The ARR slide needs two changes before it goes to the board:\n\n"
                        "- Remove the enterprise segment breakdown — that is still under NDA with Nexus.\n"
                        "- Add the net revenue retention number for Q2. Finance has it.\n\n"
                        "Send me the updated version by 9 AM tomorrow. Board call is at 11.\n\n"
                        "Thanks"
                    ),
                    "sentDateTime": _days_ago(4),
                },
                {
                    "id": "sent-s03",
                    "subject": "Re: Headcount request — 3 senior engineers",
                    "body": (
                        "Priya,\n\n"
                        "I've reviewed the JD and the capacity model. Approved in principle.\n\n"
                        "Two conditions:\n"
                        "1. Requisitions need to be live by Monday so we hit the Q3 hiring window.\n"
                        "2. Loop in Finance before posting — they flagged a budget re-forecast last week.\n\n"
                        "Let me know once reqs are posted.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(6),
                },
                {
                    "id": "sent-s04",
                    "subject": "Re: MSA countersignature — Nexus Capital",
                    "body": (
                        "James,\n\n"
                        "I've reviewed the redlines. Section 9.2 indemnification is still too broad — "
                        "we cannot accept unlimited liability on data breaches outside our control.\n\n"
                        "Proposed language attached. If Nexus accepts, I can sign by Friday 5 PM.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(7),
                },
                {
                    "id": "sent-s05",
                    "subject": "Re: Production incident — payment service",
                    "body": (
                        "Daniel,\n\n"
                        "Acknowledged. Three things I need right now:\n\n"
                        "1. Customer impact count — how many transactions failed?\n"
                        "2. Is the rollback deployed or still in progress?\n"
                        "3. Who owns the external comms if this goes past 30 minutes?\n\n"
                        "Bridge me in once you have answers.\n\n"
                        "Thanks"
                    ),
                    "sentDateTime": _days_ago(10),
                },
                {
                    "id": "sent-s06",
                    "subject": "Re: Sprint 24 retro — process improvements",
                    "body": (
                        "Hi team,\n\n"
                        "Good retro. The two things I want us to actually change (not just discuss):\n\n"
                        "1. PR review SLA — 24 hours max. If blocked, escalate, don't wait.\n"
                        "2. Definition of done must include a staging deployment before marking a ticket ready for QA.\n\n"
                        "I'll check on these in the Sprint 25 kickoff.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(12),
                },
                {
                    "id": "sent-s07",
                    "subject": "Re: Stripe verification — business documents",
                    "body": (
                        "Hi,\n\n"
                        "Documents submitted: certificate of incorporation, EIN letter, and bank statement.\n\n"
                        "Please confirm receipt and let me know if anything else is needed to complete verification.\n\n"
                        "Thanks,\nAlex Chen\nVP Engineering, TechCorp"
                    ),
                    "sentDateTime": _days_ago(14),
                },
                {
                    "id": "sent-s08",
                    "subject": "Re: CrowdStrike alert — endpoint policy",
                    "body": (
                        "Shan,\n\n"
                        "Understood. Isolate the affected machine now and open a P1 in the security tracker.\n\n"
                        "I want a preliminary root-cause summary by 3 PM today. "
                        "If this touches production infra, loop in legal immediately.\n\n"
                        "Thanks"
                    ),
                    "sentDateTime": _days_ago(15),
                },
                {
                    "id": "sent-s09",
                    "subject": "Re: Partnership proposal — DataSync integration",
                    "body": (
                        "Hi Sarah,\n\n"
                        "Thanks for the proposal. The integration looks promising.\n\n"
                        "To move forward, I need:\n"
                        "- A technical spec showing how DataSync handles our event schema.\n"
                        "- Your security posture doc (SOC 2 Type II preferred).\n\n"
                        "Send those over and we can schedule a technical review next week.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(18),
                },
                {
                    "id": "sent-s10",
                    "subject": "Re: Annual SaaS renewal — Datadog",
                    "body": (
                        "Hi,\n\n"
                        "We're open to renewing but the current pricing is 18 % above last year with no usage increase. "
                        "We need a revised quote at the same per-host rate as the previous contract.\n\n"
                        "If that's possible, I can approve by end of month.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(20),
                },
                {
                    "id": "sent-s11",
                    "subject": "Re: Performance review — Rithish K",
                    "body": (
                        "HR,\n\n"
                        "Review submitted. Rating: Exceeds Expectations.\n\n"
                        "Note for the record: Rithish led the LangGraph migration under significant time pressure "
                        "and delivered on schedule. The promotion recommendation is mine.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(22),
                },
                {
                    "id": "sent-s12",
                    "subject": "Re: Architecture review — async queue migration",
                    "body": (
                        "Team,\n\n"
                        "I've reviewed the Redis AOF proposal. Approved.\n\n"
                        "One requirement before we cut over: load test the worker pool at 4× normal volume. "
                        "I don't want to discover queue lag under the first real traffic spike.\n\n"
                        "Schedule the cutover for a Tuesday — never Friday.\n\n"
                        "Thanks"
                    ),
                    "sentDateTime": _days_ago(25),
                },
                {
                    "id": "sent-s13",
                    "subject": "Re: On-call rotation — holiday coverage",
                    "body": (
                        "Manish,\n\n"
                        "Rotation looks fair. One note: whoever is primary on December 25th gets a "
                        "comp day in January — confirm with HR.\n\n"
                        "Publish the final schedule by Friday so everyone can plan.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(28),
                },
                {
                    "id": "sent-s14",
                    "subject": "Re: Brand refresh — copy review",
                    "body": (
                        "Hi,\n\n"
                        "Feedback on the tagline options:\n\n"
                        "1. 'Work smarter' — too generic, every SaaS uses this.\n"
                        "2. 'Inbox clarity at enterprise scale' — close, but wordy.\n"
                        "3. 'Your inbox, under control' — this one works. Clear and direct.\n\n"
                        "Go with option 3. Let me know when the final deck is ready.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(30),
                },
                {
                    "id": "sent-s15",
                    "subject": "Re: Investor update — July metrics",
                    "body": (
                        "Victoria,\n\n"
                        "July metrics attached. Highlights:\n\n"
                        "- ARR: $3.2M (up 14 % MoM)\n"
                        "- NRR: 118 %\n"
                        "- Churn: 1.2 %\n\n"
                        "The wire for the next tranche should be timed before Thursday per the term sheet. "
                        "Let me know if you need anything else before the close.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(32),
                },
                {
                    "id": "sent-s16",
                    "subject": "Re: PII masking — compliance review",
                    "body": (
                        "Shan,\n\n"
                        "Reviewed the Presidio implementation. Two gaps:\n\n"
                        "1. Phone numbers in non-standard formats (e.g., +44 20 XXXX XXXX) are not caught.\n"
                        "2. The audit log currently stores the unmasked entity type label — confirm it never logs the value.\n\n"
                        "Fix both before we submit the SOC 2 evidence package.\n\n"
                        "Thanks"
                    ),
                    "sentDateTime": _days_ago(35),
                },
                {
                    "id": "sent-s17",
                    "subject": "Re: Database migration — Supabase cutover",
                    "body": (
                        "Manish,\n\n"
                        "Migration plan looks solid. Run it against staging first — full data set, not a subset.\n\n"
                        "Two things to confirm before production:\n"
                        "1. Connection pooler tested at 50 concurrent connections.\n"
                        "2. Rollback script tested and timed — I want that under 5 minutes.\n\n"
                        "Ping me when staging is green.\n\n"
                        "Thanks"
                    ),
                    "sentDateTime": _days_ago(38),
                },
                {
                    "id": "sent-s18",
                    "subject": "Re: Customer escalation — Acme Corp",
                    "body": (
                        "Hi,\n\n"
                        "I've reviewed the ticket history. This is on us — the webhook delay was "
                        "a configuration error on our side, not the customer's.\n\n"
                        "Offer them one month credit and a dedicated post-mortem call. "
                        "I'll join if they want exec involvement.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(40),
                },
                {
                    "id": "sent-s19",
                    "subject": "Re: Notion workspace audit",
                    "body": (
                        "Hi,\n\n"
                        "Noted. Archive anything not touched in 6 months.\n\n"
                        "Keep the Engineering and Product spaces as primary. "
                        "Everything else should be a sub-page, not a top-level space.\n\n"
                        "Thanks"
                    ),
                    "sentDateTime": _days_ago(42),
                },
                {
                    "id": "sent-s20",
                    "subject": "Re: Sprint 23 planning — velocity concerns",
                    "body": (
                        "Rithish,\n\n"
                        "Velocity drop makes sense given the infrastructure work last sprint — "
                        "that is not feature points but it is real work.\n\n"
                        "For Sprint 23: cap at 60 % feature tickets, 40 % tech debt and infra. "
                        "I'd rather ship less and keep the codebase healthy.\n\n"
                        "Thanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(45),
                },
            ]

            # Pad to 55 entries with brief follow-ups to satisfy the >= 50 test requirement.
            filler_subjects = [
                "Re: Weekly sync — notes", "Re: Slack channel cleanup", "Re: Expense report approval",
                "Re: Meeting reschedule", "Re: Document access request", "Re: Team lunch — Thursday",
                "Re: GitHub org permissions", "Re: Monitoring alert — disk usage",
                "Re: Candidate interview — debrief", "Re: Offsite agenda — October",
                "Re: Tool evaluation — Figma seats", "Re: Quarterly finance review",
                "Re: AWS cost optimisation", "Re: New hire onboarding — checklist",
                "Re: Legal hold — document preservation", "Re: Release notes — v2.4",
                "Re: Blog post review", "Re: Customer advisory board — agenda",
                "Re: Penetration test — scope approval", "Re: Annual review — team calibration",
                "Re: Roadmap sync — next quarter", "Re: Security training — completion reminder",
                "Re: Demo environment access", "Re: Analytics dashboard — KPI alignment",
                "Re: Data retention policy — sign-off", "Re: Contractor agreement — renewal",
                "Re: Office lease — renewal discussion", "Re: Stakeholder update — August",
                "Re: Product feedback — enterprise pilot", "Re: Interview panel — candidate review",
                "Re: Budget reforecast — Q4", "Re: Marketing alignment — launch plan",
                "Re: Support ticket SLA — policy update", "Re: Infrastructure cost review",
                "Re: LangGraph upgrade — v0.2",
            ]
            for idx, subj in enumerate(filler_subjects):
                rich_sent.append({
                    "id": f"sent-f{idx:02d}",
                    "subject": subj,
                    "body": (
                        "Hi,\n\nThanks for flagging. "
                        "Let me know if there's anything blocking and I'll unblock it.\n\nThanks,\nAlex"
                    ),
                    "sentDateTime": _days_ago(50 + idx),
                })

            return rich_sent

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


