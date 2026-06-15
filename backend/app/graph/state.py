"""
MailMind v2 — Agentic Pipeline State
-------------------------------------
Defines the shared TypedDict state that flows through every LangGraph node.
Each node reads from and writes back to this state, making the full pipeline
observable and debuggable at every step.
"""

from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict


class AxisScore(TypedDict, total=False):
    axis: str
    raw_score: float
    explanation: str
    confidence: float          # 0–1 LLM confidence in this axis score
    evidence: str              # Text from the email supporting the score


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

    # ── Triage outputs ───────────────────────────────────────────────────────
    masked_body: Optional[str]                # PII-scrubbed body
    masked_subject: Optional[str]             # PII-scrubbed subject (shares mask_mapping)
    mask_mapping: Optional[dict[str, str]]    # Mapping to restore PII
    axes: list[AxisScore]                     # Five individual axis scores
    dynamic_weights: dict[str, float]         # LLM-assigned per-axis weights (sum=1.0)
    email_type: Optional[str]                 # LLM-inferred email category
    composite_score: float                    # 0–100 weighted aggregate
    priority: Optional[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]]
    approval_mode: Optional[Literal["GATE", "SUGGEST"]]
    triage_reasoning: Optional[str]           # Triage reasoning chain-of-thought

    # ── Commitment Extraction outputs ────────────────────────────────────────
    commitments: list[CommitmentItem]         # Extracted action items
    commitment_reasoning: Optional[str]

    # ── Calendar Conflict Detection outputs ──────────────────────────────────
    calendar_events: list[dict[str, Any]]     # Raw events from Graph API
    conflict_summary: Optional[str]           # Human-readable conflict overview

    # ── RAG Precedent Retrieval + Draft outputs ───────────────────────────────
    precedents: list[PrecedentItem]           # Top-3 similar sent emails
    draft_prompt: Optional[str]               # Injected precedent prompt
    draft_reply: Optional[str]                # GPT-4o generated draft reply

    # ── Pipeline control ─────────────────────────────────────────────────────
    current_step: str                         # Tracks which node is active
    errors: list[str]                         # Non-fatal errors accumulated
    approved: bool                            # Final human approval flag