# MailMind — Compliance & Data Governance

MailMind processes personal data and is designed for GDPR / India DPDP-aligned
operation. This document describes the data we handle, the controls in place, and
the data-subject rights we support.

## 1. Data inventory

| Data | Where | Retention | Notes |
|---|---|---|---|
| Raw email body | transient (request memory only) | not persisted | masked at ingest; never stored raw, never sent raw to the LLM |
| Masked body (`[PERSON_1]…`) | `email_enrichment.masked_body` | `DATA_RETENTION_DAYS` (default 90) | no raw PII |
| Mask mapping (token→value) | request state only | request lifetime | **never persisted, never logged** |
| Triage/commitments/draft (restored) | `email_enrichment` | `DATA_RETENTION_DAYS` | business output the user sees |
| Audit trail | `audit_log` | `DATA_RETENTION_DAYS` | categories/counts only, **no raw PII** |
| Processing metrics | `processing_metric` | `DATA_RETENTION_DAYS` | latency/SLA only |

## 2. Privacy controls (how they're enforced)

| Principle | Control | Code |
|---|---|---|
| **Data minimisation** | Raw body never persisted; retention purge | `pii.py`, `repository.purge_expired` |
| **Purpose limitation** | PII masked before any LLM call | `nodes.ingest_node` → `pii.mask_text` |
| **No PII in logs** | Only category counts logged/emitted | `pii.py` (logs counts), `metrics.record_pii_masked` |
| **No PII in audit** | `details` carries counts/metadata only | `repository.write_audit` |
| **Confidentiality of mapping** | Mapping lives in request state only | `EmailAgentState.mask_mapping` |
| **Integrity** | Hallucinated tokens neutralised, not leaked | `pii.strip_unresolved_tokens` |

**PII categories masked**: PERSON_NAME, EMAIL, PHONE, ADDRESS, FINANCIAL_ID
(cards/SSN/IBAN/IFSC/bank acct), GOVERNMENT_ID (PAN/Aadhaar/GSTIN/passport/DL),
HEALTH_INFO, SECRET (API keys/JWT/passwords), PERSONAL_OBJECT_ID (IMEI/vehicle/
serial). Verified by `tests/test_pii.py`.

## 3. Data-subject rights (GDPR Arts. 15–17, 20)

All exposed under `/api/compliance` (require a configured database; otherwise 503):

| Right | Endpoint | Behaviour |
|---|---|---|
| Access / Portability (Art. 15, 20) | `GET /api/compliance/email/{id}/export` | Returns all stored data + audit trail; logs an `exported` audit event |
| Erasure / "right to be forgotten" (Art. 17) | `DELETE /api/compliance/email/{id}` | Hard-deletes the record; the deletion is itself audited |
| Processing transparency | `GET /api/compliance/email/{id}/audit` | Returns the email's processing audit trail |
| Data minimisation (Art. 5) | `POST /api/compliance/purge` | Deletes records older than the retention window |

### Examples

```bash
# Export everything stored for an email (access / portability)
curl http://localhost:8000/api/compliance/email/EMAIL_ID/export

# Erase an email's data (right to be forgotten)
curl -X DELETE http://localhost:8000/api/compliance/email/EMAIL_ID

# Run retention purge (data minimisation) — typically scheduled
curl -X POST "http://localhost:8000/api/compliance/purge?retention_days=90"
```

## 4. Retention & deletion

- Default retention: **90 days** (`DATA_RETENTION_DAYS`).
- `POST /api/compliance/purge` deletes `email_enrichment` rows older than the
  window and writes a `retention_purge` audit entry with the deleted count.
- Schedule it daily (cron / Kubernetes CronJob / Supabase scheduled function).

## 5. Sub-processors & data residency

- **Azure OpenAI (GPT-4o)** — receives only *masked* text. Choose a region-pinned
  Azure OpenAI resource for data-residency requirements; Azure OpenAI does not
  use API data to train models.
- **PostgreSQL / Supabase** — stores masked bodies + restored business output;
  pin the project region as required. Enable encryption at rest + TLS in transit.
- **Redis** — transient job payloads (masked state). Use TLS + auth in production;
  payloads are short-lived (deleted on dequeue).

## 6. Security posture (supporting controls)

- Security headers + HSTS on TLS (`app/middleware.py`).
- Global + per-endpoint rate limiting.
- Secrets via environment / Azure Key Vault (`app/config/keyvault.py`), never
  committed.
- Structured error handling that never echoes raw PII (`app/observability.py`).

## 7. Compliance test evidence

| Claim | Test |
|---|---|
| No raw PII reaches logs | `tests/test_pii.py::test_no_raw_pii_logged` |
| Audit stores counts, not values | `tests/test_production.py::test_audit_never_stores_raw_values` |
| Erasure deletes + audits | `tests/test_production.py::test_repository_delete_and_audit` |
| Restore is exact & reversible | `tests/test_pii.py::test_restore_text_returns_original` |
| Hallucinated tokens neutralised | `tests/test_production.py::test_strip_unresolved_tokens_neutralises_orphans` |
