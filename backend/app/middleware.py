"""Production middleware: security headers and global rate limiting.

These wrap every request (not just /api/ingest) so the whole surface is
protected once mounted in main.py.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Endpoints that must never be rate limited (liveness/readiness probes).
_RATE_LIMIT_EXEMPT = {"/api/health", "/api/ready", "/health", "/ready"}


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
    """Fixed-window per-IP rate limiter applied across all routes.

    This complements the per-endpoint limiter used on /api/ingest by providing
    a global ceiling. State is in-memory; for multi-instance deployments swap
    the backing store for Redis.
    """

    def __init__(self, app, limit_per_minute: int = 100):
        super().__init__(app)
        self.limit = limit_per_minute
        self.window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _RATE_LIMIT_EXEMPT or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        hits = self._hits[client_ip]

        # Drop timestamps outside the current window.
        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= self.limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry shortly."},
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)
