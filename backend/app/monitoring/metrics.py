"""
Metrics module (disabled - Prometheus removed).

All metrics functions are now no-ops for performance.
"""

from contextlib import contextmanager
from typing import Iterator


def record_llm_call(node: str, outcome: str) -> None:
    """No-op — metrics disabled."""
    pass


def record_pii_masked(categories: dict) -> None:
    """No-op — metrics disabled."""
    pass


def track_stage(stage: str) -> Iterator[None]:
    """Context manager that does nothing — metrics disabled."""
    @contextmanager
    def noop():
        yield

    return noop()


def observe_node(node: str) -> Iterator[None]:
    """Context manager that does nothing — metrics disabled."""
    @contextmanager
    def noop():
        yield

    return noop()


def set_queue_depth(depth: int) -> None:
    """No-op — metrics disabled."""
    pass


def metrics_content_type() -> str:
    """Return empty metrics (no Prometheus)."""
    return "text/plain"


def generate_metrics() -> str:
    """Return empty metrics."""
    return "# Metrics disabled\n"
