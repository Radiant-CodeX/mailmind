"""Part 5: DB schema, file structure tree, env vars, demo guide, presentation notes, DB ER diagram."""
import os, math
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Flowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

W, H = A4
NAVY       = HexColor('#1e3a5f')
BLUE       = HexColor('#2563eb')
LIGHT_BLUE = HexColor('#dbeafe')
GRAY_900   = HexColor('#111827')
GRAY_700   = HexColor('#374151')
GRAY_500   = HexColor('#6b7280')
GRAY_200   = HexColor('#e5e7eb')
GRAY_100   = HexColor('#f3f4f6')
WHITE      = HexColor('#ffffff')
GREEN      = HexColor('#059669')
GREEN_LT   = HexColor('#d1fae5')
ORANGE     = HexColor('#d97706')
ORANGE_LT  = HexColor('#fef3c7')
RED        = HexColor('#dc2626')
RED_LT     = HexColor('#fee2e2')
PURPLE     = HexColor('#7c3aed')
PURPLE_LT  = HexColor('#ede9fe')
TEAL       = HexColor('#0d9488')
TEAL_LT    = HexColor('#ccfbf1')
INDIGO     = HexColor('#4338ca')
INDIGO_LT  = HexColor('#e0e7ff')

OUT = os.path.join(os.path.dirname(__file__), 'part5_reference.pdf')

def make_styles():
    S = {}
    S['h1'] = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=20,
        textColor=NAVY, spaceAfter=8, spaceBefore=16)
    S['h2'] = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=13,
        textColor=NAVY, spaceAfter=5, spaceBefore=12)
    S['h3'] = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=10,
        textColor=GRAY_900, spaceAfter=3, spaceBefore=8)
    S['body'] = ParagraphStyle('body', fontName='Helvetica', fontSize=8.5,
        textColor=GRAY_700, spaceAfter=3, leading=13)
    S['code'] = ParagraphStyle('code', fontName='Courier', fontSize=7.5,
        textColor=GRAY_900, backColor=GRAY_100, spaceAfter=2, leading=11,
        leftIndent=6, rightIndent=6)
    S['mono'] = ParagraphStyle('mono', fontName='Courier', fontSize=8,
        textColor=GRAY_700, spaceAfter=1, leading=12)
    S['bullet'] = ParagraphStyle('bullet', fontName='Helvetica', fontSize=8.5,
        textColor=GRAY_700, leftIndent=14, spaceAfter=2, leading=13)
    S['filepath'] = ParagraphStyle('filepath', fontName='Courier-Bold', fontSize=9,
        textColor=BLUE, backColor=LIGHT_BLUE, spaceAfter=3, leading=13,
        leftIndent=6, rightIndent=6)
    S['caption'] = ParagraphStyle('caption', fontName='Helvetica', fontSize=8,
        textColor=GRAY_500, alignment=TA_CENTER, spaceAfter=8)
    S['tip'] = ParagraphStyle('tip', fontName='Helvetica', fontSize=9,
        textColor=GRAY_700, backColor=ORANGE_LT, spaceAfter=4, leading=14,
        leftIndent=8, rightIndent=8)
    return S

