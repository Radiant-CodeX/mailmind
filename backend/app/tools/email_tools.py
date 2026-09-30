"""
MailMind v2 — LangChain Tool Definitions
------------------------------------------
Each function here is decorated with @tool so it can be exposed to a
tool-calling model. They double as the deterministic (no-AI) scoring path: when
no model is configured, or a model call fails, the pipeline runs these directly.
The scorers are campus-aware (see app.services.campus).

Tools are grouped by concern:
  - Security / PII masking
  - Five-axis triage scoring
  - Commitment extraction
  - Calendar conflict detection
  - RAG precedent retrieval
  - Draft generation
"""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from langchain_core.tools import tool

# ─────────────────────────────────────────────────────────────────────────────
# 1. PII MASKING TOOL
# ─────────────────────────────────────────────────────────────────────────────

@tool
def mask_pii(text: str) -> str:
    """
    Scrub personally identifiable information from email body text before
    any LLM processing or vector indexing.

    Replaces email addresses, phone numbers, and names with
    safe placeholder tokens using Presidio + spaCy (and a regex fallback).

    Args:
        text: Raw email body text.

    Returns:
        PII-masked version of the text safe for LLM consumption.
    """
    from app.services.pii import pii_sanitizer
    masked, _ = pii_sanitizer.mask_text(text)
    return masked


