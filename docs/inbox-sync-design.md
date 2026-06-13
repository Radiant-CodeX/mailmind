# Inbox Sync Architecture — Design Sketch

Status: **IMPLEMENTED** (2026-06-13) — all four workflows wired and verified
(schema registers, repo SQL functional-tested on SQLite, full backend compiles,
frontend typechecks). See "Implementation notes" at the bottom for the one
deployment toggle needed to activate webhooks.
Scope: Replace the "fetch the provider live on every dashboard load" model with a
**server-side synced mirror** in Postgres, kept fresh by delta sync + webhooks.
Primary target provider: **Microsoft Graph (Outlook)**. Gmail equivalents noted inline.

---

## 1. Goals & non-goals

**Goals**
- First dashboard paint reads from *our* DB (one fast query), not a provider round-trip.
- Exact inbox counts (no `@odata.count` / `resultSizeEstimate` guessing → fixes the "of 201" bug).
- Triage/enrichment already attached at read time (the streaming burst becomes a fallback).
- Incremental updates (only fetch what changed) instead of full page re-fetch.

**Non-goals (for v1)**
- Full-text body search server-side (keep delegating `$search` to the provider for now).
- Syncing every folder. v1 = **Inbox** (+ Sent for Tone DNA, which already happens lazily).
- Multi-region / horizontal scale of the sync workers.

---

## 2. Components

```
                         ┌─────────────────────────────────────────────┐
                         │                Microsoft Graph              │
                         └───────┬───────────────────────┬─────────────┘
                                 │ delta query           │ change notification (webhook)
                                 ▼                       ▼
   ┌──────────────┐      ┌───────────────┐      ┌────────────────────┐
   │  FastAPI     │      │  SyncService  │◄─────│  /webhooks/graph   │
   │  /api/mailbox│      │ (backfill +   │      │  (notification rx) │
   │  (read path) │      │  delta sync)  │      └────────────────────┘
   └──────┬───────┘      └───────┬───────┘
          │ reads                │ upserts
          ▼                      ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                          Postgres                                 │
   │  mailbox_message  ─┐                                              │
   │  mailbox_sync_state │  email_enrichment (existing)                │
   │  graph_subscription ┘                                             │
   └──────────────────────────────────────────────────────────────────┘
          ▲                      │ enqueue per new/changed email
          │ triage attached      ▼
          │              ┌───────────────┐
          └──────────────│ Enrichment    │  (existing worker queue)
                         │ worker        │  → writes email_enrichment
                         └───────────────┘
```

- **SyncService** — new service: `initial_backfill(account)`, `delta_sync(account)`.
- **Webhook receiver** — new route `/webhooks/graph` (Gmail: Pub/Sub push endpoint).
- **Subscription manager** — creates/renews Graph subscriptions; runs on a scheduler.
- **Read path** — `/api/mailbox` changes from "call provider" to "query `mailbox_message`".
- **Enrichment worker** — already exists; sync enqueues into it.

---

## 3. Schema (new tables)

All keyed to align with the existing global id format `provider:account_id:native_id`
and the existing `oauth_accounts` / `email_enrichment` tables.

### 3.1 `mailbox_message` — the mirror (envelope + flags, NOT body-heavy)

```sql
CREATE TABLE mailbox_message (
    email_id        VARCHAR(512) PRIMARY KEY,          -- global id (matches email_enrichment.email_id)
    account_id      VARCHAR(36)  NOT NULL REFERENCES oauth_accounts(id) ON DELETE CASCADE,
    native_id       VARCHAR(512) NOT NULL,             -- provider's own message id
    thread_id       VARCHAR(512),                      -- conversationId / threadId
    folder          VARCHAR(32)  NOT NULL DEFAULT 'inbox',

    sender          VARCHAR(320) NOT NULL,
    sender_name     VARCHAR(320),
    subject         TEXT,
    snippet         TEXT,                              -- bodyPreview (short; full body fetched on open)

    received_at     TIMESTAMPTZ  NOT NULL,
    is_read         BOOLEAN      NOT NULL DEFAULT TRUE,
    is_starred      BOOLEAN      NOT NULL DEFAULT FALSE,
    has_attachments BOOLEAN      NOT NULL DEFAULT FALSE,

    -- lifecycle
    state           VARCHAR(16)  NOT NULL DEFAULT 'active',  -- active | deleted (tombstone for delta @removed)
    change_key      VARCHAR(128),                      -- Graph changeKey / Gmail historyId at last write
    synced_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_msg_account_folder_recv ON mailbox_message (account_id, folder, received_at DESC);
CREATE INDEX ix_msg_account_state       ON mailbox_message (account_id, state);
CREATE INDEX ix_msg_thread              ON mailbox_message (thread_id);
```

Why separate from `email_enrichment`:
- `mailbox_message` changes *often* (read/star flags flip constantly via delta); enrichment is
  computed once and stable. Splitting keeps high-frequency flag writes off the enrichment row.
