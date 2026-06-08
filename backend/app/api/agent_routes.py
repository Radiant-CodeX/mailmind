"""
MailMind v2 — Agentic FastAPI Routes
---------------------------------------
These routes expose the full LangGraph agentic pipeline.

Endpoints:
  GET  /api/agent/health              ← Pipeline health check
  POST /api/agent/process             ← Full 6-node pipeline for one email
  POST /api/agent/stream              ← SSE streaming of live node progress
  POST /api/agent/triage              ← Triage-only sub-pipeline
  POST /api/agent/commitments         ← Commitment extraction sub-pipeline
  POST /api/agent/batch               ← Process multiple emails in sequence
  POST /api/agent/approve/{email_id}  ← Human-in-the-loop approval gate
  GET  /api/agent/approve/{email_id}  ← Get approval status

Migration notes:
  - POST /api/classify → replaced by POST /api/agent/triage
  - POST /api/commitments/extract → replaced by POST /api/agent/commitments
  - POST /api/rag/retrieve → included in POST /api/agent/process
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Body, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

from app.db import repository as repo
from app.graph.pipeline import run_pipeline
from app.monitoring.metrics import set_queue_depth, track_stage
from app.queue.backends import get_queue_backend

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["Agentic Pipeline"])

# In-memory store for human-in-the-loop approvals keyed by email_id.
# In production this would be a Redis/DB store.
_approval_store: dict[str, dict[str, Any]] = {}


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
    confidence: float | None = None
    evidence: str | None = None


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
    dynamic_weights: dict[str, float]
    email_type: str | None
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

    # De-anonymize response values. restore_text reinstates known PII; the
    # strip pass then neutralises any token the LLM may have hallucinated.
    mapping = result.get("mask_mapping")
    if mapping:
        from app.services.pii import pii_sanitizer

        def _restore(value):
            if not value:
                return value
            return pii_sanitizer.strip_unresolved_tokens(
                pii_sanitizer.restore_text(value, mapping)
            )

        result["triage_reasoning"] = _restore(result.get("triage_reasoning"))
        result["draft_reply"] = _restore(result.get("draft_reply"))
        for commitment in result.get("commitments", []):
            commitment["commitment"] = _restore(commitment.get("commitment"))
            commitment["conflict_detail"] = _restore(commitment.get("conflict_detail"))

    return AgentProcessResponse(
        email_id=result["email_id"],
        masked_body=result.get("masked_body"),
        axes=[AxisScoreResponse(**a) for a in result.get("axes", [])],
        dynamic_weights=result.get("dynamic_weights", {}),
        email_type=result.get("email_type"),
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


@router.post("/stream")
async def stream_pipeline(request: AgentProcessRequest) -> StreamingResponse:
    """
    Stream the agentic pipeline progress as Server-Sent Events (SSE).

    Each LangGraph node emits a step update as the pipeline progresses:
      data: {"step": "ingest", "masked_body": "..."}
      data: {"step": "triage", "priority": "HIGH", "composite_score": 62.3}
      data: {"step": "commitment", "commitments": [...]}
      data: {"step": "gate", "done": true}

    Use this endpoint for the MailMind dashboard's live processing indicator.
    """
    received = request.received_at or datetime.now(tz=timezone.utc).isoformat()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            graph_stream = run_pipeline(
                email_payload={
                    "email_id": request.email_id,
                    "sender": str(request.sender),
                    "subject": request.subject,
                    "body": request.body,
                    "received_at": received,
                    "calendar_events": request.calendar_events,
                },
                index_documents=_load_rag_index(),
                stream=True,
            )

            for step_output in graph_stream:
                for node_name, partial_state in step_output.items():
                    payload = {
                        "step": node_name,
                        **{k: v for k, v in partial_state.items() if v is not None},
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            yield 'data: {"done": true}\n\n'

        except Exception as e:
            yield f'data: {{"error": "{str(e)}"}}\n\n'

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
        "dynamic_weights": {},
        "email_type": None,
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

    mapping = state.get("mask_mapping")
    if mapping:
        from app.services.pii import pii_sanitizer
        if state.get("triage_reasoning"):
            state["triage_reasoning"] = pii_sanitizer.restore_text(state["triage_reasoning"], mapping)

    return {
        "email_id": state["email_id"],
        "email_type": state.get("email_type"),
        "composite_score": state["composite_score"],
        "priority": state["priority"],
        "approval_mode": state["approval_mode"],
        "axes": state["axes"],
        "dynamic_weights": state.get("dynamic_weights", {}),
        "triage_reasoning": state.get("triage_reasoning"),
        "errors": state.get("errors", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# SPLIT PIPELINE: fast async triage + deferred enrichment
# ─────────────────────────────────────────────────────────────────────────────

def _fresh_state(email_id: str, sender: str, subject: str, body: str, received_at: str) -> dict[str, Any]:
    """Build a zero-initialised pipeline state dict."""
    return {
        "email_id": email_id, "sender": sender, "subject": subject,
        "body": body, "received_at": received_at,
        "masked_body": None, "axes": [], "dynamic_weights": {}, "email_type": None,
        "composite_score": 0.0, "priority": None, "approval_mode": None,
        "triage_reasoning": None, "commitments": [], "commitment_reasoning": None,
        "calendar_events": [], "conflict_summary": None, "precedents": [],
        "draft_prompt": None, "draft_reply": None,
        "current_step": "pending", "errors": [], "approved": False,
    }


@router.post("/triage-async")
def triage_async(request: TriageOnlyRequest) -> dict[str, Any]:
    """
    Production critical path: synchronous triage + deferred enrichment.

    Runs ingest + triage inline (returns priority within the triage SLA),
    persists a "triaged" record, then enqueues the full enrichment (commitments,
    calendar, RAG, draft) for a background worker. The client polls
    ``GET /api/agent/result/{email_id}`` for the enriched draft.

    This is the endpoint to call for live inbox processing at scale.
    """
    from app.agents.nodes import ingest_node, triage_node

    received = request.received_at or datetime.now(tz=timezone.utc).isoformat()
    state = _fresh_state(
        request.email_id, request.sender, request.subject, request.body, received
    )

    with track_stage("triage", request.email_id):
        state.update(ingest_node(state))
        state.update(triage_node(state))

    # Persist the triage result immediately so the inbox can render it.
    repo.upsert_enrichment(
        request.email_id, state, status="enriching", enrichment_source="fast_triage"
    )
    repo.write_audit(request.email_id, "triaged", details={"priority": state.get("priority")})

    # Hand off the (masked) state for deferred enrichment.
    queue = get_queue_backend()
    queue.enqueue({"email_id": request.email_id, "state": state, "retry_count": 0})
    set_queue_depth(queue.depth())

    return {
        "email_id": request.email_id,
        "priority": state.get("priority"),
        "composite_score": state.get("composite_score"),
        "email_type": state.get("email_type"),
        "approval_mode": state.get("approval_mode"),
        "axes": state.get("axes", []),
        "triage_reasoning": state.get("triage_reasoning"),
        "status": "enriching",
        "result_url": f"/api/agent/result/{request.email_id}",
    }


class EnrichRequest(BaseModel):
    """
    Enrichment-only request — triage scores already computed; skip ingest+triage.
    Runs commitment + calendar nodes automatically.
    RAG/draft is skipped by default — generated on demand when the user clicks
    "Generate Draft" to avoid unnecessary LLM calls on every email open.
    """
    email_id: str
    sender: str
    subject: str
    body: str
    received_at: str = ""
    # Pre-computed triage state from the inbox batch score (avoids re-running triage)
    masked_body: str | None = None
    axes: list[dict[str, Any]] = []
    composite_score: float = 0.0
    priority: str = "MEDIUM"
    approval_mode: str = "SUGGEST"
    triage_reasoning: str | None = None
    calendar_events: list[dict[str, Any]] = []
    current_user_email: str | None = None
    # When False (default), skip RAG/draft — only run commitment + calendar.
    # Set to True only when the user explicitly requests a draft.
    generate_draft: bool = False


@router.post("/enrich")
def enrich_email(request: EnrichRequest) -> dict[str, Any]:
    """
    Parallel enrichment pipeline — skips triage (already done in inbox batch),
    runs commitment + rag concurrently in threads, then merges.

    Latency target: ~5-8s (single LLM call chain, not three sequential).

    Call flow:
      inbox load  → /api/agent/triage  (batch, ~5s each, already done)
      email click → /api/agent/enrich  (commitment ‖ rag, ~5-7s total)
                                        instead of triage+commit+rag = 15-21s
    """
    import concurrent.futures
    from app.agents.nodes import calendar_node, commitment_node, gate_node, ingest_node, rag_node

    received = request.received_at or datetime.now(tz=timezone.utc).isoformat()

    # Build state from the pre-computed triage result so we skip ingest+triage.
    state: dict[str, Any] = {
        "email_id": request.email_id,
        "sender": request.sender,
        "subject": request.subject,
        "body": request.body,
        "received_at": received,
        # If masked_body was passed (it was computed during triage), reuse it.
        # Otherwise run ingest now to get the mask.
        "masked_body": request.masked_body or request.body,
        "mask_mapping": {},
        "axes": request.axes,
        "dynamic_weights": {},
        "email_type": None,
        "composite_score": request.composite_score,
        "priority": request.priority,
        "approval_mode": request.approval_mode,
        "triage_reasoning": request.triage_reasoning,
        "commitments": [],
        "commitment_reasoning": None,
        "calendar_events": request.calendar_events,
        "conflict_summary": None,
        "precedents": [],
        "draft_prompt": None,
        "draft_reply": None,
        "current_step": "triage",  # we resume after triage
        "errors": [],
        "approved": False,
    }

    # If no masked_body was provided, run ingest to get the PII mask.
    if not request.masked_body:
        state.update(ingest_node(state))

    # ── Run commitment node (always) ──────────────────────────────────────────
    # RAG/draft is skipped unless generate_draft=True (user clicked the button).
    commitment_result: dict[str, Any] = {}
    rag_result: dict[str, Any] = {}

    def run_commitment():
        return commitment_node(dict(state))

    def run_rag():
        from app.graph.pipeline import _load_rag_index
        from functools import partial
        rag_with_index = partial(rag_node, index_documents=_load_rag_index())
        return rag_with_index(dict(state))

    if request.generate_draft:
        # User explicitly requested a draft — run commitment + rag in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_commitment = executor.submit(run_commitment)
            future_rag = executor.submit(run_rag)
            try:
                commitment_result = future_commitment.result(timeout=30)
            except Exception as e:
                logger.warning("Commitment node failed: %s", e)
                commitment_result = {"commitments": [], "commitment_reasoning": "Extraction failed"}
            try:
                rag_result = future_rag.result(timeout=30)
            except Exception as e:
                logger.warning("RAG node failed: %s", e)
                rag_result = {"precedents": [], "draft_reply": None}
    else:
        # Default path — only run commitment (no LLM draft call)
        try:
            commitment_result = run_commitment()
        except Exception as e:
            logger.warning("Commitment node failed: %s", e)
            commitment_result = {"commitments": [], "commitment_reasoning": "Extraction failed"}

    # Merge results into state
    state.update(commitment_result)
    state.update(rag_result)

    # Calendar conflict check (fast, deterministic — runs after commitments are ready)
    state.update(calendar_node(state))

    # Gate
    state.update(gate_node(state))

    # PII restoration
    mapping = state.get("mask_mapping") or {}
    if mapping:
        from app.services.pii import pii_sanitizer
        def _restore(v):
            return pii_sanitizer.strip_unresolved_tokens(pii_sanitizer.restore_text(v, mapping)) if v else v
        state["triage_reasoning"] = _restore(state.get("triage_reasoning"))
        state["draft_reply"] = _restore(state.get("draft_reply"))
        for c in state.get("commitments", []):
            c["commitment"] = _restore(c.get("commitment"))

    return {
        "email_id": state["email_id"],
        "commitments": state.get("commitments", []),
        "commitment_reasoning": state.get("commitment_reasoning"),
        "conflict_summary": state.get("conflict_summary"),
        "precedents": state.get("precedents", []),
        "draft_reply": state.get("draft_reply"),
        "approval_mode": state.get("approval_mode", request.approval_mode),
        "current_step": state.get("current_step", "gate"),
        "errors": state.get("errors", []),
        "approved": state.get("approved", False),
    }


@router.get("/result/{email_id}")
def get_result(email_id: str) -> dict[str, Any]:
    """
    Fetch the persisted enrichment result for a previously-triaged email.

    Returns 404 while still enriching (or if persistence is disabled). Clients
    poll this after ``/triage-async`` until ``status == "complete"``.
    """
    record = repo.get_enrichment(email_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No result yet — still enriching or persistence disabled.",
        )
    return record


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _load_rag_index() -> list[dict]:
    """Load the ChromaDB index.json for RAG retrieval."""
    index_path = os.getenv("CHROMA_DATA_PATH", "./data/chroma")
    index_file = os.path.join(index_path, "index.json")

    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"RAG index not found at {index_file} — returning empty index")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
def agent_health() -> dict[str, Any]:
    """
    Pipeline health check. Verifies Azure OpenAI credentials are configured
    and the LangGraph pipeline can be imported.
    """
    from app.config import settings as _settings

    llm_ready = bool(
        _settings.azure_openai_api_key and _settings.azure_openai_base_endpoint
    )
    rag_index = _load_rag_index()

    return {
        "status": "ok",
        "llm_ready": llm_ready,
        "rag_index_documents": len(rag_index),
        "pipeline_nodes": ["ingest", "triage", "commitment", "calendar", "rag", "gate"],
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMMITMENTS SUB-PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/commitments")
def commitments_only(request: TriageOnlyRequest) -> dict[str, Any]:
    """
    Run the commitment extraction sub-pipeline (ingest + triage + commitment nodes).

    Lightweight alternative to /process when only action items need to be
    extracted — e.g., batch commitment scanning without draft generation.
    """
    received = request.received_at or datetime.now(tz=timezone.utc).isoformat()

    from app.agents.nodes import commitment_node, ingest_node, triage_node

    state: dict[str, Any] = {
        "email_id": request.email_id,
        "sender": request.sender,
        "subject": request.subject,
        "body": request.body,
        "received_at": received,
        "masked_body": None,
        "axes": [],
        "dynamic_weights": {},
        "email_type": None,
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
    state.update(commitment_node(state))

    mapping = state.get("mask_mapping")
    if mapping:
        from app.services.pii import pii_sanitizer
        for commitment in state.get("commitments", []):
            if commitment.get("commitment"):
                commitment["commitment"] = pii_sanitizer.restore_text(
                    commitment["commitment"], mapping
                )

    return {
        "email_id": state["email_id"],
        "commitments": state["commitments"],
        "commitment_reasoning": state.get("commitment_reasoning"),
        "priority": state.get("priority"),
        "errors": state.get("errors", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# BATCH PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

class BatchProcessRequest(BaseModel):
    emails: list[AgentProcessRequest]


class BatchProcessResponse(BaseModel):
    processed: int
    failed: int
    results: list[dict[str, Any]]


@router.post("/batch", response_model=BatchProcessResponse)
def batch_process(request: BatchProcessRequest) -> BatchProcessResponse:
    """
    Process multiple emails through the full pipeline sequentially.

    Processes each email independently — failures in one do not block others.
    Returns a summary of successes/failures alongside each result or error.

    Capped at 20 emails per batch to prevent timeout on the sync endpoint.
    Use repeated /process calls or /stream for larger volumes.
    """
    if len(request.emails) > 20:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch size capped at 20 emails per request.",
        )

    index_documents = _load_rag_index()
    results: list[dict[str, Any]] = []
    failed = 0

    for email_req in request.emails:
        received = email_req.received_at or datetime.now(tz=timezone.utc).isoformat()
        try:
            result = run_pipeline(
                email_payload={
                    "email_id": email_req.email_id,
                    "sender": str(email_req.sender),
                    "subject": email_req.subject,
                    "body": email_req.body,
                    "received_at": received,
                    "calendar_events": email_req.calendar_events,
                },
                index_documents=index_documents,
            )
            results.append({
                "email_id": email_req.email_id,
                "status": "ok",
                "priority": result.get("priority"),
                "composite_score": result.get("composite_score"),
                "commitments_count": len(result.get("commitments", [])),
                "draft_reply": result.get("draft_reply"),
            })
        except Exception as e:
            failed += 1
            logger.error(f"Batch pipeline error for email_id={email_req.email_id}: {e}")
            results.append({
                "email_id": email_req.email_id,
                "status": "error",
                "error": str(e),
            })

    return BatchProcessResponse(
        processed=len(request.emails) - failed,
        failed=failed,
        results=results,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HUMAN-IN-THE-LOOP APPROVAL GATE
# ─────────────────────────────────────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    action: str  # "approve" | "reject" | "edit"
    edited_draft: str | None = None
    reviewer_note: str | None = None


@router.post("/approve/{email_id}")
def approve_email(email_id: str, request: ApprovalRequest) -> dict[str, Any]:
    """
    Human-in-the-loop approval for GATE-mode emails (composite_score ≥ 75).

    After the pipeline's gate_node pauses with approved=False, the frontend
    calls this endpoint once the human has reviewed the draft and commitments.

    Actions:
      - approve: mark as approved, allow downstream actions (send reply, create tasks)
      - reject: discard the pipeline output, no actions taken
      - edit:   approve with an overridden draft reply
    """
    if request.action not in ("approve", "reject", "edit"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="action must be one of: approve, reject, edit",
        )

    _approval_store[email_id] = {
        "email_id": email_id,
        "action": request.action,
        "approved": request.action in ("approve", "edit"),
        "edited_draft": request.edited_draft,
        "reviewer_note": request.reviewer_note,
        "reviewed_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    logger.info(f"[GATE] email_id={email_id} action={request.action}")

    return {
        "email_id": email_id,
        "action": request.action,
        "approved": _approval_store[email_id]["approved"],
        "reviewed_at": _approval_store[email_id]["reviewed_at"],
    }


@router.get("/approve/{email_id}")
def get_approval_status(email_id: str) -> dict[str, Any]:
    """Get the current approval status for an email processed by the pipeline."""
    record = _approval_store.get(email_id)
    if not record:
        return {
            "email_id": email_id,
            "approved": False,
            "action": "pending",
            "reviewed_at": None,
        }
    return record