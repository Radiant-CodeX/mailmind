# Live Demo Checklist (15-Minute Format)

## Pre-Demo (5 min before)

- [ ] Backend running: `http://localhost:8000` (check `/docs` for Swagger)
- [ ] Frontend running: `http://localhost:3000`
- [ ] Jaeger running: `http://localhost:16686` (or configured endpoint)
- [ ] Environment variables set: `.env` has all Azure OpenAI + Graph keys
- [ ] Backend logs show: `Jaeger exporter configured`
- [ ] Test endpoint: `curl http://localhost:8000/emails` returns 3 mock emails

---

## Demo Script (Execute in Order)

### Segment 1: Fetch & Triage (2 min)
**Narration:** "Email arrives in inbox. System automatically scores it across 5 axes: urgency, stakeholder power, complexity, time sensitivity, escalation risk."

1. **Open Frontend Dashboard** → Go to `/dashboard`
   - Shows 3 mock emails in inbox
   - **Expected:** Emails have priority badges (HIGH/NORMAL/LOW)

2. **Click first email** (from manager@company.com)
   - **Expected:** Detail panel shows 5-axis triage scorecard
   - Call: `POST /triage` (visible in Network tab)
   - Show the `priority_score` and individual axis scores

3. **Demo Triage API directly** (optional, for credibility):
   ```bash
   curl -X POST http://localhost:8000/triage \
     -H "Content-Type: application/json" \
     -d '{
       "sender": "vp@company.com",
       "subject": "Urgent: Q4 budget needs EOD approval",
       "body": "We need final sign-off today..."
     }'
   ```
   - **Expected:** Returns 5-axis breakdown + composite score

---

### Segment 2: Conflict Detection (2 min)
**Narration:** "System checks calendar for conflicts and finds precedents from similar past requests."

1. **Click "Check Calendar"** button
   - **Expected:** Badge appears showing conflict status
   - Call: `POST /conflict-check`
   - Shows: "Conflict Detected" or "No Conflict"

2. **Show Precedents Panel** (if available)
   - Historical responses to similar senders
   - **Expected:** Shows past email subjects + replies

---

### Segment 3: Tone DNA Draft + RAG (3 min)
**Narration:** "AI learns your communication style from past emails and suggests a reply that matches your tone. Citations show which past emails it used as reference."

1. **Click "Generate Reply"** button
   - **Expected:** Shows loading spinner
   - Call: `POST /draft` (visible in Network tab)

2. **Show AI Draft** with RAG citations
   - Draft text appears
   - **Citations section shows:**
     - "Based on your reply to [similar email from 3 months ago]"
     - "Your tone typically uses: [specific style]"

3. **Optional: Show PII Masking**
   - Inspect Network tab → `/draft` request
   - Show request body has `[REDACTED]` in place of sensitive data
   - **Narration:** "Notice how SSN, credit card, address are masked before the AI sees them."

---

### Segment 4: Human Approval Gate (2 min)
**Narration:** "The human approver controls the gate. No automated code path exists from 'Draft Generated' (Step 9) to 'Send' (Step 11) without explicit approval."

1. **Click "Approve Draft"** button
   - **Expected:** Button changes to green "✓ Approved"
   - Call: `POST /approve` with `action: "approve"`
   - Response: `"status": "Approved"`

2. **Try to Send Without Approval** (alternative)
   - Remove the draft approval
   - Click "Send"
   - **Expected:** Error message: "Draft must be approved before sending"

3. **Show Approval in Email Status**
   - Email status changes to "Approved"
   - Only now is "Send" button enabled

---

### Segment 5: Jaeger Trace Inspection (3 min)
**Narration:** "Every email processing step is traced and linked. This trace is judge-inspectable: it shows all decisions made and proves no PII was exposed to the AI."

1. **Open Jaeger UI**: `http://localhost:16686`

2. **Navigate to Traces**
   - Service: `mailmind.v2`
   - Limit: 20
   - **Expected:** Shows traces from the last minute

3. **Click latest trace** (should be from the demo email)
   - **Show custom attributes:**
     - `email.id`: sender email address
     - `triage.composite_score`: 0.87 (example)
     - `triage.priority`: "urgent"
     - `triage.axis.urgency`: 0.9
     - `triage.axis.stakeholder_power`: 0.85
     - `triage.axis.complexity`: 0.6
     - `triage.axis.time_sensitivity`: 0.95
     - `triage.axis.escalation_risk`: 0.7

