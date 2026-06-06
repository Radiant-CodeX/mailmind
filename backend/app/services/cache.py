from __future__ import annotations

import time
from threading import Lock
from typing import Any


class TTLCache:
    """A thread-safe time-to-live cache for ephemeral lookups."""

    def __init__(self, default_ttl: int = 300) -> None:
        self.default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value with an expiration time."""
        expiry = time.time() + (ttl or self.default_ttl)
        with self._lock:
            self._store[key] = (expiry, value)

    def get(self, key: str) -> Any | None:
        """Return a cached value if it is still valid, otherwise remove and return None."""
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
        """Remove all entries from the cache."""
        with self._lock:
            self._store.clear()
