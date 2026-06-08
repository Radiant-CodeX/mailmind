"""
Prometheus metrics & SLA instrumentation.
=========================================

Exposes the four "golden signals" plus domain-specific counters so the pipeline
is observable in real time (scrape ``GET /metrics`` with Prometheus, visualise
in Grafana):

  Latency      stage_duration_seconds{stage}        (histogram)
               node_duration_seconds{node}          (histogram)
  Traffic      emails_processed_total{stage,status} (counter)
  Errors       emails_processed_total{...status=error}
  Saturation   queue_depth                          (gauge)

Domain metrics:
  llm_calls_total{node,outcome}      — LLM usage & fallback rate
  pii_masked_total{category}         — privacy coverage (counts only, no values)
  sla_compliance_total{stage,met}    — % of requests meeting their SLA target

SLA targets come from settings (``sla_triage_seconds`` / ``sla_enrichment_seconds``).
Every ``track_stage`` block records duration, success/failure, and whether the
SLA was met — all in one place so instrumentation can't drift from reality.

When ``settings.metrics_enabled`` is False all helpers become cheap no-ops.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.config.settings import settings
from app.db import repository as repo

logger = logging.getLogger(__name__)

# Dedicated registry so MailMind metrics are isolated and testable.
REGISTRY = CollectorRegistry()

# Latency buckets tuned for an LLM pipeline (sub-second to ~30s).
_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 1.5, 2.5, 5.0, 10.0, 20.0, 30.0)

EMAILS_PROCESSED = Counter(
    "mailmind_emails_processed_total",
    "Emails processed, partitioned by pipeline stage and outcome.",
    ["stage", "status"],
    registry=REGISTRY,
)

STAGE_DURATION = Histogram(
    "mailmind_stage_duration_seconds",
    "Wall-clock duration of a processing stage (triage / enrichment).",
    ["stage"],
    buckets=_LATENCY_BUCKETS,
    registry=REGISTRY,
)

NODE_DURATION = Histogram(
    "mailmind_node_duration_seconds",
    "Wall-clock duration of an individual LangGraph node.",
    ["node"],
    buckets=_LATENCY_BUCKETS,
    registry=REGISTRY,
)

LLM_CALLS = Counter(
    "mailmind_llm_calls_total",
    "LLM invocations by node and outcome (success / fallback / error).",
    ["node", "outcome"],
    registry=REGISTRY,
)

PII_MASKED = Counter(
    "mailmind_pii_masked_total",
    "PII entities masked, by category (counts only — never values).",
    ["category"],
    registry=REGISTRY,
)

SLA_COMPLIANCE = Counter(
    "mailmind_sla_compliance_total",
    "SLA outcomes per stage: met=true|false.",
    ["stage", "met"],
    registry=REGISTRY,
)

QUEUE_DEPTH = Gauge(
    "mailmind_queue_depth",
    "Pending enrichment jobs in the queue (saturation signal).",
    registry=REGISTRY,
)


def _sla_target(stage: str) -> float:
    return settings.sla_enrichment_seconds if stage == "enrichment" else settings.sla_triage_seconds


@contextmanager
def track_stage(stage: str, email_id: str | None = None) -> Iterator[None]:
    """
    Time a processing stage and record traffic, errors, latency, and SLA.

    Usage::

        with track_stage("triage", email_id):
            run_triage(...)

    On exception the stage is marked failed (and re-raised). Either way a
    ProcessingMetric row is persisted (when a DB is configured) and the SLA
    counter is incremented based on the stage's target latency.
    """
    if not settings.metrics_enabled:
        yield
        return

    start = time.perf_counter()
    status = "success"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        elapsed = time.perf_counter() - start
        sla_met = elapsed <= _sla_target(stage) and status == "success"

        STAGE_DURATION.labels(stage=stage).observe(elapsed)
        EMAILS_PROCESSED.labels(stage=stage, status=status).inc()
        SLA_COMPLIANCE.labels(stage=stage, met=str(sla_met).lower()).inc()

        # Best-effort durable metric (no-op without a DB).
        try:
            repo.record_metric(
                email_id, stage, round(elapsed * 1000, 2),
                success=(status == "success"), sla_met=sla_met,
            )
        except Exception as exc:  # never let metrics break the request
            logger.debug("record_metric failed: %s", exc)


@contextmanager
def observe_node(node: str) -> Iterator[None]:
    """Time a single LangGraph node and record its duration histogram."""
    if not settings.metrics_enabled:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        NODE_DURATION.labels(node=node).observe(time.perf_counter() - start)


def record_llm_call(node: str, outcome: str) -> None:
    """Record an LLM invocation outcome: 'success' | 'fallback' | 'error'."""
    if settings.metrics_enabled:
        LLM_CALLS.labels(node=node, outcome=outcome).inc()


def record_pii_masked(category_counts: dict[str, int]) -> None:
    """Increment PII counters by category. Accepts {'PERSON': 2, 'EMAIL': 1}."""
    if not settings.metrics_enabled:
        return
    for category, count in category_counts.items():
        PII_MASKED.labels(category=category).inc(count)


def set_queue_depth(depth: int) -> None:
    """Update the queue-depth saturation gauge."""
    if settings.metrics_enabled:
        QUEUE_DEPTH.set(depth)


def record_cache_hit(node: str) -> None:
    """Record a prompt-cache hit for a given node (tracks caching effectiveness)."""
    if settings.metrics_enabled:
        LLM_CALLS.labels(node=node, outcome="cache_hit").inc()


def render_latest_metrics() -> tuple[bytes, str]:
    """Return (body, content_type) for the ``GET /metrics`` endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
