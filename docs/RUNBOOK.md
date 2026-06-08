# MailMind — Operations Runbook

Practical guide for running, deploying, scaling, and troubleshooting MailMind.

## 1. Run locally

### Zero-dependency (dev)
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm                 # for PII name detection
uvicorn app.main:app --reload --port 8000
```
Runs with the in-memory queue and no database. The full pipeline works via
`POST /api/agent/process`. (For the split path with a worker, use Redis — below.)

### With durable infra (Redis + Postgres + worker)
```bash
pip install -r requirements.txt -r requirements-prod.txt
# from repo root:
docker compose -f docker-compose.yml -f docker-compose.scale.yml up -d --build
```
This starts: backend, frontend, a worker, Redis, Postgres, Jaeger, Prometheus.

## 2. Deploy

### Staging / production (Docker Compose)
```bash
# live secrets + durable infra
docker compose -f docker-compose.yml \
               -f docker-compose.prod.yml \
               -f docker-compose.scale.yml up -d --build

# scale the worker tier to match load
docker compose ... up -d --scale worker=4
```

### Managed Postgres (Supabase)
Set `DATABASE_URL` to the Supabase connection string on **both** `backend` and
`worker`, and remove the local `postgres` service. Tables are auto-created on
startup (`init_db`). Enable TLS + encryption at rest in Supabase.

### Required environment
| Var | Purpose |
|---|---|
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_DEPLOYMENT` | LLM |
| `QUEUE_BACKEND=redis`, `REDIS_URL` | durable queue |
| `DATABASE_URL` | persistence (Postgres/Supabase) |
| `APP_ENV=production` | error verbosity, Sentry env |
| `SLA_TRIAGE_SECONDS`, `SLA_ENRICHMENT_SECONDS` | SLA targets |
| `DATA_RETENTION_DAYS` | retention purge window |
| `SENTRY_DSN` (optional) | error tracking |

## 3. Health & monitoring

| Check | Endpoint |
|---|---|
| Liveness | `GET /api/health` |
| Readiness | `GET /api/ready` |
| Deep health (queue/db/llm) | `GET /health/deep` |
| Metrics (Prometheus) | `GET /metrics` |
| SLA config + queue depth | `GET /sla` |

Prometheus scrapes `backend:8000/metrics` (see `infra/prometheus/prometheus.yml`).
Build Grafana panels from the PromQL in [SLA.md](SLA.md).

> **Worker metrics note:** the worker writes per-stage metrics to the
> `processing_metric` table via `record_metric`. Its in-process Prometheus
> counters are not HTTP-scraped (the worker has no HTTP server). To scrape worker
> metrics directly, add `prometheus_client.start_http_server(PORT)` in
> `workers/enrichment.py::main` and a scrape target. Aggregate pipeline metrics
> are already visible via the API's `/metrics`.

## 4. Scaling playbook

| Symptom | Action |
|---|---|
| `mailmind_queue_depth` rising | scale workers: `--scale worker=N` |
| Triage p95 > 1.5s | scale API replicas; check Azure OpenAI latency/limits |
| LLM fallback rate climbing | check Azure OpenAI quota/keys; fallbacks are degraded-but-up |
| DB CPU high | add read replica; ensure indexes (priority, created_at) exist |

Throughput ≈ `worker_replicas / mean_enrichment_seconds`. With ~3.5s enrichment,
10 workers ≈ ~170 emails/min.

## 5. Common incidents

### Redis down
- **Symptom:** logs `Redis queue unavailable … falling back to in-memory queue`.
- **Impact:** enrichment becomes single-process (API-local); throughput drops.
- **Fix:** restore Redis; restart API/workers to repick the Redis backend.

### Database down
- **Symptom:** `/health/deep` shows `database.healthy=false`; compliance endpoints
  return 503; results not persisted.
- **Impact:** `/api/agent/process` still works (inline); `/result/{id}` returns 404.
- **Fix:** restore DB; `init_db` re-runs on restart and recreates tables.

### Enrichment jobs failing
- **Symptom:** `mailmind_emails_processed_total{stage="enrichment",status="error"}`.
- **Triage:** worker logs show the exception; jobs retry with exponential backoff
  up to `WORKER_MAX_RETRIES`, then persist `status="failed"` with the error.
- **Fix:** inspect `email_enrichment.error`; common causes are LLM quota or a bad
  RAG index. Re-enqueue by re-calling `/api/agent/triage-async`.

### Draft contains a `[PERSON_x]`-style token
- Shouldn't happen: `strip_unresolved_tokens` neutralises orphaned tokens. If
  seen, confirm the worker/`/process` restore path calls both `restore_text` and
  `strip_unresolved_tokens` (it does), and check for a new token prefix not in
  `_UNRESOLVED_FALLBACK`.

## 6. Data retention

Schedule the purge (daily) via cron / K8s CronJob / Supabase scheduled function:
```bash
curl -X POST "http://API_HOST/api/compliance/purge"
```

## 7. Tests & CI

```bash
cd backend
python -m pytest tests/test_pii.py tests/test_production.py tests/test_services.py -q
```
- `test_production.py` uses SQLite + fakeredis + stubbed LLM nodes — no infra
  needed. Wire this into CI as the gate.

## 8. Rollback

Images are stateless. Roll back by redeploying the previous tag; the database
schema is additive (no destructive migrations in this layer). Queue jobs in
flight are retried by workers; persisted results are unaffected.
