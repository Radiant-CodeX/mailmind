# MailMind — API Reference (production layer)

Base URL: `http://localhost:8000`. Interactive docs: `GET /docs` (Swagger),
`GET /openapi.json`. This reference focuses on the agent, monitoring, and
compliance surfaces added/used by the production architecture.

## Agentic pipeline — `/api/agent`

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/agent/process` | **Full** pipeline (all 6 nodes) synchronously. Returns the complete enriched result. Best for dev/demo/small inboxes. |
| POST | `/api/agent/triage-async` | **Critical path**: ingest + triage sync (≤1.5s), enqueues enrichment. Returns priority immediately + a `result_url`. |
| GET | `/api/agent/result/{email_id}` | Fetch the persisted enriched result. `404` while still enriching / if persistence is off. |
| POST | `/api/agent/stream` | Server-Sent Events of per-node progress. |
| POST | `/api/agent/triage` | Triage-only sub-pipeline (sync, no enqueue). |
| POST | `/api/agent/commitments` | Commitment-extraction sub-pipeline. |
| POST | `/api/agent/batch` | Process up to 20 emails sequentially. |
| POST | `/api/agent/approve/{email_id}` | Human-in-the-loop approval (approve/reject/edit). |
| GET | `/api/agent/health` | Pipeline health (LLM configured, RAG index size). |

### `POST /api/agent/triage-async`

Request:
```json
{ "email_id": "msg-001", "sender": "mgr@corp.com",
  "subject": "Urgent: Q4 report", "body": "Hi Jane, please send the report by tomorrow.",
  "received_at": "2026-06-05T09:00:00Z" }
```
Response (≤ 1.5s):
```json
{ "email_id": "msg-001", "priority": "CRITICAL", "composite_score": 88.0,
  "email_type": "internal_request", "approval_mode": "GATE",
  "axes": [ { "axis": "deadline", "raw_score": 0.9, "confidence": 0.9, "evidence": "...", "explanation": "..." } ],
  "triage_reasoning": "...", "status": "enriching",
  "result_url": "/api/agent/result/msg-001" }
```
Then poll `GET /api/agent/result/msg-001` until `status == "complete"`:
```json
{ "email_id": "msg-001", "priority": "CRITICAL", "composite_score": 88.0,
  "commitments": [ { "commitment": "Send Q4 report", "deadline": "...", "conflict_badge": false } ],
  "conflict_summary": "...", "draft_reply": "Hi Jane, ...", "precedents": [ ... ],
  "status": "complete", "enrichment_source": "agentic" }
```

## Monitoring — root scope

| Method | Path | Purpose |
|---|---|---|
| GET | `/metrics` | Prometheus exposition (counts, histograms, SLA, queue depth). |
| GET | `/health/deep` | Dependency health: queue backend + depth, database, LLM config. |
| GET | `/sla` | Configured SLA targets + live queue depth. |
| GET | `/api/health` | Liveness probe (lightweight). |
| GET | `/api/ready` | Readiness probe. |

Key metrics: `mailmind_emails_processed_total{stage,status}`,
`mailmind_stage_duration_seconds{stage}`, `mailmind_node_duration_seconds{node}`,
`mailmind_llm_calls_total{node,outcome}`, `mailmind_pii_masked_total{category}`,
`mailmind_sla_compliance_total{stage,met}`, `mailmind_queue_depth`.

## Compliance — `/api/compliance`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/compliance/email/{id}/export` | Access / portability (data + audit). |
| DELETE | `/api/compliance/email/{id}` | Erasure (right to be forgotten). |
| GET | `/api/compliance/email/{id}/audit` | Processing audit trail. |
| POST | `/api/compliance/purge?retention_days=N` | Retention purge (data minimisation). |

All compliance endpoints require a configured database (else `503`).

## Status / lifecycle values

- `enrichment.status`: `triaged` → `enriching` → `complete` | `failed`
- `enrichment_source`: `fast_triage` (split path) | `agentic` (full pipeline)
- `priority`: `CRITICAL` (≥75) · `HIGH` (≥50) · `MEDIUM` (≥25) · `LOW`
- `approval_mode`: `GATE` (CRITICAL) · `SUGGEST` (others)
