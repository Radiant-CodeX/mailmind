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
  - The caller's configured model (their own key, or the server default) via
    app.services.llm_provider — any OpenAI-compatible provider
  - A structured, campus-aware system prompt for its specific task
  - A deterministic rule-based fallback when no model is configured or it fails
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph.state import EmailAgentState
from app.monitoring.metrics import observe_node, record_llm_call, record_pii_masked
from app.services import campus, llm_provider
from app.services.tracing import trace_config
from app.tools.email_tools import (
    ALL_TOOLS,
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


def _get_llm(temperature: float = 0.1, purpose: str = "chat", max_tokens: int | None = None):
    """
    Return the chat model for the current caller, or None.

    Resolution (see llm_provider): the signed-in user's own API key/model →
    the server default (LLM_* env) → None, which triggers the deterministic
    rule-based fallbacks in every node.
    """
    llm = llm_provider.get_chat_model(temperature, purpose=purpose, max_tokens=max_tokens)
    if llm is None:
        logger.info("No AI model configured for this user — using deterministic fallbacks")
    return llm


def _current_profile() -> dict[str, Any]:
    """Campus profile (student/faculty/staff) of the user this pipeline serves."""
    from app.services.user_settings import load_campus_profile
    return load_campus_profile(llm_provider.current_ai_user_id())


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
        # Mask subject + body under one shared mapping so a value appearing in
        # both gets the same token and restoration stays consistent.
        (masked_subject, masked), mapping = pii_sanitizer.mask_fields(
            [state.get("subject") or "", state["body"]]
        )

    # Record PII coverage by category (counts only — never raw values).
    if mapping:
        category_counts: dict[str, int] = {}
        for placeholder in mapping:                      # e.g. "[PERSON_1]"
            category = placeholder.strip("[]").rsplit("_", 1)[0]
            category_counts[category] = category_counts.get(category, 0) + 1
        record_pii_masked(category_counts)

    return {
        "masked_body": masked,
        "masked_subject": masked_subject,
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
# NODE 2: TRIAGE
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


_NOREPLY_SENDER_RE = re.compile(
    r"(no[._-]?reply|do[._-]?not[._-]?reply|donotreply|mailer[-_.]?daemon|"
    r"bounce[s]?@|notifications?@|automated?@|alerts?@|postmaster@)",
    re.IGNORECASE,
)


def _is_automated_sender(sender: str, body: str) -> bool:
    """True when the email comes from a no-reply / automated address."""
    if _NOREPLY_SENDER_RE.search(sender or ""):
        return True
    b = (body or "").lower()
    return any(m in b for m in (
        "no-reply", "noreply", "do not reply", "please do not reply",
        "this is an automated", "unsubscribe",
    ))


def _dampen_automated_action(axes: list[dict], sender: str, body: str, subject: str = "") -> list[dict]:
    """
    Automated / no-reply bulk mail rarely needs the reader to act, so cap the
    'action' axis for it (e.g. a newsletter or a social notification).

    Campus exception: placement portals, the exam cell and ERP systems also
    send from no-reply addresses, and those often demand action (register on
    the portal, download the hall ticket). Official campus mail and mail with a
    campus-critical signal are never dampened.
    """
    if not _is_automated_sender(sender, body):
        return axes
    if campus.is_campus_sender(sender) or campus.has_campus_critical_signal(subject, body):
        return axes
    for a in axes:
        if a.get("axis") == "action" and float(a.get("raw_score", 0.0)) > 0.2:
            a["raw_score"] = 0.15
            a["explanation"] = "Automated / no-reply sender — no direct reply expected"
    return axes


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


def _validate_axes(raw_axes: Any) -> list[dict]:
    """
    Validate and clean the LLM's axis list. Raises ValueError if the payload
    is unusable (triggering the deterministic fallback in the caller).

    Expected format (slimmed for speed):
      {"axis": "deadline", "score": 0.5, "explanation": "..."}
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

        # Accept both "score" (new slim format) and "raw_score" (legacy).
        # Explicit None check avoids the `0.0 or fallback` pitfall.
        _s = item.get("score")
        score_val = _s if _s is not None else item.get("raw_score", 0.0)

        cleaned.append({
            "axis": axis,
            "raw_score": max(0.0, min(1.0, float(score_val))),  # normalized to [0, 1]
            "confidence": 0.95,  # default high confidence for LLM output
            "evidence": "",  # not requested from LLM anymore
            "explanation": str(item.get("explanation", "")).strip(),
        })

    missing = set(TRIAGE_AXES) - seen
    if missing:
        raise ValueError(f"LLM omitted required axes: {sorted(missing)}")

    return cleaned


_TRIAGE_OUTPUT_FORMAT = (
    'Output format (JSON only, no markdown, replace the example scores with real values):\n'
    '{"email_type":"<one category id>",'
    '"axes":['
    '{"axis":"deadline","score":0.6,"explanation":"<1 short sentence>"},'
    '{"axis":"authority","score":0.5,"explanation":"<1 short sentence>"},'
    '{"axis":"sentiment","score":0.4,"explanation":"<1 short sentence>"},'
    '{"axis":"thread_risk","score":0.3,"explanation":"<1 short sentence>"},'
    '{"axis":"action","score":0.7,"explanation":"<1 short sentence>"}'
    '],'
    '"overall_reasoning":"<1 sentence: why this priority, naming the concrete stake>"}'
)

_triage_prompt_cache: dict[tuple, str] = {}


def _triage_system_prompt(profile: dict[str, Any]) -> str:
    """Campus triage prompt, specialised to the reader's role (cached per role)."""
    key = (profile.get("role"), profile.get("department"), profile.get("year_of_study"))
    cached = _triage_prompt_cache.get(key)
    if cached:
        return cached
    prompt = (
        "You are MailMind's Triage for a university inbox. Judge how urgently the reader must "
        "act on ONE email and respond with JSON ONLY.\n\n"
        f"{campus.role_context(profile)}\n\n"
        "Score these FIVE axes from 0.0 (none) to 1.0 (maximum):\n"
        "  deadline: time pressure from any explicit/implied cut-off (registration closes, hall "
        "ticket download window, fee due date, submission date, interview/report time)\n"
        "  authority: institutional weight of the sender or referenced office\n"
        "  sentiment: warning or escalation tone (attendance shortage, debarment, penalty, "
        "final reminder, a frustrated faculty member)\n"
        "  thread_risk: what the reader LOSES if they ignore or delay it (placement eligibility, "
        "exam eligibility, a fine, a grade, a relationship with faculty)\n"
        "  action: how strongly the reader must personally do something (register, submit, pay, "
        "attend, reply, download)\n\n"
        f"{campus.authority_prompt_guide()}\n\n"
        "Rules:\n"
        "- Anchor relative dates ('tomorrow', 'this Friday') to the Received timestamp.\n"
        "- Mail from a no-reply address can still demand action (portal registration, hall "
        "tickets) — score action on what the reader must DO, not on whether they can reply.\n"
        "- Club promotions, newsletters and 'FYI' announcements score low unless they carry a "
        "deadline the reader clearly cares about.\n"
        "- Use the full 0.0–1.0 range; do not return template values.\n\n"
        "email_type must be exactly one of these category ids:\n"
        f"{campus.categories_prompt_list()}\n\n"
        f"{_TRIAGE_OUTPUT_FORMAT}"
    )
    _triage_prompt_cache[key] = prompt
    return prompt


def _commitment_system_prompt(profile: dict[str, Any], received_at: str) -> str:
    return (
        "You are MailMind's Commitment Extraction for a university inbox.\n"
        f"{campus.role_context(profile)}\n\n"
        "Extract every concrete thing the READER must do, with its deadline. On campus this "
        "includes: registering for a placement drive or event, submitting an assignment/record/"
        "project, paying a fee, downloading a hall ticket, attending an exam, interview, viva, "
        "class or meeting (use the start time as the deadline), replying to faculty, and "
        "uploading documents. Skip vague marketing asks.\n"
        "For each item give: commitment (short imperative, include the venue if one is given), "
        "deadline (ISO 8601 with time when known, e.g. 2026-10-05T17:00:00+05:30; null if none), "
        "confidence (0.0–1.0).\n"
        "Dates are Indian format (DD/MM/YYYY) unless clearly otherwise. Resolve relative dates "
        f"against the received time: {received_at or 'unknown'}. Times are IST (+05:30) unless stated.\n"
        'Return ONLY valid JSON: {"commitments":[{"commitment":"...","deadline":"...","confidence":0.9}]}'
    )


def triage_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Triage — scores email urgency across five axes with the caller's triage model.

    Optimizations:
    - Slimmed output schema: removed evidence, dynamic_weights, composite_score, overall_reasoning
    - Pre-built system prompt (module-level constant, not rebuilt per call)
    - Body truncated to 1500 chars (LLM doesn't need full body for triage scoring)
    - max_tokens=400 cap (5-axis JSON with explanations ~150-200 tokens; headroom for longer explanations)
    - Composite score + weights recomputed in Python (never trust LLM values)
    - Deterministic fallback unchanged

    Latency depends on the configured provider (Groq / OpenRouter free models
    typically answer in ~0.5-3s).

    State updates: axes, dynamic_weights, email_type, composite_score, priority,
                   approval_mode, triage_reasoning
    """
    logger.info(f"[TRIAGE] Scoring email_id={state['email_id']}")
    llm = _get_llm(temperature=0.0, purpose="triage", max_tokens=450)
    masked_body = state.get("masked_body", state["body"])

    # Truncate body — triage only needs enough context to score urgency (~1500 chars)
    body_for_triage = masked_body[:1500] if masked_body and len(masked_body) > 1500 else masked_body

    if llm:
        try:
            # Subject is masked too (shares mask_mapping with the body) so no PII
            # in the subject line reaches the LLM.
            subject_for_triage = state.get("masked_subject") or state["subject"]
            user_prompt = (
                f"Sender: {state['sender']}\n"
                f"Subject: {subject_for_triage}\n"
                f"Received: {state['received_at']}\n"
                f"Body:\n{body_for_triage}"
            )

            # max_tokens cap (set on the model): 5-axis JSON with explanations
            # averages ~150-200 tokens; 450 leaves headroom and stays fast.
            response: AIMessage = llm.invoke(
                [
                    SystemMessage(content=_triage_system_prompt(_current_profile())),
                    HumanMessage(content=user_prompt),
                ],
                config=trace_config("triage", email_id=state.get("email_id"),
                                    user=state.get("user_email")),
            )

            logger.debug("[TRIAGE] raw LLM response: %s", response.content[:300])
            data = llm_provider.parse_json(response.content)

            axes = _validate_axes(data.get("axes"))
            # No-reply/automated senders shouldn't score high on "action" (you
            # can't reply to them) — cap it before the composite is computed.
            axes = _dampen_automated_action(
                axes, state["sender"], body_for_triage or state["body"], subject_for_triage or ""
            )
            weights = _normalise_weights(data.get("dynamic_weights", {}))
            # Authoritative composite — recomputed in code, LLM value discarded.
            composite = _recompute_composite(axes, weights)
            priority, approval_mode = _priority_from_score(composite)

            email_type = campus.normalise_category(data.get("email_type"))
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
        "email_type": campus.categorize(state["sender"], state["subject"], masked_body or ""),
        "composite_score": composite["composite_score"],
        "priority": composite["priority"],
        "approval_mode": composite["approval_mode"],
        "triage_reasoning": "Deterministic fallback scoring applied (LLM unavailable).",
        "current_step": "triage",
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3: COMMITMENT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def commitment_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Agentic commitment extraction node. Uses the caller's model to:
      1. Identify all action items, tasks, and promises in the email
      2. Extract deadlines in ISO 8601 format
      3. Assign a confidence score (0.0–1.0) to each commitment
      4. Filter to commitments above the 0.80 confidence gate

    When the LLM is available: uses JSON-mode structured output for reliable parsing.
    When unavailable: calls the deterministic extract_commitments_from_text tool.

    State updates: commitments, commitment_reasoning
    """
    logger.info(f"[COMMITMENT] Extracting for email_id={state['email_id']}")
    llm = _get_llm(temperature=0.0, max_tokens=500)
    masked_body = state.get("masked_body", state["body"])

    if llm:
        try:
            # Truncate to 3000 chars — commitments need more context than triage,
            # but full bodies (10k+ chars) waste tokens on signatures/footers.
            body_for_commit = masked_body[:3000] if masked_body and len(masked_body) > 3000 else masked_body
            subject = state.get("masked_subject") or state.get("subject") or ""
            messages = [
                SystemMessage(content=_commitment_system_prompt(
                    _current_profile(), state.get("received_at", ""))),
                HumanMessage(content=f"Subject: {subject}\nEmail body:\n{body_for_commit}"),
            ]

            response = llm.invoke(
                messages,
                config=trace_config("commitment", email_id=state.get("email_id"),
                                    user=state.get("user_email")),
            )
            data = llm_provider.parse_json(response.content)
            raw_items = (data.get("commitments", []) if isinstance(data, dict) else data) or []

            commitments = []
            for item in raw_items:
                if not isinstance(item, dict) or not item.get("commitment"):
                    continue
                confidence = float(item.get("confidence", 0.5))
                if confidence >= 0.80:  # Confidence gate
                    commitments.append({
                        "id": str(uuid.uuid4()),
                        "commitment": item.get("commitment", ""),
                        "deadline": item.get("deadline"),
                        "confidence": confidence,
                        "approved": None,
                        "conflict_badge": False,
                        "conflict_detail": None,
                    })

            return {
                "commitments": commitments,
                "commitment_reasoning": (
                    f"{llm_provider.active_model_label()} extracted {len(raw_items)} items; "
                    f"{len(commitments)} passed the 0.80 confidence gate."
                ),
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
# NODE 4: CALENDAR CONFLICT DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def calendar_node(state: EmailAgentState) -> dict[str, Any]:
    """
    Calendar conflict detection node. For each extracted commitment with a
    deadline, calls check_calendar_conflict to detect scheduling collisions
    within the 72-hour calendar window.

    This node enriches the commitment items in state with conflict_badge and
    conflict_detail fields, surfaced in the frontend as visual warning badges.

    calendar_events are supplied by the caller (fetched from Google Calendar)
    before this node runs; with none supplied, no conflicts are reported.

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
# NODE 5: RAG PRECEDENT RETRIEVAL + DRAFT
# ─────────────────────────────────────────────────────────────────────────────

def rag_node(state: EmailAgentState, index_documents: list[dict] | None = None) -> dict[str, Any]:
    """
    RAG precedent retrieval and draft generation node.

    Steps:
      1. Retrieve top-3 semantically similar sent emails from the vector index
      2. Build a few-shot draft prompt injecting precedent context (Tone DNA alignment)
      3. Generate a draft reply with the caller's model and the precedent-injected prompt

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
        "threshold": llm_provider.similarity_threshold(),
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
                    "You are MailMind's Draft Reply for a university inbox. "
                    f"{campus.draft_etiquette(_current_profile(), state.get('sender'))} "
                    "Match the user's established communication style, keep it focused and "
                    "action-oriented, and under 150 words. Output only the reply text."
                )),
                HumanMessage(content=draft_prompt),
            ]
            response = llm.invoke(
                messages,
                config=trace_config("rag_draft", email_id=state.get("email_id"),
                                    user=state.get("user_email")),
            )
            draft_reply = llm_provider.clean_text(response.content)
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