"""
MailMind v2 — Agentic FastAPI Routes
---------------------------------------
These routes replace the direct GPT-4o API call routes with the full
LangGraph agentic pipeline.

New endpoints:
  POST /api/agent/process      ← Run the full pipeline for one email
  GET  /api/agent/stream/{id}  ← Stream pipeline progress (SSE)
  POST /api/agent/triage       ← Triage only (sub-pipeline)
  POST /api/agent/commitments  ← Commitments only (sub-pipeline)

Migration notes:
  - POST /api/classify → replaced by POST /api/agent/triage
  - POST /api/commitments/extract → included in POST /api/agent/process
  - POST /api/rag/retrieve → included in POST /api/agent/process

The old endpoints remain functional (backward compatibility). New frontend
development should target the /api/agent/ routes.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from app.graph.pipeline import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agentic Pipeline"])


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST / RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class AgentProcessRequest(BaseModel):
    """Full pipeline request — processes an email end-to-end through all agents."""
    email_id: str
    sender: EmailStr
    subject: str
    body: str
    received_at: str = ""
    calendar_events: list[dict[str, Any]] = []


class AxisScoreResponse(BaseModel):
    axis: str
    raw_score: float
    explanation: str


class CommitmentResponse(BaseModel):
    id: str
    commitment: str
    deadline: str | None
    confidence: float
    approved: bool | None
    conflict_badge: bool
    conflict_detail: str | None


class PrecedentResponse(BaseModel):
    email_id: str
    subject: str
    snippet: str
    similarity_score: float


class AgentProcessResponse(BaseModel):
    """Full pipeline output — every agent's contribution in one response."""
    email_id: str
    # Triage
    masked_body: str | None
    axes: list[AxisScoreResponse]
    composite_score: float
    priority: str
    approval_mode: str
    triage_reasoning: str | None
    # Commitments
    commitments: list[CommitmentResponse]
    commitment_reasoning: str | None
    # Calendar
    conflict_summary: str | None
    # RAG & Draft
    precedents: list[PrecedentResponse]
    draft_reply: str | None
    # Meta
    current_step: str
    errors: list[str]
    approved: bool


class TriageOnlyRequest(BaseModel):
    """Lightweight request for triage-only sub-pipeline."""
    email_id: str
    sender: str
    subject: str
    body: str
    received_at: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/process", response_model=AgentProcessResponse)
def process_email(request: AgentProcessRequest) -> AgentProcessResponse:
    """
    Run the full MailMind agentic pipeline for a single email.

    Executes all six LangGraph nodes in sequence:
      ingest → triage → commitment → calendar → rag → gate

    Each node uses GPT-4o tool-calling (LangChain) when Azure credentials
    are available, with deterministic rule-based fallbacks otherwise.

    Returns the complete enriched email state including triage scores,
    extracted commitments with conflict flags, precedent citations,
    and a Tone DNA-aligned draft reply.
    """
    received = request.received_at or datetime.now(tz=timezone.utc).isoformat()

    try:
        result = run_pipeline(
            email_payload={
                "email_id": request.email_id,
                "sender": str(request.sender),
                "subject": request.subject,
                "body": request.body,
                "received_at": received,
                "calendar_events": request.calendar_events,
            },
            index_documents=_load_rag_index(),
        )
    except Exception as e:
        logger.error(f"Pipeline error for email_id={request.email_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {str(e)}",
        )

    return AgentProcessResponse(
        email_id=result["email_id"],
        masked_body=result.get("masked_body"),
        axes=[AxisScoreResponse(**a) for a in result.get("axes", [])],
        composite_score=result.get("composite_score", 0.0),
        priority=result.get("priority", "LOW"),
        approval_mode=result.get("approval_mode", "SUGGEST"),
        triage_reasoning=result.get("triage_reasoning"),
        commitments=[CommitmentResponse(**c) for c in result.get("commitments", [])],
        commitment_reasoning=result.get("commitment_reasoning"),
        conflict_summary=result.get("conflict_summary"),
        precedents=[PrecedentResponse(**p) for p in result.get("precedents", [])],
        draft_reply=result.get("draft_reply"),
        current_step=result.get("current_step", "gate"),
        errors=result.get("errors", []),
        approved=result.get("approved", False),
    )


@router.get("/stream/{email_id}")
async def stream_pipeline(
    email_id: str,
    sender: str = "unknown@example.com",
    subject: str = "Email",
    body: str = "",
    received_at: str = "",
) -> StreamingResponse:
    """
    Stream the agentic pipeline progress as Server-Sent Events (SSE).

    Each LangGraph node emits a step update as the pipeline progresses,
    enabling the frontend to show real-time processing status:
      data: {"step": "triage", "priority": "HIGH", "composite_score": 62.3}
      data: {"step": "commitment", "commitments": [...]}
      data: {"step": "gate", "done": true}

    Useful for the MailMind dashboard's live processing indicator.
    """
    received = received_at or datetime.now(tz=timezone.utc).isoformat()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            graph_stream = run_pipeline(
                email_payload={
                    "email_id": email_id,
                    "sender": sender,
                    "subject": subject,
                    "body": body,
                    "received_at": received,
                    "calendar_events": [],
                },
                index_documents=_load_rag_index(),
                stream=True,
            )

            for step_output in graph_stream:
                # step_output is a dict: {node_name: partial_state}
                for node_name, partial_state in step_output.items():
                    payload = {
                        "step": node_name,
                        **{k: v for k, v in partial_state.items() if v is not None},
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            yield "data: {\"done\": true}\n\n"

        except Exception as e:
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/triage")
def triage_only(request: TriageOnlyRequest) -> dict[str, Any]:
    """
    Run only the triage sub-pipeline (ingest + triage nodes).

    Lightweight alternative to /process when commitment extraction and
    draft generation are not needed — e.g., for bulk inbox scoring.
    """
    received = request.received_at or datetime.now(tz=timezone.utc).isoformat()

    from app.agents.nodes import ingest_node, triage_node

    state = {
        "email_id": request.email_id,
        "sender": request.sender,
        "subject": request.subject,
        "body": request.body,
        "received_at": received,
        "masked_body": None,
        "axes": [],
        "composite_score": 0.0,
        "priority": None,
        "approval_mode": None,
        "triage_reasoning": None,
        "commitments": [],
        "commitment_reasoning": None,
        "calendar_events": [],
        "conflict_summary": None,
        "precedents": [],
        "draft_prompt": None,
        "draft_reply": None,
        "current_step": "pending",
        "errors": [],
        "approved": False,
    }

    state.update(ingest_node(state))
    state.update(triage_node(state))

    return {
        "email_id": state["email_id"],
        "composite_score": state["composite_score"],
        "priority": state["priority"],
        "approval_mode": state["approval_mode"],
        "axes": state["axes"],
        "triage_reasoning": state.get("triage_reasoning"),
        "errors": state.get("errors", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_rag_index() -> list[dict]:
    """
    Load the ChromaDB index.json for RAG retrieval.
    Returns empty list if index file is not found.
    """
    index_path = os.getenv("CHROMA_DATA_PATH", "./data/chroma")
    index_file = os.path.join(index_path, "index.json")

    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"RAG index not found at {index_file} — returning empty index")
        return []