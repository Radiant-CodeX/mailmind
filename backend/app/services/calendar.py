from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, List, Optional

from app.models.schemas import CalendarEvent
from app.services.graph import GraphClient


class CalendarConflictService:
    """Utility service for parsing dates and checking calendar conflicts."""

    def __init__(self, graph_client: GraphClient) -> None:
        self.graph_client = graph_client

    def _parse_date_string(self, raw: str, reference: datetime) -> Optional[datetime]:
        """Parse raw date text into a datetime object."""
        lower = raw.lower().strip()
        # Handle relative dates
        if "today" in lower:
            return reference
        elif "tomorrow" in lower:
            return reference + timedelta(days=1)
        elif "next week" in lower:
            return reference + timedelta(days=7)
        
        # Check weekdays
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for idx, day in enumerate(weekdays):
            if day in lower:
                curr_weekday = reference.weekday()
                target_weekday = idx
                days_ahead = target_weekday - curr_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                return reference + timedelta(days=days_ahead)

        # Standard date parses
        patterns = [
            r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z?)",
            r"(\d{4}-\d{2}-\d{2})",
            r"([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw, re.I)
            if match:
                val = match.group(1)
                try:
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        return datetime.strptime(val, "%B %d, %Y")
                    except ValueError:
                        try:
                            return datetime.strptime(val, "%B %d")
                        except ValueError:
                            continue
        return None

    def _fallback_extract_date(self, text: str, reference: datetime | None = None) -> Optional[datetime]:
        """Original deterministic fallback regex date finder."""
        reference = reference or datetime.utcnow()
        patterns = [
            r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z?)",
            r"(\d{4}-\d{2}-\d{2})",
            r"on\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
            r"by\s+([A-Za-z]+\s+\d{1,2}(?:,\s*\d{4})?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                raw = match.group(1)
                try:
                    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        return datetime.strptime(raw, "%B %d, %Y")
                    except ValueError:
                        try:
                            return datetime.strptime(raw, "%B %d")
                        except ValueError:
                            continue
        return None

    def extract_date_ner(self, text: str, reference: datetime | None = None) -> Optional[dict[str, Any]]:
        """Extract date/time entities using spaCy and return structured date, time, and confidence."""
        reference = reference or datetime.utcnow()
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            doc = nlp(text)
            date_ents = [ent for ent in doc.ents if ent.label_ in ("DATE", "TIME")]
            if date_ents:
                ent = date_ents[0]
                dt = self._parse_date_string(ent.text, reference)
                if dt:
                    return {
                        "date": dt.date().isoformat(),
                        "time": dt.time().isoformat(),
                        "confidence": 0.95 if ent.label_ == "DATE" else 0.85
                    }
        except Exception:
            pass

        # Fallback to regex
        dt = self._fallback_extract_date(text, reference)
        if dt:
            return {
                "date": dt.date().isoformat(),
                "time": dt.time().isoformat(),
                "confidence": 0.70
            }
        return None

    def extract_date(self, text: str, reference: datetime | None = None) -> Optional[datetime]:
        """Extract a date from free-form text using spaCy NER model, falling back to regex patterns."""
        info = self.extract_date_ner(text, reference)
        if info:
            dt_str = f"{info['date']}T{info['time']}"
            return datetime.fromisoformat(dt_str)
        return None

    def fetch_events(self, days: int = 3) -> List[CalendarEvent]:
        """Fetch and normalize graph calendar events to the CalendarEvent schema."""
        now = datetime.utcnow()
        raw = self.graph_client.get_calendar_events(now, now + timedelta(days=days))
        events: list[CalendarEvent] = []
        for item in raw:
            try:
                events.append(
                    CalendarEvent(
                        title=item.get("title", "Untitled event"),
                        start_time=item.get("start_time", now),
                        end_time=item.get("end_time", now + timedelta(hours=1)),
                        organizer=item.get("organizer", "unknown@example.com"),
                    )
                )
            except Exception:
                continue
        return events

    def check_conflict(self, deadline: datetime, window_hours: int = 2) -> dict[str, Any]:
        """Detect whether a proposed deadline collides with existing calendar events."""
        events = self.graph_client.get_calendar_events(datetime.utcnow(), datetime.utcnow() + timedelta(days=3))
        for event in events:
            start = event.get("start_time")
            end = event.get("end_time")
            if not isinstance(start, datetime) or not isinstance(end, datetime):
                continue
            if abs((start - deadline).total_seconds()) <= window_hours * 3600:
                return {
                    "conflict_badge": True,
                    "conflict_detail": f"Conflicts with '{event.get('title', 'event')}' at {start.isoformat()}",
                }
        return {"conflict_badge": False, "conflict_detail": None}
