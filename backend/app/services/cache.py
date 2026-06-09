from __future__ import annotations

import json
import logging
import time
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class TTLCache:
    """A thread-safe time-to-live in-memory cache for ephemeral lookups."""

    def __init__(self, default_ttl: int = 300) -> None:
        self.default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        expiry = time.time() + (ttl or self.default_ttl)
        with self._lock:
            self._store[key] = (expiry, value)

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            expiry, value = item
            if expiry < time.time():
                del self._store[key]
                return None
            return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class TriageCache:
    """
    Two-level triage cache: Redis (fast, shared) → in-memory TTLCache (local).

    Cache hierarchy on GET:
      1. In-memory TTLCache (sub-ms)
      2. Redis (1-5ms, shared across workers)
      3. PostgreSQL DB (caller's responsibility)

    On SET, writes to both Redis and in-memory so the next call is instant.
    Falls back gracefully to memory-only when Redis is not configured/reachable.
    TTL: 7 days (triage scores are stable; only invalidated on explicit delete).
    """

    TRIAGE_TTL = 7 * 24 * 3600  # 7 days in seconds
    KEY_PREFIX = "mailmind:triage:"

    def __init__(self) -> None:
        self._memory = TTLCache(default_ttl=self.TRIAGE_TTL)
        self._redis: Any = None
        self._redis_ok = False
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import os
            redis_url = os.getenv("REDIS_URL", "")
            if not redis_url:
                return
            import redis as redis_lib
            client = redis_lib.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
            client.ping()
            self._redis = client
            self._redis_ok = True
            logger.info("[TriageCache] Redis connected at %s", redis_url)
        except Exception as e:
            logger.info("[TriageCache] Redis not available (%s) — using memory-only cache", e)
            self._redis_ok = False

    def _rkey(self, email_id: str, user_email: str = "") -> str:
        prefix = user_email.lower() if user_email else "_global"
        return f"{self.KEY_PREFIX}{prefix}:{email_id}"

    def _mkey(self, email_id: str, user_email: str = "") -> str:
        prefix = user_email.lower() if user_email else "_global"
        return f"{prefix}:{email_id}"

    def get(self, email_id: str, user_email: str = "") -> dict[str, Any] | None:
        mkey = self._mkey(email_id, user_email)
        # 1. In-memory
        hit = self._memory.get(mkey)
        if hit is not None:
            return hit
        # 2. Redis
        if self._redis_ok:
            try:
                raw = self._redis.get(self._rkey(email_id, user_email))
                if raw:
                    data = json.loads(raw)
                    self._memory.set(mkey, data, ttl=self.TRIAGE_TTL)
                    return data
            except Exception as e:
                logger.warning("[TriageCache] Redis get error: %s", e)
        return None

    def set(self, email_id: str, data: dict[str, Any], user_email: str = "") -> None:
        self._memory.set(self._mkey(email_id, user_email), data, ttl=self.TRIAGE_TTL)
        if self._redis_ok:
            try:
                self._redis.setex(self._rkey(email_id, user_email), self.TRIAGE_TTL, json.dumps(data))
            except Exception as e:
                logger.warning("[TriageCache] Redis set error: %s", e)

    def delete(self, email_id: str, user_email: str = "") -> None:
        mkey = self._mkey(email_id, user_email)
        self._memory._store.pop(mkey, None)
        if self._redis_ok:
            try:
                self._redis.delete(self._rkey(email_id, user_email))
            except Exception:
                pass

    def clear_memory(self) -> None:
        """Clear the in-memory layer (called on user switch to prevent cross-user hits)."""
        self._memory.clear()


# Global cache instances
classification_cache = TTLCache(default_ttl=86400)
triage_cache_store = TriageCache()          # Redis-backed triage cache
precedents_cache = TTLCache(default_ttl=86400)
commitments_cache = TTLCache(default_ttl=86400)

# Keep legacy name working
triage_cache = TTLCache(default_ttl=86400)


def clear_all_user_caches() -> None:
    """
    Wipe all in-memory caches.

    Call this when a new user logs in so stale data from the previous session
    cannot bleed through to the incoming user.  Redis keys are user-scoped by
    email prefix, so they are safe without a full flush.
    """
    classification_cache.clear()
    triage_cache_store.clear_memory()
    precedents_cache.clear()
    commitments_cache.clear()
    triage_cache.clear()
    logger.info("[cache] All in-memory user caches cleared on session change.")
