"""
Monitoring & operational endpoints.
===================================

  GET /metrics       Prometheus exposition format (scrape target)
  GET /health/deep   Dependency health (queue, database, LLM) for readiness gating
  GET /sla           Human-readable SLA configuration + live queue depth

These complement the lightweight ``/api/health`` and ``/api/ready`` probes used
by container orchestrators; ``/health/deep`` is for dashboards and on-call use.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response

from app.config.settings import settings
from app.db.base import is_persistence_enabled
from app.monitoring.metrics import metrics_content_type, generate_metrics, set_queue_depth
from app.queue.backends import get_queue_backend

router = APIRouter(tags=["monitoring"])


@router.get("/metrics")
def metrics() -> Response:
    """Metrics endpoint (disabled — Prometheus removed)."""
    try:
        set_queue_depth(get_queue_backend().depth())
    except Exception:
        pass
    body = generate_metrics()
    content_type = metrics_content_type()
    return Response(content=body, media_type=content_type)


@router.get("/health/deep")
def health_deep() -> dict:
    """
    Deep health check across all dependencies.

    Returns 200 always (so it never trips a liveness probe), but the body's
    ``status`` is "degraded" if any non-critical dependency is down. Callers
    can decide how to react.
    """
    queue = get_queue_backend()
    queue_ok = queue.healthy()
    db_ok = is_persistence_enabled()
    llm_ok = bool(settings.azure_openai_api_key and settings.azure_openai_base_endpoint)

    checks = {
        "queue": {"backend": queue.name, "healthy": queue_ok, "depth": _safe_depth(queue)},
        "database": {"enabled": db_ok, "healthy": db_ok},
        "llm": {"configured": llm_ok},
    }
    # The queue is the only hard dependency for accepting work.
    overall = "ok" if queue_ok else "degraded"

    return {
        "status": overall,
        "environment": settings.app_env,
        "release": settings.app_release,
        "checks": checks,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@router.get("/sla")
def sla_summary() -> dict:
    """Report configured SLA targets and current saturation."""
    queue = get_queue_backend()
    return {
        "targets_seconds": {
            "triage": settings.sla_triage_seconds,
            "enrichment": settings.sla_enrichment_seconds,
        },
        "queue_depth": _safe_depth(queue),
        "queue_backend": queue.name,
        "metrics_enabled": settings.metrics_enabled,
        "note": "Live SLA compliance percentages are exported via /metrics "
                "(mailmind_sla_compliance_total).",
    }


def _safe_depth(queue) -> int:
    try:
        return queue.depth()
    except Exception:
        return -1
