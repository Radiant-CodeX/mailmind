"""
MailMind v2 — LangGraph Agent Nodes
--------------------------------------
Each function here is a LangGraph node. Nodes receive the full pipeline state,
run their agent logic (LLM + tool calls), and return a partial state update.

LangGraph merges these partial updates into the shared EmailAgentState as
the email moves through the graph.

Node execution order (defined in graph.py):
  ingest_node → triage_node → commitment_node → calendar_node → rag_node → gate_node

Each node that involves LLM reasoning uses:
  - AzureChatOpenAI (GPT-4o) as the model
  - bind_tools() to give the LLM access to relevant tool functions
  - A structured system prompt for its specific task
  - Manual tool dispatch (call_tool_by_name) to execute the LLM's chosen tool calls
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import AzureChatOpenAI

from app.graph.state import EmailAgentState
from app.monitoring.metrics import observe_node, record_llm_call, record_pii_masked
from app.tools.email_tools import (
    ALL_TOOLS,
    TRIAGE_TOOLS,
    build_draft_prompt,
    check_calendar_conflict,
    compute_composite_score,
    extract_commitments_from_text,
    retrieve_rag_precedents,
    score_action_axis,
    score_authority_axis,
    score_deadline_axis,
    score_decay_axis,
    score_sentiment_axis,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LLM FACTORY
# ─────────────────────────────────────────────────────────────────────────────

# Module-level LLM cache — one instance per temperature, reused across all requests.
# Creating AzureChatOpenAI is not free: it validates credentials and sets up the
# HTTP client. Caching saves ~200-400ms per request.
_llm_cache: dict[float, AzureChatOpenAI] = {}


def _get_llm(temperature: float = 0.1) -> AzureChatOpenAI | None:
    """
    Return a cached AzureChatOpenAI instance. Built once per temperature value
    and reused for all subsequent requests in this process lifetime.
    Returns None if Azure credentials are not present (triggers fallback paths).
    """
    global _llm_cache
    if temperature in _llm_cache:
        return _llm_cache[temperature]

    from app.config import settings as _settings
    api_key = _settings.azure_openai_api_key
    endpoint = _settings.azure_openai_base_endpoint
    deployment = _settings.azure_openai_chat_deployment
    api_version = _settings.azure_openai_api_version

    if not api_key or not endpoint:
        logger.warning("Azure OpenAI credentials not set — using deterministic fallbacks")
        return None

    instance = AzureChatOpenAI(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        api_key=api_key,
        api_version=api_version,
        temperature=temperature,
    )
    _llm_cache[temperature] = instance
    logger.info("AzureChatOpenAI instance cached (temperature=%.1f)", temperature)
    return instance


# ─────────────────────────────────────────────────────────────────────────────
# TOOL DISPATCH HELPER
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_MAP = {t.name: t for t in ALL_TOOLS}


def _dispatch_tool(tool_call: dict[str, Any]) -> Any:
    """
    Execute a tool call emitted by the LLM and return its result.

    LangChain's tool-calling API returns tool_call dicts with:
      - name: the function name
      - args: dict of keyword arguments

    This dispatcher resolves the tool by name and invokes it.
    """
    tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name", "")
    raw_args = tool_call.get("args") or tool_call.get("function", {}).get("arguments", "{}")

    if isinstance(raw_args, str):
        try:
            args = json.loads(raw_args)
        except json.JSONDecodeError:
            args = {}
    else:
        args = raw_args

    tool_fn = _TOOL_MAP.get(tool_name)
    if not tool_fn:
        logger.warning(f"Unknown tool called by LLM: {tool_name}")
        return f"Tool '{tool_name}' not found"

    logger.info(f"Dispatching tool: {tool_name} with args: {list(args.keys())}")
    return tool_fn.invoke(args)


# ─────────────────────────────────────────────────────────────────────────────
# NODE 1: INGEST NODE
# ─────────────────────────────────────────────────────────────────────────────

def ingest_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Pipeline entry point. Validates the incoming email payload and runs PII
    masking as the first step before any LLM processing.

    This is a deterministic node — no LLM call needed. PII masking is always
    rule-based for security (we never send raw PII to an LLM).

    State updates: masked_body, mask_mapping, current_step
    """
    logger.info(f"[INGEST] Processing email_id={state['email_id']}")

    from app.services.pii import pii_sanitizer
    with observe_node("ingest"):
        masked, mapping = pii_sanitizer.mask_text(state["body"])

    # Record PII coverage by category (counts only — never raw values).
    if mapping:
        category_counts: dict[str, int] = {}
        for placeholder in mapping:                      # e.g. "[PERSON_1]"
            category = placeholder.strip("[]").rsplit("_", 1)[0]
            category_counts[category] = category_counts.get(category, 0) + 1
        record_pii_masked(category_counts)

    return {
        "masked_body": masked,
        "mask_mapping": mapping,
        "current_step": "ingest",
        "errors": [],
        "axes": [],
        "commitments": [],
        "calendar_events": [],
        "precedents": [],
        "approved": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 2: TRIAGE AGENT NODE
# ─────────────────────────────────────────────────────────────────────────────

# The five triage axes the LLM must score. Note: the dynamic LLM path uses
# "thread_risk" (a holistic stakeholder/escalation-risk judgement) where the
# deterministic fallback uses the simpler time-based "decay" axis.
TRIAGE_AXES = ["deadline", "authority", "sentiment", "thread_risk", "action"]

# Default weights used to normalise / repair LLM weight output. Mirror the
# static weighting so a missing axis weight degrades gracefully.
DEFAULT_DYNAMIC_WEIGHTS = {
    "deadline": 0.30,
    "authority": 0.25,
    "sentiment": 0.20,
    "thread_risk": 0.15,
    "action": 0.10,
}


def _priority_from_score(composite: float) -> tuple[str, str]:
    """Map a 0–100 composite score to (priority, approval_mode)."""
    if composite >= 75:
        return "CRITICAL", "GATE"
    if composite >= 50:
        return "HIGH", "SUGGEST"
    if composite >= 25:
        return "MEDIUM", "SUGGEST"
    return "LOW", "SUGGEST"


def _normalise_weights(weights: dict[str, Any]) -> dict[str, float]:
    """
    Coerce LLM-supplied weights into clean floats that sum to exactly 1.0.

    Missing axes are filled from DEFAULT_DYNAMIC_WEIGHTS; the whole set is then
    renormalised so the final dict always sums to 1.0 regardless of LLM output.
    """
    cleaned: dict[str, float] = {}
    for axis in TRIAGE_AXES:
        try:
            cleaned[axis] = max(0.0, float(weights.get(axis, DEFAULT_DYNAMIC_WEIGHTS[axis])))
        except (TypeError, ValueError):
            cleaned[axis] = DEFAULT_DYNAMIC_WEIGHTS[axis]

    total = sum(cleaned.values())
    if total <= 0:
        cleaned = dict(DEFAULT_DYNAMIC_WEIGHTS)
        total = sum(cleaned.values())

    return {axis: round(w / total, 4) for axis, w in cleaned.items()}


def _recompute_composite(axes: list[dict], weights: dict[str, float]) -> float:
    """
    Recalculate the composite score in code from axis raw_scores × weights.

    Never trust the LLM's own composite_score — this is the authoritative value.
    """
    by_axis = {a["axis"]: a for a in axes}
    weighted_sum = sum(
        float(by_axis.get(axis, {}).get("raw_score", 0.0)) * weight
        for axis, weight in weights.items()
    )
    return round(max(0.0, min(100.0, weighted_sum * 100.0)), 2)


def _parse_triage_json(raw: str) -> dict[str, Any]:
    """Strip markdown fences and parse the LLM triage JSON payload."""
    content = raw.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def _validate_axes(raw_axes: Any) -> list[dict]:
    """
    Validate and clean the LLM's axis list. Raises ValueError if the payload
    is unusable (triggering the deterministic fallback in the caller).
    """
    if not isinstance(raw_axes, list) or not raw_axes:
        raise ValueError("axes missing or not a list")

    cleaned: list[dict] = []
    seen: set[str] = set()
    for item in raw_axes:
        if not isinstance(item, dict):
            continue
        axis = str(item.get("axis", "")).strip().lower()
        if axis not in TRIAGE_AXES or axis in seen:
            continue
        seen.add(axis)
        cleaned.append({
            "axis": axis,
            "raw_score": max(0.0, min(1.0, float(item.get("raw_score", 0.0)))),
            "confidence": max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
            "evidence": str(item.get("evidence", "")).strip(),
            "explanation": str(item.get("explanation", "")).strip(),
        })

    missing = set(TRIAGE_AXES) - seen
    if missing:
        raise ValueError(f"LLM omitted required axes: {sorted(missing)}")

    return cleaned


def triage_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Dynamic agentic triage node.

    When Azure OpenAI is available, GPT-4o performs a single holistic triage
    pass that:
      1. Classifies the email_type (e.g. client_escalation, internal_request).
      2. Scores five axes (deadline, authority, sentiment, thread_risk, action)
         from 0–1 with a confidence and supporting evidence for each — inferring
         business urgency from the subject, sender, masked body, implied
         deadlines, and stakeholder risk rather than keyword matching.
      3. Assigns dynamic per-axis weights tailored to this specific email.

    The composite score is ALWAYS recomputed in code from raw_scores × weights —
    the LLM's own composite/priority numbers are never trusted directly.

    When the LLM is unavailable, returns invalid JSON, or errors, the node falls
    back to the unchanged deterministic five-tool scoring path.

    State updates: axes, dynamic_weights, email_type, composite_score, priority,
                   approval_mode, triage_reasoning
    """
    logger.info(f"[TRIAGE] Scoring email_id={state['email_id']}")
    llm = _get_llm(temperature=0.0)
    masked_body = state.get("masked_body", state["body"])

    if llm:
        try:
            system_prompt = (
                "You are MailMind's Triage Agent for an enterprise inbox. Assess the "
                "BUSINESS urgency of one email and respond with JSON ONLY.\n\n"
                "Do NOT rely on keyword spotting. Reason about meaning: infer implied "
                "deadlines (even when phrased indirectly), the sender's stakeholder power "
                "and escalation risk, the true emotional tone, and whether a concrete "
                "action is actually required of the recipient.\n\n"
                "Score these FIVE axes, each from 0.0 (none) to 1.0 (maximal):\n"
                "  - deadline:    time pressure / urgency of any explicit or implied due date\n"
                "  - authority:   stakeholder power & importance of the sender / referenced people\n"
                "  - sentiment:   emotional urgency, frustration, or escalation in the tone\n"
                "  - thread_risk: business/relationship risk if this email is ignored or delayed\n"
                "  - action:      how strongly a direct response or action is required\n\n"
                "Then assign dynamic_weights to each axis reflecting what matters MOST for "
                "THIS email (e.g. a legal threat weights thread_risk higher; a newsletter "
                "weights everything low). dynamic_weights MUST sum to 1.0.\n\n"
                "Anchor all relative dates ('today', 'tomorrow', 'by Friday') to the email's "
                "received timestamp, not the current date.\n\n"
                "Respond with EXACTLY this JSON shape and nothing else (no markdown):\n"
                "{\n"
                '  "email_type": "<short category, e.g. client_escalation | internal_request | '
                'meeting_request | fyi_newsletter | approval_request>",\n'
                '  "axes": [\n'
                '    {"axis": "deadline", "raw_score": 0.0, "confidence": 0.0, '
                '"evidence": "<quote/paraphrase from the email>", "explanation": "<why>"},\n'
                '    {"axis": "authority", ...},\n'
                '    {"axis": "sentiment", ...},\n'
                '    {"axis": "thread_risk", ...},\n'
                '    {"axis": "action", ...}\n'
                "  ],\n"
                '  "dynamic_weights": {"deadline": 0.0, "authority": 0.0, "sentiment": 0.0, '
                '"thread_risk": 0.0, "action": 0.0},\n'
                '  "composite_score": 0.0,\n'
                '  "priority": "CRITICAL|HIGH|MEDIUM|LOW",\n'
                '  "approval_mode": "GATE|SUGGEST",\n'
                '  "overall_reasoning": "<2-3 sentence justification>"\n'
                "}"
            )
            user_prompt = (
                f"Email metadata and content:\n"
                f"Sender: {state['sender']}\n"
                f"Subject: {state['subject']}\n"
                f"Received: {state['received_at']}\n"
                f"Body:\n{masked_body}"
            )

            response: AIMessage = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])

            data = _parse_triage_json(response.content)

            axes = _validate_axes(data.get("axes"))
            weights = _normalise_weights(data.get("dynamic_weights", {}))
            # Authoritative composite — recomputed in code, LLM value discarded.
            composite = _recompute_composite(axes, weights)
            priority, approval_mode = _priority_from_score(composite)

            email_type = str(data.get("email_type", "")).strip() or "uncategorised"
            reasoning = str(data.get("overall_reasoning", "")).strip()

            logger.info(
                f"[TRIAGE] email_id={state['email_id']} type={email_type} "
                f"score={composite} priority={priority}"
            )
            record_llm_call("triage", "success")

            return {
                "axes": axes,
                "dynamic_weights": weights,
                "email_type": email_type,
                "composite_score": composite,
                "priority": priority,
                "approval_mode": approval_mode,
                "triage_reasoning": reasoning,
                "current_step": "triage",
            }

        except Exception as e:
            logger.warning(f"[TRIAGE] Dynamic LLM triage failed: {e} — using deterministic fallback")
            state["errors"].append(f"triage_llm_error: {str(e)}")
            record_llm_call("triage", "error")

    # The deterministic path runs both when no LLM is configured and after an
    # LLM error — count it as a fallback for the fallback-rate metric.
    record_llm_call("triage", "fallback")

    # ── Deterministic fallback ────────────────────────────────────────────────
    axes = [
        score_deadline_axis.invoke({
            "body": masked_body,
            "subject": state["subject"],
            "received_at": state["received_at"],
        }),
        score_authority_axis.invoke({
            "sender_email": state["sender"],
            "subject": state["subject"],
            "body": masked_body,
        }),
        score_sentiment_axis.invoke({"body": masked_body}),
        score_decay_axis.invoke({"received_at": state["received_at"]}),
        score_action_axis.invoke({"body": masked_body}),
    ]
    composite = compute_composite_score.invoke({"axes": axes})

    return {
        "axes": axes,
        # Static weights (mirrors compute_composite_score) for response parity.
        "dynamic_weights": {
            "deadline": 0.30, "authority": 0.25, "sentiment": 0.20,
            "decay": 0.15, "action": 0.10,
        },
        "email_type": "uncategorised",
        "composite_score": composite["composite_score"],
        "priority": composite["priority"],
        "approval_mode": composite["approval_mode"],
        "triage_reasoning": "Deterministic fallback scoring applied (LLM unavailable).",
        "current_step": "triage",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3: COMMITMENT EXTRACTION AGENT NODE
# ─────────────────────────────────────────────────────────────────────────────

def commitment_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Agentic commitment extraction node. Uses GPT-4o structured output to:
      1. Identify all action items, tasks, and promises in the email
      2. Extract deadlines in ISO 8601 format
      3. Assign a confidence score (0.0–1.0) to each commitment
      4. Filter to commitments above the 0.80 confidence gate

    When the LLM is available: uses JSON-mode structured output for reliable parsing.
    When unavailable: calls the deterministic extract_commitments_from_text tool.

    State updates: commitments, commitment_reasoning
    """
    logger.info(f"[COMMITMENT] Extracting for email_id={state['email_id']}")
    llm = _get_llm(temperature=0.0)
    masked_body = state.get("masked_body", state["body"])

    if llm:
        try:
            messages = [
                SystemMessage(content=(
                    "You are MailMind's Commitment Extraction Agent.\n\n"
                    "Extract ALL action items, commitments, and deadlines from the email below.\n"
                    "For each commitment:\n"
                    "  - 'commitment': concise description of the required action\n"
                    "  - 'deadline': ISO 8601 datetime string, or null if not specified\n"
                    "  - 'confidence': 0.0–1.0 confidence score\n\n"
                    "Return ONLY a valid JSON object: "
                    "{\"commitments\": [{\"commitment\": ..., \"deadline\": ..., \"confidence\": ...}]}\n"
                    "Do not include markdown, backticks, or any other text."
                )),
                HumanMessage(content=f"Email body:\n{masked_body}"),
            ]

            import uuid as _uuid
            response = llm.invoke(messages)
            content = response.content.strip()
            # Strip markdown fences if present
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

            data = json.loads(content)
            raw_items = data.get("commitments", [])

            commitments = []
            for item in raw_items:
                confidence = float(item.get("confidence", 0.5))
                if confidence >= 0.80:  # Confidence gate
                    commitments.append({
                        "id": str(_uuid.uuid4()),
                        "commitment": item.get("commitment", ""),
                        "deadline": item.get("deadline"),
                        "confidence": confidence,
                        "approved": None,
                        "conflict_badge": False,
                        "conflict_detail": None,
                    })

            return {
                "commitments": commitments,
                "commitment_reasoning": f"GPT-4o extracted {len(raw_items)} commitments; {len(commitments)} passed the 0.80 confidence gate.",
                "current_step": "commitment",
            }

        except Exception as e:
            logger.warning(f"[COMMITMENT] LLM failed: {e} — using deterministic fallback")
            state["errors"].append(f"commitment_llm_error: {str(e)}")

    # ── Deterministic fallback ────────────────────────────────────────────────
    fallback_commitments = extract_commitments_from_text.invoke({"masked_text": masked_body})
    return {
        "commitments": [c for c in fallback_commitments if c["confidence"] >= 0.80],
        "commitment_reasoning": "Deterministic regex fallback applied (LLM unavailable).",
        "current_step": "commitment",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 4: CALENDAR CONFLICT AGENT NODE
# ─────────────────────────────────────────────────────────────────────────────

def calendar_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Calendar conflict detection node. For each extracted commitment with a
    deadline, calls check_calendar_conflict to detect scheduling collisions
    within the 72-hour calendar window.

    This node enriches the commitment items in state with conflict_badge and
    conflict_detail fields, surfaced in the frontend as visual warning badges.

    In mock mode (USE_MOCK_GRAPH=true): uses empty calendar (no conflicts).
    In live mode: calendar_events are populated by the Graph API caller before
    this node runs.

    State updates: commitments (enriched with conflict data), conflict_summary
    """
    logger.info(f"[CALENDAR] Checking conflicts for email_id={state['email_id']}")
    commitments = state.get("commitments", [])
    calendar_events = state.get("calendar_events", [])

    if not commitments:
        return {"current_step": "calendar", "conflict_summary": "No commitments to check."}

    enriched = []
    conflict_count = 0

    for commitment in commitments:
        deadline = commitment.get("deadline")
        if deadline:
            conflict_result = check_calendar_conflict.invoke({
                "deadline_str": deadline,
                "calendar_events": calendar_events,
                "window_hours": 2,
            })
            commitment["conflict_badge"] = conflict_result["conflict_badge"]
            commitment["conflict_detail"] = conflict_result.get("conflict_detail")
            if conflict_result["conflict_badge"]:
                conflict_count += 1
        enriched.append(commitment)

    summary = (
        f"{conflict_count} of {len(enriched)} commitments have calendar conflicts."
        if conflict_count > 0
        else f"No calendar conflicts detected across {len(enriched)} commitments."
    )

    return {
        "commitments": enriched,
        "conflict_summary": summary,
        "current_step": "calendar",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 5: RAG AGENT NODE
# ─────────────────────────────────────────────────────────────────────────────

def rag_node(state: EmailAgentState, index_documents: list[dict] | None = None) -> dict[str, Any]:
    """
    RAG precedent retrieval and draft generation node.

    Steps:
      1. Retrieve top-3 semantically similar sent emails from the vector index
      2. Build a few-shot draft prompt injecting precedent context (Tone DNA alignment)
      3. Generate a draft reply using GPT-4o with the precedent-injected prompt

    The draft incorporates the user's historical communication style — this is
    MailMind's Tone DNA feature: responses that sound like the user wrote them.

    State updates: precedents, draft_prompt, draft_reply
    """
    logger.info(f"[RAG] Retrieving precedents for email_id={state['email_id']}")
    masked_body = state.get("masked_body", state["body"])
    logger.info(
        f"index_documents type={type(index_documents)} "
        f"value={index_documents}"
    )
    documents = index_documents or []

    if isinstance(documents, dict):
        documents = [documents]

    # Step 1: Retrieve precedents
    precedents = retrieve_rag_precedents.invoke({
        "masked_email_text": masked_body,
        "index_documents": documents,
        "top_k": 3,
        "threshold": 0.75,
    })

    # Step 2: Build draft prompt
    draft_prompt = build_draft_prompt.invoke({
        "email_text": masked_body,
        "precedents": precedents,
    })

    # Step 3: Generate draft reply
    draft_reply = ""
    llm = _get_llm(temperature=0.3)

    if llm:
        try:
            messages = [
                SystemMessage(content=(
                    "You are MailMind's Draft Generation Agent. "
                    "Write a professional, concise reply that matches the user's established communication style. "
                    "Keep the reply focused, action-oriented, and under 150 words."
                )),
                HumanMessage(content=draft_prompt),
            ]
            response = llm.invoke(messages)
            draft_reply = response.content.strip()
        except Exception as e:
            logger.warning(f"[RAG] Draft generation failed: {e}")
            draft_reply = f"[Draft unavailable — LLM error: {str(e)}]"
            state["errors"].append(f"rag_draft_error: {str(e)}")
    else:
        draft_reply = (
            "Thank you for your email. I have received your message and will respond shortly.\n\n"
            "Best regards"
        )

    return {
        "precedents": precedents,
        "draft_prompt": draft_prompt,
        "draft_reply": draft_reply,
        "current_step": "rag",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 6: APPROVAL GATE NODE
# ─────────────────────────────────────────────────────────────────────────────

def gate_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Human-in-the-loop approval gate node — the final step in the pipeline.

    For CRITICAL emails (composite_score ≥ 75), the pipeline pauses here and
    requires explicit human approval via POST /api/commitments/confirm before
    any actions (task creation, calendar events, reply sending) proceed.

    For HIGH/MEDIUM/LOW, suggestions are surfaced in the UI but actions can
    proceed without blocking approval.

    In a full LangGraph deployment, this node can use LangGraph's built-in
    interrupt() primitive to pause graph execution until the human responds.

    State updates: current_step, approved (remains False until human confirms)
    """
    logger.info(f"[GATE] Approval gate for email_id={state['email_id']} priority={state.get('priority')}")

    approval_mode = state.get("approval_mode", "SUGGEST")
    priority = state.get("priority", "LOW")
    composite = state.get("composite_score", 0.0)

    gate_message = (
        f"⛔ GATE — Human approval required before proceeding. "
        f"Priority: {priority} | Score: {composite:.1f}"
        if approval_mode == "GATE"
        else f"✅ SUGGEST — Actions suggested for review. Priority: {priority} | Score: {composite:.1f}"
    )

    logger.info(f"[GATE] {gate_message}")

    return {
        "current_step": "gate",
        "approved": False,  # Human must set this to True via the confirm endpoint
    }


__all__ = [
    "ingest_node",
    "triage_node",
    "commitment_node",
    "calendar_node",
    "rag_node",
    "gate_node",
]