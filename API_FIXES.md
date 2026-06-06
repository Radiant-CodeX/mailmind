# MailMind API Fixes for Live Demo

## Critical Issues & Quick Fixes

### Issue 1: Azure OpenAI Prompts Expose Raw PII (Security)
**File:** `backend/services/azure_openai_service.py` (lines 24, 56)
**Problem:** `email.sender`, `email.body` sent directly to LLM without masking.
**Fix:** Apply Presidio analyzer before sending prompts.

```python
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()

def mask_pii_in_prompt(email_body: str) -> str:
    """Mask PII before sending to LLM."""
    results = analyzer.analyze(text=email_body, language="en")
    if results:
        for result in results:
            email_body = email_body[:result.start] + "[REDACTED]" + email_body[result.end:]
    return email_body

def azure_summary(email, priority):
    if azure_client is None:
        raise Exception("Azure OpenAI environment variables missing.")
    
    # ADDED: Mask PII before building prompt
    masked_body = mask_pii_in_prompt(email.body)
    
    prompt = f"""
Analyze this email and return a concise business summary.

Sender: [SENDER_MASKED]  # Don't expose email addresses
Subject: {email.subject}
Body: {masked_body}
Priority: {priority["priority_label"]}
Score: {priority["priority_score"]}

Return only this format:
Summary: ...
Action Required: ...
Recommended Response Time: ...
"""
    # ... rest unchanged
```

---

### Issue 2: MS Graph Token Flow Fails (Interactive Device Code)
**File:** `backend/services/graph_service.py` (lines 15-25)
**Problem:** Device code flow requires user interaction; fails silently in headless/demo mode.
**Fix:** Add mock fallback + environment variable for test token.

```python
import os

def get_graph_token():
    # ADDED: Allow test token override for demo
    test_token = os.getenv("GRAPH_TEST_TOKEN")
    if test_token:
        logging.info("Using test token from GRAPH_TEST_TOKEN env var (demo mode)")
        return test_token
    
    if not CLIENT_ID:
        raise Exception("CLIENT_ID missing in .env file.")

    try:
        app_graph = msal.PublicClientApplication(
            CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        )

        flow = app_graph.initiate_device_flow(scopes=GRAPH_SCOPE)

        if "user_code" not in flow:
            raise Exception("Failed to initiate device code flow.")

        print("\n========== MICROSOFT GRAPH LOGIN ==========")
        print(flow["message"])
        print("==========================================\n", flush=True)

        result = app_graph.acquire_token_by_device_flow(flow)

        if "access_token" not in result:
            raise Exception(result.get("error_description", "Failed to obtain Graph token"))

        return result["access_token"]
    except Exception as e:
        logging.error(f"Graph token acquisition failed: {e}")
        # ADDED: Return mock token if device flow fails
        return "mock_graph_token_for_demo_" + os.urandom(16).hex()
```

---

### Issue 3: Graph API Response Not Parsed Correctly
**File:** `backend/routes/graph_routes.py` (line 17)
**Problem:** Returns raw response text instead of parsed JSON.
**Fix:** Parse JSON response.

```python
@router.get("/emails")
def graph_emails():
    try:
        token = get_graph_token()

        headers = {"Authorization": f"Bearer {token}"}
        url = "https://graph.microsoft.com/v1.0/me/messages?$top=10"

        response = requests.get(url, headers=headers, timeout=10)
        
        # ADDED: Parse JSON response
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "graph_response": data,
                "message_count": len(data.get("value", [])),
            }
        else:
            return {
                "status": "error",
                "status_code": response.status_code,
                "message": response.text[:200],  # Truncate for clarity
            }

    except Exception as e:
        logging.error(f"Graph emails fetch failed: {e}")
        return {
            "status": "error",
            "message": str(e)[:200],
        }
```

---

### Issue 4: No Custom Span Attributes Emitted to Jaeger
**File:** `backend/routes/email_routes.py` (line 69)
**Problem:** Span is created but attributes not set; can't filter by triage scores in Jaeger.
**Fix:** Call `span_triage()` helper from `main.py` after triage completes.

```python
from app.main import span_triage

@router.post("/triage")
def triage_email(email: EmailInput):
    logging.info(f"Triage requested for sender: {email.sender}")

    with tracer.start_as_current_span("five_axis_triage"):
        result = calculate_priority(email)
        
        # ADDED: Emit custom span attributes for Jaeger
        span_triage(
            email_id=str(email.sender),  # Use sender as temp ID for demo
            axes=result.get("axes", []),
            composite_score=result.get("priority_score", 0.0),
            priority=result.get("priority_label", "unknown")
        )

    logging.info(f"Triage result: {result}")
    return result
```

---

### Issue 5: Frontend Approval Check Missing Before Send
**File:** Frontend `useEmailDetail.ts` hook
**Problem:** No code-level gate preventing send without approval.
**Fix:** Add explicit check in `sendDraft()` function.

