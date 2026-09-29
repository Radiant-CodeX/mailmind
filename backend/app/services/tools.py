from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, List

from app.services.cache import TTLCache


class ThreadFetcher:
    """Fetch thread messages with a local TTL cache to avoid repeated Gmail calls."""

    def __init__(self, mail_client: Any, ttl_seconds: int = 300) -> None:
        self.mail_client = mail_client
        self.cache = TTLCache(default_ttl=ttl_seconds)

    def fetch(self, thread_id: str) -> List[dict[str, Any]]:
        """Return thread messages, using cached results when available."""
        cached = self.cache.get(thread_id)
        if cached is not None:
            return cached

        messages = self.mail_client.get_thread_messages(thread_id)
        if len(messages) > 10:
            messages = messages[-10:]
        self.cache.set(thread_id, messages)
        return messages


class CalendarFetcher:
    """Retrieve calendar events and normalize them for API output."""

    def __init__(self, mail_client: Any) -> None:
        self.mail_client = mail_client

    def fetch_next_events(self, days: int = 3) -> List[dict[str, Any]]:
        """Fetch upcoming events for the next n days."""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(days=days)
        raw_events = self.mail_client.get_calendar_events(start_time, end_time)
        return [
            {
                "title": item.get("title", "Untitled event"),
                "start_time": item.get("start_time", start_time),
                "end_time": item.get("end_time", end_time),
                "organizer": item.get("organizer", "unknown@example.com"),
            }
            for item in raw_events
        ]