# ─────────────────────────────────────────────────────────────────────────────
# 2. FIVE-AXIS TRIAGE SCORING TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@tool
def score_deadline_axis(body: str, subject: str = "", received_at: str = "") -> dict[str, Any]:
    """
    Score the email on the DEADLINE axis (weight: 30%).

    Parses natural language deadline expressions across both subject and body:
    - Relative: today, tomorrow, next Friday, this Monday, end of week/month
    - Absolute: June 15, 15th June, June 15th, 2026-06-15, 06/15/2026
    - Time-relative: within 24 hours, within 48 hours, within the week
    - Time-of-day: by EOD, by 5 PM, by noon, by end of day
    - Business: by COB, by close of business

    All relative expressions are anchored to received_at (the email's arrival
    time) rather than the current clock, so "today" means the day the email
    was sent, not when the pipeline processes it.

    Args:
        body: PII-masked email body text.
        subject: Email subject line (may contain deadline hints).
        received_at: ISO 8601 datetime when the email was received. Defaults
                     to current time if not provided.

    Returns:
        dict with keys: axis (str), raw_score (float 0-1), explanation (str).
    """
    # ── Reference point: use email's received_at, not pipeline runtime ──────
    now_real = datetime.now(tz=timezone.utc)
    try:
        ref = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        ref = now_real

    # Search both subject and body; subject keywords often carry the deadline
    full_text = f"{subject} {body}".lower().strip()
    deadline: datetime | None = None
    explanation_hint = ""

    # ── 1. Overdue / already-passed signals ─────────────────────────────────
    if re.search(r"\b(overdue|past due|missed deadline|already late)\b", full_text):
        return {"axis": "deadline", "raw_score": 1.0, "explanation": "Says something is already overdue"}
    if re.search(r"\b(closes today|closing today|last date is today|today is the last date|"
                 r"final call|registration closes in)\b", full_text):
        return {"axis": "deadline", "raw_score": 1.0, "explanation": "Closes today"}

    # ── 2. Absolute time-relative expressions ───────────────────────────────
    within_match = re.search(r"within\s+(\d+)\s*(hour|hr|day)", full_text)
    if within_match:
        qty = int(within_match.group(1))
        unit = within_match.group(2)
        delta = timedelta(hours=qty) if "hour" in unit or "hr" in unit else timedelta(days=qty)
        deadline = ref + delta
        explanation_hint = f"'within {qty} {unit}(s)' of receipt"

    # ── 3. EOD / COB / noon expressions ─────────────────────────────────────
    if not deadline:
        if re.search(r"\b(eod|end of (the )?day|close of (business|day)|cob)\b", full_text):
            deadline = ref.replace(hour=17, minute=0, second=0, microsecond=0)
            if deadline < ref:
                deadline += timedelta(days=1)
            explanation_hint = "by end of business day"
        elif re.search(r"\bby\s+noon\b", full_text):
            deadline = ref.replace(hour=12, minute=0, second=0, microsecond=0)
            if deadline < ref:
                deadline += timedelta(days=1)
            explanation_hint = "by noon"
        elif re.search(r"\bby\s+(\d{1,2})\s*(am|pm)\b", full_text):
            m = re.search(r"\bby\s+(\d{1,2})\s*(am|pm)\b", full_text)
            hour = int(m.group(1))
            if m.group(2) == "pm" and hour != 12:
                hour += 12
            elif m.group(2) == "am" and hour == 12:
                hour = 0
            deadline = ref.replace(hour=hour, minute=0, second=0, microsecond=0)
            if deadline < ref:
                deadline += timedelta(days=1)
            explanation_hint = f"by {m.group(1)}{m.group(2)}"

    # ── 4. Simple relative words ─────────────────────────────────────────────
    if not deadline:
        if re.search(r"\btoday\b", full_text):
            deadline = ref.replace(hour=17, minute=0, second=0, microsecond=0)
            explanation_hint = "today"
        elif re.search(r"\btomorrow\b", full_text):
            deadline = ref + timedelta(days=1)
            deadline = deadline.replace(hour=17, minute=0, second=0, microsecond=0)
            explanation_hint = "tomorrow"
        elif re.search(r"\bend of (this )?week\b", full_text):
            days_to_friday = (4 - ref.weekday()) % 7 or 7
            deadline = ref + timedelta(days=days_to_friday)
            deadline = deadline.replace(hour=17, minute=0, second=0, microsecond=0)
            explanation_hint = "end of week"
        elif re.search(r"\bnext week\b", full_text):
            deadline = ref + timedelta(days=7)
            explanation_hint = "next week"
        elif re.search(r"\bend of (this )?month\b", full_text):
            # Last day of the reference month
            if ref.month == 12:
                deadline = ref.replace(year=ref.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                deadline = ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)
            deadline = deadline.replace(hour=17, minute=0, second=0, microsecond=0)
            explanation_hint = "end of month"

    # ── 5. Named weekdays: "this Monday", "next Friday", "by Friday" ─────────
    if not deadline:
        weekday_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }
        next_match = re.search(
            r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", full_text
        )
        this_match = re.search(
            r"\b(?:this|by|on)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", full_text
        )
        target_match = next_match or this_match
        if target_match:
            day_name = target_match.group(1)
            target_wd = weekday_map[day_name]
            if next_match:
                # "next Friday" = always the Friday of next calendar week
                days_ahead = (target_wd - ref.weekday() + 7) % 7
                days_ahead = days_ahead if days_ahead > 0 else 7
                days_ahead += 7 if next_match else 0
            else:
                # "this Friday" / "by Friday" = nearest upcoming occurrence
                days_ahead = (target_wd - ref.weekday() + 7) % 7 or 7
            deadline = ref + timedelta(days=days_ahead)
            deadline = deadline.replace(hour=17, minute=0, second=0, microsecond=0)
            explanation_hint = f"by {day_name}"

    # ── 6. Month + day: "June 15", "June 15th", "15th June", "Jun 15" ───────
    if not deadline:
        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
            "january": 1, "february": 2, "march": 3, "april": 4,
            "june": 6, "july": 7, "august": 8, "september": 9,
            "october": 10, "november": 11, "december": 12,
        }
        # "June 15" / "June 15th"
        m = re.search(
            r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
            r"\s+(\d{1,2})(?:st|nd|rd|th)?\b",
            full_text,
        )
        if not m:
            # "15th June" / "15 June"
            m = re.search(
                r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
                r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
                r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
                full_text,
            )
            if m:
                day_part, month_part = m.group(1), m.group(2)
            else:
                day_part, month_part = None, None
        else:
            month_part, day_part = m.group(1), m.group(2)

        if month_part and day_part:
            month_num = month_map.get(month_part[:3].lower()) or month_map.get(month_part.lower())
            if month_num:
                year = ref.year
                try:
                    candidate = datetime(year, month_num, int(day_part), 17, 0, 0, tzinfo=timezone.utc)
                    if candidate < ref:
                        candidate = candidate.replace(year=year + 1)
                    deadline = candidate
                    explanation_hint = f"{month_part.title()} {day_part}"
                except ValueError:
                    pass

    # ── 7. ISO / numeric dates: 2026-06-15, 15/06/2026, 15-06-2026, 15.06.26 ─
    # Numeric day-first dates follow the Indian convention (DD/MM/YYYY); a
    # value that can't be a valid day-first date falls back to month-first.
    if not deadline:
        iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", full_text)
        dmy = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2}|\d{4})\b", full_text)
        if iso:
            try:
                deadline = datetime(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)),
                                    17, 0, 0, tzinfo=timezone.utc)
                explanation_hint = iso.group(0)
            except ValueError:
                pass
        elif dmy:
            a, b, year = int(dmy.group(1)), int(dmy.group(2)), int(dmy.group(3))
            if year < 100:
                year += 2000
            for day, month in ((a, b), (b, a)):
                try:
                    deadline = datetime(year, month, day, 17, 0, 0, tzinfo=timezone.utc)
                    explanation_hint = dmy.group(0)
                    break
                except ValueError:
                    continue

    # ── No deadline found ────────────────────────────────────────────────────
    if not deadline:
        return {"axis": "deadline", "raw_score": 0.0, "explanation": "No deadline mentioned"}

    # ── Score: use real wall-clock time to measure urgency from now ──────────
    seconds_until = (deadline - now_real).total_seconds()
    when = deadline.strftime("%A, %d %b")
    if seconds_until <= 0:
        raw_score = 1.0
        explanation = f"The deadline ({explanation_hint or when}) has passed"
    else:
        days_until = seconds_until / 86400.0
        # Steep decay: full score at 0 days, 0 score at 14 days
        raw_score = max(0.0, min(1.0, 1.0 - (days_until / 14.0)))
        hours = seconds_until / 3600.0
        if hours < 20:
            explanation = f"Due in about {max(1, round(hours))} hours"
        elif days_until < 1.6:
            explanation = f"Due tomorrow, {when}"
        else:
            explanation = f"Due in {round(days_until)} days, {when}"

    return {"axis": "deadline", "raw_score": round(raw_score, 3), "explanation": explanation}


