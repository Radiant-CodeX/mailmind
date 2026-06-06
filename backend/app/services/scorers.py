from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.models.schemas import AxisScore, TriageResult


def _ensure_utc(value: datetime) -> datetime:
    """Normalize naive datetimes to UTC for consistent scoring."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@dataclass
class DeadlineScorer:
    """Score emails by inferred deadline urgency."""

    lookback_days: int = 14

    def score(self, body: str, reference_date: datetime | None = None) -> AxisScore:
        reference_date = _ensure_utc(reference_date or datetime.now(tz=timezone.utc))
        deadline = self._find_deadline(body, reference_date)
        if not deadline:
            return AxisScore(axis="deadline", raw_score=0.0, explanation="No deadline detected")

        days_until = max(0.0, (deadline - reference_date).total_seconds() / 86400.0)
        raw_score = max(0.0, min(1.0, 1.0 - (days_until / self.lookback_days)))
        explanation = f"Deadline in {days_until:.1f} days"
        if days_until <= 0:
            explanation = "Deadline has passed or is due today"
        return AxisScore(axis="deadline", raw_score=raw_score, explanation=explanation)

    def _find_deadline(self, body: str, reference_date: datetime) -> datetime | None:
        """Parse natural language deadline expressions from the email body."""
        body = body.lower()
        patterns = [
            r"due(?: on)? (?P<date>[a-zA-Z0-9\-: ]+)",
            r"by (?P<date>[a-zA-Z0-9\-: ]+)",
            r"deadline(?:\s*:)? (?P<date>[a-zA-Z0-9\-: ]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, body)
            if match:
                raw = match.group("date").strip()
                parsed = self._parse_date(raw, reference_date)
                if parsed:
                    return parsed
        return None

    def _parse_date(self, raw: str, reference_date: datetime) -> datetime | None:
        """Convert simple date phrases into datetime objects."""
        raw = raw.strip().lower()
        if raw == "today":
            return _ensure_utc(datetime(reference_date.year, reference_date.month, reference_date.day))
        if raw == "tomorrow":
            tomorrow = reference_date + timedelta(days=1)
            return _ensure_utc(datetime(tomorrow.year, tomorrow.month, tomorrow.day))
        iso_match = re.match(r"(\d{4}-\d{2}-\d{2})(?:[ t](\d{2}:\d{2}))?", raw)
        if iso_match:
            date_part = iso_match.group(1)
            time_part = iso_match.group(2) or "00:00"
            try:
                parsed = datetime.fromisoformat(f"{date_part}T{time_part}")
                return _ensure_utc(parsed)
            except ValueError:
                return None
        weekday_map = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        if raw.startswith("next "):
            day = raw[5:]
            if day in weekday_map:
                target = weekday_map[day]
                current = reference_date.weekday()
                offset = (target - current + 7) % 7 or 7
                return reference_date + timedelta(days=offset)
        if raw in weekday_map:
            target = weekday_map[raw]
            current = reference_date.weekday()
            offset = (target - current + 7) % 7
            if offset == 0:
                offset = 7
            return reference_date + timedelta(days=offset)
        md_match = re.match(r"([a-zA-Z]+) (\d{1,2})(?:,? (\d{4}))?", raw)
        if md_match:
            month_name = md_match.group(1)
            day = int(md_match.group(2))
            year = int(md_match.group(3)) if md_match.group(3) else reference_date.year
            try:
                month = datetime.strptime(month_name, "%B").month
            except ValueError:
                try:
                    month = datetime.strptime(month_name, "%b").month
                except ValueError:
                    return None
            try:
                return _ensure_utc(datetime(year, month, day))
            except ValueError:
                return None
        return None


@dataclass
class SenderAuthorityScorer:
    """Score sender authority using Graph metadata and local caching."""

    graph_client: Any
    cache: dict[str, tuple[float, dict[str, Any]]] | None = None

    def __post_init__(self) -> None:
        if self.cache is None:
            self.cache = {}

    def score(self, sender_email: str) -> AxisScore:
        cached = self.cache.get(sender_email)
        if cached and cached[0] > datetime.now(tz=timezone.utc).timestamp():
            return AxisScore(axis="authority", raw_score=cached[1]["score"], explanation=cached[1]["explanation"])
        metadata = self.graph_client.get_sender_authority(sender_email)
        role = metadata.get("role", "external")
        score = metadata.get("score", 0.1)
        explanation = f"Sender role {role}"
        self.cache[sender_email] = (datetime.now(tz=timezone.utc).timestamp() + 7 * 24 * 3600, {"score": score, "explanation": explanation})
        return AxisScore(axis="authority", raw_score=score, explanation=explanation)


@dataclass
class ThreadAgeDecayScorer:
    """Score older threads lower to prioritize recent messages."""

    max_days: int = 30

    def score(self, creation_date: datetime) -> AxisScore:
        creation_date = creation_date if creation_date.tzinfo else creation_date.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(tz=timezone.utc) - creation_date).total_seconds() / 86400.0)
        raw_score = max(0.0, min(1.0, 1.0 - (age_days / self.max_days) ** 2))
        explanation = f"Thread age {age_days:.1f} days"
        return AxisScore(axis="decay", raw_score=raw_score, explanation=explanation)


@dataclass
class ActionTypeScorer:
    """Detect whether an email requires direct action or is informational."""

    required_patterns: list[str] = (
        r"\b(review|approve|sign|action required|please respond|respond by)\b",
    )
    optional_patterns: list[str] = (
        r"\b(if interested|optional|when convenient|when you have time)\b",
    )

    def score(self, body: str) -> AxisScore:
        lower = body.lower()
        for pattern in self.required_patterns:
            if re.search(pattern, lower):
                return AxisScore(axis="action", raw_score=1.0, explanation="Action required detected")
        for pattern in self.optional_patterns:
            if re.search(pattern, lower):
                return AxisScore(axis="action", raw_score=0.5, explanation="Action optional detected")
        return AxisScore(axis="action", raw_score=0.0, explanation="No action keyword detected")


@dataclass
class CompositeAggregator:
    """Combine multiple axis scores into one triage recommendation."""

    weights: dict[str, float] = None

    def __post_init__(self) -> None:
        if self.weights is None:
            self.weights = {
                "deadline": 0.30,
                "authority": 0.25,
                "sentiment": 0.20,
                "decay": 0.15,
                "action": 0.10,
            }

    def aggregate(self, axes: list[AxisScore]) -> TriageResult:
        weighted_sum = 0.0
        for axis in axes:
            weight = self.weights.get(axis.axis, 0.0)
            weighted_sum += axis.raw_score * weight
        composite_score = max(0.0, min(100.0, weighted_sum * 100.0))
        if composite_score >= 75:
            priority = "CRITICAL"
            approval_mode = "GATE"
        elif composite_score >= 50:
            priority = "HIGH"
            approval_mode = "SUGGEST"
        elif composite_score >= 25:
            priority = "MEDIUM"
            approval_mode = "SUGGEST"
        else:
            priority = "LOW"
            approval_mode = "SUGGEST"
        return TriageResult(axes=axes, composite_score=composite_score, priority=priority, approval_mode=approval_mode)
