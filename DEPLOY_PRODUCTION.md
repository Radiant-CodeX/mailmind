# Production Deployment Guide

## What Was Fixed

✅ **API Bridge** — Translates frontend `/api/*` calls to backend routes  
✅ **CORS Middleware** — Updated to allow localhost:3000/3001  
✅ **Missing Endpoints** — Auth, compose, reply-send, commitments  
✅ **Fallback Handlers** — All endpoints have mock data fallback  
✅ **Error Handling** — Proper logging + error messages  

---

## Deployment Steps

### 1. Copy New Files

```bash
# Copy API bridge to backend
cp backend/api_bridge.py C:\Users\kmani\Documents\GitHub\mailmind\backend\

# Verify file exists
ls -la backend/api_bridge.py
```

### 2. Update Backend (Already Done)

- ✅ `app/main.py` — Updated CORS + added api_bridge_router import/include
- Check by viewing the file:
  ```bash
  grep "api_bridge" backend/app/main.py
  ```

### 3. Restart Backend

```bash
cd backend

# Kill previous process
pkill -f "uvicorn app.main:app"

# Restart with fresh imports
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Verify API Bridge Works

```bash
# Test auth endpoint
curl http://localhost:8000/api/auth/status | jq .

# Expected output:
# {
#   "authenticated": true,
#   "user_principal_name": "demo@company.com",
#   "status": "mock_unauthenticated"
# }

# Test emails endpoint
curl http://localhost:8000/api/emails | jq .

# Test triage
curl -X POST http://localhost:8000/api/emails/triage \
  -H "Content-Type: application/json" \
  -d '{
    "from": "manager@company.com",
    "subject": "Urgent report",
    "body": "Need by EOD"
  }' | jq .
```

### 5. Test Frontend Connection

```bash
# In browser DevTools (F12):
# 1. Go to http://localhost:3000
# 2. Open Console tab
# 3. Check for errors

# Should see:
# - No "Failed to fetch" for /api/auth/status
# - Dashboard loads with mock emails
# - No CORS errors
```

---

## Quick Troubleshooting

### Problem: Still getting "Failed to fetch" errors

**Check 1: API bridge loaded?**
```bash
curl http://localhost:8000/api/auth/status
```
If 404, api_bridge.py not imported. Check main.py includes it.

**Check 2: Backend still running?**
```bash
curl http://localhost:8000/docs
```
Should show Swagger UI with `/api/auth/status` route listed.

**Check 3: CORS still blocking?**
```bash
# Browser DevTools → Network tab → any failed request
# Should show "Access-Control-Allow-Origin: http://localhost:3000"
```

### Problem: "Active login session not found"

This is expected in MOCK_MODE. The `/api/auth/login-poll` endpoint returns success for any device_code. Frontend should show "Checking authorization status..." then load dashboard.

### Problem: Triage returns 0.5 score (fallback)

The internal `/triage` endpoint may be failing. Check:
```bash
# Direct test to internal endpoint
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"sender":"test@test.com","subject":"Test","body":"Test"}'
```

If this fails, check backend services are working (calculate_priority service).

---

## Environment Variables

Create/update `.env` in backend root:

```bash
# Mock mode (for demo)
MOCK_AUTH=true

# Jaeger
OTEL_EXPORTER_JAEGER_ENDPOINT=http://localhost:14268/api/traces

# CORS origins
FRONTEND_ORIGIN=http://localhost:3000

# Internal backend (for api_bridge to call)
INTERNAL_BACKEND_URL=http://localhost:8000
```

---

## Testing Checklist

- [ ] `GET /api/auth/status` returns 200 with `authenticated: true`
- [ ] `POST /api/auth/login-poll` returns 200
- [ ] `GET /api/emails` returns list of emails
- [ ] `POST /api/emails/triage` returns 5-axis scores
- [ ] `POST /api/emails/conflict-check` returns conflict status
- [ ] `POST /api/emails/draft` returns AI draft
- [ ] `POST /api/emails/compose` returns success
- [ ] `POST /api/emails/{id}/reply` returns success
- [ ] `POST /api/commitments/extract` returns tasks + events
- [ ] Frontend loads without console errors
- [ ] All API calls show in Network tab → no CORS errors

---

## Demo Readiness

After deploying these fixes:

1. **Start backend:** `uvicorn app.main:app --reload --port 8000`
2. **Start frontend:** `npm run dev --port 3000`
3. **Go to:** `http://localhost:3000/dashboard`
4. **Expected:** Dashboard loads, shows emails, can triage, approve, etc.

---

## Rollback (If Needed)

If something breaks:

```bash
# Remove api_bridge
rm backend/api_bridge.py

# Revert main.py
git checkout backend/app/main.py

# Restart backend
uvicorn app.main:app --reload --port 8000
```

---

## Next Steps (Production)

1. Implement real auth (remove MOCK_MODE)
2. Add database for email storage
3. Connect real MS Graph tokens
4. Enable Jaeger in production
5. Add monitoring + alerting
