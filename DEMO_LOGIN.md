# Demo Login Setup

One-click demo account for judges, stakeholders, and presentations. Pre-loaded with 10 realistic emails, full triage scores, and all features ready to explore.

---

## Quick Start

### 1. Seed Demo Account (One-Time Setup)

```bash
cd backend

# Create database and seed demo account
python scripts/seed_demo_account.py --db postgresql://user:pass@host/db

# Expected output:
# ✓ Created user [uuid]
# ✓ Created OAuth account for demo@mailmind.app
# ✓ Created 10 demo inbox messages
# ✓ Created enrichment cache for all emails
# ✓ Created tone profile
# 
# ✅ DEMO ACCOUNT CREATED SUCCESSFULLY
# ==================================================
# Inbox:
#   10 demo emails loaded (CRITICAL, HIGH, MEDIUM, LOW)
```

### 2. Access Demo Login (Always Available)

**Frontend:** `http://localhost:3000/api/demo/login`

You'll see a beautiful one-click login page:

```
📧 MailMind Demo

Click below to access the demo account with pre-loaded emails...

[Enter Demo Button]

Pre-loaded with 10 realistic emails
✓ Five-axis triage scoring
✓ Draft generation with Tone DNA
✓ Commitment extraction
✓ Calendar conflict detection
```

Click **"Enter Demo"** → Instant login → Dashboard with 10 emails ready to explore.

---

## Demo Account Details

| Property | Value |
|----------|-------|
| **Email** | `demo@mailmind.app` |
| **Provider** | Google (mock OAuth) |
| **Session** | 24 hours TTL |
| **Inbox** | 10 realistic emails |
| **Tone DNA** | VP/Director persona (55 sent emails) |
| **Triage Cache** | All emails pre-scored |

---

## Demo Inbox Emails

10 emails across all priority levels, with realistic bodies and deadlines:

| # | From | Subject | Priority | Deadline |
|---|------|---------|----------|----------|
| 1 | Victoria Hayes (Nexus Capital) | $4.2M wire transfer | **CRITICAL** | Today 3 PM |
| 2 | Daniel Park (CTO) | Production down — revenue impact | **CRITICAL** | Today (urgent) |
| 3 | James Whitfield (Legal) | MSA countersignature | **HIGH** | Friday 5 PM |
| 4 | Priya Nair (VP Eng) | Headcount approval — 3 seniors | **HIGH** | Monday 9 AM |
| 5 | CrowdStrike | Security alert — endpoint policy | **HIGH** | ASAP |
| 6 | Sprint Bot | Sprint 24 retro — action items | **MEDIUM** | This week |
| 7 | Stripe | Account verification | **MEDIUM** | 14-day deadline |
| 8 | Marketing | Brand refresh feedback | **MEDIUM** | Thursday |
| 9 | TLDR | Tech Newsletter | **LOW** | FYI |
| 10 | Notion | Workspace report | **LOW** | FYI |

---

## Demo Features Ready

- ✅ **Five-Axis Triage** — All emails scored across deadline, sender authority, sentiment, action type, thread decay
- ✅ **Tone DNA** — 55 sent emails in profile, drafts match VP tone (direct, short sentences, "Thanks" sign-off)
- ✅ **Commitment Extraction** — Deadlines + action items auto-extracted (cached in DB)
- ✅ **Calendar Conflicts** — 5 calendar events deliberately overlap with email deadlines (demo the conflict detection)
- ✅ **Draft Generation** — Click "Generate Draft" → AI generates reply in demo tone
- ✅ **RAG Precedents** — Similar past emails + context injected into drafts
- ✅ **Priority Override** — Click "Mark Done" → email removed from inbox (persisted)

---

## Demo Workflow (5-Minute Presentation)

```
1. Login (30 sec)
   → Click "Enter Demo"
   → Instant session
   
2. Inbox (1 min)
   → See 10 emails with CRITICAL/HIGH/MEDIUM/LOW badges
   → Scroll through, note priority scores
   
3. Email Detail (1.5 min)
   → Click email #1 (wire transfer, CRITICAL)
   → Scroll to "Five-Axis Triage Breakdown"
   → Show 5 axes with scores + reasoning
   → Note calendar conflict badge ("⚠️ CONFLICT: Investor Relations meeting")
   
4. Draft Generation (1.5 min)
   → Click "Generate Draft" button
   → Show LLM generating reply
   → Note Tone DNA system prompt prefix
   → See RAG citations (similar past emails)
   
5. Commitments (1 min)
   → Show extracted action items
   → Show calendar conflict detection
   → Click "Create Event" (would create calendar entry)
```

---

## Production Deployment

Demo login is always available (no configuration needed).

```bash
# Deploy normally
docker compose -f docker-compose.yml \
               -f docker-compose.prod.yml \
               up -d

# Access demo at: https://your-domain.com/api/demo/login
```

To remove demo access later, simply delete the demo account from the database (see below).

---

## Troubleshooting

### "Demo account not found"

**Problem:** Running demo login but seed script wasn't run.

**Fix:**
```bash
cd backend
python scripts/seed_demo_account.py --db "$DATABASE_URL"
```


### Emails not showing

**Problem:** Demo account created but emails not visible in inbox.

**Check:**
```bash
# Verify mailbox_message rows exist
docker exec -i mailmind-postgres psql -U postgres -d mailmind -c \
  "SELECT COUNT(*) FROM mailbox_message WHERE account_id = 'demo-account-id';"
```

### Can't click "Enter Demo"

**Problem:** Button not responding.

**Check browser console:**
```javascript
fetch('/api/demo/login', { method: 'POST' })
  .then(r => r.json())
  .then(console.log)
```

---

## Cleaning Up Later

### Delete Demo Account

```bash
# Remove demo account from database
docker exec -i mailmind-postgres psql -U postgres -d mailmind -c \
  "DELETE FROM users WHERE id = (SELECT user_id FROM oauth_accounts WHERE email = 'demo@mailmind.app');"

# Verify it's gone
docker exec -i mailmind-postgres psql -U postgres -d mailmind -c \
  "SELECT * FROM oauth_accounts WHERE email = 'demo@mailmind.app';"
# (should return no rows)
```

After deletion, attempting to access `/api/demo/login` will return:
```json
{"detail": "Demo account 'demo@mailmind.app' not found."}
```

### Delete Demo Account (Remove Access)

```bash
# Delete the demo account entirely
docker exec -i mailmind-postgres psql -U postgres -d mailmind -c \
  "DELETE FROM users WHERE id = (SELECT user_id FROM oauth_accounts WHERE email = 'demo@mailmind.app');"
```

---

## Features Not in Demo

- ❌ Real OAuth (uses pre-configured mock account)
- ❌ Webhook subscriptions (can't receive live updates, but delta sync works)
- ❌ Email sending (draft generation only, no send button)
- ❌ Task creation in Microsoft To-Do (calendar events only, but flow is the same)

---

## API Reference

### GET /api/demo/login

Returns an HTML page with one-click login button.

**Response:** HTML with inline JavaScript

**Status codes:**
- `200` — HTML page rendered
- `404` — Demo account not found (run seed script)

### POST /api/demo/login

Creates a session for the demo account and returns session token.

**Request:** (no body required)

**Response:**
```json
{
  "session_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "demo@mailmind.app",
  "message": "Demo login successful. Redirecting to dashboard..."
}
```

**Status codes:**
- `200` — Session created
- `404` — Demo account not found (run seed script)
- `500` — Server error

**Usage:**
```bash
curl -X POST http://localhost:8000/api/demo/login | jq .session_token
```

---

**Ready to demo!** 🚀
