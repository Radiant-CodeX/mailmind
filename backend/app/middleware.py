"""Production middleware: security headers and global rate limiting.

Uses pure ASGI middleware (not BaseHTTPMiddleware) to avoid Starlette's known
issue where BaseHTTPMiddleware can strip Set-Cookie headers from responses.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from starlette.types import ASGIApp, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """Attach a baseline set of hardening headers to every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_https = scope.get("scheme") == "https"

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {h[0].lower() for h in headers}
                to_add = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
                ]
                if is_https:
                    to_add.append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                for key, value in to_add:
                    if key not in existing:
                        headers.append((key, value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


_RATE_LIMIT_EXEMPT = {"/api/health", "/api/ready", "/health", "/ready"}


class RateLimitMiddleware:
    """Fixed-window per-IP rate limiter applied across all routes."""

    def __init__(self, app: ASGIApp, limit_per_minute: int = 100) -> None:
        self.app = app
        self.limit = limit_per_minute
        self.window = 60.0
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")

        if path in _RATE_LIMIT_EXEMPT or method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        now = time.time()
        hits = self._hits[client_ip]

        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= self.limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            body = b'{"detail":"Rate limit exceeded. Please retry shortly."}'
            headers = [
                (b"content-type", b"application/json"),
                (b"retry-after", str(retry_after).encode()),
                (b"content-length", str(len(body)).encode()),
            ]
            await send({"type": "http.response.start", "status": 429, "headers": headers})
            await send({"type": "http.response.body", "body": body})
            return

        hits.append(now)
        await self.app(scope, receive, send)