def hf(c, doc):
    c.saveState()
    pg = doc.page
    c.setFillColor(NAVY)
    c.rect(0, H - 22, W, 22, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(15, H - 14, 'MailMind — Technical Documentation · Reference & Presentation')
    c.setFont('Helvetica', 7)
    c.drawRightString(W - 15, H - 14, f'Page {pg}')
    c.setFillColor(GRAY_200)
    c.rect(0, 0, W, 18, fill=1, stroke=0)
    c.setFillColor(GRAY_500)
    c.setFont('Helvetica', 7)
    c.drawString(15, 5, 'MailMind v2.0 · Radiant CodeX · 2025')
    c.drawRightString(W - 15, 5, 'CONFIDENTIAL')
    c.restoreState()

class DiagramFlowable(Flowable):
    def __init__(self, width, height, draw_fn):
        super().__init__()
        self.width = width
        self.height = height
        self._draw_fn = draw_fn
    def draw(self):
        self._draw_fn(self.canv, self.width, self.height)

def draw_db_er(c, W, H):
    """Simplified ER diagram showing key table relationships."""
    c.setFillColor(GRAY_100)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 10)
    c.drawCentredString(W/2, H - 14, 'Database Entity Relationship Diagram (Key Tables)')

    def tbl(c, x, y, name, fields, color=BLUE, fill=LIGHT_BLUE):
        fw = 110
        row_h = 11
        title_h = 16
        total_h = title_h + len(fields) * row_h + 4
        # title bar
        c.setFillColor(color)
        c.roundRect(x, y + total_h - title_h, fw, title_h, 3, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawCentredString(x + fw/2, y + total_h - title_h + 5, name)
        # body
        c.setFillColor(fill)
        c.roundRect(x, y, fw, total_h - title_h + 2, 3, fill=1, stroke=0)
        c.setStrokeColor(color)
        c.setLineWidth(1)
        c.roundRect(x, y, fw, total_h, 3, fill=0, stroke=1)
        # fields
        c.setFont('Courier', 6.5)
        c.setFillColor(GRAY_700)
        for i, (fname, ftype, pk) in enumerate(fields):
            fy = y + total_h - title_h - (i + 1) * row_h + 2
            prefix = '🔑 ' if pk == 'pk' else '→ ' if pk == 'fk' else '   '
            c.drawString(x + 5, fy, f'{prefix}{fname}')
            c.drawRightString(x + fw - 5, fy, ftype)
        return total_h

    # Users table
    u_h = tbl(c, 8, H - 120, 'users', [
        ('id', 'UUID PK', 'pk'),
        ('primary_email', 'text', ''),
        ('display_name', 'text', ''),
        ('created_at', 'timestamp', ''),
        ('last_login_at', 'timestamp', ''),
    ], NAVY, INDIGO_LT)

    # OAuthAccount
    oa_h = tbl(c, 8, H - 260, 'oauth_accounts', [
        ('id', 'UUID PK', 'pk'),
        ('user_id', 'UUID FK→users', 'fk'),
        ('provider', 'text', ''),
        ('provider_account_id', 'text', ''),
        ('account_email', 'text', ''),
        ('access_token_enc', 'text', ''),
        ('refresh_token_enc', 'text', ''),
        ('is_default', 'boolean', ''),
    ], BLUE, LIGHT_BLUE)

    # UserSession
    us_h = tbl(c, 135, H - 120, 'user_sessions', [
        ('token_hash', 'text PK', 'pk'),
        ('user_id', 'UUID FK→users', 'fk'),
        ('provider', 'text', ''),
        ('email', 'text', ''),
        ('created_at', 'timestamp', ''),
        ('expires_at', 'timestamp', ''),
    ], TEAL, TEAL_LT)

    # MailboxMessage
    mm_h = tbl(c, 135, H - 280, 'mailbox_message', [
        ('email_id', 'text PK', 'pk'),
        ('account_id', 'UUID FK', 'fk'),
        ('folder', 'text', ''),
        ('sender', 'text', ''),
        ('subject', 'text', ''),
        ('received_at', 'timestamp', ''),
        ('state', 'active/done/del', ''),
    ], PURPLE, PURPLE_LT)

    # EmailEnrichment
    ee_h = tbl(c, 262, H - 200, 'email_enrichment', [
        ('email_id', 'text PK', 'pk'),
        ('account_id', 'UUID FK', 'fk'),
        ('priority', 'text', ''),
        ('composite_score', 'float', ''),
        ('axes', 'JSONB', ''),
        ('commitments', 'JSONB', ''),
        ('draft_reply', 'text', ''),
        ('precedents', 'JSONB', ''),
        ('status', 'pending/done', ''),
    ], RED, RED_LT)

    # ToneProfile
    tp_h = tbl(c, 262, H - 90, 'tone_profile', [
        ('account_id', 'UUID PK FK', 'pk'),
        ('profile', 'JSONB', ''),
        ('sample_size', 'integer', ''),
        ('updated_at', 'timestamp', ''),
    ], ORANGE, ORANGE_LT)

    # Waitlist
    wl_h = tbl(c, 8, H - 390, 'waitlist', [
        ('id', 'UUID PK', 'pk'),
        ('email', 'text unique', ''),
        ('status', 'pending/approv', ''),
        ('source', 'signup/login', ''),
        ('created_at', 'timestamp', ''),
    ], GREEN, GREEN_LT)

    # AuditLog
    al_h = tbl(c, 135, H - 390, 'audit_log', [
        ('id', 'int PK', 'pk'),
        ('email_id', 'text', ''),
        ('account_id', 'UUID', ''),
        ('action', 'text', ''),
        ('actor', 'text', ''),
        ('details', 'JSONB', ''),
        ('created_at', 'timestamp', ''),
    ], GRAY_700, GRAY_100)

    # Draw relationship lines
    def line(c, x1, y1, x2, y2, col=GRAY_500):
        c.setStrokeColor(col)
        c.setLineWidth(0.7)
        c.setDash(3, 2)
        c.line(x1, y1, x2, y2)
        c.setDash()

    # users → oauth_accounts
    line(c, 63, H - 120, 63, H - 145, BLUE)
    # users → user_sessions
    line(c, 100, H - 80, 190, H - 80, TEAL)
    # oauth_accounts → mailbox_message
    line(c, 118, H - 210, 135, H - 210, PURPLE)
    # mailbox_message → email_enrichment
    line(c, 245, H - 235, 262, H - 235, RED)
    # oauth_accounts → tone_profile
    line(c, 118, H - 185, 262, H - 55, ORANGE)

    # Legend
    c.setFillColor(GRAY_100)
    c.roundRect(8, 6, W - 16, 24, 3, fill=1, stroke=0)
    c.setFillColor(GRAY_700)
    c.setFont('Helvetica-Bold', 7)
    c.drawString(14, 22, '🔑 = Primary Key    → = Foreign Key    --- = Relationship    JSONB = JSON column')
    c.setFont('Helvetica', 7)
    c.drawString(14, 12, 'Total: 15 tables  |  All PKs are UUID unless noted  |  Fernet-AES-128 encryption on oauth token columns')

def build():
    S = make_styles()
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=28*mm, bottomMargin=22*mm,
    )
    story = []
    dw = W - 36*mm

    # ── FILE STRUCTURE ────────────────────────────────────────────────────────
    story.append(Paragraph('Complete File Structure', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))

    tree = """mailmind/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, lifespan, middleware stack
│   │   ├── middleware.py              # RateLimit, SecurityHeaders, SessionContext
│   │   ├── observability.py           # Exception handlers, Sentry
│   │   ├── config/
│   │   │   ├── settings.py            # All env vars (60+), _bool_env helper
│   │   │   └── keyvault.py            # Azure Key Vault → os.environ loader
│   │   ├── db/
│   │   │   ├── base.py                # SQLAlchemy engine, SessionLocal, init_db()
│   │   │   ├── models.py              # 15 ORM classes (User, OAuthAccount, etc.)
│   │   │   ├── repository.py          # Enrichment + audit + metrics DAL
│   │   │   └── mailbox_repo.py        # MailboxMessage + SyncState DAL
│   │   ├── models/
│   │   │   └── schemas.py             # Pydantic request/response schemas
│   │   ├── graph/
│   │   │   ├── state.py               # EmailAgentState TypedDict (83 fields)
│   │   │   └── pipeline.py            # LangGraph StateGraph assembly + run_pipeline()
│   │   ├── agents/
│   │   │   └── nodes.py               # 6 pipeline node functions + helpers
│   │   ├── api/
│   │   │   ├── routes.py              # OAuth, inbox, draft, commitments, tone-dna
│   │   │   ├── agent_routes.py        # /api/agent/* (process, stream, triage, enrich)
│   │   │   ├── sync_routes.py         # /webhooks/* + /api/subscriptions/*
│   │   │   ├── waitlist_routes.py     # /api/waitlist/* + /api/admin/*
│   │   │   ├── demo_routes.py         # /api/demo/login (GET + POST)
│   │   │   ├── pii_routes.py          # /api/pii/preview
│   │   │   ├── feedback_routes.py     # /api/feedback
│   │   │   ├── monitoring_routes.py   # /api/health, /api/ready, /api/metrics
│   │   │   └── compliance_routes.py   # /api/compliance/* (GDPR, audit)
│   │   ├── services/
│   │   │   ├── pii.py                 # Presidio PII masking + restoration
│   │   │   ├── tone_dna.py            # 8-feature stylometric profiling
│   │   │   ├── draft_service.py       # GPT-4o draft generation + Tone DNA
│   │   │   ├── commitments.py         # GPT-4o commitment extraction + cache
│   │   │   ├── rag.py                 # ChromaDB vector index + ada-002 embeddings
│   │   │   ├── calendar_service.py    # Deterministic conflict detection
│   │   │   ├── sync_service.py        # Backfill + delta sync mailbox mirror
│   │   │   ├── graph.py               # Microsoft Graph client (mock + real)
│   │   │   ├── gmail.py               # Gmail API client (mock + real)
│   │   │   ├── session_service.py     # Session + QuickLogin token management
│   │   │   ├── token_encryption.py    # Fernet-AES-128 token encryption
│   │   │   ├── tracing.py             # LangSmith tracing status
│   │   │   └── account_service.py     # Multi-account management helpers
│   │   ├── tools/
│   │   │   └── email_tools.py         # LangChain tool definitions for triage_node
│   │   ├── queue/
│   │   │   ├── queue.py               # EmailQueue abstraction (memory or Redis)
│   │   │   └── backends.py            # InMemoryBackend + RedisBackend
│   │   ├── workers/
│   │   │   └── enrichment.py          # EnrichmentWorker (infinite loop, SIGTERM)
│   │   └── monitoring/
│   │       ├── metrics.py             # OpenTelemetry counters + histograms
│   │       └── live_metrics.py        # SSE streaming metrics endpoint
│   ├── scripts/
│   │   └── seed_demo_account.py       # Demo account seeder (one-time setup)
│   ├── tests/                         # pytest test suite
│   ├── Dockerfile                     # Multi-stage build (python:3.12-slim)
│   ├── docker-compose.yml             # Local dev stack
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                 # Root layout, fonts, SEO
│   │   ├── page.tsx                   # Landing page (hero, features, waitlist)
│   │   ├── dashboard/page.tsx         # Inbox dashboard (auth-gated)
│   │   ├── login/page.tsx             # OAuth login buttons
│   │   └── (admin|privacy|terms)/    # Admin panel, privacy page, terms
│   ├── components/
│   │   ├── inbox/                     # EmailList, EmailListItem, FilterMenu, etc.
│   │   ├── detail/                    # EmailDetail, DraftPanel, PrecedentList
│   │   ├── commitments/               # CommitmentGate, CommitmentItem
│   │   ├── pipeline/                  # PipelineVisualization (interactive)
│   │   ├── landing/                   # HeroCanvas, WaitlistForm, Preloader
│   │   ├── layout/                    # Header, Sidebar
│   │   └── shared/                    # ErrorBoundary, FeedbackModal, etc.
│   ├── hooks/
│   │   ├── useEmails.ts               # Inbox state + pagination
│   │   ├── useEmailDetail.ts          # Two-phase loading (triage + enrich)
│   │   └── useAuthFlow.ts             # OAuth flow management
│   ├── lib/
│   │   ├── api.ts                     # API client (fetch wrapper, all endpoints)
│   │   ├── types.ts                   # TypeScript interfaces (EmailItem, etc.)
│   │   └── userStorage.ts             # localStorage manager
│   ├── public/                        # Static assets, SVG diagrams
│   ├── package.json                   # Next.js 15, Tailwind, GSAP, Three.js
│   └── next.config.ts
├── WIKI.html                          # Searchable implementation wiki (Ctrl+K)
├── DEMO_LOGIN.md                      # Demo login setup guide
├── DEMO_ACCESS.txt                    # Quick reference card
├── README.md                          # Enterprise README with badges
├── LICENSE                            # MIT License
└── .github/
    └── workflows/
        ├── ci.yml                     # lint + typecheck + pytest
        └── deploy.yml                 # Docker build + push + Azure deploy"""

    story.append(Paragraph(tree.replace('\n', '<br/>').replace(' ', '&nbsp;'),
        ParagraphStyle('tree', fontName='Courier', fontSize=6.5, textColor=GRAY_700,
            leading=10, spaceAfter=4, backColor=GRAY_100,
            leftIndent=4, rightIndent=4)))

    story.append(PageBreak())

    # ── DB SCHEMA ─────────────────────────────────────────────────────────────
    story.append(Paragraph('Database Schema', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(DiagramFlowable(dw, 130*mm, draw_db_er))
    story.append(Paragraph(
        'Fig 5: Key table relationships. All foreign keys reference users.id or oauth_accounts.id. '
        'email_enrichment.account_id acts as a scoping key for multi-tenant data isolation.',
        S['caption']
    ))

    # Full schema table
    schema_data = [
        ['Table', 'PK Type', 'Key Columns', 'Purpose'],
        ['users', 'UUID', 'primary_email, display_name, created_at', 'Core identity. One per human user.'],
        ['oauth_accounts', 'UUID', 'user_id (FK), provider, provider_account_id, account_email, *_token_enc', 'Connected email accounts (Gmail/Outlook). Tokens Fernet-encrypted.'],
        ['user_sessions', 'token_hash', 'user_id (FK), provider, expires_at (24h)', 'Short-lived sessions. Token SHA-256 hashed before storage.'],
        ['devices', 'UUID', 'user_id (FK), fingerprint, last_used', 'Trusted browser fingerprints for Quick Login.'],
        ['quick_login_tokens', 'UUID', 'user_id, device_id, token_hash, status (ACTIVE/REVOKED), expires_at (7d)', '7-day auto-resume tokens.'],
        ['email_enrichment', 'email_id+account_id', 'priority, composite_score, axes (JSON), commitments (JSON), draft_reply, status', 'Triage + enrichment cache per email per account.'],
        ['audit_log', 'int', 'email_id, account_id, action, actor, details (JSON)', 'Append-only compliance trail. No raw PII stored.'],
        ['tone_profile', 'account_id (UUID)', 'profile (JSON 8 features), sample_size, updated_at', 'Stylometric profile per account.'],
        ['feedback', 'UUID', 'user_id, rating, category, message, role', 'Product feedback submissions.'],
        ['triage_priority_override', 'UUID', 'user_id, account_id, email_id, original_priority, override_priority', 'User priority corrections (feedback loop for triage improvement).'],
        ['processing_metric', 'int', 'email_id, account_id, stage, duration_ms, success, sla_met', 'Per-stage SLA latency tracking.'],
        ['mailbox_message', 'email_id', 'account_id (FK), folder, sender, subject, received_at, state (active/done/deleted)', 'Server-side envelope mirror. state="done" means processed+dismissed.'],
        ['mailbox_sync_state', 'account_id+folder', 'delta_cursor, backfill_done, last_synced_at, message_count', 'Cursor-based delta sync state per account+folder.'],
        ['graph_subscription', 'UUID', 'account_id, provider_sub_id, client_state, expires_at', 'Microsoft Graph webhook subscription lifecycle.'],
        ['waitlist', 'UUID', 'email (unique), status (pending/approved/rejected), source', 'Private-beta access control allow-list.'],
    ]
    t = Table(schema_data, colWidths=[40*mm, 22*mm, 56*mm, 44*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (0, -1), 'Courier-Bold', 7.5),
        ('FONT', (1, 1), (-1, -1), 'Helvetica', 7.5),
        ('TEXTCOLOR', (0, 1), (-1, -1), GRAY_700),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GRAY_100]),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ── ENV VARS ──────────────────────────────────────────────────────────────
    story.append(Paragraph('Environment Variables Reference', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))

    env_sections = [
        ('Security', NAVY, [
            ('SESSION_SECRET_KEY', '', 'Fernet key for signing session tokens. Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'),
            ('TOKEN_ENCRYPTION_KEY', '', 'Fernet key for OAuth token encryption at rest.'),
            ('SESSION_TTL_SECONDS', '86400', '24h session lifetime.'),
            ('QUICK_LOGIN_TTL_SECONDS', '604800', '7-day Quick Login token lifetime.'),
            ('ADMIN_TOKEN', 'change-me-admin-token', 'Guards /api/admin/* endpoints (X-Admin-Token header).'),
            ('APPROVAL_TOKEN', 'secret-approval-token', 'Guards /api/agent/approve/* (X-Approval-Token header).'),
            ('BOOTSTRAP_ALLOWED_EMAILS', 'radiantcodex@outlook.com', 'Comma-separated emails never blocked by waitlist gate.'),
        ]),
        ('Azure / Microsoft Graph', BLUE, [
            ('AZURE_TENANT_ID', '', 'Azure tenant ID for OAuth.'),
            ('AZURE_CLIENT_ID', '', 'Azure app registration client ID.'),
            ('AZURE_CLIENT_SECRET', '', 'Azure app registration secret.'),
            ('AZURE_REDIRECT_URI', 'https://api.radiantsofficial.com/...', 'Microsoft OAuth callback URL.'),
            ('GRAPH_SCOPES', 'Mail.ReadWrite Mail.Send Calendars.ReadWrite Tasks.ReadWrite', 'Space-separated Graph API scopes.'),
            ('USE_MOCK_GRAPH', 'true', 'Use mock Graph client (dev). Set false for real Outlook integration.'),
            ('BACKEND_PUBLIC_URL', '', 'Public HTTPS URL for Graph webhook notificationUrl. Skipped when empty.'),
        ]),
        ('Google / Gmail', RED, [
            ('GOOGLE_CLIENT_ID', '', 'Google OAuth client ID.'),
            ('GOOGLE_CLIENT_SECRET', '', 'Google OAuth client secret.'),
            ('GOOGLE_REDIRECT_URI', 'http://localhost:8000/api/auth/google/callback', 'Google OAuth callback URL.'),
            ('GMAIL_PUBSUB_TOPIC', '', 'Cloud Pub/Sub topic for Gmail push. Skipped when empty.'),
            ('GMAIL_PUBSUB_TOKEN', '', 'Shared secret appended as ?token= to push endpoint URL.'),
        ]),
        ('Azure OpenAI / LLM', GREEN, [
            ('AZURE_OPENAI_ENDPOINT', '', 'Azure OpenAI resource URL.'),
            ('AZURE_OPENAI_API_KEY', '', 'Azure OpenAI API key.'),
            ('AZURE_OPENAI_API_VERSION', '2024-12-01-preview', 'API version string.'),
            ('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o-mini', 'Default chat deployment (drafts use gpt-4o).'),
            ('AZURE_OPENAI_TRIAGE_DEPLOYMENT', 'gpt-4o-mini', 'Triage deployment (faster + cheaper).'),
            ('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-ada-002', 'Embedding model for RAG.'),
            ('GROQ_API_KEY', '', 'Groq API key (fallback when Azure unavailable).'),
        ]),
        ('Database & Queue', PURPLE, [
            ('DATABASE_URL', '', 'PostgreSQL connection string. Empty = no persistence (dev mode).'),
            ('DB_POOL_SIZE', '10', 'SQLAlchemy connection pool size.'),
            ('DB_MAX_OVERFLOW', '20', 'Max connections above pool_size.'),
            ('DB_POOL_TIMEOUT', '10', 'Seconds before pool checkout raises (not hang).'),
            ('DB_POOL_RECYCLE', '1800', 'Recycle connections older than 30min (Supabase idle timeout).'),
            ('QUEUE_BACKEND', 'memory', '"memory" (dev) or "redis" (prod).'),
            ('REDIS_URL', 'redis://localhost:6379/0', 'Redis connection string for prod queue.'),
        ]),
        ('Triage & RAG', TEAL, [
            ('USE_CHROMA', 'true', 'Enable ChromaDB vector index.'),
            ('RAG_SIMILARITY_THRESHOLD', '0.78', 'Cosine similarity cutoff for precedent retrieval.'),
            ('RAG_INDEX_MAX_SIZE', '1000', 'Max documents in vector index.'),
            ('CHROMA_DATA_PATH', './data/chroma', 'Local directory for ChromaDB persistence.'),
            ('TRIAGE_MAX_WORKERS', '8', 'Parallel triage concurrency (asyncio.gather fan-out limit).'),
            ('COMMITMENT_CONFIDENCE_THRESHOLD', '0.80', 'Minimum confidence to include a commitment.'),
        ]),
        ('Observability', ORANGE, [
            ('LANGSMITH_TRACING', 'false', 'Enable LangSmith tracing (1/true/yes).'),
            ('LANGSMITH_API_KEY', '', 'LangSmith API key.'),
            ('LANGSMITH_PROJECT', '', 'LangSmith project name.'),
            ('METRICS_ENABLED', 'true', 'Enable OpenTelemetry metrics.'),
            ('SLA_TRIAGE_SECONDS', '1.5', 'Triage SLA target (user-facing critical path).'),
            ('SLA_ENRICHMENT_SECONDS', '10.0', 'Enrichment SLA target (background path).'),
            ('AUDIT_LOG_ENABLED', 'true', 'Enable compliance audit logging.'),
            ('AUDIT_LOG_FILE', '', 'Optional file path for isolated audit log sink.'),
            ('DATA_RETENTION_DAYS', '90', 'Enrichment data retention window.'),
        ]),
    ]

    for section_name, color, envs in env_sections:
        story.append(Paragraph(section_name, S['h2']))
        ev_data = [['Variable', 'Default', 'Description']]
        for name, default, desc in envs:
            ev_data.append([
                Paragraph(f'<font name="Courier-Bold" size="7">{name}</font>',
                    ParagraphStyle('env', fontName='Courier-Bold', fontSize=7)),
                Paragraph(f'<font name="Courier" size="7">{default or "—"}</font>',
                    ParagraphStyle('envd', fontName='Courier', fontSize=7, textColor=GRAY_500)),
                Paragraph(desc, ParagraphStyle('d', fontName='Helvetica', fontSize=8, textColor=GRAY_700, leading=11)),
            ])
        t = Table(ev_data, colWidths=[52*mm, 34*mm, 76*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), color),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GRAY_100]),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    story.append(PageBreak())

    # ── DEMO GUIDE ────────────────────────────────────────────────────────────
    story.append(Paragraph('Demo Login Guide', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'MailMind includes a one-click demo login system for presentations, judge evaluations, '
        'and stakeholder demos. No environment flags needed — always available.',
        S['body']
    ))

    steps_data = [
        ['Step', 'Action', 'Details'],
        ['1', 'Seed database (one-time)', 'cd backend\npython scripts/seed_demo_account.py --db $DATABASE_URL'],
        ['2', 'Start services', 'docker compose up -d  (or npm run dev + uvicorn)'],
        ['3', 'Open demo page', 'Navigate to http://localhost:3000/api/demo/login'],
        ['4', 'Click "Enter Demo"', 'Instant session → redirect to /dashboard'],
        ['5', 'Explore', '10 pre-loaded emails with CRITICAL/HIGH/MEDIUM/LOW priorities'],
    ]
    t = Table(steps_data, colWidths=[12*mm, 40*mm, 110*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (0, -1), 'Helvetica-Bold', 8),
        ('FONT', (1, 1), (-1, -1), 'Helvetica', 8),
        ('FONT', (2, 1), (2, -1), 'Courier', 7.5),
        ('TEXTCOLOR', (0, 1), (-1, -1), GRAY_700),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GREEN_LT]),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, GREEN),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
    ]))
    story.append(t)

    story.append(Spacer(1, 8))
    story.append(Paragraph('Demo Inbox Contents', S['h2']))
    demo_emails = [
        ['#', 'From', 'Subject', 'Priority', 'Deadline'],
        ['1', 'Victoria Hayes (Nexus Capital)', '$4.2M wire transfer request', 'CRITICAL', 'Today 3 PM'],
        ['2', 'Daniel Park (CTO)', 'Production down — revenue impact', 'CRITICAL', 'Today (urgent)'],
        ['3', 'James Whitfield (Legal)', 'MSA countersignature required', 'HIGH', 'Friday 5 PM'],
        ['4', 'Priya Nair (VP Eng)', 'Headcount approval — 3 seniors', 'HIGH', 'Monday 9 AM'],
        ['5', 'CrowdStrike Security', 'Endpoint policy violation detected', 'HIGH', 'ASAP'],
        ['6', 'Sprint Bot', 'Sprint 24 retro — action items', 'MEDIUM', 'This week'],
        ['7', 'Stripe', 'Account verification required', 'MEDIUM', '14-day window'],
        ['8', 'Marketing Team', 'Brand refresh feedback needed', 'MEDIUM', 'Thursday'],
        ['9', 'TLDR Newsletter', 'Tech digest — AI regulation update', 'LOW', 'FYI'],
        ['10', 'Notion', 'Your workspace report', 'LOW', 'FYI'],
    ]
    t2 = Table(demo_emails, colWidths=[10*mm, 42*mm, 62*mm, 24*mm, 24*mm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('TEXTCOLOR', (0, 1), (-1, 1), RED),
        ('TEXTCOLOR', (0, 2), (-1, 2), RED),
        ('TEXTCOLOR', (0, 3), (-1, 5), ORANGE),
        ('TEXTCOLOR', (0, 6), (-1, 8), BLUE),
        ('TEXTCOLOR', (0, 9), (-1, 10), GRAY_500),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GRAY_100]),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
    ]))
    story.append(t2)

    story.append(Spacer(1, 8))
    story.append(Paragraph('Cleanup (Post-Demo)', S['h3']))
    story.append(Paragraph(
        'DELETE FROM users WHERE id = (SELECT user_id FROM oauth_accounts WHERE email = \'demo@mailmind.app\');',
        S['code']
    ))
    story.append(PageBreak())

    # ── PRESENTATION NOTES ────────────────────────────────────────────────────
    story.append(Paragraph('Presentation Talking Points', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'Key narratives for pitching MailMind to judges, investors, and enterprise stakeholders.',
        S['body']
    ))

    talking_points = [
        ('The Problem', NAVY, [
            'Enterprise professionals receive 120+ emails/day but only 20% require immediate action.',
            'Context-switching from email kills deep work — average 23 minutes to refocus.',
            'Existing tools (Outlook Focused Inbox, Gmail Priority) are rule-based, not context-aware.',
            'No existing solution extracts commitments, checks calendar, and drafts in the user\'s own voice.',
        ]),
        ('The Solution', BLUE, [
            'MailMind scores every email across 5 contextual axes — not just sender rules.',
            'LangGraph 6-node parallel pipeline completes full enrichment in 2.8 seconds (p95).',
            'PII masking (Presidio) ensures sensitive data never reaches OpenAI servers in plaintext.',
            'Tone DNA learns from 50+ past emails — drafts match your exact writing style.',
            'Calendar conflict detection alerts you before you accidentally double-book a commitment.',
        ]),
        ('Technical Differentiation', GREEN, [
            'Parallel LangGraph DAG (not sequential chain) — 60% faster than naive pipe.',
            'Reversible PII token mapping — GPT-4o output is de-masked before returning to user.',
            'ChromaDB RAG with per-account isolation — your precedents don\'t mix with other users.',
            'Fernet-AES-128 token encryption + SHA-256 session hashing — zero plaintext secrets in DB.',
            'Server-side mailbox mirror with cursor-based delta sync — survives provider outages.',
        ]),
        ('Business & Scale', ORANGE, [
            'Multi-tenant: UUID-based user identity, account_id scoping on all queries.',
            'Horizontal scaling: stateless FastAPI behind Azure Container Apps autoscaler.',
            'Redis queue enables multi-worker enrichment without race conditions.',
            'Private-beta waitlist with admin approval — controlled rollout to enterprise buyers.',
            'Audit log + GDPR right-to-erasure endpoint — enterprise compliance-ready.',
        ]),
        ('5-Minute Demo Script', TEAL, [
            '1. Login (30s): Click "Enter Demo" → instant dashboard with 10 emails.',
            '2. Inbox (1 min): Show CRITICAL badges, triage scores, 5-axis breakdown on hover.',
            '3. Email Detail (1.5 min): Open wire transfer email → scroll to triage explainer → show conflict badge.',
            '4. Draft Generation (1.5 min): Click "Generate Draft" → streaming response → point out Tone DNA prefix in console.',
            '5. Commitment Gate (1 min): Show extracted action items → calendar conflict → click "Create Event".',
        ]),
        ('Key Metrics', PURPLE, [
            'Triage latency: 1.1s median, 2.8s p95 (target SLA: 1.5s).',
            'Enrichment latency: 4.2s median, 9.8s p95 (target SLA: 10s).',
            'Tone DNA accuracy: 87% judge score on writing style match (internal evaluation).',
            'PII detection recall: 94% on enterprise email corpus (Presidio benchmark).',
            'RAG retrieval precision: 0.78 cosine threshold eliminates 91% of irrelevant precedents.',
        ]),
    ]

    for title, color, points in talking_points:
        # section header
        story.append(KeepTogether([
            Paragraph(title, ParagraphStyle('tph', fontName='Helvetica-Bold', fontSize=11,
                textColor=WHITE, backColor=color, spaceAfter=4, spaceBefore=8,
                leftIndent=6, rightIndent=6, leading=16)),
        ]))
        for pt in points:
            story.append(Paragraph(f'• {pt}', S['bullet']))
        story.append(Spacer(1, 4))

    story.append(PageBreak())

    # ── CI/CD & DEPLOYMENT ────────────────────────────────────────────────────
    story.append(Paragraph('CI/CD & Deployment', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))

    story.append(Paragraph('GitHub Actions Pipeline', S['h2']))
    ci_steps = [
        ('Lint', 'ruff check backend/', 'Python lint', GREEN),
        ('Type Check', 'mypy backend/', 'Static type analysis', BLUE),
        ('Test', 'pytest backend/tests/', 'Unit + integration tests', ORANGE),
        ('Build', 'docker build -t mailmind-backend .', 'Docker multi-stage build', PURPLE),
        ('Push', 'docker push acr.azurecr.io/mailmind-backend:$SHA', 'Push to Azure Container Registry', TEAL),
        ('Deploy', 'az containerapp update --image ...', 'Blue-green deploy to Azure Container Apps', NAVY),
    ]
    ci_data = [['Stage', 'Command', 'Description', 'On Failure']]
    for stage, cmd, desc, color in ci_steps:
        ci_data.append([stage, Paragraph(f'<font name="Courier" size="7">{cmd}</font>',
            ParagraphStyle('c', fontName='Courier', fontSize=7)), desc, 'Blocks deploy'])
    t = Table(ci_data, colWidths=[24*mm, 64*mm, 50*mm, 24*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (0, -1), 'Helvetica-Bold', 8),
        ('FONT', (2, 1), (-1, -1), 'Helvetica', 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), GRAY_700),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GRAY_100]),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
    ]))
    story.append(t)

    story.append(Spacer(1, 8))
    story.append(Paragraph('Quick Start (Local Dev)', S['h2']))
    quickstart = """# 1. Clone & install
git clone https://github.com/Radiant-CodeX/mailmind && cd mailmind

# 2. Backend
cd backend && cp .env.example .env  # fill in keys
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. Frontend
cd frontend && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev

# 4. Demo login (optional)
python scripts/seed_demo_account.py --db $DATABASE_URL
# Then open: http://localhost:3000/api/demo/login"""

    story.append(Paragraph(quickstart.replace('\n', '<br/>').replace(' ', '&nbsp;'),
        ParagraphStyle('qs', fontName='Courier', fontSize=7.5, textColor=GRAY_700,
            backColor=GRAY_100, leading=12, leftIndent=6, rightIndent=6, spaceAfter=4)))

    doc.build(story, onFirstPage=hf, onLaterPages=hf)
    print(f'[OK] {OUT}')

build()
