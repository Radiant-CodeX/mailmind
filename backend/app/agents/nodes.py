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
import os
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import AzureChatOpenAI

from app.graph.state import EmailAgentState
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

def _get_llm(temperature: float = 0.1) -> AzureChatOpenAI | None:
    """
    Return an AzureChatOpenAI instance configured from environment variables.
    Returns None if Azure credentials are not present (triggers fallback paths).
    """
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")

    if not api_key or not endpoint:
        logger.warning("Azure OpenAI credentials not set — using deterministic fallbacks")
        return None

    return AzureChatOpenAI(
        azure_endpoint=endpoint,
        azure_deployment=deployment,
        api_key=api_key,
        api_version="2024-02-01",
        temperature=temperature,
    )


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
    masked, mapping = pii_sanitizer.mask_text(state["body"])

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

def triage_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Agentic triage node. Uses GPT-4o with bound triage tools to:
      1. Score all five axes (deadline, authority, sentiment, decay, action)
      2. Compute the composite score (0–100)
      3. Determine priority (CRITICAL/HIGH/MEDIUM/LOW) and approval mode

    When Azure OpenAI is available: the LLM reasons about which scoring tools
    to call and in what order, producing a chain-of-thought triage explanation.

    When unavailable: falls back to calling all five scoring tools deterministically.

    State updates: axes, composite_score, priority, approval_mode, triage_reasoning
    """
    logger.info(f"[TRIAGE] Scoring email_id={state['email_id']}")
    llm = _get_llm(temperature=0.0)
    masked_body = state.get("masked_body", state["body"])

    if llm:
        try:
            llm_with_tools = llm.bind_tools(TRIAGE_TOOLS)
            messages = [
                SystemMessage(content=(
                    "You are MailMind's Triage Agent. Your task is to score the incoming email "
                    "across five axes using the provided tools, then compute a composite score.\n\n"
                    "REQUIRED STEPS (call each tool in order):\n"
                    "1. score_deadline_axis — detect and score urgency of any deadlines\n"
                    "2. score_authority_axis — assess sender importance\n"
                    "3. score_sentiment_axis — detect emotional urgency signals\n"
                    "4. score_decay_axis — penalise older threads\n"
                    "5. score_action_axis — detect whether a direct response is required\n"
                    "6. compute_composite_score — combine all axis scores into a final 0–100 score\n\n"
                    "After all tool calls, summarise your triage reasoning in 2–3 sentences."
                )),
                HumanMessage(content=(
                    f"Email Details:\n"
                    f"Sender: {state['sender']}\n"
                    f"Subject: {state['subject']}\n"
                    f"Received: {state['received_at']}\n"
                    f"Body: {masked_body}\n\n"
                    f"Run all five axis scoring tools, then compute_composite_score."
                )),
            ]

            axes: list[dict] = []
            composite_result: dict = {}
            reasoning = ""
            max_iterations = 10

            for _ in range(max_iterations):
                response: AIMessage = llm_with_tools.invoke(messages)
                messages.append(response)

                if not response.tool_calls:
                    reasoning = response.content or ""
                    break

                for tc in response.tool_calls:
                    result = _dispatch_tool(tc)
                    messages.append(
                        ToolMessage(content=json.dumps(result), tool_call_id=tc["id"])
                    )
                    if isinstance(result, dict):
                        if "axis" in result:
                            axes.append(result)
                        elif "composite_score" in result:
                            composite_result = result

            return {
                "axes": axes,
                "composite_score": composite_result.get("composite_score", 0.0),
                "priority": composite_result.get("priority", "LOW"),
                "approval_mode": composite_result.get("approval_mode", "SUGGEST"),
                "triage_reasoning": reasoning,
                "current_step": "triage",
            }

        except Exception as e:
            logger.warning(f"[TRIAGE] LLM failed: {e} — using deterministic fallback")
            state["errors"].append(f"triage_llm_error: {str(e)}")

    # ── Deterministic fallback ────────────────────────────────────────────────
    axes = [
        score_deadline_axis.invoke({"body": masked_body}),
        score_authority_axis.invoke({"sender_email": state["sender"]}),
        score_sentiment_axis.invoke({"body": masked_body}),
        score_decay_axis.invoke({"received_at": state["received_at"]}),
        score_action_axis.invoke({"body": masked_body}),
    ]
    composite = compute_composite_score.invoke({"axes": axes})

    return {
        "axes": axes,
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


# Re-export for graph assembly
import re  # noqa: E402 — needed inside commitment_node

__all__ = [
    "ingest_node",
    "triage_node",
    "commitment_node",
    "calendar_node",
    "rag_node",
    "gate_node",
]