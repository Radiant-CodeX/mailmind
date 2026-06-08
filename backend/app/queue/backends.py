"""
Queue backends — pluggable durable work queue for the enrichment pipeline.
============================================================================

MailMind splits email processing into a fast synchronous *triage* path and a
deferred asynchronous *enrichment* path (commitments → calendar → RAG → draft).
The enrichment jobs are handed off through a queue so that:

  * the API responds in <1.5s (triage SLA) while heavy work runs in the
    background, and
  * enrichment workers can be scaled horizontally and independently.

Two interchangeable backends are provided behind a single ``QueueBackend``
protocol so the same code runs from laptop to production:

  ┌────────────┬──────────────────────────┬──────────────────────────────┐
  │ Backend    │ Use                      │ Durability                   │
  ├────────────┼──────────────────────────┼──────────────────────────────┤
  │ memory     │ local dev / tests        │ lost on restart (in-process) │
  │ redis      │ staging / production     │ survives restarts, multi-node│
  └────────────┴──────────────────────────┴──────────────────────────────┘

``get_queue_backend()`` selects the backend from ``settings.queue_backend`` and
*gracefully degrades* to in-memory if Redis is configured but unreachable, so a
transient Redis outage never hard-crashes the API.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from typing import Any, Optional, Protocol

from app.config.settings import settings

logger = logging.getLogger(__name__)


class QueueBackend(Protocol):
    """Minimal queue contract used by producers (API) and consumers (workers)."""

    name: str

    def enqueue(self, job: dict[str, Any]) -> None:
        """Append a job (a JSON-serialisable dict) to the tail of the queue."""
        ...

    def dequeue(self) -> Optional[dict[str, Any]]:
        """Pop the next job from the head, or return None if the queue is empty."""
        ...

    def depth(self) -> int:
        """Return the current number of pending jobs (for metrics/backpressure)."""
        ...

    def healthy(self) -> bool:
        """Return True if the backend is reachable/operational."""
        ...


class InMemoryQueueBackend:
    """
    Thread-safe in-process FIFO queue.

    Suitable for development and unit tests. Not durable: jobs are lost on
    process restart and are not shared across processes. The API and worker
    must run in the same process to share this queue.
    """

    name = "memory"

    def __init__(self) -> None:
        self._queue: deque[dict[str, Any]] = deque()
        self._lock = threading.Lock()

    def enqueue(self, job: dict[str, Any]) -> None:
        with self._lock:
            self._queue.append(job)

    def dequeue(self) -> Optional[dict[str, Any]]:
        with self._lock:
            return self._queue.popleft() if self._queue else None

    def depth(self) -> int:
        with self._lock:
            return len(self._queue)

    def healthy(self) -> bool:
        return True


class RedisQueueBackend:
    """
    Redis-backed durable FIFO queue using a single list key.

    Jobs are pushed with LPUSH and consumed with RPOP (FIFO ordering). Values
    are JSON-encoded. Durable across restarts and shared by any number of API
    and worker processes pointed at the same Redis instance.
    """

    name = "redis"

    def __init__(self, redis_url: str, key: str) -> None:
        import redis  # imported lazily so dev installs need not include redis

        self._key = key
        # decode_responses=True → we get/put str, not bytes.
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        # Fail fast on construction so the factory can fall back cleanly.
        self._client.ping()

    def enqueue(self, job: dict[str, Any]) -> None:
        self._client.lpush(self._key, json.dumps(job))

    def dequeue(self) -> Optional[dict[str, Any]]:
        raw = self._client.rpop(self._key)
        return json.loads(raw) if raw else None

    def depth(self) -> int:
        return int(self._client.llen(self._key))

    def healthy(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False


_backend_singleton: Optional[QueueBackend] = None


def get_queue_backend() -> QueueBackend:
    """
    Return the process-wide queue backend, constructing it on first use.

    Selection follows ``settings.queue_backend``. If "redis" is requested but
    the Redis server cannot be reached, we log a clear warning and fall back to
    the in-memory backend so the service stays up (degraded, single-process).
    """
    global _backend_singleton
    if _backend_singleton is not None:
        return _backend_singleton

    if settings.queue_backend.lower() == "redis":
        try:
            _backend_singleton = RedisQueueBackend(settings.redis_url, settings.queue_enrichment_key)
            logger.info("Queue backend: redis (%s)", settings.queue_enrichment_key)
        except Exception as exc:  # connection refused, auth error, etc.
            logger.warning(
                "Redis queue unavailable (%s: %s) — falling back to in-memory queue. "
                "Enrichment will run single-process until Redis recovers.",
                type(exc).__name__, exc,
            )
            _backend_singleton = InMemoryQueueBackend()
    else:
        _backend_singleton = InMemoryQueueBackend()
        logger.info("Queue backend: memory")

    return _backend_singleton


def reset_queue_backend() -> None:
    """Reset the singleton (used by tests to swap backends)."""
    global _backend_singleton
    _backend_singleton = None