@tool
def score_authority_axis(sender_email: str, subject: str = "", body: str = "") -> dict[str, Any]:
    """
    Score the email on the SENDER AUTHORITY axis (weight: 25%).

    Campus-aware: ranks university leadership and the Controller of
    Examinations, then HODs and the placement office, faculty, institutional
    offices, recruiters, fellow students and finally unknown senders. Titles
    only count when they come from an official campus address.

    Args:
        sender_email: The sender's email address (optionally with display name).
        subject: Email subject line.
        body: PII-masked email body text (signature is inspected).

    Returns:
        dict with keys: axis, raw_score (0-1), explanation.
    """
    from app.services.campus import score_authority

    result = score_authority(sender_email, subject, body)
    return {"axis": "authority", "raw_score": result["raw_score"], "explanation": result["explanation"]}


@tool
def score_sentiment_axis(body: str) -> dict[str, Any]:
    """
    Score the email on the SENTIMENT axis (weight: 20%).

    Detects emotional urgency signals — escalation language, frustration,
    panic — which indicate emails requiring faster human attention.
    Positive or neutral sentiment scores lower (less urgency).

    Args:
        body: PII-masked email body text.

    Returns:
        dict with keys: axis, raw_score (0-1), explanation.
    """
    from app.services.campus import consequence_hits

    lower = body.lower()

    # Campus consequence language (debarment, attendance shortage, penalties,
    # final reminders) is the strongest urgency signal in a student inbox.
    campus_hits = consequence_hits(body)
    if len(campus_hits) >= 2:
        return {"axis": "sentiment", "raw_score": 1.0,
                "explanation": f"Warns of {' and '.join(campus_hits[:2])}"}
    if campus_hits:
        return {"axis": "sentiment", "raw_score": 0.8,
                "explanation": f"Warns of {campus_hits[0]}"}

    critical_signals = ["furious", "escalate", "lawsuit", "unacceptable", "demand",
                        "immediately", "emergency", "critical", "outage", "down"]
    negative_signals = ["frustrated", "disappointed", "issue", "problem", "complaint",
                        "concern", "worried", "confused", "urgent", "asap"]
    positive_signals = ["thank", "great", "appreciate", "wonderful", "excellent",
                        "happy", "pleased", "fyi", "newsletter", "update"]

    critical_count = sum(1 for kw in critical_signals if kw in lower)
    negative_count = sum(1 for kw in negative_signals if kw in lower)
    positive_count = sum(1 for kw in positive_signals if kw in lower)

    if critical_count >= 2:
        return {"axis": "sentiment", "raw_score": 1.0, "explanation": "Written as an emergency or escalation"}
    if critical_count == 1:
        return {"axis": "sentiment", "raw_score": 0.85, "explanation": "Urgent, escalating tone"}
    if negative_count >= 3:
        return {"axis": "sentiment", "raw_score": 0.7, "explanation": "Frustrated or worried tone"}
    if negative_count >= 1:
        return {"axis": "sentiment", "raw_score": 0.5, "explanation": "Raises a problem or concern"}
    if positive_count >= 2:
        return {"axis": "sentiment", "raw_score": 0.1, "explanation": "Friendly, informational tone"}

    return {"axis": "sentiment", "raw_score": 0.3, "explanation": "Neutral tone"}


