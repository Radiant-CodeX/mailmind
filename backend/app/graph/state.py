"""
MailMind v2 — Agentic Pipeline State
-------------------------------------
Defines the shared TypedDict state that flows through every LangGraph node.
Each node reads from and writes back to this state, making the full pipeline
observable and debuggable at every step.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict


class AxisScore(TypedDict):
    axis: str
    raw_score: float
    explanation: str


class CommitmentItem(TypedDict):
    id: str
    commitment: str
    deadline: Optional[str]       # ISO 8601 string or None
    confidence: float
    approved: Optional[bool]
    conflict_badge: bool
    conflict_detail: Optional[str]


class PrecedentItem(TypedDict):
    email_id: str
    subject: str
    snippet: str
    similarity_score: float


class EmailAgentState(TypedDict):
    """
    The single shared state object that traverses the entire LangGraph pipeline.

    Populated progressively — each node fills its own fields and passes
    the enriched state forward. Fields that haven't been populated yet
    hold their default (None / empty list).
    """

    # ── Input ────────────────────────────────────────────────────────────────
    email_id: str
    sender: str
    subject: str
    body: str
    received_at: str                          # ISO 8601 datetime string

    # ── Triage Agent outputs ─────────────────────────────────────────────────
    masked_body: Optional[str]                # PII-scrubbed body
    axes: list[AxisScore]                     # Five individual axis scores
    composite_score: float                    # 0–100 weighted aggregate
    priority: Optional[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]]
    approval_mode: Optional[Literal["GATE", "SUGGEST"]]
    triage_reasoning: Optional[str]           # Agent chain-of-thought

    # ── Commitment Agent outputs ─────────────────────────────────────────────
    commitments: list[CommitmentItem]         # Extracted action items
    commitment_reasoning: Optional[str]

    # ── Calendar Conflict Agent outputs ──────────────────────────────────────
    calendar_events: list[dict[str, Any]]     # Raw events from Graph API
    conflict_summary: Optional[str]           # Human-readable conflict overview

    # ── RAG Agent outputs ────────────────────────────────────────────────────
    precedents: list[PrecedentItem]           # Top-3 similar sent emails
    draft_prompt: Optional[str]               # Injected precedent prompt
    draft_reply: Optional[str]                # GPT-4o generated draft reply

    # ── Pipeline control ─────────────────────────────────────────────────────
    current_step: str                         # Tracks which node is active
    errors: list[str]                         # Non-fatal errors accumulated
    approved: bool                            # Final human approval flag