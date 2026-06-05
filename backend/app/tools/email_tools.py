"""
MailMind v2 — LangChain Tool Definitions
------------------------------------------
Each function here is decorated with @tool, making it callable by the
AzureChatOpenAI model via its tool-calling API (function calling).

The LLM decides WHICH tools to invoke and with WHAT arguments based on
the email context and its system prompt — this is what makes the pipeline
agentic rather than a hardcoded sequence of API calls.

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

    Replaces email addresses, phone numbers, and credit card numbers with
    safe placeholder tokens: [EMAIL], [PHONE], [CARD].

    Args:
        text: Raw email body text.

    Returns:
        PII-masked version of the text safe for LLM consumption.
    """
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    text = re.sub(r"\b\+?\d[\d\-\s]{7,}\d\b", "[PHONE]", text)
    text = re.sub(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD]", text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# 2. FIVE-AXIS TRIAGE SCORING TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@tool
def score_deadline_axis(body: str) -> dict[str, Any]:
    """
    Score the email on the DEADLINE axis (weight: 30%).

    Parses natural language deadline expressions (today, tomorrow, next Friday,
    ISO dates, 'due by X', 'deadline: X') and calculates urgency based on
    days remaining. Closer deadlines score higher (0.0–1.0).

    Args:
        body: PII-masked email body text.

    Returns:
        dict with keys: axis (str), raw_score (float 0-1), explanation (str).
    """
    body_lower = body.lower()
    now = datetime.now(tz=timezone.utc)
    deadline = None

    # Natural language patterns
    if "today" in body_lower:
        deadline = now
    elif "tomorrow" in body_lower:
        deadline = now + timedelta(days=1)
    elif "next week" in body_lower:
        deadline = now + timedelta(days=7)
    else:
        # Regex: "due by", "by Friday", ISO dates
        patterns = [
            r"due(?:\s+by)?\s+([a-zA-Z0-9\-:, ]+)",
            r"by\s+([a-zA-Z0-9\-:, ]+)",
            r"deadline(?:\s*:)?\s+([a-zA-Z0-9\-:, ]+)",
            r"(\d{4}-\d{2}-\d{2})",
        ]
        weekday_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2,
            "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
        }
        for pattern in patterns:
            match = re.search(pattern, body_lower)
            if match:
                raw = match.group(1).strip()
                for day_name, day_idx in weekday_map.items():
                    if day_name in raw:
                        offset = (day_idx - now.weekday() + 7) % 7 or 7
                        deadline = now + timedelta(days=offset)
                        break
                if not deadline:
                    try:
                        deadline = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        if deadline.tzinfo is None:
                            deadline = deadline.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
                if deadline:
                    break

    if not deadline:
        return {"axis": "deadline", "raw_score": 0.0, "explanation": "No deadline detected"}

    days_until = max(0.0, (deadline - now).total_seconds() / 86400.0)
    raw_score = max(0.0, min(1.0, 1.0 - (days_until / 14.0)))
    explanation = f"Deadline in {days_until:.1f} days" if days_until > 0 else "Deadline is today or overdue"
    return {"axis": "deadline", "raw_score": round(raw_score, 3), "explanation": explanation}


