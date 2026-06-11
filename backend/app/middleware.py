"""Production middleware: security headers and global rate limiting.

These wrap every request (not just /api/ingest) so the whole surface is
protected once mounted in main.py.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

audit = logging.getLogger("mailmind.audit")

# Endpoints that must never be rate limited (liveness/readiness probes).
_RATE_LIMIT_EXEMPT = {"/api/health", "/api/ready", "/health", "/ready"}


class SessionContextMiddleware:
    """Pure-ASGI middleware that binds the request's session to a ContextVar.

    Runs in the same task/context as the endpoint (unlike BaseHTTPMiddleware),
    so ``get_mail_client()`` — and any thread it spawns via
    ``request_context.run_in_context`` — sees the correct user's identity.
    This is what keeps concurrent users' mailboxes isolated within one process.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from app.services import identity
        from app.services.request_context import reset_current_session, set_current_session

        # Extract the session token from the cookie header (primary) or the
        # transitional X-MailMind-Session header.
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        token = headers.get("x-mailmind-session")
        if not token and (cookie := headers.get("cookie")):
            for part in cookie.split(";"):
                name, _, value = part.strip().partition("=")
                if name == "mailmind_session":
                    token = value
                    break

        session = identity.get_session(token) if token else None
        if session:
            audit.debug(
                "REQUEST_CONTEXT_BOUND path=%s provider=%s email=%s user_id=%s",
                scope.get("path", "?"),
                session.get("provider"), session.get("email"), session.get("user_id"),
            )
        else:
            audit.debug("REQUEST_CONTEXT_ANONYMOUS path=%s", scope.get("path", "?"))
        ctx_token = set_current_session(session)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_current_session(ctx_token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach a baseline set of hardening headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        # Only advertise HSTS over real TLS connections.
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter applied across all routes.

    Authenticated requests are limited per session (a hash of the session
    token), so users behind a shared proxy/NAT don't exhaust each other's
    quota and one abusive user can't starve the rest. Unauthenticated
    requests fall back to per-IP limiting.

    State is in-memory; for multi-instance deployments swap the backing
    store for Redis.
    """

    def __init__(self, app, limit_per_minute: int = 100):
        super().__init__(app)
        self.limit = limit_per_minute
        self.window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    @staticmethod
    def _client_key(request: Request) -> str:
        # Prefer the session identity (cookie, then transitional header).
        token = request.cookies.get("mailmind_session") or request.headers.get("x-mailmind-session")
        if token:
            import hashlib
            return "s:" + hashlib.sha256(token.encode()).hexdigest()[:32]
        return "ip:" + (request.client.host if request.client else "unknown")

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _RATE_LIMIT_EXEMPT or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = self._client_key(request)
        now = time.time()
        hits = self._hits[client_ip]

        # Drop timestamps outside the current window.
        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= self.limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            audit.warning(
                "RATE_LIMIT_EXCEEDED client=%s path=%s hits=%d limit=%d retry_after=%ds",
                client_ip, request.url.path, len(hits), self.limit, retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry shortly."},
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)
