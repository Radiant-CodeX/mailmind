# MailMind Live Demo Guide

## Target Flow (Single End-to-End Path)
**Email → Triage → Conflict Check → AI Draft → Human Approve → Send**

---

## Prerequisites
- Backend running on `http://localhost:8000`
- Frontend running on `http://localhost:3000`
- Jaeger running on `http://localhost:6831` (or configured endpoint)
- MS Graph credentials in `.env` (CLIENT_ID, TENANT_ID)
- Presidio analyzer loaded + spaCy en_core_web_sm

---

## 5 Unique Features to Demonstrate

### U1: Five-Axis Triage Scorecard
**Endpoint:** `POST /triage`
```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "vp@company.com",
    "subject": "Urgent Q4 budget approval needed",
    "body": "We need final sign-off by EOD today for the budget..."
  }'
```
**Expected:** Returns 5-axis scores (urgency, stakeholder_power, complexity, time_sensitivity, escalation_risk) + composite priority.

---

### U2: Conflict Badge (Calendar + Commitments)
**Endpoint:** `POST /conflict-check`
```bash
curl -X POST http://localhost:8000/conflict-check \
  -H "Content-Type: application/json" \
  -d '{
    "email_id": "msg123",
    "sender": "client@company.com",
    "subject": "Can we meet Tuesday 2-3pm?",
    "body": "..."
  }'
```
**Expected:** Returns conflict status (yes/no), conflicting event details, and precedents from past similar emails.

---

### U3: Tone DNA Draft + RAG Citations
**Endpoint:** `POST /draft`
```bash
curl -X POST http://localhost:8000/draft \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "manager@company.com",
    "subject": "Project status update",
    "body": "..."
  }'
```
**Expected:** AI-generated draft reply matching sender's communication style + RAG citations from past emails.

---

### U4: Human Approval Gate (Step 9→11 Blocker)
**Endpoint:** `POST /approve`
```bash
curl -X POST http://localhost:8000/approve \
  -H "Content-Type: application/json" \
  -d '{
    "email_id": "msg123",
    "action": "approve",
    "draft_reply": "Thank you for your message..."
  }'
```
**Expected:** Returns `"status": "Approved"` — **without this approval, Step 11 (Send) never executes.**

---

### U5: Jaeger Trace URL + Presidio PII Masking
**Traces:** After each endpoint call, retrieve Jaeger trace:
```
http://localhost:16686/search?service=mailmind.v2&limit=20
```
**Custom attributes per email:**
- `email.id`: The source email ID
- `triage.composite_score`: Final priority
- `triage.priority`: Label (urgent/high/normal/low)
- `triage.axis.*`: Individual 5-axis scores

**PII Masking:** Inspect LLM call logs — confirm no raw email addresses, SSNs, or credit cards in prompts sent to Azure OpenAI.

---

## Demo Flow (Live Walkthrough)

### Step 1: Fetch Emails
```bash
GET http://localhost:8000/emails
```
Shows mock emails with mock triage scores.

### Step 2: Select Email & Trigger Triage
Click email → Backend calls `/triage` → UI shows 5-axis scorecard.

### Step 3: Conflict Check
Click "Check Calendar" → `/conflict-check` → Badge appears if conflict detected.

### Step 4: Generate Draft
Click "Generate Reply" → `/draft` → Shows AI draft + RAG citations.

### Step 5: Approve
Click "Approve Draft" → `/approve` (action=approve) → Draft marked ready.

### Step 6: Send Email
Click "Send" → **Only executes after approval.** Sends to Graph API `/me/messages/send`.

### Step 7: View Trace
After completion, visit Jaeger UI → Search for email ID → Show trace with:
- All 5 triage axes
- Custom span attributes
- Latency per step
- No PII visible in span data

---

## Known Issues & Workarounds

### Issue 1: MS Graph Token Acquisition Fails
**Cause:** Device code flow requires interactive user prompt.
**Workaround:** Mock the `get_graph_token()` return for demo. Use test token from Azure Portal.

### Issue 2: Presidio Analyzer Not Loaded
**Cause:** spaCy model missing on first run.
**Fix:** Run `python -m spacy download en_core_web_sm` before starting backend.

### Issue 3: Jaeger Exporter Connection Error
**Cause:** Jaeger not running on localhost:14268.
**Workaround:** Falls back gracefully (warning logged). Traces still work if JaegerExporter unavailable.

### Issue 4: Azure OpenAI Fails (API key missing)
**Cause:** Missing `AZURE_OPENAI_*` env vars.
**Workaround:** Fallback drafts already coded in `ai_routes.py` — API failures return mock response.

---

## Recording Alternative (If Live Breaks)

If live APIs fail mid-demo:
1. Pre-record the happy path using `recorded_demo.mp4`
2. Play recording while narrating
3. Switch to live for **Jaeger trace inspection** (show linkable trace URL)
4. Manually demonstrate PII masking by:
   - Showing raw email with SSN
   - Running Presidio analyzer offline
   - Showing masked output

---

## Success Criteria Checklist

- [ ] Email arrives → Triage scorecard shows all 5 axes
- [ ] Conflict badge appears when calendar conflict detected
- [ ] Tone DNA draft generated with RAG citations visible
- [ ] User clicks "Approve" → status updates to "Approved"
- [ ] User clicks "Send" → **only works after approval**
- [ ] Jaeger trace URL is linkable and shows custom attributes
- [ ] Presidio masking confirmed: no raw PII in LLM prompts
- [ ] Zero code path exists from Step 9 → Step 11 without human gate
- [ ] All 5 features demonstrated in <15 minutes

---

## Quick Start Commands

```bash
# Terminal 1: Backend
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Jaeger (if using Docker)
docker run -d -p 6831:6831/udp -p 16686:16686 jaegertracing/all-in-one

# Test Backend Health
curl http://localhost:8000/docs  # FastAPI Swagger UI
```

---

## Frontend Integration Notes

- **useEmails()** hook: Calls `GET /emails` → populates inbox
- **useEmailDetail()** hook: Calls `POST /triage` → shows scorecard
- **useCommitments()** hook: Calls `POST /conflict-check` → shows badge
- **useEmailDetail().generateDraft()**: Calls `POST /draft` → updates aiDraft state
- **useEmailDetail().sendDraft()**: Calls `POST /approve` → validates human approval before send

All frontend-to-backend calls use fetch with error boundaries. Fallback UI renders if API fails.

---

## Custom Span Attributes (OBS-01/02)

From `main.py` line 101:
```python
def span_triage(email_id: str, axes: list, composite_score: float, priority: str):
    with tracer.start_as_current_span("mailmind.triage") as span:
        span.set_attribute("email.id", email_id)
        span.set_attribute("triage.composite_score", composite_score)
        span.set_attribute("triage.priority", priority)
        for axis in axes:
            span.set_attribute(f"triage.axis.{axis.axis}", axis.raw_score)
```

Call this after triage completes to emit the custom span.

---

## Contact & Support

Questions during demo? Check:
1. Backend logs: `uvicorn` console for errors
2. Frontend console: `F12 → Console tab` for JS errors
3. Jaeger: `http://localhost:16686` for trace inspection
4. FastAPI docs: `http://localhost:8000/docs` for endpoint schema
