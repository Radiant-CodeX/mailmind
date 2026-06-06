# MailMind — Production Go-Live Checklist

Work top to bottom. Each section has a concrete verification step.

## 1. Azure AD app registration

- [ ] App registered in **Azure Portal → App registrations**
- [ ] **API permissions** granted *and admin-consented* (green check):
  - `Mail.ReadWrite`
  - `Mail.Send`
  - `Calendars.ReadWrite`
  - `Tasks.ReadWrite`
  - `User.Read`
- [ ] A **client secret** generated and copied (note the expiry date)
- [ ] For app-only/daemon mode: set `AZURE_USER_UPN` to the target mailbox

## 2. Backend `.env`

```ini
USE_MOCK_GRAPH=false
AZURE_TENANT_ID=<your-tenant-guid>
AZURE_CLIENT_ID=<your-app-client-id>
AZURE_CLIENT_SECRET=<your-secret>
GRAPH_SCOPES=https://graph.microsoft.com/.default

# Azure OpenAI — endpoint must be the BASE url only:
#   https://<resource>.openai.azure.com/
# (the app strips any /openai/deployments/... path automatically, but keep it clean)
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_CHAT_DEPLOYMENT=<deployment-name>
AZURE_OPENAI_API_VERSION=2024-12-01-preview

APPROVAL_TOKEN=<generate a strong random secret>
FRONTEND_ORIGIN=https://your-production-domain.com

# Optional monitoring
SENTRY_DSN=<your-sentry-dsn>          # leave blank to disable
APP_ENV=production
```

> **Secrets hygiene:** `.env` and `.env.*` are gitignored (verified). Never commit real
> keys. Rotate the `AZURE_CLIENT_SECRET` and `AZURE_OPENAI_API_KEY` that were previously
> present in the repo's `.env` before going public.

## 3. Verify live wiring (automated)

```bash
cd backend
python scripts/verify_live.py
```

This checks: Graph token acquisition, read access to all mail folders, and an
Azure OpenAI chat round-trip. Exit code is non-zero if any required check fails —
safe to use as a deploy gate.

## 4. Run the test suites

```bash
# Backend
cd backend
PYTHONPATH=. pytest tests/ -v

# Frontend
cd frontend
npm test
```

## 5. Frontend `.env.local`

```ini
NEXT_PUBLIC_API_URL=https://api.your-production-domain.com
NEXT_PUBLIC_SENTRY_DSN=<optional>
```

## 6. Deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

- [ ] `GET /api/health` returns `{"status":"ok","mode":"live"}`
- [ ] `GET /api/ready` returns `{"ready":true, ...}`
- [ ] Sign in via Microsoft on the frontend completes the device-code flow
- [ ] Triage scores render on real inbox mail (confirms Azure OpenAI path is active)

## 7. Post-deploy smoke test

- [ ] Send a reply to a real email → arrives
- [ ] Compose a new email → arrives
- [ ] Move an email to Trash → disappears from Inbox, appears in Trash in Outlook
- [ ] Restore from Trash → returns to Inbox
- [ ] Confirm a commitment → task/event created in To-Do / Calendar