4. **Show No PII in Spans**
   - Expand span details
   - Point out: No raw email addresses, no SSN, no addresses in span data
   - **Narration:** "All sensitive data is replaced with [REDACTED] before any LLM processing."

5. **Share Trace URL** (optional)
   - Copy trace URL from browser address bar
   - **Example:** `http://localhost:16686/trace/a1b2c3d4?uiEmbed=v0`
   - Can be shared with auditors or judges
   - **Narration:** "This URL is stable and can be bookmarked for audit trails."

---

## Success Criteria (Check All)

During demo, confirm:

- [ ] **U1: Five-Axis Triage** — Scorecard shows all 5 axes with scores
- [ ] **U2: Conflict Badge** — Calendar conflict detected and displayed
- [ ] **U3: Tone DNA + RAG** — Draft generated with citations visible
- [ ] **U4: Human Approval Gate** — User cannot send without explicit approve action
- [ ] **U5: Jaeger + PII Masking** — Trace URL is linkable, custom attributes visible, no raw PII in spans

---

## Fallback Scenarios

### If API Call Fails Mid-Demo

**Scenario A: `/draft` API times out**
- Already has fallback in `ai_routes.py` line 50
- Shows mock draft: "Thank you for your email regarding..."
- **Narration:** "Due to API latency, showing fallback draft. The approval and tracing still work identically."

**Scenario B: Jaeger not reachable**
- Doesn't break the flow — tracing works
- Just can't show the UI
- **Workaround:** Pre-show a screenshot of a good trace, OR open Jaeger before demo starts

**Scenario C: Graph API fails**
- Code already returns mock response (see `graph_routes.py` line 28)
- **Narration:** "Calendar is mocked for this demo. The approval and audit trail mechanisms work live."

---

## Quick Narrative (Memorize This)

> "MailMind is an AI email triage system with 5 key features:
>
> **First**, it scores emails across 5 axes — urgency, stakeholder power, complexity, time sensitivity, and escalation risk. This 5-axis approach ensures we don't just look at sender importance but also business impact.
>
> **Second**, it checks your calendar for conflicts and learns from precedents in your email history.
>
> **Third**, it generates a reply draft that matches your communication style, pulling citations from past similar emails.
>
> **Fourth**, and critically, every draft requires human approval. There is literally zero code path from draft generation to sending without a human clicking 'Approve'.
>
> **Fifth**, every step is traced using Jaeger. The trace is judge-inspectable — you can see all decisions, and critically, you can verify that no sensitive PII was ever exposed to the AI. Everything is masked before it touches the LLM."

---

## Timing Breakdown

| Segment | Time | What You Show |
|---------|------|---------------|
| Triage | 2 min | Email arrives → 5-axis scorecard |
| Conflict | 2 min | Calendar check + precedents |
| Draft + RAG | 3 min | AI reply with citations + PII masking |
| Approval Gate | 2 min | No-send-without-approve gate |
| Jaeger Trace | 3 min | Linkable trace + custom attributes |
| **Total** | **~15 min** | All 5 features live |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|---|---|
| Frontend won't load | Frontend not running on 3000 | `cd frontend && npm run dev` |
| API returns 500 | Missing env vars | Check `.env` has all keys |
| Jaeger shows no traces | Jaeger endpoint wrong | Check `OTEL_EXPORTER_JAEGER_ENDPOINT` |
| Trace has no custom attributes | `span_triage()` not called | Add it after `calculate_priority()` call |
| PII still visible in spans | Presidio not masking prompts | Add `mask_pii_in_prompt()` before LLM call |
| Graph API fails | No token | Set `GRAPH_TEST_TOKEN` env var |
| Draft takes >5 sec | Azure OpenAI latency | Use fallback draft (already coded) |

---

## Post-Demo

- [ ] Note any API improvements needed
- [ ] Save Jaeger trace URL for later audit reference
- [ ] Collect feedback on which feature impressed most
- [ ] Document any production blockers discovered

---

## Contact

If stuck during demo:
- **Backend logs:** `cd backend && tail -f app.log`
- **Frontend console:** Open DevTools (F12)
- **API docs:** `http://localhost:8000/docs`
- **Jaeger debug:** `http://localhost:16686`