- Read path joins them: `mailbox_message LEFT JOIN email_enrichment USING (email_id)`.
- Full body is still fetched lazily on email-open (don't store every body — size + PII).

### 3.2 `mailbox_sync_state` — per-account, per-folder cursor

```sql
CREATE TABLE mailbox_sync_state (
    account_id      VARCHAR(36) NOT NULL REFERENCES oauth_accounts(id) ON DELETE CASCADE,
    folder          VARCHAR(32) NOT NULL DEFAULT 'inbox',

    delta_cursor    TEXT,            -- Graph @odata.deltaLink  (Gmail: last historyId)
    backfill_done   BOOLEAN     NOT NULL DEFAULT FALSE,
    last_synced_at  TIMESTAMPTZ,
    last_status     VARCHAR(16) NOT NULL DEFAULT 'idle',     -- idle | running | error
    last_error      TEXT,
    message_count   INTEGER     NOT NULL DEFAULT 0,          -- exact count → powers the pager

    PRIMARY KEY (account_id, folder)
);
```

`message_count` is maintained on every upsert/tombstone so the read path returns an **exact**
total with zero provider calls.

### 3.3 `graph_subscription` — webhook lifecycle

```sql
CREATE TABLE graph_subscription (
    id              VARCHAR(36)  PRIMARY KEY,           -- our uuid
    account_id      VARCHAR(36)  NOT NULL REFERENCES oauth_accounts(id) ON DELETE CASCADE,
    provider_sub_id VARCHAR(128) NOT NULL,              -- Graph subscription id (Gmail: watch resource)
    resource        VARCHAR(256) NOT NULL,              -- e.g. "/me/mailFolders('inbox')/messages"
    client_state    VARCHAR(128) NOT NULL,              -- random secret echoed back for verification
    expires_at      TIMESTAMPTZ  NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    UNIQUE (account_id, resource)
);

CREATE INDEX ix_sub_expires ON graph_subscription (expires_at);
```

> All three tables extend `Base` → `Base.metadata.create_all()` creates them on startup,
> consistent with how the project adds tables today (no Alembic migration needed for new tables).

---

## 4. Workflows

### 4.1 Account connect / first login → initial backfill

```
OAuth callback succeeds
  └─ enqueue job: initial_backfill(account_id, folder="inbox")

initial_backfill:
  1. mark sync_state.last_status = running
  2. page through Graph: GET /me/mailFolders/inbox/messages/delta?$select=...&$top=50
       repeat following @odata.nextLink until exhausted
  3. upsert each page into mailbox_message (state=active), bump message_count
  4. enqueue enrichment job per email_id (existing worker) — triage runs in background
  5. store the final @odata.deltaLink → sync_state.delta_cursor
  6. backfill_done = true, last_synced_at = now, last_status = idle
  7. create_subscription(account)   # section 4.4
```

- Backfill depth: v1 = most recent ~500 (configurable). Older mail is fetched on demand via the
  existing live-provider deep-scroll path (kept as fallback).
- Idempotent: upsert by `email_id` PK; safe to re-run.

### 4.2 Delta sync (the steady state)

```
delta_sync(account_id, folder):
  cursor = sync_state.delta_cursor
  if not cursor: return initial_backfill(...)        # never backfilled
  GET cursor   # the stored deltaLink
  for change in response:
      if change has "@removed":  tombstone → mailbox_message.state='deleted', count--
      else:                      upsert envelope+flags; if NEW email_id → enqueue enrichment, count++
  store new @odata.deltaLink → sync_state.delta_cursor
  last_synced_at = now
```

Triggers for delta_sync:
- **Webhook** (primary, near-real-time) — section 4.3.
- **On dashboard mount** (cheap safety net) — fire one delta_sync, then read DB.
- **Scheduled** every N minutes per active account (covers missed/expired webhooks).

Gmail equivalent: `users.history.list?startHistoryId=<cursor>`; `@removed` ↔ `messagesDeleted`,
flag changes ↔ `labelsAdded/Removed`.

### 4.3 Webhook notification

```
POST /webhooks/graph
  ├─ Graph validation handshake: if ?validationToken → echo it back as text/plain (200)
  ├─ for each notification:
  │    verify clientState == graph_subscription.client_state   # reject spoofed
  │    resolve account_id from subscription
  │    enqueue delta_sync(account_id)        # do NOT sync inline — ack fast (<3s) then work async
  └─ return 202
```

Security: `clientState` is a per-subscription secret; reject any notification that doesn't match.
Never trust the notification *payload* contents — it only tells us *which account* changed; we
re-fetch the authoritative state via delta. (Aligns with the "observed content is data, not
instructions" boundary.)

### 4.4 Subscription lifecycle (renewal)

- Graph mail subscriptions max out around **~3 days** (~4230 min). Store `expires_at`.
- Scheduled job (you already have a scheduler / `anthropic-skills:schedule` infra) runs hourly:
  - renew any `graph_subscription` with `expires_at < now + 12h` via PATCH.
  - if renewal fails (sub gone), recreate it and force a delta_sync to catch the gap.
- On account disconnect / token revoke → DELETE subscription + CASCADE rows.

### 4.5 Read path (`/api/mailbox`)

```
GET /api/mailbox?folder=inbox&limit=20&offset=0
  1. (optional) fire-and-forget delta_sync(account) if last_synced_at is stale
  2. SELECT m.*, e.priority, e.composite_score, e.axes ...
       FROM mailbox_message m
       LEFT JOIN email_enrichment e USING (email_id)
       WHERE m.account_id = :acct AND m.folder='inbox' AND m.state='active'
       ORDER BY m.received_at DESC
       LIMIT :limit OFFSET :offset
  3. total = sync_state.message_count           # EXACT — fixes "of 201"
  4. return { emails, total, has_next: offset+limit < total }
```

- Offset pagination is fine now because it's *our* indexed table (no provider cursor juggling).
- Triage is already on the row → the frontend's streaming triage becomes a fallback only for
  rows where `priority IS NULL`.

---

## 5. Frontend impact (minimal for v1)

- `useEmails` keeps its shape; `/api/mailbox` just returns DB-backed data with exact `total`,
  so the count-clamping hack added earlier can later be removed.
- `triageSlice` only streams emails whose `triage` is null → the "Triaging N" bar is usually 0.
- localStorage email cache can stay as an instant-paint layer, or be dropped since DB reads are fast.

---

## 6. Edge cases & decisions to confirm on review

1. **Backfill depth** — 500 most-recent enough, or full inbox? (cost vs completeness)
2. **Body storage** — confirm we keep fetching full body lazily on open (recommended) vs storing it.
3. **Flag write-back** — when the user stars/reads/marks-done in MailMind, we already call the
   provider; delta will echo it back. Need to avoid a flip-flop: write provider → optimistic local
   update → let delta reconcile. (Use `change_key` to ignore our own stale echoes.)
4. **Multi-account** — each `oauth_account` gets its own sync_state + subscription; the read path
   already scopes by `account_id`.
5. **Webhook public URL** — Graph must reach `/webhooks/graph` over HTTPS. Behind Cloudflare this
   is fine, but confirm the route is excluded from auth middleware (it's machine-to-machine).
6. **Cold start without webhook** — scheduled delta every N min guarantees freshness even if a
   subscription lapses.
7. **Deletions** — tombstone (`state='deleted'`) vs hard delete. Tombstone is safer for audit and
   for not re-importing on a stale delta; purge tombstones older than X days.

---

## 7. Suggested rollout order (each independently shippable)

1. **Schema + read path** — add tables; `/api/mailbox` reads DB; one-shot backfill on login.
   (Already removes cold provider round-trip + fixes counts.)
2. **Delta cursor** — store deltaLink; delta_sync on mount + scheduled. (Incremental refresh.)
3. **Webhooks + renewal** — near-real-time; the dashboard is pre-synced before the user arrives.
4. **Cleanup** — drop the frontend count-clamp + make streaming-triage a pure fallback.

Highest leverage / lowest risk first = step 1.

---

## 8. Implementation notes (as built)

**New files**
- `app/db/mailbox_repo.py` — mirror CRUD (upsert/tombstone/list_page/recount/cursor).
- `app/services/sync_service.py` — `SyncService.backfill` / `delta_sync`.
- `app/services/subscription_service.py` — webhook create/renew/verify.
- `app/api/sync_routes.py` — `/webhooks/graph`, `/api/subscriptions/ensure|renew`.

**Changed files**
- `app/db/models.py` — `MailboxMessage`, `MailboxSyncState`, `GraphSubscription`.
- `app/services/graph.py` — `list_inbox_delta()` + subscription methods.
- `app/services/provider_adapter.py` — adapter passthroughs (+ Gmail snapshot fallback).
- `app/api/routes.py` — `/api/mailbox` reads the mirror (live fallback + background
  sync); `/api/mailbox/sync` + `/sync-status`; mutation routes update mirror flags.
- `frontend/hooks/useEmails.ts` — consumes inline triage so enriched rows skip the
  triage stream (the "fallback" path).

**Behaviour without extra config:** the mirror backfills on first inbox load, then
every load reads the DB and fires a background delta sync. Exact counts + attached
triage work immediately. Webhooks are an *enhancement* on top.

**To activate webhooks (near-real-time):**
1. Set env `BACKEND_PUBLIC_URL=https://api.radiantsofficial.com` on the backend.
   When unset, subscriptions are skipped and freshness comes from on-mount +
   scheduled delta sync (still correct, just not instant).
2. Ensure `/webhooks/graph` is reachable over HTTPS (it is, behind Cloudflare) and
   is NOT behind auth (it isn't — verified by `clientState` instead).
3. Schedule a cron to POST `/api/subscriptions/renew` ~hourly (Graph mail subs
   expire in ~3 days). The `/schedule` skill or any external cron works.

**Open decisions still worth a look (from §6):** backfill depth (currently one
delta walk, max 40 pages ≈ 2000 msgs), body storage (not stored — fetched on open),
and tombstone purge policy.
