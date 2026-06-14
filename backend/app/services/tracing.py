"""
LangSmith tracing helpers for the agentic pipeline.
====================================================

LangChain auto-traces every ``.invoke()`` to LangSmith when ``LANGCHAIN_TRACING_V2``
is enabled (wired from ``LANGSMITH_TRACING`` in ``config/settings.py``). The SDK
buffers run submissions on a background thread and flushes them periodically.

That batching is the reason the **streaming** endpoints appeared to never reach
LangSmith: a Server-Sent-Events response can finish streaming and the request
context unwinds *before* the periodic flush fires, so the runs for that stream are
dropped on the floor. The fix is to force a flush when the generator finishes
(``flush_tracers`` in a ``finally``), and to tag each node's LLM call so the runs
are searchable per email/user instead of a flat list of anonymous chat calls.

Everything here is a no-op when tracing is disabled and never raises into the
request path — observability must not be able to break email processing.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


def tracing_enabled() -> bool:
    """True when LangSmith tracing is switched on for this process."""
    return (
        os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
        or os.getenv("LANGSMITH_TRACING", "").lower() in ("1", "true", "yes")
    )


def flush_tracers() -> None:
    """Force any buffered LangSmith runs to be posted *now*.

    Call this in the ``finally`` of a streaming generator so the runs produced
    while serving the stream are sent before the connection closes, rather than
    waiting for a periodic flush that may never come once the request unwinds.
    """
    if not tracing_enabled():
        return
    try:
        from langchain_core.tracers.langchain import wait_for_all_tracers
        wait_for_all_tracers()
    except Exception as exc:  # pragma: no cover - tracing must never break a request
        logger.debug("flush_tracers skipped: %s", exc)


def trace_config(
    node: str,
    *,
    email_id: str | None = None,
    user: str | None = None,
    extra_tags: Optional[list[str]] = None,
    **metadata: Any,
) -> Optional[dict[str, Any]]:
    """Build a LangChain ``config`` that names + tags an LLM run for LangSmith.

    Returns ``None`` when tracing is off so callers can pass it straight through
    to ``.invoke(messages, config=...)`` with zero overhead in the common case.
    Tagging by node/email/user turns the trace view into something you can
    actually search and group by, which is the whole point of wiring LangSmith.
    """
    if not tracing_enabled():
        return None
    tags = [f"node:{node}"]
    if extra_tags:
        tags.extend(extra_tags)
    md: dict[str, Any] = {"node": node}
    if email_id:
        md["email_id"] = email_id
    if user:
        md["user"] = user
    md.update(metadata)
    return {"run_name": f"{node}", "tags": tags, "metadata": md}
