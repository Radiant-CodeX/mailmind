<div align="center">

<img src="frontend/public/mailmind-logo.svg" alt="MailMind Logo" width="72" height="72" />

# MailMind

**The Intelligent Email Co-Pilot for the Enterprise**

AI-powered inbox triage, commitment extraction, calendar conflict detection, and Tone DNA draft generation — with mandatory human-in-the-loop approval on every outbound action.

<div align="center">

[![CI](https://github.com/Radiant-CodeX/mailmind/actions/workflows/ci.yml/badge.svg)](https://github.com/Radiant-CodeX/mailmind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure](https://img.shields.io/badge/Azure-OpenAI-0078D4?logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)

[📘 Live Demo](https://mailmind.radiantsofficial.com) · [📚 API Docs](https://api.radiantsofficial.com/docs) · [🏗️ Architecture](#architecture) · [📋 Implementation Wiki](WIKI.html)

</div>

---

## Overview

Enterprise knowledge workers lose an average of **2.5 hours per day** to email — reading, prioritising, drafting, and following up on messages that often contain hidden commitments and scheduling conflicts. MailMind eliminates that overhead.

MailMind sits alongside Gmail and Outlook as an intelligent co-pilot. It triages every incoming message across five explainable axes, surfaces action items and deadlines, guards your calendar against conflicts, and drafts context-aware replies in your own voice — while keeping you in complete control of every outgoing send.

> **No email is ever sent automatically.** Human approval is enforced at the protocol layer, not the UI layer.

---

## Screenshots

### Inbox View with Triage Scores
![Inbox with CRITICAL, HIGH, MEDIUM priority badges](https://via.placeholder.com/800x400?text=Inbox+View+with+Triage+Scores)

### Email Detail Panel & Five-Axis Triage Breakdown
![Email detail showing triage reasoning across 5 axes](https://via.placeholder.com/800x400?text=Email+Detail+%26+Triage)

### Draft Generation with Tone DNA & Calendar Conflicts
![Draft panel with calendar conflict badge](https://via.placeholder.com/800x400?text=Draft+Generation)

### Commitment Extraction & Approval Gate
![Commitments list with calendar conflict flags](https://via.placeholder.com/800x400?text=Commitments+Extraction)

### Admin Waitlist Panel
![Waitlist approval interface](https://via.placeholder.com/800x400?text=Admin+Panel)

---

## Key Capabilities

| Capability | Description |
|---|---|
| **Five-Axis Explainable Triage** | Every email receives a composite priority score (CRITICAL / HIGH / MEDIUM / LOW) across deadline proximity, sender authority, sentiment urgency, thread age decay, and action type. Full reasoning exposed to the user. |
| **Tone DNA** | Builds a per-account stylometric profile from sent-mail history. Drafts match your vocabulary, formality level, sentence rhythm, and sign-off style. Each connected account has its own independent profile. |
| **Commitment Extractor** | Detects action items, commitments, and deadlines using GPT-4o with NER. Converts approved items into Microsoft To-Do tasks or Google Calendar events after explicit user confirmation. |
| **Calendar Conflict Detection** | Compares extracted deadlines against your upcoming calendar before surfacing them, flagging clashes before you commit to a schedule. |
| **RAG Precedent Engine** | Retrieves semantically similar historical threads via ChromaDB and `text-embedding-ada-002` to provide organisational context and improve draft quality. |
| **PII Masking** | All email content is masked via Microsoft Presidio + spaCy before any LLM call. Masked tokens are restored post-generation. Raw PII is never stored or transmitted to a model. |
| **Priority Feedback Loop** | Manual priority overrides (including "Mark Done") are persisted and fed back into the triage engine, improving accuracy per sender over time. |
| **Multi-Account Support** | Connect multiple Gmail and Outlook accounts under a single MailMind identity. Each account has isolated triage, Tone DNA, and RAG context. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Client  (Next.js 15 · React · Tailwind CSS · GSAP)                 │
│  mailmind.radiantsofficial.com  ·  Vercel CDN + SSR                 │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTPS REST / SSE
┌────────────────────────▼────────────────────────────────────────────┐
│  Backend  (FastAPI · Python 3.12 · Azure Container Apps · East US)  │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │
│  │  API Routers │  │  Middleware  │  │  AI Pipeline (LangGraph)  │  │
│  │  /api/agent  │  │  RateLimit   │  │  PII Mask → Triage →      │  │
│  │  /api/auth   │  │  SecurityHdr │  │  Commit Extract →         │  │
│  │  /api/emails │  │  CORS        │  │  Calendar Guard →         │  │
│  │  /api/rag    │  │  SessionCtx  │  │  RAG Retrieve →           │  │
│  │  /webhooks   │  └──────────────┘  │  Draft Generate →         │  │
│  │  /metrics    │                    │  PII Restore               │  │
│  └──────────────┘                    └───────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────┐  ┌─────────────────────────────────┐  │
│  │  Queue + Workers         │  │  Core Services                  │  │
│  │  Redis 7 AOF (prod)      │  │  IdentityService · SessionSvc   │  │
│  │  In-memory (dev)         │  │  SyncService · ToneDNA          │  │
│  │  N enrichment replicas   │  │  CommitmentService · DraftSvc   │  │
│  └──────────────────────────┘  └─────────────────────────────────┘  │
└──────┬──────────────┬──────────────────┬────────────────┬───────────┘
       │              │                  │                │
┌──────▼──────┐ ┌─────▼──────┐  ┌───────▼──────┐ ┌──────▼──────────┐
│  Supabase   │ │  ChromaDB  │  │ Azure OpenAI │ │  MS Graph API   │
│  PostgreSQL │ │  (local)   │  │ gpt-4o-mini  │ │  Gmail API      │
│  us-east-1  │ │  ada-002   │  │ gpt-4o       │ │  Pub/Sub Push   │
│  :6543      │ │  RAG index │  │ ada-002      │ └─────────────────┘
└─────────────┘ └────────────┘  └──────────────┘
```

### Infrastructure

| Component | Technology | Region / Config |
|---|---|---|
| Frontend hosting | Vercel (CDN + SSR) | Global edge |
| Backend compute | Azure Container Apps | East US |
| Database | Supabase PostgreSQL | us-east-1 (transaction pooler :6543) |
| Secret management | Azure Key Vault | East US |
| LLM inference | Azure OpenAI | East US |
| Identity provider | Azure Entra ID | App Registration (multi-tenant) |
| Vector store | ChromaDB | Local disk (container volume) |
| Queue | Redis 7 (AOF) | Sidecar container |
| Tracing | Jaeger (OTEL) + LangSmith | Self-hosted + cloud |
| Metrics | Prometheus + Grafana | Self-hosted |
| Error monitoring | Sentry | Cloud |

---

## Security & Compliance

- **PII masking** enforced before every LLM call via Microsoft Presidio + spaCy `en_core_web_sm`. Raw PII is never stored or sent to a model.
- **No automatic sends.** Human approval is mandatory at the protocol layer. There is no code path that bypasses it.
- **OAuth tokens** are Fernet-AES-128 encrypted at rest. Never stored in plaintext.
- **Sessions** are stored as SHA-256 hashes (24h TTL). Raw tokens live only in `HttpOnly; Secure; SameSite=Strict` cookies.
- **Rate limiting** at 100 req/min per session enforced in middleware.
- **Security headers** — HSTS, CSP, X-Frame-Options, X-Content-Type-Options — applied to every response.
- **Audit log** — append-only table tracks every pipeline action. No raw PII in the log.
- **Data retention** — configurable (default 90 days). Governed by `DATA_RETENTION_DAYS`.
- **Private-beta gate** — waitlist allow-list controls access. Bootstrap owner emails bypass the gate to prevent lockout.
- **Secrets** sourced exclusively from Azure Key Vault in production. `.env` is for local development only.

---

## Tech Stack

### Frontend
- **Next.js 15** (App Router) · **TypeScript** · **Tailwind CSS**
- **GSAP** (animations) · **DOMPurify** (HTML sanitisation)
- **IndexedDB** score cache (30-day TTL, per-user namespace)

### Backend
- **FastAPI** · **Python 3.12** · **Uvicorn**
- **SQLAlchemy** (ORM) · **Pydantic v2**
- **LangGraph** (AI pipeline orchestration) · **LangChain**

### AI & Models
- **Azure OpenAI** — `gpt-4o-mini` (triage), `gpt-4o` (commitments, drafts), `text-embedding-ada-002` (RAG)
- **Microsoft Presidio** + **spaCy** — PII detection and masking
- **ChromaDB** — local vector store for RAG precedents
- **Groq** — LLM fallback when Azure OpenAI is unconfigured

### Integrations
- **Microsoft Graph API** — mail, calendar, tasks (Microsoft To-Do), webhooks
- **Gmail API** — mail, calendar, Google Cloud Pub/Sub push notifications
- **LangSmith** — LangChain run tracing and observability

### Infrastructure & Observability
- **Azure Container Apps** · **Azure Key Vault** · **Azure Entra ID**
- **Supabase PostgreSQL** (managed, HA, automatic backups)
- **Redis 7** (AOF persistent queue)
- **Prometheus** · **Jaeger** (OTEL) · **Sentry**
- **Vercel** (frontend hosting + analytics)
- **GitHub Actions** (CI/CD)

---

## Repository Structure

```
mailmind/
├── backend/                    # FastAPI application
│   ├── app/
│   │   ├── api/               # Route handlers (routes.py, agent_routes.py, …)
│   │   ├── config/            # Settings, Azure Key Vault loader
│   │   ├── db/                # SQLAlchemy models, repository layer, mailbox repo
│   │   ├── middleware/        # Rate limiting, security headers, session context
│   │   ├── models/            # Pydantic schemas
│   │   ├── queue/             # EmailQueue abstraction (memory / Redis)
│   │   ├── services/          # Core business logic (triage, RAG, ToneDNA, …)
│   │   └── workers/           # Enrichment consumer workers
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                   # Next.js 15 application
│   ├── app/                   # App Router pages, layout, OG image, sitemap
│   ├── components/            # UI components (inbox, detail, commitments, …)
│   ├── hooks/                 # React hooks (useEmails, useCommitments, …)
│   ├── lib/                   # API client, types, caching utilities
│   └── public/                # Static assets, logo
│
├── infra/
│   └── prometheus/            # Prometheus scrape config
│
├── .github/
│   └── workflows/             # CI pipeline (ci.yml, ci.yaml)
│
├── docker-compose.yml          # Development stack (mock mode)
├── docker-compose.prod.yml     # Production overlay (live Azure)
├── docker-compose.scale.yml    # Scale overlay (Redis + workers)
├── WIKI.html                   # Implementation feature wiki (searchable)
└── LICENSE
```

---

## Local Development

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker (optional, for full stack)

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m spacy download en_core_web_sm

uvicorn app.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Full Stack (Docker)

```bash
# Development — mock Graph, in-memory queue
docker compose up -d

# Production — live Azure, Redis queue, Supabase DB
docker compose -f docker-compose.yml \
               -f docker-compose.prod.yml \
               -f docker-compose.scale.yml up -d --build

# Scale workers
docker compose ... up -d --scale worker=4
```

### Environment Variables

Copy `.env.example` to `.env` in the `backend/` directory and populate the required values. In production, all secrets are sourced from **Azure Key Vault** (`AZURE_KEY_VAULT_URL`).

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Production | Supabase PostgreSQL connection string |
| `AZURE_OPENAI_ENDPOINT` | Production | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | Production | Azure OpenAI API key |
| `AZURE_TENANT_ID` | Production | Entra ID tenant |
| `AZURE_CLIENT_ID` | Production | App Registration client ID |
| `AZURE_CLIENT_SECRET` | Production | App Registration secret |
| `GOOGLE_CLIENT_ID` | Production | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Production | Google OAuth client secret |
| `SESSION_SECRET_KEY` | Production | Signs session tokens (Fernet key) |
| `TOKEN_ENCRYPTION_KEY` | Production | Encrypts OAuth tokens at rest (Fernet key) |
| `REDIS_URL` | Production | Redis connection string |
| `BACKEND_PUBLIC_URL` | Optional | Enables Graph webhooks and Gmail Pub/Sub push |
| `LANGSMITH_API_KEY` | Optional | Enables LangChain run tracing |
| `SENTRY_DSN` | Optional | Enables error monitoring |

---

## CI / CD

Every pull request against `main` or `develop` runs:

| Stage | Tool | Details |
|---|---|---|
| Lint | `ruff` | `E, F, W` rules |
| Type check (backend) | `pyright` | Python 3.12, non-blocking |
| Unit + integration tests | `pytest` | `fakeredis` + SQLite — no live infra required |
| Type check (frontend) | `tsc --noEmit` | Node 20 |
| Docker build | `docker build` | Backend image, runs on `main` only |

Test results are uploaded as artifacts on every run.

---

## Quality Gates

Pull requests must satisfy:

- Ruff lint (zero errors on `E, F, W`)
- Pyright type-check
- Full test suite (`pytest`) — PII safety, production config, service contracts
- Frontend TypeScript check (`tsc --noEmit`)
- Docker image builds successfully

---

## Team

| Member | Role |
|---|---|
| Tarunkumar S | Product Lead & Solution Strategist |
| Rithish K | AI Workflow & Automation Lead |
| Manish K | LLM & Integrations Lead |
| Rithish Barath N | Full Stack & Experience Lead |
| Shan Neeraj | Enterprise Security Lead |

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
<sub>Built by <a href="https://radiantsofficial.com">Radiants</a> · <a href="mailto:radiantcodex@outlook.com">radiantcodex@outlook.com</a></sub>
</div>
