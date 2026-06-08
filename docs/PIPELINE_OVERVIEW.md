# MailMind Pipeline Architecture & Presentation Guide

## 1️⃣ Pipeline Is Fully Configured ✅

Your backend has a **complete 6-node LangGraph pipeline** that processes emails end-to-end:

```
[EMAIL ARRIVES]
       ↓
   INGEST NODE          (PII masking + validation)
       ↓
   TRIAGE NODE          (5-axis scoring with dynamic weights)
       ↓
   COMMITMENT NODE      (Extract action items)
       ↓
   CALENDAR NODE        (Detect scheduling conflicts)
       ↓
   RAG NODE             (Retrieve precedents + generate draft)
       ↓
   GATE NODE            (Human approval checkpoint)
       ↓
   [RESULTS STORED]
```

---

## 2️⃣ How to View It Right Now

### Via Email Detail Panel (Real-time)
Open any email in the inbox → right panel shows:
- **Triage Explainer** — 5-axis breakdown (deadline, authority, sentiment, thread_risk, action)
- **Composite Score** — 0–100 priority (color gradient)
- **Approval Gate Status** — "GATE" (red) or "SUGGEST ONLY" (green)
- **Commitments** — extracted action items with deadlines
- **Calendar Conflicts** — visual badges on conflicting commitments
- **Precedents** — semantically similar past emails
- **AI Draft** — generated reply (Tone DNA matched to your style)

### Via Prometheus Metrics Dashboard
```bash
# Terminal 1: Start backend with metrics enabled
cd backend && METRICS_ENABLED=true python -m uvicorn app.main:app --reload

# Terminal 2: Start Prometheus
docker run -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Terminal 3: Start Grafana (optional, nicer dashboards)
docker run -p 3000:3000 \
  -e GF_SECURITY_ADMIN_PASSWORD=admin \
  grafana/grafana
```

Then open:
- **Prometheus** → http://localhost:9090
- **Grafana** → http://localhost:3000 (add Prometheus as data source)

Query metrics:
```promql
# SLA compliance (% meeting target latency)
rate(mailmind_sla_compliance_total{met="true"}[5m]) / (rate(mailmind_sla_compliance_total[5m]) + 1)

# Average latency per stage
rate(mailmind_stage_duration_seconds_sum[5m]) / rate(mailmind_stage_duration_seconds_count[5m])

# Queue depth (pending enrichment jobs)
mailmind_queue_depth

# LLM fallback rate
rate(mailmind_llm_calls_total{outcome="fallback"}[5m]) / rate(mailmind_llm_calls_total[5m])
```

### Via Deep Health Check
```bash
curl http://localhost:8000/api/health/deep | jq .
```

Response shows:
```json
{
  "status": "healthy",
  "checks": {
    "database": { "status": "connected", "latency_ms": 45 },
    "redis": { "status": "connected", "latency_ms": 2 },
    "azure_openai": { "status": "connected" },
    "queue": { "depth": 0, "backend": "redis" }
  },
  "sla_targets": {
    "triage_seconds": 1.5,
    "enrichment_seconds": 10.0
  }
}
```

---

## 3️⃣ How to Show It While Presenting

### Option A: Live Walkthrough (Best for Demo)

1. **Launch the app in dev mode:**
   ```bash
   # Terminal 1: Backend (with mock Graph if needed)
   cd backend
   export USE_MOCK_GRAPH=true  # For testing without Azure auth
   python -m uvicorn app.main:app --reload

   # Terminal 2: Frontend
   cd frontend
   npm run dev
   ```

2. **Open the email inbox** → http://localhost:3000

3. **Click on an email** to trigger the full pipeline:
   - **Watch in real-time** as the right panel loads:
     - Triage score appears (0–100)
     - 5-axis breakdown visualizes
     - Commitments appear with deadlines
     - Calendar conflicts flagged
     - Draft reply generates
     - Gate status shows approval requirement

