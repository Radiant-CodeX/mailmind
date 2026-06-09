# MailMind

**Intelligent Enterprise Email Co-Pilot**

MailMind is an AI-powered email productivity platform that helps knowledge workers prioritize emails, draft context-aware responses, extract commitments, and reduce inbox overload while maintaining full human control over every outgoing message.

Built for the **Capgemini AI Buildathon** by **Team RadiantCodeX**.

---

##  Problem Statement

Enterprise employees spend a significant portion of their workday managing email instead of performing high-value work.

MailMind addresses:

* Inbox overload and attention fragmentation
* Missed commitments and deadlines
* Context loss while drafting replies
* Enterprise PII and compliance risks
* Lack of explainability in AI-assisted email workflows

---

##  Key Features

### U1 — Tone DNA

Learns a user's writing style from historical sent emails and generates drafts that match their communication patterns.

### U2 — Five-Axis Explainable Triage

Every email receives a composite priority score based on:

* Deadline proximity
* Sender authority
* Sentiment urgency
* Thread age decay
* Action type

Users can inspect exactly why an email received its score.

### U3 — Calendar Conflict Detection

Detects scheduling conflicts before replying by comparing email deadlines against upcoming calendar events.

### U4 — Commitment Extractor

Automatically identifies:

* Action items
* Commitments
* Deadlines

and converts them into actionable tasks after user approval.

### U5 — RAG Precedent Engine

Retrieves semantically similar historical email threads to provide organizational context and improve draft quality.

---

##  Architecture Overview

```text
Email Ingestion
      ↓
PII Masking
      ↓
Commitment Extraction
      ↓
Calendar Conflict Detection
      ↓
Thread Retrieval
      ↓
RAG Retrieval
      ↓
Five-Axis Triage
      ↓
Draft Generation
      ↓
PII Restoration
      ↓
Approval Inbox
      ↓
Confirmed Actions
```

Human approval is mandatory before any email can be sent.

There is no automatic send path.

---

##  Tech Stack

### Frontend

* Next.js 15
* TypeScript
* Tailwind CSS

### Backend

* FastAPI
* Python 3.12

### AI & Agents

* Azure OpenAI GPT-4o
* Semantic Kernel
* LangChain

### Integrations

* Microsoft Graph API
* Microsoft To Do
* Microsoft Calendar

### Security

* Microsoft Presidio
* Azure Entra ID
* OAuth2

### Observability

* OpenTelemetry
* Jaeger
* Prometheus

### Storage & Retrieval

* Azure AI Search
* ChromaDB

---

##  Repository Structure

```text
mailmind-v2/
├── backend/
├── frontend/
├── docs/
├── infra/
├── eval/
├── demo/
└── .github/
```

---

##  Team RadiantCodeX

| Member           | Role                               |
| ---------------- | ---------------------------------- |
| Tarunkumar S     | Product Lead & Solution Strategist |
| Rithish K        | AI Workflow & Automation Lead      |
| Manish K         | LLM & Integrations Lead            |
| Rithish Barath N | Full Stack & Experience Lead       |
| Shan Neeraj      | Enterprise Security Lead           |

---

##  Git Workflow

### Main Branches

```text
main
develop
feature/*
hotfix/*
```

### Feature Development

```bash
git checkout develop
git pull

git checkout -b feature/TRI-01-deadline-scorer
```

Create a Pull Request into `develop`.

Direct pushes to `main` are not allowed.

---

##  Local Development

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on:

```text
http://localhost:3000
```

---

### Backend

```bash
cd backend

python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run API:

```bash
uvicorn app.main:app --reload
```

Runs on:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

---

##  Quality Gates

Every Pull Request must pass:

* Ruff Lint
* Unit Tests
* Integration Tests
* PII Safety Checks
* Build Validation

---

##  Security Principles

* No secrets committed to source control
* PII masked before any LLM call
* Approval required before sending email
* OAuth2 delegated authentication
* Request-scoped token restoration

---

##  Project Status

Current Phase:

```text
Sprint 1 — Core Pipeline
```

Target:

```text
Production-ready AI email assistant with human-in-the-loop governance.
```

---

## 📄 License

This project is developed as part of the Capgemini AI Buildathon by Team RadiantCodeX.
