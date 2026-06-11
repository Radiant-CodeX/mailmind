"""
Request-scoped identity for per-request mail-client construction.
=================================================================

A ``ContextVar`` carries the current request's session ({user_id, provider,
email}) so that ``get_mail_client()`` — called from routes *and* from deep
inside services (draft, tone-DNA, commitments) — resolves the correct user's
mailbox without every caller having to thread a ``session`` argument through.

ContextVars are isolated per asyncio task, so concurrent requests never see
each other's identity. They do NOT auto-propagate into worker threads, so
code that hands mail-client work to a ``ThreadPoolExecutor`` must run it inside
``contextvars.copy_context()`` (see ``run_in_context``).
"""
from __future__ import annotations

import contextvars
from typing import Any, Callable

_current_session: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "mailmind_current_session", default=None
)


def set_current_session(session: dict[str, Any] | None) -> contextvars.Token:
    """Bind the current request's session; returns a token for reset()."""
    return _current_session.set(session)


def get_current_session() -> dict[str, Any] | None:
    """Return the session bound to this request/task, or None."""
    return _current_session.get()


def reset_current_session(token: contextvars.Token) -> None:
    """Restore the previous session binding (call in a finally block)."""
    _current_session.reset(token)


def run_in_context(fn: Callable[[], Any]) -> Callable[[], Any]:
    """Wrap ``fn`` so it runs inside a copy of the current context.

    Use when submitting mail-client work to a thread pool, so the worker
    thread sees the same session as the request that spawned it::

        executor.submit(run_in_context(do_work))
    """
    ctx = contextvars.copy_context()
    return lambda: ctx.run(fn)