@tool
def score_authority_axis(sender_email: str) -> dict[str, Any]:
    """
    Score the email on the SENDER AUTHORITY axis (weight: 25%).

    Classifies sender as C-suite, manager, internal peer, or external party
    based on email domain and title keywords. Higher authority = higher score.

    Args:
        sender_email: The sender's email address (already PII-safe as it's metadata).

    Returns:
        dict with keys: axis, raw_score (0-1), explanation.
    """
    lower = sender_email.lower()

    # C-suite / executive indicators
    if any(kw in lower for kw in ["ceo", "cto", "cfo", "coo", "president", "vp", "director"]):
        return {"axis": "authority", "raw_score": 1.0, "explanation": "Executive-level sender detected"}

    # Manager / lead indicators
    if any(kw in lower for kw in ["manager", "lead", "head", "chief", "supervisor"]):
        return {"axis": "authority", "raw_score": 0.8, "explanation": "Manager-level sender detected"}

    # Client / partner (external high-priority)
    if any(kw in lower for kw in ["client", "partner", "vendor", "customer"]):
        return {"axis": "authority", "raw_score": 0.7, "explanation": "Client/partner sender"}

    # Internal peer (same domain heuristic)
    if "@" in lower and not any(
        domain in lower for domain in ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
    ):
        return {"axis": "authority", "raw_score": 0.5, "explanation": "Internal peer sender"}

    return {"axis": "authority", "raw_score": 0.2, "explanation": "External or unknown sender"}


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
    lower = body.lower()

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
        return {"axis": "sentiment", "raw_score": 1.0, "explanation": f"Critical escalation signals detected ({critical_count})"}
    if critical_count == 1:
        return {"axis": "sentiment", "raw_score": 0.85, "explanation": "Escalation or emergency language detected"}
    if negative_count >= 3:
        return {"axis": "sentiment", "raw_score": 0.7, "explanation": f"High frustration signals ({negative_count})"}
    if negative_count >= 1:
        return {"axis": "sentiment", "raw_score": 0.5, "explanation": f"Mild negative sentiment ({negative_count} signals)"}
    if positive_count >= 2:
        return {"axis": "sentiment", "raw_score": 0.1, "explanation": "Positive or informational tone"}

    return {"axis": "sentiment", "raw_score": 0.3, "explanation": "Neutral sentiment"}


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
    return {
        "axis": "decay",
        "raw_score": round(raw_score, 3),
        "explanation": f"Email received {age_days:.1f} days ago",
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
                "respond by", "need your input", "waiting for", "please confirm"]
    optional = ["if interested", "optional", "when convenient", "when you have time",
                "no rush", "fyi", "just letting you know"]

    for phrase in required:
        if phrase in lower:
            return {"axis": "action", "raw_score": 1.0, "explanation": f"Action required: '{phrase}' detected"}
    for phrase in optional:
        if phrase in lower:
            return {"axis": "action", "raw_score": 0.5, "explanation": f"Optional action: '{phrase}' detected"}

    return {"axis": "action", "raw_score": 0.0, "explanation": "No action keyword detected"}


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

    For production use, the Commitment Agent calls this as a fallback tool
    while GPT-4o provides the primary extraction via structured output.

    Args:
        masked_text: PII-masked email body text.

    Returns:
        List of commitment dicts: id, commitment, deadline, confidence.
    """
    commitments = []
    sentences = re.split(r"[.\n!?]", masked_text)
    action_pattern = re.compile(
        r"\b(please|need to|must|review|approve|schedule|confirm|send|complete|finish|submit)\b",
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
    (fetched from Microsoft Graph) within a configurable time window (default ±2h).

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


def _fallback_embed(text: str) -> list[float]:
    """Deterministic character-frequency embedding (64-dim) used when OpenAI is unavailable."""
    normalized = text.lower().strip()
    vector = [0.0] * 64
    for idx, char in enumerate(normalized[:64]):
        vector[idx] = (ord(char) % 32) / 31.0
    return vector


@tool
def retrieve_rag_precedents(
    masked_email_text: str,
    index_documents: list[dict[str, Any]],
    top_k: int = 3,
    threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """
    Retrieve the top-K most semantically similar sent emails from the RAG index.

    Embeds the query text using the fallback character-frequency embedder
    (or OpenAI text-embedding-ada-002 when configured) and performs cosine
    similarity search against the indexed sent email corpus.

    Args:
        masked_email_text: PII-masked incoming email text to query against.
        index_documents: List of indexed documents with 'embedding', 'email_id',
                         'subject', 'masked_body' fields.
        top_k: Maximum number of precedents to return (default 3).
        threshold: Minimum similarity score to include in results (default 0.75).

    Returns:
        List of precedent dicts: email_id, subject, snippet, similarity_score.
    """
    query_vector = _fallback_embed(masked_email_text)
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

    The generated prompt is passed to the Draft Agent which uses GPT-4o to
    produce a reply that matches the user's historical communication style
    (Tone DNA alignment via RAG).

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