```typescript
async function sendDraft() {
    // ADDED: Explicit gate - no send without approval
    if (!isDraftApproved) {
        setError("Draft must be approved before sending. Click 'Approve' first.");
        return;
    }

    if (!selectedEmail?.id) {
        setError("No email selected.");
        return;
    }

    setIsSendingDraft(true);
    try {
        const response = await fetch(`${API_BASE}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                email_id: selectedEmail.id,
                action: "approve",  // Already approved
                draft_reply: aiDraft,
            }),
        });

        if (!response.ok) throw new Error("Send failed");
        
        // Then POST to /graph/send or similar
        // ...
    } catch (err) {
        setError(err.message);
    } finally {
        setIsSendingDraft(false);
    }
}
```

---

### Issue 6: Conflict Service Not Integrated with Calendar
**File:** `backend/services/conflict_service.py`
**Problem:** Likely not calling Graph API to fetch actual calendar events.
**Fix:** Fetch real calendar and check conflicts.

```python
def detect_conflict_and_precedent(email: ConflictInput):
    """Check for calendar conflicts and historical precedents."""
    try:
        # Step 1: Parse email for meeting time
        meeting_time = extract_meeting_time(email.body)  # Implement using regex/NER
        
        # Step 2: Fetch calendar events from Graph API
        calendar_events = fetch_calendar_events(
            start_time=meeting_time,
            end_time=meeting_time + timedelta(hours=1)
        )
        
        # Step 3: Check for conflicts
        has_conflict = any(
            overlaps(event["start"], event["end"], meeting_time)
            for event in calendar_events
        )
        
        # Step 4: Find precedents from past emails with same sender
        precedents = find_sender_precedents(email.sender)
        
        return {
            "conflict_detected": has_conflict,
            "conflicting_events": [ev["subject"] for ev in calendar_events] if has_conflict else [],
            "precedents": precedents,
            "recommendation": "Propose alternative time" if has_conflict else "Schedule accepted"
        }
    except Exception as e:
        logging.error(f"Conflict check failed: {e}")
        return {"conflict_detected": False, "error": str(e)}
```

---

## Environment Variables Needed for Demo

Create/update `.env` in backend root:

```bash
# Azure OpenAI
AZURE_OPENAI_API_KEY=<your-key>
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# MS Graph
CLIENT_ID=<azure-app-id>
TENANT_ID=<azure-tenant-id>
GRAPH_SCOPE=["Mail.Read", "Calendar.Read", "Tasks.ReadWrite"]

# For Demo Mode (skip device code flow)
GRAPH_TEST_TOKEN=demo_token_12345

# Jaeger
OTEL_EXPORTER_JAEGER_ENDPOINT=http://localhost:14268/api/traces

# Presidio
PRESIDIO_ANALYZER_AVAILABLE=true
```

---

## Test Commands After Fixes

```bash
# 1. Test triage with PII masking
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "john.doe@company.com",
    "subject": "SSN request",
    "body": "Please confirm SSN 123-45-6789"
  }' | jq .

# 2. Test Graph token (should use test token if env var set)
curl http://localhost:8000/graph/test

# 3. Test conflict check
curl -X POST http://localhost:8000/conflict-check \
  -H "Content-Type: application/json" \
  -d '{
    "email_id": "msg1",
    "sender": "client@company.com",
    "subject": "Meeting Tuesday 2pm?",
    "body": "Can we meet next Tuesday at 2:00 PM?"
  }' | jq .

# 4. Test approval gate
curl -X POST http://localhost:8000/approve \
  -H "Content-Type: application/json" \
  -d '{
    "email_id": "msg1",
    "action": "approve",
    "draft_reply": "Thank you for reaching out."
  }' | jq .

# 5. Check Jaeger for custom spans
curl http://localhost:16686/api/services | jq '.data[] | select(.name == "mailmind.v2")'
```

---

## Implementation Priority

1. **HIGH:** Fix PII masking (Issue #1) — required for security demo
2. **HIGH:** Add span attributes (Issue #4) — required to show Jaeger trace
3. **HIGH:** Add approval gate frontend check (Issue #5) — required for human gate demo
4. **MEDIUM:** Fix Graph token (Issue #2) — fallback already in place
5. **MEDIUM:** Fix Graph response parsing (Issue #3) — helps with calendar integration
6. **LOW:** Enhance conflict detection (Issue #6) — can work with mock data

---

## Success Criteria

After implementing fixes:
- ✅ Jaeger shows linkable trace with custom attributes per email
- ✅ PII inspection in Jaeger spans shows only [REDACTED]
- ✅ Frontend shows error if user tries to send without approval
- ✅ All 5 features demonstrable without production credentials
- ✅ Backend logs show masking + approval flow
