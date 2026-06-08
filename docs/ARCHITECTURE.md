# MailMind v2 — System Architecture

> Production-grade, PII-safe, agentic email assistant.
> FastAPI · LangGraph · Azure OpenAI (GPT-4o) · Presidio · Redis · PostgreSQL · Prometheus

This document is the canonical reference for how MailMind is designed, why it is
designed that way, and how data flows through it. Read it top-to-bottom for a
full mental model, or jump to a section.

- [1. High-level overview](#1-high-level-overview)
- [2. The split pipeline](#2-the-split-pipeline-critical-path--deferred-enrichment)
- [3. The agentic pipeline (6 nodes)](#3-the-agentic-pipeline-6-nodes)
- [4. PII masking & reversibility](#4-pii-masking--reversibility)
- [5. Components & responsibilities](#5-components--responsibilities)
- [6. Data flow (end to end)](#6-data-flow-end-to-end)
- [7. Graceful degradation](#7-graceful-degradation-dev--prod-on-one-codebase)
- [8. Scaling model](#8-scaling-model)
- [9. Directory map](#9-directory-map)

---

## 1. High-level overview

MailMind ingests an email, understands it with an LLM-driven agent pipeline, and
returns a priority score plus a ready-to-send draft — without ever sending raw
personal data to the LLM.

```
                    ┌──────────────────────────────────────────────────────┐
   Email sources    │                      MailMind                        │
  ┌──────────────┐  │                                                      │
  │ Outlook      │  │   FastAPI API ──┐                                    │
  │ Gmail        │──┼──▶  (gateway)   │  fast triage (<1.5s, sync)         │
  │ IMAP / webhook│ │                 ▼                                    │
  └──────────────┘  │            ┌─────────┐   enqueue   ┌──────────────┐  │
                    │            │ Triage  │────────────▶│  Queue       │  │
                    │            │ (LLM)   │             │ memory/redis │  │
                    │            └─────────┘             └──────┬───────┘  │
                    │                                           │ dequeue   │
                    │                                           ▼           │
                    │                                   ┌───────────────┐   │
                    │                                   │ Enrichment    │   │
                    │                                   │ worker(s)     │   │
                    │                                   │ commit→cal→   │   │
                    │                                   │ rag→draft     │   │
                    │                                   └──────┬────────┘   │
                    │                                          │ persist     │
                    │   ┌──────────┐   ◀── read result ───  ┌──▼─────────┐  │
                    │   │Prometheus│ ◀── /metrics ───────   │ PostgreSQL │  │
                    │   └──────────┘                        │ (Supabase) │  │
                    │                                       └────────────┘  │
                    └──────────────────────────────────────────────────────┘
```

Two ideas define the architecture:

1. **Split pipeline** — a fast synchronous *triage* path (what the user needs
   immediately) and a deferred asynchronous *enrichment* path (the expensive
   work). See §2.
2. **Graceful degradation** — the exact same code runs on a laptop with zero
   external services (in-memory queue, no DB) and in production with Redis +
   PostgreSQL, selected purely by environment variables. See §7.

---

## 2. The split pipeline (critical path + deferred enrichment)

Not all of an email's processing is equally urgent. Triage (priority/score) is
needed *now* to sort the inbox; the draft reply can be ready a few seconds later
while the user reads the message. We split on that boundary:

```
  CRITICAL PATH (synchronous, SLA ≤ 1.5s)        DEFERRED PATH (async, SLA ≤ 10s)
  ───────────────────────────────────────        ────────────────────────────────
  POST /api/agent/triage-async                    enrichment worker
    ├─ ingest   (PII mask)                          ├─ commitment  (LLM)
    └─ triage   (LLM, 5-axis dynamic scoring)       ├─ calendar    (conflict check)
         │                                          ├─ rag         (precedents + draft)
         │  persist "enriching"                     └─ gate        (approval flag)
         │  enqueue job ───────────────▶ QUEUE ──────────┘  │
         ▼                                                  │ persist "complete"
   returns priority immediately                            ▼
                                            client polls GET /api/agent/result/{id}
```

**Why split here (the justification):**

| Property        | Triage                         | Enrichment                          |
|-----------------|--------------------------------|-------------------------------------|
| User urgency    | High (inbox sort/filter)       | Low (read on click)                 |
| Latency budget  | ≤ 1.5s                         | ≤ 10s (background)                  |
| Failure impact  | Blocks inbox → must be sync    | Degrades gracefully → can retry     |
| Cost            | 1 LLM call                     | 2–3 LLM calls (skippable if unread) |

This yields: instant inbox UX, independent failure domains, horizontal worker
scaling, and the option to skip expensive draft generation for emails the user
never opens.

> The original synchronous `POST /api/agent/process` (all six nodes in one call)
> still exists — ideal for development, demos, and small inboxes. The split path
> is the production default for live, high-volume inboxes.

---

## 3. The agentic pipeline (6 nodes)

Orchestrated with **LangGraph** as a typed `StateGraph`. A single
`EmailAgentState` (TypedDict) flows through every node; each node returns a
partial update that LangGraph merges.

```
[START] → ingest → triage → commitment → calendar → rag → gate → [END]
```

| # | Node          | Kind            | What it does                                                            |
|---|---------------|-----------------|------------------------------------------------------------------------|
| 1 | `ingest`      | deterministic   | PII masking → `masked_body` + `mask_mapping`. No LLM ever sees raw PII. |
| 2 | `triage`      | **LLM** dynamic | One JSON call: classifies `email_type`, scores 5 axes with confidence + evidence, assigns dynamic per-axis weights. Composite recomputed in code. Falls back to deterministic scoring. |
| 3 | `commitment`  | **LLM** + regex | Extracts action items + deadlines, gated at 0.80 confidence. Regex fallback. |
| 4 | `calendar`    | deterministic   | Flags commitments that collide with calendar events.                   |
| 5 | `rag`         | **LLM** + vector| Retrieves precedent emails, builds a Tone-DNA few-shot prompt, drafts a reply. |
| 6 | `gate`        | deterministic   | Human-in-the-loop checkpoint; CRITICAL emails require approval.        |

**Dynamic triage** (node 2) is the technical centrepiece — it does *not* keyword
match. It reasons about implied deadlines, stakeholder power, escalation risk,
and required action, then weights the axes per-email (a legal threat weights
`thread_risk` higher; a newsletter weights everything low). The composite score
is always recomputed in code from `raw_score × weight` — the LLM's own number is
never trusted. See `app/agents/nodes.py::triage_node`.

Every LLM node has a **deterministic fallback**, so the pipeline never hard-fails
when the LLM is unavailable — it degrades to rule-based scoring/extraction.

---

## 4. PII masking & reversibility

The privacy guarantee: **no raw personal data is sent to the LLM**, and outputs
are reconstructed afterwards.

```
raw body ──▶ mask_text() ──▶ "[PERSON_1] ... [GOV_ID_1]"  +  mapping{token→value}
                                       │
                              (all LLM processing here)
                                       │
LLM draft "Hi [PERSON_1]" ──▶ restore_text() ──▶ strip_unresolved_tokens() ──▶ "Hi Jane"
```

- **Rubric-driven** (`app/services/pii.py`): mask only data specific enough to
  identify/harm a small set of individuals — `PERSON_NAME, EMAIL, PHONE, ADDRESS,
  FINANCIAL_ID, GOVERNMENT_ID, HEALTH_INFO, SECRET, PERSONAL_OBJECT_ID`. A
  "Golden Rule" filter skips generic demographics, public figures, and vague
  statements.
- **Detection**: regex for hard identifiers (incl. Indian PAN/Aadhaar/GSTIN/IFSC,
  cards via Luhn, API keys/JWT); Presidio + spaCy NLP for names/locations; longest-
  span wins on overlaps.
- **Reversible tokens**: `[PERSON_1]`, value-deduplicated and stably numbered.
- **Robust restore**: tolerant of LLM token reformatting (`[person 1]`,
  `[ PERSON-1 ]`), and **neutralises hallucinated tokens** the LLM may invent
  (e.g. `[PERSON_2]` with no mapping → "there") so nothing broken ever reaches
  the user.
- **Never logged**: only category counts are logged/emitted as metrics, never raw
  values.

---

## 5. Components & responsibilities

| Component | Path | Responsibility |
|---|---|---|
| API / gateway | `app/main.py`, `app/api/` | HTTP surface, routing, middleware |
| Agent pipeline | `app/agents/`, `app/graph/` | LangGraph nodes + assembly |
| Tools | `app/tools/email_tools.py` | Scoring, extraction, RAG, draft tools |
| PII | `app/services/pii.py` | Mask / restore / strip; rubric + Golden Rule |
| **Queue** | `app/queue/backends.py` | `memory`↔`redis` durable work queue |
| **Persistence** | `app/db/` | SQLAlchemy models + repository (optional) |
| **Worker** | `app/workers/enrichment.py` | Deferred enrichment consumer |
| **Monitoring** | `app/monitoring/metrics.py` | Prometheus metrics + SLA |
| **Compliance** | `app/api/compliance_routes.py` | GDPR export/erasure/audit/purge |
| Config | `app/config/settings.py` | Env-driven settings + feature toggles |
| Observability | `app/observability.py` | Structured logging, Sentry, error handlers |
| Security | `app/middleware.py` | Security headers, global rate limiting |

(**Bold** = added in the production layer.)

---

## 6. Data flow (end to end)

```
1. Email arrives  →  POST /api/agent/triage-async
2. ingest_node     →  mask PII; record pii_masked metric; mapping kept in state
3. triage_node     →  GPT-4o dynamic 5-axis JSON; composite recomputed in code
4. persist          →  upsert_enrichment(status="enriching"); audit "triaged"
5. enqueue          →  {email_id, state} pushed to queue; queue_depth gauge set
6. RESPOND          →  priority + score returned to client  (≤ 1.5s, SLA tracked)
   ───────────────────────────────────────────────────────────────────────────
7. worker dequeues  →  commitment → calendar → rag → gate  (track_stage enrichment)
8. restore PII      →  restore_text + strip_unresolved_tokens on draft/reasoning
9. persist          →  upsert_enrichment(status="complete"); audit "enriched"
10. client polls    →  GET /api/agent/result/{id} → full enriched record
```

Observability taps: steps 2 (`pii_masked`), 3 (`llm_calls`), 6 (`stage=triage`
latency + SLA), 7 (`stage=enrichment` latency + SLA), 5/worker (`queue_depth`).

---

## 7. Graceful degradation (dev ↔ prod on one codebase)

Every production dependency is **optional** and selected by environment:

| Concern | Dev default | Production | Mechanism |
|---|---|---|---|
| Queue | `memory` (in-process) | `redis` | `QUEUE_BACKEND`; auto-falls back to memory if Redis is down |
| Persistence | disabled (inline only) | PostgreSQL/Supabase | `DATABASE_URL` empty ⇒ repository calls are no-ops |
| Metrics | on (in-process registry) | scraped by Prometheus | `METRICS_ENABLED` |
| LLM | fallback scoring if no key | Azure GPT-4o | credentials present ⇒ LLM path |

Consequence: `git clone && docker compose up` works with **zero** external
services, and the *same* image scales to production by setting env vars — no code
branches. This is what makes the system both easy to run and genuinely
production-ready.

---

## 8. Scaling model

```
            ┌─────────────┐
  clients ─▶│ API (1..N)  │  stateless → scale behind a load balancer
            └──────┬──────┘
                   │ enqueue
            ┌──────▼──────┐
            │   Redis     │  single logical queue, durable (AOF)
            └──────┬──────┘
                   │ dequeue (competing consumers)
       ┌───────────┼───────────┐
   ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
   │worker1│   │worker2│   │worker3│   stateless → scale to match queue depth
   └───┬───┘   └───┬───┘   └───┬───┘
       └───────────┼───────────┘
            ┌──────▼──────┐
            │ PostgreSQL  │  results + audit + metrics
            └─────────────┘
```

- **API tier** and **worker tier** are independently scalable and stateless.
- **Throughput** ≈ `worker_replicas × (1 / mean_enrichment_seconds)`.
- **Backpressure** is observable via `mailmind_queue_depth`; autoscale workers on
  it. See [RUNBOOK.md](RUNBOOK.md).

---

## 9. Directory map

```
backend/app/
├── main.py                 # app assembly, middleware, router wiring, lifespan
├── config/settings.py      # env-driven settings (queue, db, SLA, retention…)
├── api/
│   ├── agent_routes.py     # /process, /stream, /triage, /triage-async, /result, /batch, /approve
│   ├── monitoring_routes.py# /metrics, /health/deep, /sla
│   ├── compliance_routes.py# GDPR export / erase / audit / purge
│   └── routes.py           # core API (emails, auth, webhook, health/ready…)
├── agents/nodes.py         # 6 LangGraph nodes (ingest…gate)
├── graph/
│   ├── pipeline.py         # StateGraph assembly + run_pipeline
│   └── state.py            # EmailAgentState TypedDict
├── tools/email_tools.py    # scoring / extraction / RAG / draft tools
├── services/pii.py         # PII mask / restore / strip (+ Golden Rule, Indian IDs)
├── queue/
│   ├── queue.py            # legacy in-memory EmailQueue (webhook ingest)
│   └── backends.py         # QueueBackend protocol + memory/redis + factory
├── db/
│   ├── base.py             # engine/session + graceful no-DB fallback
│   ├── models.py           # EmailEnrichment, AuditLog, ProcessingMetric
│   └── repository.py       # all DB reads/writes (no-op without a DB)
├── workers/enrichment.py   # deferred-enrichment consumer
├── monitoring/metrics.py   # Prometheus metrics + SLA instrumentation
├── observability.py        # logging, Sentry, exception handlers
└── middleware.py           # security headers + rate limiting

backend/tests/
├── test_pii.py             # masking rubric, Indian IDs, restore, no-PII-logging
├── test_production.py      # queue, repository, metrics/SLA, worker
└── test_services.py        # scorers, classification, draft, graph
```

See also: [RUNBOOK.md](RUNBOOK.md) · [SLA.md](SLA.md) · [COMPLIANCE.md](COMPLIANCE.md) · [API.md](API.md) · [ADR/](ADR/)