4. **Show backend logs** in another terminal to narrate each step:
   ```bash
   # In backend terminal, you'll see:
   [INGEST] Processing email_id=msg-001
   [TRIAGE] Scoring email_id=msg-001
   [COMMITMENT] Extracting for email_id=msg-001
   [CALENDAR] Checking conflicts for email_id=msg-001
   [RAG] Retrieving precedents for email_id=msg-001
   [GATE] Approval gate for email_id=msg-001 priority=CRITICAL
   ```

### Option B: Grafana Dashboard (Best for Metrics)

1. **Build the dashboard** (one-time):
   ```bash
   docker run -d -p 3000:3000 \
     -e GF_SECURITY_ADMIN_PASSWORD=admin \
     grafana/grafana
   ```

2. **Add Prometheus data source:**
   - Grafana → Data Sources → Add Prometheus
   - URL: http://localhost:9090

3. **Create panels** showing:
   - **Golden Signals** (latency, traffic, errors, saturation)
   - **SLA Compliance %** per stage
   - **LLM Fallback Rate** (% of emails using deterministic path)
   - **Queue Depth** (pending jobs)
   - **PII Masked** (privacy coverage)

### Option C: Presentation Visualization Component (New)

I'll create a **`PipelineVisualization` component** that shows:
- ✅ Animated node progression as email moves through pipeline
- ✅ Timing breakdown per node
- ✅ Success/error indicators
- ✅ State snapshots at each step

Would you like me to build this now? It would look like:

```
┌──────────────────────────────────────────────────────┐
│  EMAIL PIPELINE EXECUTION                 msg-001    │
├──────────────────────────────────────────────────────┤
│                                                      │
│  ✅ INGEST        12ms   [████]                     │
│     └─ Masked 5 PII entities                        │
│                                                      │
│  ✅ TRIAGE        480ms  [██████████████]           │
│     └─ Score: 78 | Type: client_escalation         │
│     └─ Weights: deadline 30%, authority 25%, ...   │
│                                                      │
│  ✅ COMMITMENT    340ms  [████████████]             │
│     └─ Found 3 commitments (2 high confidence)      │
│                                                      │
│  ✅ CALENDAR      45ms   [██]                       │
│     └─ 1 conflict detected with existing event      │
│                                                      │
│  ✅ RAG           520ms  [████████████████]         │
│     └─ Retrieved 3 precedents | Draft: 142 chars    │
│                                                      │
│  🔴 GATE          0ms    [AWAITING APPROVAL]        │
│     └─ Priority: CRITICAL | Mode: GATE              │
│                                                      │
│  Total: 1.4s | SLA: ✅ MET (1.5s target)           │
└──────────────────────────────────────────────────────┘
```

---

## 4️⃣ Detailed Pipeline Breakdown

### Node 1: INGEST (PII Masking)
- **Input:** Raw email body
- **Process:** Rule-based masking (emails, phone numbers, names)
- **Output:** Masked text, mask mapping dict
- **Code:** `app/agents/nodes.py` → `ingest_node()`
- **Timing:** ~10–50ms