@tool
def score_decay_axis(received_at: str) -> dict[str, Any]:
    """
    Score the email on the THREAD AGE DECAY axis (weight: 15%).

    Newer emails score higher; older threads decay toward zero over 30 days.
    This prioritizes fresh messages over long-stale threads that may have
    already been resolved through other channels.

    Args:
        received_at: ISO 8601 datetime string of when the email was received.

    Returns:
        dict with keys: axis, raw_score (0-1), explanation.
    """
    try:
        received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        if received.tzinfo is None:
            received = received.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return {"axis": "decay", "raw_score": 0.5, "explanation": "Could not parse received_at timestamp"}

    now = datetime.now(tz=timezone.utc)
    age_days = max(0.0, (now - received).total_seconds() / 86400.0)
    raw_score = max(0.0, min(1.0, 1.0 - (age_days / 30.0) ** 2))
    if age_days < 1:
        age = f"{max(1, round(age_days * 24))} hours ago"
    else:
        age = f"{round(age_days)} day{'s' if round(age_days) != 1 else ''} ago"
    return {
        "axis": "decay",
        "raw_score": round(raw_score, 3),
        "explanation": f"Arrived {age}",
    }


@tool
def score_action_axis(body: str) -> dict[str, Any]:
    """
    Score the email on the ACTION REQUIRED axis (weight: 10%).

    Detects whether the email requires a direct response or action from
    the recipient. Strong action keywords (review, approve, sign, respond by)
    score 1.0; optional language scores 0.5; no action signal scores 0.0.

    Args:
        body: PII-masked email body text.

    Returns:
        dict with keys: axis, raw_score (0-1), explanation.
    """
    lower = body.lower()
    required = ["review", "approve", "sign", "action required", "please respond",
                "respond by", "need your input", "waiting for", "please confirm",
                # campus actions
                "register", "registration", "apply before", "apply by", "submit", "pay the",
                "fee payment", "download your hall ticket", "download the hall ticket",
                "report to", "reporting time", "must attend", "mandatory", "fill the form",
                "fill out the form", "upload", "complete the assessment",
                "meet me", "please meet", "come to my", "visit the", "collect your", "reply to confirm",
                "confirm your"]
    optional = ["if interested", "optional", "when convenient", "when you have time",
                "no rush", "fyi", "just letting you know"]

    for phrase in required:
        if phrase in lower:
            return {"axis": "action", "raw_score": 1.0, "explanation": _ACTION_WORDING.get(phrase, f"Asks you to {phrase}")}
    for phrase in optional:
        if phrase in lower:
            return {"axis": "action", "raw_score": 0.5, "explanation": "Optional, no action required"}

    return {"axis": "action", "raw_score": 0.0, "explanation": "Nothing asked of you"}


_ACTION_WORDING = {
    "review": "Asks you to review something",
    "approve": "Asks for your approval",
    "sign": "Asks for your signature",
    "action required": "Marked action required",
    "please respond": "Asks for your reply",
    "respond by": "Asks for your reply by a date",
    "need your input": "Asks for your input",
    "waiting for": "Someone is waiting on you",
    "please confirm": "Asks you to confirm",
    "register": "Asks you to register",
    "registration": "Asks you to register",
    "apply before": "Asks you to apply",
    "apply by": "Asks you to apply",
    "submit": "Asks you to submit something",
    "pay the": "Asks you to pay",
    "fee payment": "Asks you to pay a fee",
    "download your hall ticket": "Asks you to download your hall ticket",
    "download the hall ticket": "Asks you to download your hall ticket",
    "report to": "Asks you to report in person",
    "reporting time": "Gives you a reporting time",
    "must attend": "Asks you to attend",
    "mandatory": "Something is mandatory for you",
    "fill the form": "Asks you to fill a form",
    "fill out the form": "Asks you to fill a form",
    "upload": "Asks you to upload something",
    "complete the assessment": "Asks you to complete an assessment",
    "meet me": "Asks to meet you",
    "please meet": "Asks to meet you",
    "come to my": "Asks you to come in person",
    "visit the": "Asks you to visit in person",
    "collect your": "Asks you to collect something",
    "reply to confirm": "Asks you to reply and confirm",
    "confirm your": "Asks you to confirm",
}


