"""
Enrichment worker — the deferred (asynchronous) half of the split pipeline.
===========================================================================

The API serves the fast *triage* path synchronously (priority in <1.5s) and
enqueues an enrichment job. One or more of these workers then run the heavy
deferred nodes — commitment extraction, calendar conflict detection, RAG
precedent retrieval, and draft generation — restore PII, and persist the result.

Run standalone (one process per replica)::

    python -m app.workers.enrichment

Design notes:
  * ``process_one`` is pure and unit-testable; ``run`` is the infinite loop.
  * Failures are retried with exponential backoff up to ``worker_max_retries``;
    exhausted jobs are persisted with status="failed" so nothing is lost
    silently and on-call can investigate.
  * Every stage is wrapped in ``track_stage`` so latency + SLA land in metrics.
  * PII is restored only here, at the very end, before persistence.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
from typing import Any

from app.agents.nodes import calendar_node, commitment_node, gate_node, rag_node
from app.config.settings import settings
from app.db import repository as repo
from app.monitoring.metrics import set_queue_depth, track_stage
from app.queue.backends import get_queue_backend
from app.services.pii import pii_sanitizer

logger = logging.getLogger(__name__)


def _load_rag_index() -> list[dict]:
    """Load the RAG index documents for precedent retrieval (empty if absent)."""
    index_path = os.getenv("CHROMA_DATA_PATH", "./data/chroma")
    index_file = os.path.join(index_path, "index.json")
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _restore_field(value: str | None, mapping: dict) -> str | None:
    """Restore known tokens, then neutralise any hallucinated/orphaned tokens."""
    if not value:
        return value
    restored = pii_sanitizer.restore_text(value, mapping)
    # Safety net: an LLM may invent a token number absent from the mapping.
    return pii_sanitizer.strip_unresolved_tokens(restored)


def _restore_pii(state: dict[str, Any]) -> None:
    """Restore PII in all user-facing outputs in place, using the mask mapping."""
    mapping = state.get("mask_mapping") or {}
    if not mapping:
        return
    state["draft_reply"] = _restore_field(state.get("draft_reply"), mapping)
    state["triage_reasoning"] = _restore_field(state.get("triage_reasoning"), mapping)
    for commitment in state.get("commitments") or []:
        commitment["commitment"] = _restore_field(commitment.get("commitment"), mapping)
        commitment["conflict_detail"] = _restore_field(commitment.get("conflict_detail"), mapping)


class EnrichmentWorker:
    """Consumes enrichment jobs from the queue and completes the pipeline."""

    def __init__(self) -> None:
        self.queue = get_queue_backend()
        self.index_documents = _load_rag_index()

    # ── Pure, testable unit of work ──────────────────────────────────────────

    def process_one(self, job: dict[str, Any]) -> dict[str, Any]:
        """
        Run the deferred nodes for a single job and persist the result.

        ``job`` shape: {"email_id": str, "state": <pipeline state after triage>}.
        Returns the enriched, PII-restored state. Raises on unrecoverable error
        (the caller decides whether to retry).
        """
        email_id = job["email_id"]
        state = job["state"]
        user_email: str = state.get("user_email") or ""

        with track_stage("enrichment"):
            state.update(commitment_node(state))
            state.update(calendar_node(state))
            state.update(rag_node(state, index_documents=self.index_documents))
            state.update(gate_node(state))

        # Restore PII before anything leaves the trust boundary (DB included
        # stores restored business text; masked_body remains masked).
        _restore_pii(state)

        repo.upsert_enrichment(email_id, state, user_email=user_email or None, status="complete", enrichment_source="agentic")
        repo.write_audit(email_id, "enriched", details={
            "priority": state.get("priority"),
            "commitments": len(state.get("commitments") or []),
        })
        logger.info("[WORKER] Enriched email_id=%s", email_id)
        return state

    # ── Retry handling ───────────────────────────────────────────────────────

    def _handle_failure(self, job: dict[str, Any], exc: Exception) -> None:
        email_id = job.get("email_id", "unknown")
        retry_count = job.get("retry_count", 0)

        if retry_count < settings.worker_max_retries:
            job["retry_count"] = retry_count + 1
            delay = settings.worker_retry_base_delay_seconds * (2 ** retry_count)
            logger.warning(
                "[WORKER] email_id=%s failed (%s); retry %d/%d in ~%ds",
                email_id, exc, job["retry_count"], settings.worker_max_retries, delay,
            )
            # Re-enqueue for another attempt. (Production Redis can use a delayed
            # set / ZADD; the in-memory backend retries on the next poll.)
            self.queue.enqueue(job)
        else:
            logger.error("[WORKER] email_id=%s exhausted retries: %s", email_id, exc)
            try:
                _state = job.get("state", {})
                repo.upsert_enrichment(
                    email_id, _state, user_email=_state.get("user_email") or None,
                    status="failed", enrichment_source="agentic", error=str(exc),
                )
                repo.write_audit(email_id, "enrich_failed", details={"error": type(exc).__name__})
            except Exception:
                logger.exception("[WORKER] failed to persist failure for %s", email_id)

    # ── Graceful shutdown ────────────────────────────────────────────────────

    def _install_signal_handlers(self) -> None:
        """
        Register SIGTERM and SIGINT handlers so a container stop / Ctrl-C
        finishes the current job before exiting rather than killing it mid-flight.

        The handler sets a threading.Event that the run-loop checks between jobs,
        so we never interrupt an in-progress enrichment.
        """
        self._stop_event = threading.Event()

        def _handle(signum: int, _frame) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("[WORKER] %s received — draining current job then stopping.", sig_name)
            self._stop_event.set()

        signal.signal(signal.SIGTERM, _handle)
        signal.signal(signal.SIGINT,  _handle)

    # ── Infinite consumer loop ───────────────────────────────────────────────

    def run(self) -> None:
        self._install_signal_handlers()
        logger.info(
            "Enrichment worker started (queue=%s, poll=%.1fs, max_retries=%d)",
            self.queue.name, settings.worker_poll_interval_seconds, settings.worker_max_retries,
        )
        while not self._stop_event.is_set():
            try:
                set_queue_depth(self.queue.depth())
                job = self.queue.dequeue()
                if job is None:
                    time.sleep(settings.worker_poll_interval_seconds)
                    continue
                try:
                    self.process_one(job)
                except Exception as exc:
                    self._handle_failure(job, exc)
            except Exception:  # never let the loop die on an unexpected error
                logger.exception("[WORKER] unexpected loop error")
                time.sleep(settings.worker_poll_interval_seconds)

        logger.info("[WORKER] Shutdown complete — no jobs in flight.")


def main() -> None:
    from app.db.base import init_db
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    init_db()
    EnrichmentWorker().run()


if __name__ == "__main__":
    main()