### Node 2: TRIAGE (Dynamic Scoring)
- **Input:** Sender, subject, masked body, received timestamp
- **Process:** GPT-4o scores 5 axes; dynamic weights for THIS email
- **Axes:**
  - `deadline` (urgency of any implied/explicit due date)
  - `authority` (sender's stakeholder power)
  - `sentiment` (emotional tone, frustration)
  - `thread_risk` (business risk if ignored)
  - `action` (concrete response required?)
- **Output:** 
  - Composite score 0–100
  - Priority: CRITICAL (≥75) | HIGH (≥50) | MEDIUM (≥25) | LOW
  - Approval mode: GATE (requires manual approval) | SUGGEST (suggestions only)
- **Fallback:** Deterministic 5-tool scoring if LLM unavailable
- **Code:** `app/agents/nodes.py` → `triage_node()`
- **Timing:** 300–800ms (LLM) or ~100ms (fallback)

### Node 3: COMMITMENT (Extract Action Items)
- **Input:** Masked email body
- **Process:** GPT-4o extracts all tasks, promises, deadlines
- **Output:** 
  - List of commitments: `[{commitment, deadline, confidence}]`
  - Only commitments with confidence ≥0.80 are kept
- **Code:** `app/agents/nodes.py` → `commitment_node()`
- **Timing:** 200–600ms (LLM) or ~50ms (fallback)

### Node 4: CALENDAR (Conflict Detection)
- **Input:** Commitments with deadlines, calendar events
- **Process:** Check if deadline overlaps with existing events (72-hour window)
- **Output:** Commitments enriched with `conflict_badge` and `conflict_detail`
- **Code:** `app/agents/nodes.py` → `calendar_node()`
- **Timing:** ~20–100ms (deterministic)

### Node 5: RAG (Precedent Retrieval + Draft Generation)
- **Input:** Masked email body, ChromaDB vector index
- **Process:**
  1. Retrieve top-3 semantically similar sent emails (Tone DNA)
  2. Build draft prompt injecting precedent context
  3. Generate reply matching user's communication style
- **Output:**
  - `precedents`: similar past emails
  - `draft_reply`: generated reply text
- **Code:** `app/agents/nodes.py` → `rag_node()`
- **Timing:** 400–1000ms (LLM)

### Node 6: GATE (Approval Checkpoint)
- **Input:** Email priority and approval mode
- **Process:** 
  - If CRITICAL: pause and wait for human `POST /api/commitments/confirm`
  - If HIGH/MEDIUM/LOW: suggestions only (no block)
- **Output:** `approved: true|false`
- **Code:** `app/agents/nodes.py` → `gate_node()`
- **Timing:** 0ms (instant) or ⏸ (blocked until human approval)

---

## 5️⃣ Monitoring & Observability

### Metrics Available (Prometheus)

```
mailmind_emails_processed_total{stage,status}    — Count by stage & outcome
mailmind_stage_duration_seconds{stage}             — Latency histogram per stage
mailmind_node_duration_seconds{node}               — Individual node timing
mailmind_sla_compliance_total{stage,met}           — SLA success rate
mailmind_llm_calls_total{node,outcome}             — LLM usage & fallback rate
mailmind_pii_masked_total{category}                — Privacy coverage
mailmind_queue_depth                               — Pending jobs
```

### Logging

Each node logs its progress to stdout/file:
```
[INGEST] Processing email_id=msg-001
[TRIAGE] Scoring email_id=msg-001 type=client_escalation score=78 priority=CRITICAL
[COMMITMENT] Extracting for email_id=msg-001
[CALENDAR] Checking conflicts for email_id=msg-001
[RAG] Retrieving precedents for email_id=msg-001
[GATE] Approval gate for email_id=msg-001 priority=CRITICAL
```

### Audit Trail

All pipeline executions are logged to `processing_metrics` table (SQL):
```sql
SELECT 
  email_id, 
  stage, 
  duration_ms, 
  success, 
  sla_met 
FROM processing_metrics 
WHERE email_id = 'msg-001' 
ORDER BY created_at;
```

---

## 6️⃣ Live Demo Script

Perfect for presenting to stakeholders:

```markdown
## MailMind Pipeline Demo

**Scenario:** CFO receives urgent escalation email from major client about contract review.

### Step 1: Email Arrives
- Click on the email → right panel starts loading
- Show: "Performing NLP classification and calculating priority indices..."

### Step 2: Triage (480ms)
- **Show:** Triage Explainer panel fills in
- **Narrate:** "The system just scored 5 dimensions:
  - Deadline: 85% (explicit 'by EOD' deadline)
  - Authority: 90% (major client CFO)
  - Sentiment: 75% (urgent tone with potential contract risk)
  - Thread Risk: 88% (business relationship at stake)
  - Action: 70% (concrete review required)"
- **Result:** Composite score = 82 → **CRITICAL priority**
- **Gate Status:** 🔴 **APPROVAL REQUIRED** (human must review before actions proceed)

### Step 3: Commitments (340ms)
- **Show:** Commitments section appears
- **Narrate:** "Extracted 3 action items:
  1. 'Review contract by EOD' (deadline: today 5PM) — Confidence 95%
  2. 'Arrange signature ceremony' (deadline: tomorrow) — Confidence 88%
  3. 'Coordinate with legal' (deadline: tomorrow 10AM) — Confidence 92%"

### Step 4: Calendar Conflicts (45ms)
- **Show:** Red conflict badge on commitment #1
- **Narrate:** "Uh oh — the 5PM deadline conflicts with the CFO's existing 4–5PM client call.
  System flagged it automatically. Human can now make an informed decision."

### Step 5: Draft Reply (520ms)
- **Show:** Draft panel generates
- **Narrate:** "The system also generated a reply matching the user's communication style:
  'We received your urgent request regarding the XYZ contract. Our legal team will
  complete the review by 3PM today. I'll coordinate with [client contact] directly.'"
- **Key Point:** "Notice the tone — professional but warm. This is 'Tone DNA' —
  the system learned from the user's 50 previous emails sent to this client."

### Step 6: User Decision
- **Show:** Commitment gate with approve/reject toggle
- **Narrate:** "User reviews the recommended actions and can:
  1. Approve all commitments → automatically creates calendar events & task reminders
  2. Modify deadlines if conflicts exist
  3. Edit the draft before sending"

### Final Metrics
- **Total pipeline time:** 1.4 seconds
- **SLA compliance:** ✅ MET (1.5s target)
- **LLM calls:** 3 (triage, commitment, draft)
- **Fallbacks used:** 0 (all LLM paths succeeded)
- **PII handled:** 5 entities masked before LLM (full security)

**Takeaway:** From email arrival to approval-ready action items — 1.4 seconds.
Human stays in the loop for CRITICAL decisions, but routine emails flow through
without manual review, saving 20–30 hours per inbox per month.
```

---

## 7️⃣ Deployment Observation

Once deployed to Azure Container Instances:

```bash
# Check pipeline health in production
curl https://mailmind-api.azurewebsites.net/api/health/deep

# Stream live metrics
watch -n 5 'curl http://localhost:8000/api/metrics | grep mailmind_'

# View audit trail for a specific email
psql postgresql://... -c "
  SELECT stage, duration_ms, success, sla_met 
  FROM processing_metrics 
  WHERE email_id = '$EMAIL_ID'
  ORDER BY created_at;"
```

---

## 8️⃣ Code References

**Pipeline assembly:** `backend/app/graph/pipeline.py`
- `build_mailmind_graph()` — Constructs the 6-node graph
- `run_pipeline()` — Executes the pipeline for one email
- `stream=True` option — Stream step-by-step results to frontend (real-time UI updates)

**Node implementations:** `backend/app/agents/nodes.py`
- 6 functions: `ingest_node()`, `triage_node()`, `commitment_node()`, `calendar_node()`, `rag_node()`, `gate_node()`
- Each node handles its own LLM errors gracefully (fallback paths)

**Frontend UI:** 
- `frontend/components/triage/TriageExplainer.tsx` — 5-axis visualization
- `frontend/components/commitments/CommitmentGate.tsx` — Approval checkpoint
- `frontend/components/detail/PrecedentList.tsx` — Tone DNA precedents
- `frontend/components/detail/DraftPanel.tsx` — Generated reply

**State definition:** `backend/app/graph/state.py`
- `EmailAgentState` TypedDict — Full pipeline state (inputs, intermediate results, outputs)

---

## Summary

✅ **Pipeline is fully configured, observable, and production-ready.**
✅ **Three ways to view it:** Email UI, Prometheus metrics, health endpoints.
✅ **Live walkthrough script provided above** for stakeholder demos.
✅ **All nodes instrument with timing, logging, and metrics.**
✅ **Graceful fallbacks ensure no hard failures** (LLM unavailable = deterministic path).
