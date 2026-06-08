# MailMind Documentation

Production-grade, PII-safe, agentic email assistant.

## Start here

| Doc | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, the split pipeline, the 6 agent nodes, PII flow, components, scaling, directory map |
| [API.md](API.md) | Endpoint reference (agent / monitoring / compliance) with examples |
| [RUNBOOK.md](RUNBOOK.md) | Run locally, deploy, scale, monitor, troubleshoot |
| [SLA.md](SLA.md) | Service level objectives, how each is measured, PromQL, alerts |
| [COMPLIANCE.md](COMPLIANCE.md) | GDPR/DPDP rights, data inventory, privacy controls, test evidence |

## Architecture Decision Records

| ADR | Decision |
|---|---|
| [0001](ADR/0001-split-pipeline.md) | Split into synchronous triage + asynchronous enrichment |
| [0002](ADR/0002-queue-and-persistence-optional.md) | Pluggable queue & optional persistence (one codebase, dev→prod) |
| [0003](ADR/0003-pii-reversible-masking.md) | Reversible PII masking with hallucinated-token neutralisation |

## The 60-second mental model

```
POST /api/agent/triage-async
  ingest (mask PII) → triage (GPT-4o, dynamic 5-axis) ──┐ returns priority ≤1.5s
                                                        │ enqueue
                                                  ┌─────▼─────┐
                                                  │   queue   │  memory ↔ redis
                                                  └─────┬─────┘
                                                        │ worker dequeues
              commitment → calendar → rag → draft → gate → restore PII → persist
                                                        │
GET /api/agent/result/{id}  ◀───────────────────────────┘
```

- **Masking before the LLM, restore after** — raw PII never leaves the box.
- **Dynamic triage** — the LLM weighs axes per-email; the score is recomputed in
  code, never blindly trusted.
- **Graceful degradation** — same code runs with zero deps (in-memory, no DB) or
  full production (Redis + Postgres + Prometheus), chosen by env vars.
- **Observable & compliant** — `/metrics`, SLA tracking, audit log, GDPR endpoints.

## Quick links

- Run it: [RUNBOOK §1](RUNBOOK.md#1-run-locally)
- Metrics & SLOs: [SLA.md](SLA.md)
- Cost & deployment options: [../DEPLOYMENT_AND_COSTS.md](../DEPLOYMENT_AND_COSTS.md)
