# MailMind — Service Level Objectives & Agreements

This document defines the service levels MailMind targets, how they are measured,
and how they are enforced/observed in code.

## 1. Service Level Objectives (SLOs)

| # | Objective | Target | Window |
|---|---|---|---|
| SLO-1 | **Triage latency** (critical path) | p95 ≤ **1.5s** | rolling 30 days |
| SLO-2 | **Enrichment latency** (deferred) | p95 ≤ **10s** | rolling 30 days |
| SLO-3 | **Triage availability** | ≥ **99.9%** | monthly |
| SLO-4 | **Enrichment success rate** (incl. retries) | ≥ **99.5%** | monthly |
| SLO-5 | **Data durability** (persisted results) | ≥ **99.99%** | yearly |
| SLO-6 | **PII leak rate** (raw PII in LLM input or logs) | **0** | always |

Targets are configurable via env: `SLA_TRIAGE_SECONDS`, `SLA_ENRICHMENT_SECONDS`.

## 2. How each SLO is measured

All processing is wrapped in `app/monitoring/metrics.py::track_stage`, which on
every request records latency, success/failure, and whether the stage met its
SLA target. Exposed at `GET /metrics` (Prometheus) and persisted per-email in the
`processing_metric` table.

| SLO | Metric / source |
|---|---|
| SLO-1/2 | `mailmind_stage_duration_seconds{stage}` histogram → compute p95 in Grafana |
| SLO-1/2 | `mailmind_sla_compliance_total{stage,met}` → `met="true" / total` = SLA % |
| SLO-3 | API uptime via `/api/health` + `mailmind_emails_processed_total{stage="triage"}` error ratio |
| SLO-4 | `mailmind_emails_processed_total{stage="enrichment",status}` success/total |
| SLO-5 | PostgreSQL backup/replication health (infra), `email_enrichment` row counts |
| SLO-6 | `mailmind_pii_masked_total` coverage; `tests/test_pii.py::test_no_raw_pii_logged`; design guarantee (mask before LLM) |

### Example PromQL

```promql
# Triage SLA compliance (last 5m)
sum(rate(mailmind_sla_compliance_total{stage="triage",met="true"}[5m]))
  / sum(rate(mailmind_sla_compliance_total{stage="triage"}[5m]))

# Triage p95 latency
histogram_quantile(0.95, sum(rate(mailmind_stage_duration_seconds_bucket{stage="triage"}[5m])) by (le))

# Enrichment error rate
sum(rate(mailmind_emails_processed_total{stage="enrichment",status="error"}[5m]))
  / sum(rate(mailmind_emails_processed_total{stage="enrichment"}[5m]))

# LLM fallback rate (degraded quality signal)
sum(rate(mailmind_llm_calls_total{outcome="fallback"}[5m]))
  / sum(rate(mailmind_llm_calls_total[5m]))
```

## 3. Error budgets

| SLO | Budget (monthly) |
|---|---|
| Triage availability 99.9% | ~43m downtime |
| Enrichment success 99.5% | 0.5% of emails may exhaust retries |

When an error budget is being burned (e.g. enrichment success < 99.5% over 1h),
page on-call. See [RUNBOOK.md](RUNBOOK.md) §Alerts.

## 4. Degradation policy (graceful, not failing)

MailMind prefers **degraded service over outage**:

- LLM unavailable → deterministic scoring/extraction fallback (lower quality, not
  an error). Tracked as `llm_calls_total{outcome="fallback"}`.
- Redis unreachable → in-memory queue fallback (single-process, not an outage).
- DB unavailable → results returned inline; persistence/compliance features
  return 503 explicitly.

## 5. Alerting thresholds (recommended)

| Alert | Condition | Severity |
|---|---|---|
| Triage SLA breach | SLA% < 95% for 10m | warning |
| Enrichment backlog | `mailmind_queue_depth` > 1000 for 15m | warning |
| Enrichment failures | error rate > 1% for 10m | critical |
| LLM degraded | fallback rate > 20% for 15m | warning |
| API down | `/api/health` failing 3× | critical |