@tool
def compute_composite_score(axes: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Aggregate five axis scores into a single composite triage score (0–100)
    using the MailMind weighted formula:
        deadline×0.30 + authority×0.25 + sentiment×0.20 + decay×0.15 + action×0.10

    Maps composite score to priority level and approval mode:
        ≥75 → CRITICAL / GATE (human must approve before any action)
        ≥50 → HIGH / SUGGEST
        ≥25 → MEDIUM / SUGGEST
         <25 → LOW / SUGGEST

    Args:
        axes: List of axis score dicts (each with 'axis', 'raw_score', 'explanation').

    Returns:
        dict with composite_score, priority, approval_mode.
    """
    weights = {
        "deadline": 0.30,
        "authority": 0.25,
        "sentiment": 0.20,
        "decay": 0.15,
        "action": 0.10,
    }
    weighted_sum = sum(
        axis["raw_score"] * weights.get(axis["axis"], 0.0)
        for axis in axes
    )
    composite = round(max(0.0, min(100.0, weighted_sum * 100.0)), 2)

    if composite >= 75:
        priority, approval_mode = "CRITICAL", "GATE"
    elif composite >= 50:
        priority, approval_mode = "HIGH", "SUGGEST"
    elif composite >= 25:
        priority, approval_mode = "MEDIUM", "SUGGEST"
    else:
        priority, approval_mode = "LOW", "SUGGEST"

    return {
        "composite_score": composite,
        "priority": priority,
        "approval_mode": approval_mode,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. COMMITMENT EXTRACTION TOOL
# ─────────────────────────────────────────────────────────────────────────────

@tool
def extract_commitments_from_text(masked_text: str) -> list[dict[str, Any]]:
    """
    Deterministic rule-based commitment extractor used as a fallback when
    the LLM tool-calling extraction is unavailable.

    Scans sentences for action verbs (review, approve, schedule, confirm,
    please, must, need to) and extracts them as commitment candidates with
    an estimated confidence score.

    The Commitment Agent calls this as a fallback while the configured model
    provides the primary extraction.

    Args:
        masked_text: PII-masked email body text.

    Returns:
        List of commitment dicts: id, commitment, deadline, confidence.
    """
    commitments = []
    sentences = re.split(r"[.\n!?]", masked_text)
    action_pattern = re.compile(
        r"\b(please|need to|must|review|approve|schedule|confirm|send|complete|finish|submit|"
        r"register|apply|pay|download|attend|report|upload|fill)\b",
        re.IGNORECASE,
    )
    deadline_pattern = re.compile(
        r"(due|by|before|on)\s+([A-Za-z0-9\-:, ]+)", re.IGNORECASE
    )

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue
        if action_pattern.search(sentence):
            confidence = 0.85 if re.search(r"\b(please|must|need to)\b", sentence, re.I) else 0.65
            deadline = None
            dl_match = deadline_pattern.search(sentence)
            if dl_match:
                deadline = dl_match.group(2).strip()

            commitments.append({
                "id": str(uuid.uuid4()),
                "commitment": sentence,
                "deadline": deadline,
                "confidence": confidence,
                "approved": None,
                "conflict_badge": False,
                "conflict_detail": None,
            })

    return commitments


# ─────────────────────────────────────────────────────────────────────────────
# 4. CALENDAR CONFLICT DETECTION TOOL
# ─────────────────────────────────────────────────────────────────────────────

@tool
def check_calendar_conflict(
    deadline_str: Optional[str],
    calendar_events: list[dict[str, Any]],
    window_hours: int = 2,
) -> dict[str, Any]:
    """
    Check whether a commitment deadline collides with an existing calendar event.

    Compares the proposed deadline against the user's upcoming calendar events
    (fetched from Google Calendar) within a configurable time window (default ±2h).

    Args:
        deadline_str: ISO 8601 deadline string from the commitment extractor, or None.
        calendar_events: List of calendar event dicts with 'title', 'start_time', 'end_time'.
        window_hours: Collision window in hours (default 2).

    Returns:
        dict with conflict_badge (bool) and conflict_detail (str or None).
    """
    if not deadline_str:
        return {"conflict_badge": False, "conflict_detail": None}

    try:
        deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return {"conflict_badge": False, "conflict_detail": "Could not parse deadline"}

    for event in calendar_events:
        start_raw = event.get("start_time")
        if not start_raw:
            continue
        try:
            start = (
                datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
                if isinstance(start_raw, str)
                else start_raw
            )
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            continue

        if abs((start - deadline).total_seconds()) <= window_hours * 3600:
            return {
                "conflict_badge": True,
                "conflict_detail": f"Conflicts with '{event.get('title', 'event')}' at {start.isoformat()}",
            }

    return {"conflict_badge": False, "conflict_detail": None}


# ─────────────────────────────────────────────────────────────────────────────
# 5. RAG PRECEDENT RETRIEVAL TOOL
# ─────────────────────────────────────────────────────────────────────────────

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity for the local fallback embedder."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


@tool
def retrieve_rag_precedents(
    masked_email_text: str,
    index_documents: list[dict[str, Any]],
    top_k: int = 3,
    threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """
    Retrieve the top-K most semantically similar sent emails from the RAG index.

    Embeds the query with the same embedder used to build the index (the
    caller's embedding model when configured, otherwise free local hashed
    embeddings) and performs cosine similarity search over the sent-mail corpus.

    Args:
        masked_email_text: PII-masked incoming email text to query against.
        index_documents: List of indexed documents with 'embedding', 'email_id',
                         'subject', 'masked_body' fields.
        top_k: Maximum number of precedents to return (default 3).
        threshold: Minimum similarity score to include in results (default 0.75).

    Returns:
        List of precedent dicts: email_id, subject, snippet, similarity_score.
    """
    from app.services.llm_provider import embed_text

    query_vector = embed_text(masked_email_text)
    candidates = []

    for doc in index_documents:
        sim = _cosine_similarity(query_vector, doc.get("embedding", []))
        if sim >= threshold:
            candidates.append((sim, doc))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "email_id": doc["email_id"],
            "subject": doc.get("subject", ""),
            "snippet": doc.get("masked_body", "")[:200],
            "similarity_score": round(sim, 4),
        }
        for sim, doc in candidates[:top_k]
    ]


@tool
def build_draft_prompt(
    email_text: str,
    precedents: list[dict[str, Any]],
) -> str:
    """
    Construct a few-shot draft prompt by injecting the top precedent emails
    as context for tone and style matching.

    The generated prompt is passed to the Draft Agent, which produces a reply
    that matches the user's historical communication style (Tone DNA alignment
    via RAG).

    Args:
        email_text: The incoming email text to respond to.
        precedents: List of precedent dicts from retrieve_rag_precedents.

    Returns:
        A fully-formed prompt string for the draft generation step.
    """
    if not precedents:
        return (
            f"Draft a professional reply to the following email:\n\n{email_text}"
        )

    context_lines = "\n".join(
        f"  [{i+1}] Subject: {p['subject']}\n      Sample: {p['snippet']}"
        for i, p in enumerate(precedents)
    )
    return (
        f"Here are {len(precedents)} similar emails you have sent previously "
        f"(use their tone, vocabulary, and structure):\n\n"
        f"{context_lines}\n\n"
        f"Now draft a professional reply to the following email, "
        f"matching the style above:\n\n{email_text}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOOL REGISTRY — exported for use by agents
# ─────────────────────────────────────────────────────────────────────────────

TRIAGE_TOOLS = [
    mask_pii,
    score_deadline_axis,
    score_authority_axis,
    score_sentiment_axis,
    score_decay_axis,
    score_action_axis,
    compute_composite_score,
]

COMMITMENT_TOOLS = [
    extract_commitments_from_text,
]

CALENDAR_TOOLS = [
    check_calendar_conflict,
]

RAG_TOOLS = [
    retrieve_rag_precedents,
    build_draft_prompt,
]

ALL_TOOLS = TRIAGE_TOOLS + COMMITMENT_TOOLS + CALENDAR_TOOLS + RAG_TOOLS