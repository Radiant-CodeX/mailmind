"""Error tracking and structured logging setup.

Centralises:
  * structured logging configuration
  * optional Sentry initialisation (no-op unless SENTRY_DSN is set)
  * global exception handlers that return clean JSON and log full context

Wire this up from main.py via `init_observability(app)`.
"""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("mailmind")

_SENTRY_ENABLED = False


def init_sentry() -> bool:
    """Initialise Sentry if SENTRY_DSN is configured. Returns True if enabled."""
    global _SENTRY_ENABLED
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("APP_ENV", "production"),
            release=os.getenv("APP_RELEASE", "mailmind@2.0.0"),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            integrations=[StarletteIntegration(), FastApiIntegration()],
            send_default_pii=False,
        )
        _SENTRY_ENABLED = True
        logger.info("Sentry error tracking enabled")
        return True
    except Exception as exc:  # pragma: no cover - depends on optional dep
        logger.warning("Sentry requested but failed to initialise: %s", exc)
        return False


def _capture(exc: Exception) -> None:
    if _SENTRY_ENABLED:
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(exc)
        except Exception:  # pragma: no cover
            pass


def _cors_headers(request: Request) -> dict[str, str]:
    """Echo the request Origin back so error responses are never blocked by CORS.

    Exception handlers can bypass CORSMiddleware in some Starlette setups, which
    makes the browser report a real 4xx/5xx as a misleading 'Failed to fetch'.
    Adding the header here guarantees the client always sees the actual error.
    """
    origin = request.headers.get("origin")
    if not origin:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


def init_observability(app: FastAPI) -> None:
    """Attach structured logging and global exception handlers to the app."""
    init_sentry()

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Pass through intended HTTP errors (401/404/429/...) untouched but logged.
        if exc.status_code >= 500:
            logger.error("HTTP %s on %s %s: %s", exc.status_code, request.method, request.url.path, exc.detail)
            _capture(exc)
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.detail}, headers=_cors_headers(request)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
        return JSONResponse(status_code=422, content={"detail": exc.errors()}, headers=_cors_headers(request))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Last-resort handler: never leak stack traces to the client.
        error_id = uuid.uuid4().hex[:12]
        logger.exception("Unhandled error [%s] on %s %s", error_id, request.method, request.url.path)
        _capture(exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal error occurred. Please try again.",
                "error_id": error_id,
            },
            headers=_cors_headers(request),
        )
