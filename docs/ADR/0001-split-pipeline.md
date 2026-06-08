# ADR 0001 — Split the pipeline into synchronous triage + asynchronous enrichment

- Status: Accepted
- Date: 2026-06-07
- Deciders: MailMind engineering

## Context

The full agent pipeline (ingest → triage → commitment → calendar → rag → gate)
takes ~3–4s end-to-end, dominated by 3 GPT-4o calls. Running all of it
synchronously per email means:

- the inbox can't render a priority until the (expensive) draft is also done;
- a slow/failed draft step blocks the user-facing response;
- we pay for draft generation even for emails the user never opens;
- horizontal scaling is coarse (one knob for everything).

But triage (priority/score) *is* needed synchronously — it drives inbox sort,
filter, and notifications.

## Decision

Split processing at the triage boundary:

- **Critical path (sync, SLA ≤ 1.5s):** `ingest` + `triage`. Returns priority
  immediately, persists a `enriching` record, and enqueues the rest.
- **Deferred path (async, SLA ≤ 10s):** a worker runs `commitment → calendar →
  rag → gate`, restores PII, and persists the `complete` record. Clients poll
  `GET /api/agent/result/{id}`.

The original single-call `POST /api/agent/process` is retained for dev/demo and
small inboxes.

## Consequences

**Positive**

- Instant inbox UX; draft appears while the user reads.
- Independent failure domains — a draft failure never breaks triage.
- Independent, queue-depth-driven scaling of the worker tier.
- Cost control — drafts can be skipped/deprioritised for unopened mail.

**Negative / trade-offs**

- Introduces a queue + result store (operational surface). Mitigated by the
  graceful-degradation design (memory queue, no-DB mode) for dev.
- Eventual consistency: the draft isn't in the first response; clients poll.

## Alternatives considered

- **Keep it fully synchronous.** Simplest, but violates the inbox latency SLA and
  couples failure domains. Rejected for production (kept as `/process`).
- **Split every node into its own queue stage.** Maximal parallelism but large
  operational complexity and shared-state (PII mapping) hops for little gain —
  enrichment nodes don't overlap enough to justify it. Rejected (see ADR 0001
  discussion in ARCHITECTURE §2).
