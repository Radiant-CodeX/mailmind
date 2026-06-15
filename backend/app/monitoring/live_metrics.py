"""
Live in-process metrics collector for the operations dashboard.
=================================================================

Lightweight, dependency-free, thread-safe. Records:

  • per-stage latency samples  → p50 / p95 percentiles
  • LLM call outcomes          → error rate
  • pipeline run timings       → sequential-vs-parallel speedup

Everything lives in bounded ring buffers so memory is constant regardless of
uptime. This is intentionally NOT Prometheus — it powers a single live JSON
endpoint (`/api/metrics/live`) that the frontend polls, so judges can see
production-readiness signals without standing up a metrics stack.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Any

# How many recent samples to keep per stat (bounded memory).
_MAX_SAMPLES = 500

# The six pipeline stages, in execution order. Used for the speedup model and
# to give the dashboard a stable set of rows even before traffic arrives.
PIPELINE_STAGES = ["ingest", "triage", "commitments", "calendar", "rag", "draft"]


class _LiveMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        # stage -> deque of duration_ms
        self._latencies: dict[str, deque[float]] = {}
        # LLM outcome counters
        self._llm_ok = 0
        self._llm_err = 0
        # recent end-to-end pipeline runs, each a (sequential_ms, parallel_ms)
        # pair measured from the SAME batch so the speedup is apples-to-apples:
        #   sequential_ms = sum of every item's individual processing time
        #   parallel_ms   = wall-clock of the concurrent batch
        self._pipeline_runs: deque[tuple[float, float]] = deque(maxlen=_MAX_SAMPLES)
        self._started = time.time()

    # ── recording ────────────────────────────────────────────────────
    def record_latency(self, stage: str, duration_ms: float) -> None:
        with self._lock:
            buf = self._latencies.get(stage)
            if buf is None:
                buf = deque(maxlen=_MAX_SAMPLES)
                self._latencies[stage] = buf
            buf.append(float(duration_ms))

    def record_llm(self, *, success: bool) -> None:
        with self._lock:
            if success:
                self._llm_ok += 1
            else:
                self._llm_err += 1

    def record_pipeline_run(self, parallel_ms: float, sequential_ms: float | None = None) -> None:
        """
        Record one batch's parallel wall-clock and the equivalent sequential cost.

        ``sequential_ms`` is the sum of each item's individual processing time —
        i.e. what the batch WOULD have cost run one-after-another. When omitted
        the run is ignored for the speedup model (we never fabricate a baseline).
        """
        if sequential_ms is None or parallel_ms <= 0:
            return
        with self._lock:
            self._pipeline_runs.append((float(sequential_ms), float(parallel_ms)))

    # ── reporting ────────────────────────────────────────────────────
    @staticmethod
    def _percentile(values: list[float], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return round(ordered[0], 1)
        rank = (pct / 100) * (len(ordered) - 1)
        lo = int(rank)
        hi = min(lo + 1, len(ordered) - 1)
        frac = rank - lo
        return round(ordered[lo] + (ordered[hi] - ordered[lo]) * frac, 1)

    def latency_percentiles(self) -> dict[str, Any]:
        """p50/p95 per stage, plus an aggregate across all stages."""
        with self._lock:
            snapshot = {k: list(v) for k, v in self._latencies.items()}

        per_stage: dict[str, dict[str, float]] = {}
        all_samples: list[float] = []
        for stage in PIPELINE_STAGES:
            vals = snapshot.get(stage, [])
            all_samples.extend(vals)
            per_stage[stage] = {
                "p50": self._percentile(vals, 50),
                "p95": self._percentile(vals, 95),
                "count": len(vals),
            }
        # include any non-pipeline stages that were recorded (e.g. "classify")
        for stage, vals in snapshot.items():
            if stage not in per_stage:
                all_samples.extend(vals)
                per_stage[stage] = {
                    "p50": self._percentile(vals, 50),
                    "p95": self._percentile(vals, 95),
                    "count": len(vals),
                }

        return {
            "overall": {
                "p50": self._percentile(all_samples, 50),
                "p95": self._percentile(all_samples, 95),
                "count": len(all_samples),
            },
            "per_stage": per_stage,
        }

    def llm_error_rate(self) -> dict[str, Any]:
        with self._lock:
            ok, err = self._llm_ok, self._llm_err
        total = ok + err
        rate = round((err / total) * 100, 2) if total else 0.0
        return {"error_rate": rate, "errors": err, "ok": ok, "total": total}

    def speedup(self) -> dict[str, Any]:
        """
        Sequential-vs-parallel speedup, measured from real batches.

        For each batch we recorded a matched pair:
          • sequential = sum of every item's own processing time (the cost of
            running them one-after-another)
          • parallel   = the concurrent batch's wall-clock time

        We report the median of each across recent batches, so the figures are a
        true apples-to-apples comparison rather than mixing single-call medians
        with multi-item batch timings.

        Returns measured=False with zeroed figures until at least one real batch
        is recorded — we never fabricate a baseline.
        """
        with self._lock:
            runs = list(self._pipeline_runs)

        seq_samples = [s for s, _ in runs]
        par_samples = [p for _, p in runs]
        sequential_ms = self._percentile(seq_samples, 50) if seq_samples else 0.0
        parallel_ms = self._percentile(par_samples, 50) if par_samples else 0.0

        measured = sequential_ms > 0 and parallel_ms > 0

        speedup_x = round(sequential_ms / parallel_ms, 2) if parallel_ms else 0.0
        saved_pct = round((1 - parallel_ms / sequential_ms) * 100, 1) if sequential_ms else 0.0
        return {
            "sequential_ms": round(sequential_ms, 0),
            "parallel_ms": round(parallel_ms, 0),
            "sequential_s": round(sequential_ms / 1000, 1),
            "parallel_s": round(parallel_ms / 1000, 1),
            "speedup_x": speedup_x,
            "time_saved_pct": saved_pct,
            "measured": measured,
            "runs": len(runs),
        }

    def uptime_seconds(self) -> float:
        return round(time.time() - self._started, 0)

    def reset(self) -> None:
        with self._lock:
            self._latencies.clear()
            self._llm_ok = 0
            self._llm_err = 0
            self._pipeline_runs.clear()
            self._started = time.time()


# Process-global singleton.
live_metrics = _LiveMetrics()
