# MailMind Backend — Production AI Email Agent

MailMind Backend is a production-ready FastAPI service that implements the intelligent email ingestion, triage, RAG, and action-extraction pipeline for **MailMind v2**.

---

## 🚀 Key Features

* **Intelligent Triage & Prioritization**: 
  - Categorizes emails and calculates priority using Azure OpenAI / GPT-4o.
  - Utilizes a robust **five-axis scoring system** (deadline, authority, sentiment, decay, actionability).
  - Enforces JSON structured output with a 10s timeout gate and a deterministic rule-based regex fallback.
* **Semantic Action & Commitment Extraction**:
  - Automatically extracts action items, commitments, and deadlines.
  - Normalizes deadlines and timeline expressions (e.g., "tomorrow", "next Friday") using **spaCy NER (`en_core_web_sm`)** combined with relative date calculation.
  - Filters extraction using a confidence gate (>= 0.80) to control quality and logs false positives.
* **PII-Masked RAG Indexing & Precedents**:
  - Automatically indexes historical sent emails in batches of 50.
  - Applies a security-focused PII masking layer (filtering emails, phone numbers, and names) before embedding generation.
  - Generates semantic embeddings using OpenAI's **`text-embedding-ada-002`** and stores them in a local ChromaDB index.
* **Microsoft Graph & Outlook Integration**:
  - Integrated with **MSAL** for secure client-credentials flow tokens.
  - Full support for Graph webhooks, calendar schedule fetch, MS To-Do task insertion, and calendar meeting invites.
  - Double-mode toggles allow seamless switching between Live production mode and Mock simulation mode.

---

## 🛠️ Technology Stack

- **Framework**: FastAPI (Python 3.12+)
- **WSGI / Dev Server**: Uvicorn
- **NLP / Entity Parsing**: spaCy (`en_core_web_sm`)
- **Vector Database**: ChromaDB
- **LLM / Embeddings**: Azure OpenAI / OpenAI Client (`gpt-4o`, `text-embedding-ada-002`)
- **Authentication**: MSAL (Microsoft Authentication Library)

---

## ⚙️ Environment Configuration

The backend reads configuration from `mailmind-v2/backend/.env`. Required variables include:

```ini
# Microsoft Graph Authentication
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
GRAPH_SCOPES=https://graph.microsoft.com/.default
USE_MOCK_GRAPH=true # Set to false to connect to the live Graph API

# LLM Integrations (Azure OpenAI)
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002

# Standard OpenAI (Alternative Fallback)
OPENAI_API_KEY=your_openai_key
```

---

## 🏃 Run the Service Locally

Follow these quick commands to spin up the service in your shell:

```powershell
Primary step : pip install -r requirements.txt
# 1. Navigate to the backend folder
cd mailmind-v2/backend

# 2. Activate the python virtual environment
.venv\Scripts\Activate.ps1

# 3. Ensure NLP model is downloaded
python -m spacy download en_core_web_sm

# 4. Start the FastAPI development server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 🗺️ Key API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| **GET** | `/api/health` | Service health check |
| **POST** | `/api/webhook` | Receives incoming Microsoft Graph webhooks |
| **POST** | `/api/ingest` | Enqueues raw emails for background processing |
| **POST** | `/api/classify` | Performs GPT-4o email triage |
| **POST** | `/api/commitments/extract` | Extracts commitments using GPT-4o & spaCy |
| **POST** | `/api/commitments/confirm` | Confirms action and writes to MS To-Do & MS Calendar |
| **POST** | `/api/rag/retrieve` | Semantic similarity retrieval of precedent emails |

---

## 📚 Onboarding & Developer Documentation
For details regarding specific onboarding tasks, layout patterns, and frontend dashboard integration guidelines, reference:
- 🧑‍💻 [Developer Onboarding Guide (Backend)](./DEV_ONBOARDING.md)
- 🖥️ [Developer Onboarding Guide (Fullstack / UI)](../DEV_ONBOARDING_FULLSTACK.md)
