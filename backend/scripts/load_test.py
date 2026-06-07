"""Lightweight load + smoke test for MailMind.

Fires concurrent requests at the key read endpoints and a webhook validation
ping, then reports throughput, latency percentiles, and error rate. No external
deps (uses the stdlib + httpx which is already a dependency).

Usage (backend running on :8000):
    python scripts/load_test.py --base http://localhost:8000 --requests 200 --concurrency 20
"""
from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

# (method, path, optional json) — read-only + cheap endpoints safe to hammer.
ENDPOINTS = [
    ("GET", "/api/health", None),
    ("GET", "/api/ready", None),
    ("GET", "/api/emails?limit=10", None),
    ("GET", "/api/emails/sent?limit=10", None),
    ("GET", "/api/teams", None),
    ("GET", "/api/webhook?validationToken=ping", None),
]


def _one(base: str, method: str, path: str, body) -> tuple[int, float]:
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, base + path, json=body)
        return resp.status_code, (time.perf_counter() - start) * 1000.0
    except Exception:
        return 0, (time.perf_counter() - start) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()

    jobs = [ENDPOINTS[i % len(ENDPOINTS)] for i in range(args.requests)]
    latencies: list[float] = []
    statuses: list[int] = []

    print(f"Load test → {args.base}  ({args.requests} requests, {args.concurrency} concurrent)")
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(_one, args.base, m, p, b) for (m, p, b) in jobs]
        for fut in as_completed(futures):
            code, ms = fut.result()
            statuses.append(code)
            latencies.append(ms)
    elapsed = time.perf_counter() - started

    ok = sum(1 for s in statuses if 200 <= s < 300)
    errors = len(statuses) - ok
    latencies.sort()

    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    print("\n── Results ──")
    print(f"  Total:        {len(statuses)}")
    print(f"  Success:      {ok}")
    print(f"  Errors:       {errors}")
    print(f"  Throughput:   {len(statuses) / elapsed:.1f} req/s")
    print(f"  Latency mean: {statistics.mean(latencies):.1f} ms")
    print(f"  Latency p50:  {pct(0.50):.1f} ms")
    print(f"  Latency p95:  {pct(0.95):.1f} ms")
    print(f"  Latency p99:  {pct(0.99):.1f} ms")

    if errors:
        print(f"\n FAIL: {errors} request(s) errored.")
        return 1
    print("\n All requests succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
