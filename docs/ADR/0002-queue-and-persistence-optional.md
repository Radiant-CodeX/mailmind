# ADR 0002 — Pluggable queue & optional persistence (one codebase, dev→prod)

- Status: Accepted
- Date: 2026-06-07
- Deciders: MailMind engineering

## Context

We want a system that a judge/engineer can run with `docker compose up` and **no**
external services, yet that is genuinely production-ready (durable queue, results
store) when deployed. Maintaining two codepaths (a "demo" one and a "real" one)
would rot and erode trust in the POC.

## Decision

Abstract both infrastructural concerns behind interfaces selected by environment
variables, with safe fallbacks:

**Queue** (`app/queue/backends.py`) — a `QueueBackend` protocol with two
implementations:
- `InMemoryQueueBackend` (default, `QUEUE_BACKEND=memory`) — thread-safe deque.
- `RedisQueueBackend` (`QUEUE_BACKEND=redis`) — durable LPUSH/RPOP FIFO.
- The factory **falls back to in-memory if Redis is configured but unreachable**,
  logging a clear warning, so a transient Redis outage degrades rather than
  crashes.

**Persistence** (`app/db/`) — SQLAlchemy with a no-DB fallback:
- `DATABASE_URL` empty ⇒ engine is `None`; every repository function is a safe
  no-op returning `None`/`[]`/`False`. Results are still returned inline.
- `DATABASE_URL` set (PostgreSQL/Supabase, or SQLite in tests) ⇒ durable storage,
  no code change.

## Consequences

**Positive**
- One image, zero-dependency dev, env-flip to production. No `if demo:` branches.
- Tests run against SQLite + fakeredis with no infrastructure.
- Resilience: Redis/DB outages degrade gracefully.

**Negative / trade-offs**
- In `memory` queue mode the API and worker must share a process (documented);
  multi-process needs Redis. Acceptable — production uses Redis.
- Repository no-op mode means "successful" writes that persist nothing in dev;
  this is explicit and logged at startup ("persistence disabled").

## Alternatives considered

- **Require Redis/Postgres always.** Higher fidelity but kills the
  zero-dependency dev experience and complicates CI. Rejected.
- **Celery/RQ task framework.** More features (scheduling, result backends) but
  heavier and opinionated; our queue needs are a single durable FIFO. Revisit if
  we need delayed ret[r]y sets or priorities at scale.
