"""
MailMind v2 — LangGraph Pipeline Assembly
-------------------------------------------
This module assembles the full agentic email processing pipeline using
LangGraph's StateGraph API.

Graph topology (linear DAG):

  [START]
     │
     ▼
  ingest_node          ← PII masking, payload validation
     │
     ▼
  triage_node          ← Triage (GPT-4o five-axis scoring)
     │
     ▼
  commitment_node      ← Commitment Extraction (GPT-4o structured output)
     │
     ▼
  calendar_node        ← Calendar Conflict Detection (deterministic)
     │
     ▼
  rag_node             ← RAG Precedent Retrieval + Draft Reply (GPT-4o)
     │
     ▼
  gate_node            ← Approval Gate (human-in-the-loop checkpoint)
     │
     ▼
  [END]

Key LangGraph concepts used:
  - StateGraph: typed state that flows through all nodes
  - add_node: registers each processing step
  - add_edge: defines the execution order
  - compile(): produces a runnable graph object
  - invoke(): synchronous graph execution
  - stream(): streaming step-by-step execution for real-time UI updates
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    calendar_node,
    commitment_node,
    gate_node,
    ingest_node,
    rag_node,
    triage_node,
)
from app.graph.state import EmailAgentState

logger = logging.getLogger(__name__)


def build_mailmind_graph(index_documents: list[dict] | None = None):
    """
    Construct and compile the MailMind agentic email processing graph.

    Args:
        index_documents: Pre-loaded RAG index documents to inject into the
                         rag_node. Pass the ChromaDB index contents here.

    Returns:
        A compiled LangGraph CompiledGraph ready for .invoke() or .stream().
    """
    # Bind index documents to rag_node (partial application)
    rag_with_index = partial(rag_node, index_documents=index_documents or [])

    # ── Build the state graph ────────────────────────────────────────────────
    graph = StateGraph(EmailAgentState)

    # Register all nodes
    graph.add_node("ingest", ingest_node)
    graph.add_node("triage", triage_node)
    graph.add_node("commitment", commitment_node)
    graph.add_node("calendar", calendar_node)
    graph.add_node("rag", rag_with_index)
    graph.add_node("gate", gate_node)

    # Define the execution edges (linear pipeline)
    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "triage")
    graph.add_edge("triage", "commitment")
    graph.add_edge("commitment", "calendar")
    graph.add_edge("calendar", "rag")
    graph.add_edge("rag", "gate")
    graph.add_edge("gate", END)

    # Compile into a runnable graph
    compiled = graph.compile()
    logger.info("MailMind LangGraph pipeline compiled successfully")
    return compiled


def run_pipeline(
    email_payload: dict[str, Any],
    index_documents: list[dict] | None = None,
    stream: bool = False,
) -> dict[str, Any] | Any:
    """
    Execute the full MailMind agentic pipeline for a single email.

    Args:
        email_payload: Dict matching EmailAgentState input fields:
                       email_id, sender, subject, body, received_at
        index_documents: RAG index documents for precedent retrieval
        stream: If True, returns a generator yielding state at each node.
                If False, runs to completion and returns the final state.

    Returns:
        Final EmailAgentState dict (or generator if stream=True).

    Example:
        result = run_pipeline({
            "email_id": "msg-001",
            "sender": "manager@company.com",
            "subject": "Urgent: Review contract by tomorrow",
            "body": "Please review and sign the attached contract by tomorrow 5PM.",
            "received_at": "2026-06-05T09:00:00Z",
        })
        print(result["priority"])          # "CRITICAL"
        print(result["composite_score"])   # e.g., 78.5
        print(result["commitments"])       # extracted action items
        print(result["draft_reply"])       # GPT-4o generated reply
    """
    graph = build_mailmind_graph(index_documents=index_documents)

    # Initialise all optional state fields with defaults
    initial_state: EmailAgentState = {
        "email_id": email_payload["email_id"],
        "sender": email_payload["sender"],
        "subject": email_payload["subject"],
        "body": email_payload["body"],
        "received_at": email_payload.get("received_at", ""),
        # Triage outputs
        "masked_body": None,
        "axes": [],
        "dynamic_weights": {},
        "email_type": None,
        "composite_score": 0.0,
        "priority": None,
        "approval_mode": None,
        "triage_reasoning": None,
        # Commitment outputs
        "commitments": [],
        "commitment_reasoning": None,
        # Calendar outputs
        "calendar_events": email_payload.get("calendar_events", []),
        "conflict_summary": None,
        # RAG outputs
        "precedents": [],
        "draft_prompt": None,
        "draft_reply": None,
        # Control
        "current_step": "pending",
        "errors": [],
        "approved": False,
    }

    if stream:
        return graph.stream(initial_state)

    return graph.invoke(initial_state)


def _load_rag_index() -> list[dict]:
    """Load RAG index documents — shared by pipeline.py and agent_routes.py."""
    import json
    import os
    index_path = os.getenv("CHROMA_DATA_PATH", "./data/chroma")
    index_file = os.path.join(index_path, "index.json")
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _load_rag_index_safe() -> list[dict]:
    """Alias used by the parallel enrichment endpoint."""
    return _load_rag_index()