# MailMind — Complete Technical Reference

> AI-powered email triage for the Agentif AI Buildathon by Capgemini.  
> FastAPI · LangGraph · Azure OpenAI (GPT-4o) · DOMPurify · Redis · PostgreSQL (Supabase) · Prometheus

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [The Agentic Pipeline (6 Nodes)](#3-the-agentic-pipeline-6-nodes)
4. [PII Masking & Privacy](#4-pii-masking--privacy)
5. [Split Pipeline Design](#5-split-pipeline-design)
6. [Email Providers](#6-email-providers)
7. [Frontend Architecture](#7-frontend-architecture)
8. [API Reference](#8-api-reference)
9. [Running Locally](#9-running-locally)
10. [Deployment](#10-deployment)
11. [Monitoring & Observability](#11-monitoring--observability)
12. [Innovation Stories — Challenges & Solutions](#12-innovation-stories--challenges--solutions)
13. [Directory Map](#13-directory-map)

---

## 1. Project Overview

MailMind is an AI co-pilot for enterprise email that:

- **Triages** every email with a 5-axis urgency score (deadline, authority, sentiment, thread risk, action required)
- **Extracts** commitments and detects calendar conflicts automatically
- **Drafts** replies matching the user's Tone DNA (learned from sent email history via RAG)
- **Protects privacy** — no raw PII is ever sent to the LLM
- Supports both **Microsoft Outlook** (Graph API) and **Gmail** (Google API)

---

## 2. Architecture

```
                    ┌──────────────────────────────────────────────────────┐
   Email sources    │                      MailMind                        │
  ┌──────────────┐  │                                                      │
  │ Outlook      │  │   FastAPI API ──┐                                    │
  │ Gmail        │──┼──▶  (gateway)   │  fast triage (<1.5s, sync)         │
  └──────────────┘  │                 ▼                                    │
                    │            ┌─────────┐   enqueue   ┌──────────────┐  │
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

Two core principles:

1. **Split pipeline** — fast synchronous triage (what the user needs now) + deferred asynchronous enrichment (the expensive work). See §5.
2. **Graceful degradation** — same code runs on a laptop with zero external services and in production with Redis + PostgreSQL, controlled purely by env vars. See §5.

---

## 3. The Agentic Pipeline (6 Nodes)

Orchestrated with **LangGraph** as a typed `StateGraph`. A single `EmailAgentState` flows through every node; each node returns a partial update merged into shared state.

```
[START] → ingest → triage → commitment → calendar → rag → gate → [END]
```

| # | Node | Kind | What it does |
|---|------|------|-------------|
| 1 | `ingest` | deterministic | PII masking → `masked_body` + `mask_mapping`. No LLM ever sees raw PII. |
| 2 | `triage` | **LLM** | One JSON call: classifies `email_type`, scores 5 axes with confidence + evidence, assigns dynamic per-axis weights. Composite recomputed in code — LLM's number never trusted. |
| 3 | `commitment` | **LLM** + regex | Extracts action items + deadlines, gated at 0.80 confidence. Regex fallback. |
| 4 | `calendar` | deterministic | Flags commitments that collide with calendar events. |
| 5 | `rag` | **LLM** + vector | Retrieves precedent emails, builds a Tone-DNA few-shot prompt, drafts a reply. |
| 6 | `gate` | deterministic | Human-in-the-loop checkpoint; CRITICAL emails require approval. |

### Triage Axes

| Axis | Measures |
|------|---------|
| `deadline` | Time pressure from any explicit or implied due date |
| `authority` | Stakeholder power of sender / referenced people |
| `sentiment` | Emotional urgency, frustration, or escalation |
| `thread_risk` | Business/relationship risk if ignored or delayed |
| `action` | How strongly a direct response or action is required |

Dynamic per-email weights are assigned by the LLM (a legal threat weights `thread_risk` higher; a newsletter weights everything low). Composite score is recomputed as `Σ raw_score × weight × 100` in code — never from the LLM's own number.

**Score thresholds:** CRITICAL ≥75 · HIGH ≥50 · MEDIUM ≥25 · LOW <25

Every LLM node has a **deterministic fallback**, so the pipeline never hard-fails when the LLM is unavailable.

---

## 4. PII Masking & Privacy

The privacy guarantee: **no raw personal data is sent to the LLM**.

```
raw body ──▶ mask_text() ──▶ "[PERSON_1] ... [GOV_ID_1]"  +  mapping{token→value}
                                       │
                              (all LLM processing here)
                                       │
LLM draft "Hi [PERSON_1]" ──▶ restore_text() ──▶ strip_unresolved_tokens() ──▶ "Hi Jane"
```

**What gets masked:** `PERSON_NAME, EMAIL, PHONE, ADDRESS, FINANCIAL_ID, GOVERNMENT_ID, HEALTH_INFO, SECRET, PERSONAL_OBJECT_ID`

**Indian-specific identifiers:** PAN, Aadhaar, GSTIN, IFSC, VPA (UPI), Passport

**Detection stack:** regex for hard identifiers + Presidio + spaCy NLP for names/locations; longest-span wins on overlaps.

**Robust restore:** tolerant of LLM token reformatting (`[person 1]`, `[ PERSON-1 ]`), and neutralises hallucinated tokens the LLM may invent so nothing broken ever reaches the user.

**Never logged:** only category counts are emitted as metrics, never raw values.

---

## 5. Split Pipeline Design

```
  CRITICAL PATH (sync, SLA ≤ 1.5s)          DEFERRED PATH (async, SLA ≤ 10s)
  ─────────────────────────────────          ─────────────────────────────────
  POST /api/agent/triage-async                enrichment worker
    ├─ ingest   (PII mask)                      ├─ commitment  (LLM)
    └─ triage   (LLM, 5-axis)                   ├─ calendar    (conflict check)
         │                                      ├─ rag         (precedents + draft)
         │  persist "enriching"                 └─ gate        (approval flag)
         │  enqueue job ───────────▶ QUEUE ─────────┘
         ▼                                    persist "complete"
   returns priority immediately        client polls GET /api/agent/result/{id}
```

**Why this split matters:**

| Property | Triage | Enrichment |
|----------|--------|------------|
| User urgency | High (inbox sort) | Low (read on click) |
| Latency budget | ≤ 1.5s | ≤ 10s (background) |
| Failure impact | Blocks inbox → must be sync | Degrades gracefully → can retry |

**Three-level triage cache:** Redis → PostgreSQL DB → LangGraph LLM. Once an email is triaged, it is never re-scored — the result is served from cache instantly on every subsequent load.

**Graceful degradation:**

| Concern | Dev default | Production | Mechanism |
|---------|-------------|------------|-----------|
| Queue | memory (in-process) | Redis | `QUEUE_BACKEND` env var |
| Persistence | disabled (inline) | PostgreSQL/Supabase | `DATABASE_URL` empty → no-ops |
| LLM | deterministic fallback | Azure GPT-4o | credentials present → LLM path |

---

## 6. Email Providers

Both providers share the same interface (`get_mail_client()` in `mail_provider.py` routes by `active_provider`).

### Microsoft Outlook (Graph API)

- Auth: MSAL OAuth 2.0 auth-code flow with `offline_access` scope
- **Refresh token:** persisted to `data/msal_cache.bin` — session survives indefinitely; access token proactively refreshed 5 minutes before expiry
- Pagination: `$skip`-based with `$count=true`
- HTML emails: `body.contentType == "html"` served as `html_body`; plain text derived via `_graph_html_to_text()`
- Attachments: `GET /messages/{id}/attachments` → streamed via `/api/emails/{id}/attachments/{attId}`

### Gmail (Google API)

- Auth: OAuth 2.0 auth-code flow; tokens persisted to `data/google_token.json`
- Pagination: opaque cursor (`nextPageToken`) — **not** numeric skip
- HTML emails: MIME multipart walk; `text/html` part served as `html_body`; `_html_to_text()` strips `<style>`/`<script>` blocks entirely before tag removal
- Attachments: `GET /messages/{id}/attachments/{attId}` (base64url) → streamed via same endpoint
- **Note:** App must be added to Google OAuth test users or go through verification for accounts outside the developer's Google Cloud project

### Email body strategy

| Field | Used for | How |
|-------|---------|-----|
| `html_body` | Frontend display | Rendered via DOMPurify + sandboxed iframe |
| `body` | Agent/LLM processing | Clean plain text (style/script stripped) |

---

## 7. Frontend Architecture

### Two-phase inbox loading

```
Phase 1 — INSTANT (0ms):
  inbox batch pre-scored every email with /api/agent/triage
  → read email.triage directly, no network call

Phase 2 — BACKGROUND (~5-8s):
  call /api/agent/enrich → commitment + rag IN PARALLEL
  → commitment_node ‖ rag_node (ThreadPoolExecutor, max_workers=2)
```

### Pagination strategy

- **10 emails per page** fetched directly from Graph/Gmail
- **Cursor-based:** stores actual `next_page_token` from API response (Gmail requires opaque cursor, not numeric offset)
- **Cache-first:** `EMAIL_CACHE_VERSION = 'v3'`; TTL 5 minutes; on reload shows cache instantly, skips API call
- **New email detection:** polls `GET /api/inbox/poll` (1 tiny request) every 60s; on change, fetches only 1 new email and prepends — no full re-fetch

### User-scoped storage

All localStorage is namespaced by `mm_{simpleHash(userEmail)}_` to prevent cross-account leaks. Cache is cleared on logout.

### Key components

| Component | Path | Role |
|-----------|------|------|
| `EmailBodyHtml` | `detail/EmailDetail.tsx` | DOMPurify sanitized HTML in sandboxed iframe |
| `AttachmentList` | `detail/EmailDetail.tsx` | Downloadable attachments with file icons + sizes |
| `CalendarView` | `calendar/CalendarView.tsx` | Month/Week/Agenda views; create event modal |
| `TriageExplainer` | `triage/TriageExplainer.tsx` | 5-axis score visualization |
| `CommitmentGate` | `commitments/CommitmentGate.tsx` | Human-in-the-loop approval |
| `useEmails` | `hooks/useEmails.ts` | Pagination, cache, triage, SSE poll |
| `useEmailDetail` | `hooks/useEmailDetail.ts` | Two-phase loading, draft generation |

---

## 8. API Reference

### Agent pipeline

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/agent/triage` | POST | Single email triage — Redis → DB → LLM (3-level cache) |
| `/api/agent/triage-page` | POST | Batch triage for up to 10 emails; cache hits return instantly |
| `/api/agent/triage-async` | POST | Fast triage + enqueue enrichment; returns priority immediately |
| `/api/agent/enrich` | POST | Commitment + RAG in parallel (skips triage) |
| `/api/agent/process` | POST | Full 6-node pipeline (dev / demo) |
| `/api/agent/result/{id}` | GET | Poll enrichment result |

### Inbox

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/mailbox` | GET | Paginated folder listing |
| `/api/inbox/poll` | GET | Lightweight new-email check (id + received_at only) |
| `/api/emails/{id}/attachments/{attId}` | GET | Stream attachment for download |

### Calendar & Tasks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/calendar` | GET | Fetch events (Graph or Google Calendar) |
| `/api/calendar/event` | POST | Create calendar event |
| `/api/tasks` | GET | List tasks (Microsoft To Do or Google Tasks) |
| `/api/tasks` | POST | Create task |

### Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health/deep` | GET | DB + Redis + Azure OpenAI + queue health |
| `/api/metrics` | GET | Prometheus metrics |
| `/api/sla` | GET | SLA compliance report |

### Compliance (GDPR)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/compliance/export/{id}` | GET | Export all data for an email |
| `/api/compliance/erase/{id}` | DELETE | Hard-delete email data (right to erasure) |
| `/api/compliance/audit` | GET | Audit log entries |
| `/api/compliance/purge` | POST | Purge data older than retention policy |

---

## 9. Running Locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Copy and fill in credentials
cp .env.local.example .env

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Required `.env` keys:**

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://<resource>.cognitiveservices.azure.com/...
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_CHAT_DEPLOYMENT=mailmind-gpt

# Microsoft Graph OAuth
AZURE_TENANT_ID=common
AZURE_CLIENT_ID=<app_id>
AZURE_CLIENT_SECRET=<secret>

# Google OAuth
GOOGLE_CLIENT_ID=<id>
GOOGLE_CLIENT_SECRET=<secret>

# Database (optional — app works without it)
DATABASE_URL=postgresql://...

# Auth
APPROVAL_TOKEN=<random_string>
FRONTEND_ORIGIN=http://localhost:3000
```

### Frontend

```bash
cd frontend
npm install
# Create .env.local:
# NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
# NEXT_PUBLIC_APPROVAL_TOKEN=<same as backend APPROVAL_TOKEN>
npm run dev
```

---

## 10. Deployment

### Azure Container Instances (recommended)

```bash
# Build backend image
docker build -t mailmind-backend ./backend
az acr push mailmind-backend

# Set all secrets in Azure Key Vault
bash scripts/setup-keyvault.sh

# Deploy
az container create \
  --resource-group mailmind-rg \
  --name mailmind-api \
  --image mailmind-backend \
  --environment-variables QUEUE_BACKEND=redis DATABASE_URL=...
```

### Supabase (PostgreSQL)

Connection: `postgresql://postgres.<project>:<pass>@aws-1-ap-south-1.pooler.supabase.com:5432/postgres`

Use the **pooler URL** (not `db.xxx.supabase.co`) to avoid IPv6 DNS resolution issues.

Tables auto-created on startup: `email_enrichment`, `audit_log`, `processing_metric`.

---

## 11. Monitoring & Observability

### Prometheus metrics

```
mailmind_emails_processed_total{stage,status}   — Count by stage & outcome
mailmind_stage_duration_seconds{stage}           — Latency histogram per stage
mailmind_node_duration_seconds{node}             — Individual node timing
mailmind_sla_compliance_total{stage,met}         — SLA success rate
mailmind_llm_calls_total{node,outcome}           — LLM usage & fallback rate
mailmind_pii_masked_total{category}              — Privacy coverage
mailmind_queue_depth                             — Pending jobs
```

### Health check

```bash
curl http://localhost:8000/api/health/deep | jq .
```

### LangSmith tracing

Set `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` + `LANGSMITH_PROJECT=mailmind` in `.env`. All LangGraph pipeline runs appear in the LangSmith dashboard with per-node timing and token counts.

---

## 12. Innovation Stories — Challenges & Solutions

This section documents the real technical complications encountered during the buildathon and how they were solved. These are not hypothetical — each represents hours of debugging in a time-constrained environment.

---

### 12.1 The Triage Agent Was a Separate Pipeline

**Problem:**  
The original architecture had triage running as a completely separate pipeline from the enrichment nodes (commitment, calendar, RAG). This meant LangSmith traces stopped showing up after 10:45 AM for an entire morning — we couldn't understand why the inbox was fast but the pipeline looked broken.

**Root cause:**  
`triageEmail()` in the frontend was calling `/api/triage` (a deterministic, non-LangGraph route) while `/api/agent/triage` was the real LangGraph path. No LangSmith traces appeared because we were calling the wrong endpoint.

**Solution:**  
Unified the pipeline — triage feeds directly into the enrichment state so triage scores are passed to enrichment without re-running. Frontend now calls `/api/agent/triage` exclusively. A two-phase approach was introduced: Phase 1 shows triage instantly (0ms, from cached result), Phase 2 runs commitment + RAG in parallel in background.

**What we learned:**  
The split between "fast" and "correct" APIs was invisible. We now use a single agent endpoint with a 3-level cache (Redis → DB → LLM) so the same path handles both.

---

### 12.2 Gmail Pagination Was Silently Broken

**Problem:**  
After implementing 10-emails-per-page pagination, clicking "Next" showed the counter changing to "11-20" but the *same 10 emails* appeared. The backend logs confirmed emails 11-20 were being fetched and returned 200 OK.

**Root cause:**  
The frontend was computing the pagination cursor as `String(fetchOffset)` — a numeric string like `"10"`. Microsoft Graph uses `$skip=10` so this worked. Gmail API uses **opaque cursor tokens** like `"AqBCdef..."` — passing `"10"` as a `pageToken` caused Gmail to ignore it entirely and return page 1 again. The counter updated (state worked), but the email list didn't (wrong data).

**Solution:**  
Introduced `nextPageTokenRef` that stores the actual `next_page_token` from the API response. For Gmail this is the opaque cursor; for Graph it's the numeric skip string. `nextPage()` now reads from this ref exclusively — never computes an offset.

**What we learned:**  
Two providers with superficially identical response shapes can have fundamentally incompatible pagination models. Provider-agnostic abstraction must go below the response structure level.

---

### 12.3 React useEffect Cascade Resetting Pagination

**Problem:**  
After fixing the Gmail cursor, the next 10 emails would appear briefly but then snap back to the first 10. The "11-20 of 201" counter would show, then reset to "1-10" within seconds.

**Root cause:**  
`triageSlice` depended on `[activeFolder, pageIndex, setEmails]`. When `pageIndex` changed during `nextPage()`, `triageSlice` got a new function reference. `loadEmails` had `triageSlice` in its deps, so it also re-created. Two `useEffect`s were both watching `loadEmails` — one for folder change, one for initial load — and both fired, calling `loadEmails()` which reset `pageIndex` to 0 and called `setEmails(page1emails)`.

**Solution:**  
- Made `triageSlice` and `loadEmails` have **zero deps** (`useCallback(async () => {...}, [])`) — they read all mutable values from refs (`activeFolderRef`, `pageIndexRef`, `allEmailsRef`, etc.) rather than closing over state
- Replaced `setEmails(newEmails)` in `nextPage` with `setEmailsRaw(newEmails)` — bypassed the functional updater wrapper whose `prev` could be stale mid-batch
- Replaced 3 separate `useEffect`s firing `loadEmails` with one unified effect that tracks `activeFolder|searchQuery` as a single trigger string

**What we learned:**  
React hooks dependency arrays are a footgun at scale. The pattern of "stable callbacks that read from refs" is essential when multiple async operations can race with state updates.

---

### 12.4 Azure AD Personal Account Blocked

**Problem:**  
After implementing Microsoft Graph OAuth and logging in with a personal `@outlook.com` account, we got `AADSTS50020: User account from identity provider 'live.com' does not exist in tenant 'Default Directory'`. Login was completely broken.

**Root cause:**  
The Azure AD app was registered in an organizational tenant (`Default Directory`). Personal Microsoft accounts (`live.com`) are considered a different identity provider and cannot authenticate against organizational tenant apps by default.

**Solution:**  
Two-pronged: (1) Changed `authority` from the tenant-specific URL to `https://login.microsoftonline.com/common` so both personal and work accounts can authenticate. (2) Added `offline_access` to `_DELEGATED_SCOPES` to ensure refresh tokens are issued — sessions now survive indefinitely without re-authentication, with proactive token refresh 5 minutes before expiry.

**What we learned:**  
`common` vs tenant-specific authority is a silent gotcha in MSAL. Personal accounts on organizational tenants requires specific app manifest settings or the `common` authority.

---

### 12.5 Duplicate AZURE_CLIENT_ID in .env Breaking Login

**Problem:**  
After setting up an Azure Service Principal for Key Vault access, all Microsoft login stopped working even though the OAuth app was unchanged.

**Root cause:**  
python-dotenv uses the **last occurrence** of a duplicate key. We had added Key Vault SP credentials as `AZURE_CLIENT_ID=3d624300...` (SP app ID) below the existing `AZURE_CLIENT_ID=539cc80a...` (MS Graph OAuth app). python-dotenv silently used the SP's ID for all OAuth calls. MSAL received the wrong `client_id` and all token acquisitions failed with opaque errors.

**Solution:**  
Renamed the Key Vault SP credentials to `AZURE_SP_CLIENT_ID`, `AZURE_SP_CLIENT_SECRET`, and `AZURE_SP_TENANT_ID` to avoid collision. Added a comment block in `.env` explicitly marking which `AZURE_CLIENT_ID` is which.

**What we learned:**  
Never duplicate key names in `.env` files. Add explicit namespace prefixes for multi-credential setups. This cost 2+ hours of debugging because the symptom (login failure) pointed nowhere near the cause (wrong env variable).

---

### 12.6 LangSmith Traces Disappearing

**Problem:**  
LangSmith was receiving traces until 10:45 AM, then nothing appeared for over 30 minutes despite emails being processed.

**Root cause (multi-layer):**  
1. The app used `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`, but LangChain SDK actually reads `LANGCHAIN_TRACING_V2` and `LANGCHAIN_API_KEY`. The environment variables had the wrong names.
2. Even after fixing variable names, the frontend was calling `/api/triage` (old deterministic route) not `/api/agent/triage` (LangGraph route). Non-LangGraph routes don't produce traces.

**Solution:**  
Added env var mapping in `settings.py` startup:
```python
if os.getenv("LANGSMITH_TRACING"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
```
And unified all frontend triage calls to agent routes.

**What we learned:**  
LangSmith documentation and LangChain SDK documentation use different variable name conventions. Always verify the SDK-level env var names, not just the service-level documentation.

---

### 12.7 HTML Emails Showing Raw CSS and JSON-LD

**Problem:**  
Many emails (LinkedIn, newsletters) displayed raw CSS `@media` rules and JSON-LD schema blobs (`{ "@context": "http://schema.org"...}`) as visible text in the email body.

**Root cause:**  
The Gmail `_extract_body()` function only extracted `text/plain` MIME parts. When an email had only a `text/html` part, it fell back to the Gmail API `snippet` field — a plain-text truncation that included the first characters of the HTML, which happened to be `<style>` tag contents. The `_html_to_text()` function was stripping HTML tags but not removing `<style>...</style>` block *content* first.

**Solution:**  
1. Rewrote `_extract_body()` to walk the full MIME tree, collect both `text/html` and `text/plain` parts
2. Returns `(html_body, plain_body)` tuple — HTML for display, plain text for agents
3. Fixed `_html_to_text()` to use `re.sub(r'<style[^>]*>.*?</style>', '', html, flags=DOTALL)` before any tag stripping
4. Frontend renders `html_body` via DOMPurify + sandboxed iframe; `body` (plain) goes to agents

**What we learned:**  
Email MIME structure is deeply nested and provider-inconsistent. Any email processing that handles only one MIME type will silently degrade for a large fraction of real emails.

---

### 12.8 Supabase IPv6 DNS Failure

**Problem:**  
Database consistently failed with `could not translate host name "db.iwmlmmmcpihfqnqtzfwz.supabase.co" to address: Name or service not known` — even on home WiFi after confirming the Supabase project was healthy.

**Root cause:**  
The Supabase direct connection host only resolves to an **IPv6 address** (`2406:da1a:...`). Windows machines on many consumer ISPs have IPv6 disabled or firewalled at the router level, so DNS resolution succeeds (returns AAAA record) but the TCP connection fails silently.

**Solution:**  
Switched `DATABASE_URL` to use the Supabase **connection pooler URL** (`aws-1-ap-south-1.pooler.supabase.com:5432`) which resolves to an IPv4 address. All DB operations now succeed without any network configuration changes.

**What we learned:**  
Cloud database hostnames may resolve to IPv6 addresses that are unreachable on many development machines. Always test with pooler/proxy URLs in environments with unknown IPv6 support.

---

### 12.9 16-Second Pipeline Latency

**Problem:**  
LangSmith showed 16-17 second end-to-end latency for a full pipeline run, with 5-7 seconds just for `AzureChatOpenAI` initialization.

**Root cause (multi-cause):**
1. `AzureChatOpenAI` was instantiated on every single API request — HTTP client setup + credential validation added 200-400ms per call
2. LLM system prompts were being constructed as multi-line string concatenations on every call
3. The full email body (often 10k+ chars) was being passed to the triage node — far more tokens than needed for urgency scoring
4. No `max_tokens` cap — the LLM could generate arbitrarily long responses

**Solution:**
- **Module-level LLM caching:** `_llm_cache: dict[float, AzureChatOpenAI] = {}` — one instance per temperature, reused across all requests
- **Pre-built prompts:** `_TRIAGE_SYSTEM_PROMPT` and `_COMMITMENT_SYSTEM_PROMPT` as module-level constants — built once at import
- **Body truncation:** triage truncates to 1500 chars; commitment to 3000 chars
- **Token caps:** `llm.bind(max_tokens=600)` for triage, `max_tokens=400` for commitment

**Result:** Latency reduced from 16-17s to 5-7s for a full pipeline run.

**What we learned:**  
Every per-request instantiation of heavyweight clients (LLM, embedding, HTTP) is a latency bomb. Module-level singleton pattern with lazy initialization is essential for production API servers.

---

### 12.10 Gmail Refresh on Page Reload

**Problem:**  
Every page reload triggered fresh Gmail API calls, re-fetching all 10 emails even when nothing had changed. This caused unnecessary API quota consumption and slower perceived load times.

**Solution:**  
Implemented a versioned email cache (`EMAIL_CACHE_VERSION = 'v3'`) with 5-minute TTL stored in user-scoped localStorage:
- On reload within TTL: serve from cache instantly, zero API calls
- On cache miss / stale: show stale cache immediately while fetching fresh data in background
- New email SSE poll: every 60s, fetches only 1 email ID; if new, fetches just that email and prepends
- Cache is versioned — bumping the version number forces all clients to re-fetch (used when email shape changes)

**What we learned:**  
Frontend caching for API-heavy apps is not optional. The combination of cache-first + stale-while-revalidate + versioned invalidation gives the best UX with minimal API calls.

---

## 13. Directory Map

```
mailmind/
├── backend/
│   ├── app/
│   │   ├── main.py                  # App assembly, middleware, router wiring
│   │   ├── config/settings.py       # Env-driven settings
│   │   ├── api/
│   │   │   ├── agent_routes.py      # /process, /triage, /triage-page, /enrich, /approve
│   │   │   ├── monitoring_routes.py # /metrics, /health/deep, /sla
│   │   │   ├── compliance_routes.py # GDPR export/erase/audit/purge
│   │   │   └── routes.py            # Core API (emails, auth, calendar, tasks, poll)
│   │   ├── agents/nodes.py          # 6 LangGraph nodes (ingest…gate)
│   │   ├── graph/
│   │   │   ├── pipeline.py          # StateGraph assembly + run_pipeline
│   │   │   └── state.py             # EmailAgentState TypedDict
│   │   ├── tools/email_tools.py     # Scoring / extraction / RAG / draft tools
│   │   ├── services/
│   │   │   ├── pii.py               # PII mask / restore / strip
│   │   │   ├── graph.py             # Microsoft Graph client + MSAL
│   │   │   ├── gmail.py             # Gmail client + OAuth
│   │   │   ├── cache.py             # TriageCache (Redis + in-memory)
│   │   │   ├── draft_service.py     # Tone DNA draft generation
│   │   │   └── mail_provider.py     # Provider routing (Microsoft / Google)
│   │   ├── queue/
│   │   │   └── backends.py          # Memory / Redis queue factory
│   │   ├── db/
│   │   │   ├── base.py              # Engine/session + graceful no-DB fallback
│   │   │   ├── models.py            # EmailEnrichment, AuditLog, ProcessingMetric
│   │   │   └── repository.py        # All DB reads/writes
│   │   ├── workers/enrichment.py    # Deferred enrichment consumer
│   │   └── monitoring/metrics.py    # Prometheus metrics + SLA
│   ├── tests/                       # pytest test suite
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # Login page
│   │   └── dashboard/page.tsx       # Main dashboard
│   ├── components/
│   │   ├── detail/EmailDetail.tsx   # Email body, attachments, draft panel
│   │   ├── calendar/CalendarView.tsx# Month/Week/Agenda calendar
│   │   ├── triage/TriageExplainer.tsx
│   │   ├── commitments/CommitmentGate.tsx
│   │   └── layout/Sidebar.tsx
│   ├── hooks/
│   │   ├── useEmails.ts             # Pagination, cache, triage, SSE poll
│   │   └── useEmailDetail.ts        # Two-phase loading, draft generation
│   ├── lib/
│   │   ├── types.ts                 # Email, Attachment, TriageResult, etc.
│   │   ├── api.ts                   # All backend API calls
│   │   ├── userStorage.ts           # User-scoped localStorage
│   │   └── session.ts               # Login session management
│   └── package.json
└── README.md                        # Quick start guide
```

---

*MailMind — Agentif AI Buildathon 2026 by Capgemini*
