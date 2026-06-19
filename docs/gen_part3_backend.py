"""Part 3: Backend file documentation — main.py, config, db, graph, agents, middleware, queue, workers."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
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

OUT = os.path.join(os.path.dirname(__file__), 'part3_backend.pdf')

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
    S['bullet'] = ParagraphStyle('bullet', fontName='Helvetica', fontSize=8.5,
        textColor=GRAY_700, leftIndent=14, spaceAfter=2, leading=13)
    S['filepath'] = ParagraphStyle('filepath', fontName='Courier-Bold', fontSize=9,
        textColor=BLUE, backColor=LIGHT_BLUE, spaceAfter=3, leading=13,
        leftIndent=6, rightIndent=6)
    return S

def hf(c, doc):
    c.saveState()
    pg = doc.page
    c.setFillColor(NAVY)
    c.rect(0, H - 22, W, 22, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(15, H - 14, 'MailMind — Technical Documentation · Backend Reference')
    c.setFont('Helvetica', 7)
    c.drawRightString(W - 15, H - 14, f'Page {pg}')
    c.setFillColor(GRAY_200)
    c.rect(0, 0, W, 18, fill=1, stroke=0)
    c.setFillColor(GRAY_500)
    c.setFont('Helvetica', 7)
    c.drawString(15, 5, 'MailMind v2.0 · Radiant CodeX · 2025')
    c.drawRightString(W - 15, 5, 'CONFIDENTIAL')
    c.restoreState()

def method_table(methods, accent=BLUE):
    """Render a table of method docs: [(name, params, description), ...]"""
    data = [['Method / Function', 'Parameters', 'Description']]
    for name, params, desc in methods:
        data.append([
            Paragraph(f'<font name="Courier-Bold" size="7.5">{name}</font>', ParagraphStyle('m', fontName='Courier-Bold', fontSize=7.5, textColor=GRAY_900)),
            Paragraph(f'<font name="Courier" size="7">{params}</font>', ParagraphStyle('p', fontName='Courier', fontSize=7, textColor=GRAY_500)),
            Paragraph(desc, ParagraphStyle('d', fontName='Helvetica', fontSize=8, textColor=GRAY_700, leading=11)),
        ])
    t = Table(data, colWidths=[46*mm, 44*mm, 72*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), accent),
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
    return t

def file_header(story, S, filepath, purpose, color=BLUE):
    story.append(KeepTogether([
        Paragraph(filepath, S['filepath']),
        Paragraph(purpose, S['body']),
    ]))

def build():
    S = make_styles()
    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=28*mm, bottomMargin=22*mm,
    )
    story = []

    # ── SECTION TITLE ─────────────────────────────────────────────────────────
    story.append(Paragraph('Backend File Documentation', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'This section documents every Python file in the backend, including its purpose, '
        'key classes, and all public functions with their parameters and descriptions.',
        S['body']
    ))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/main.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Entry Point & Application Bootstrap', S['h2']))
    file_header(story, S, 'backend/app/main.py',
        'FastAPI application factory. Configures structured logging, registers ASGI middleware '
        '(SessionContext → SecurityHeaders → RateLimit → CORS), mounts all routers, '
        'and runs startup tasks via the lifespan context manager.')

    story.append(method_table([
        ('_configure_logging()', '→ None', 'Sets up structured logging with a dedicated mailmind.audit logger. '
         'Attaches a FileHandler when AUDIT_LOG_FILE env var is set for an isolated audit sink.'),
        ('lifespan(app)', 'app: FastAPI → AsyncGenerator', 'Startup: creates EmailQueue, calls init_db(), ensures ChromaDB directory, '
         'pre-warms Presidio/spaCy (eliminates 4s cold-start), checks LangSmith status.'),
        ('app = FastAPI(...)', '—', 'Creates FastAPI instance with title, description, version 2.0.0, and lifespan handler.'),
        ('init_observability(app)', 'app: FastAPI → None', 'Registers global exception handlers and optional Sentry integration (from observability.py).'),
        ('app.add_middleware(...)', '—', 'Middleware stack (reverse order): RateLimit → SecurityHeaders → SessionContext → CORS.'),
        ('app.include_router(...)', '—', 'Mounts: main router, agent, demo, monitoring, feedback, waitlist, pii, compliance, sync routers.'),
    ], accent=NAVY))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/config/settings.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Configuration', S['h2']))
    file_header(story, S, 'backend/app/config/settings.py',
        'Single Settings class that reads all environment variables. '
        'Loaded once at import time; dotenv first, then Azure Key Vault takes precedence.')

    story.append(method_table([
        ('_bool_env(name, default)', 'name: str, default: bool → bool', 'Parses boolean env vars — accepts "1", "true", "yes".'),
        ('Settings.bootstrap_allowed_set', '→ set[str]', 'Property — lowercase set of always-allowed owner emails (never locked out by waitlist).'),
        ('Settings.is_production', '→ bool', 'Property — True when APP_ENV == "production".'),
        ('Settings.persistence_enabled', '→ bool', 'Property — True when DATABASE_URL is non-empty.'),
        ('Settings.azure_openai_base_endpoint', '→ str', 'Property — strips deployment path from Azure URL to get scheme+host only.'),
    ], accent=BLUE))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/config/keyvault.py
    # ══════════════════════════════════════════════════════════════════════════
    file_header(story, S, 'backend/app/config/keyvault.py',
        'Azure Key Vault integration. Loads secrets into os.environ at startup '
        'so downstream code reads them like normal env vars.')

    story.append(method_table([
        ('load_keyvault_into_env()', '→ None', 'Reads AZURE_KEYVAULT_URL; if set, fetches all secrets and writes to os.environ. '
         'Requires Azure Managed Identity or AZURE_CLIENT_* credentials.'),
    ], accent=BLUE))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/middleware.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('ASGI Middleware', S['h2']))
    file_header(story, S, 'backend/app/middleware.py',
        'Three custom ASGI middleware classes stacked on the FastAPI application.')

    story.append(method_table([
        ('SecurityHeadersMiddleware.__call__', 'request, call_next', 'Injects: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, '
         'Permissions-Policy, and HSTS (when HSTS_ENABLED=true and HTTPS).'),
        ('RateLimitMiddleware.__call__', 'request, call_next', 'Fixed-window per-IP rate limiter (default 100 req/min). '
         'Exempts /api/health, /api/ready, and OPTIONS. Returns HTTP 429 with Retry-After header.'),
        ('SessionContextMiddleware.__call__', 'request, call_next', 'Binds a ContextVar (current_session) before the request and clears it after. '
         'Downstream code calls get_current_session() instead of passing sessions.'),
    ], accent=ORANGE))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/db/base.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Database Base', S['h2']))
    file_header(story, S, 'backend/app/db/base.py',
        'SQLAlchemy engine factory and session maker. Configures pool parameters from settings.')

    story.append(method_table([
        ('create_engine(...)', '—', 'Creates async-compatible SQLAlchemy engine with pool_size, max_overflow, pool_timeout, '
         'pool_pre_ping, pool_recycle from Settings.'),
        ('SessionLocal', '—', 'sessionmaker factory; use as context manager or via FastAPI dependency.'),
        ('init_db()', '→ None', 'Calls Base.metadata.create_all() — creates all ORM tables on first run. '
         'No-op when DATABASE_URL is empty.'),
    ], accent=PURPLE))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/db/models.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('ORM Models', S['h2']))
    file_header(story, S, 'backend/app/db/models.py',
        'All 15 SQLAlchemy ORM classes (tables). UUID primary keys throughout. '
        'Defines relationships, unique constraints, and JSON columns.')

    classes = [
        ('User', 'Core identity. UUID PK. One user can have multiple OAuthAccounts.'),
        ('OAuthAccount', 'Connected email account (Gmail/Outlook). Fernet-encrypted tokens. '
         'UniqueConstraint(provider, provider_account_id). Links to User.'),
        ('UserSession', 'Short-lived session (24h). token_hash = SHA-256(secret + raw_token). '
         'Links to User.'),
        ('Device', 'Trusted browser fingerprint for Quick Login. Links to User.'),
        ('QuickLoginToken', '7-day auto-resume token. status: ACTIVE/LOGGED_OUT/REVOKED/EXPIRED.'),
        ('EmailEnrichment', 'Triage + enrichment results. JSON columns: axes, dynamic_weights, '
         'commitments, precedents. status: pending/done/error.'),
        ('AuditLog', 'Append-only compliance trail. No raw PII. action, actor, details (JSON).'),
        ('ToneProfile', 'Stylometric profile per account. profile (JSON 8 features). One row per account.'),
        ('Feedback', 'Product feedback. rating, category, message, role.'),
        ('TriagePriorityOverride', 'User priority feedback loop. original vs override priority per email.'),
        ('ProcessingMetric', 'SLA latency per stage. duration_ms, success, sla_met.'),
        ('MailboxMessage', 'Server-side envelope mirror. state: active/done/deleted. '
         'sender, subject, snippet, received_at, is_read, is_starred.'),
        ('MailboxSyncState', 'Delta cursor per account+folder. delta_cursor, backfill_done, '
         'last_synced_at, message_count.'),
        ('GraphSubscription', 'Microsoft Graph webhook subscription lifecycle. '
         'provider_sub_id, client_state, expires_at.'),
        ('Waitlist', 'Private-beta access control. status: pending/approved/rejected. source: signup/login.'),
    ]
    cls_data = [['Class (Table)', 'Description']]
    for name, desc in classes:
        cls_data.append([
            Paragraph(f'<font name="Courier-Bold">{name}</font>', ParagraphStyle('c', fontName='Courier-Bold', fontSize=8, textColor=GRAY_900)),
            Paragraph(desc, ParagraphStyle('d', fontName='Helvetica', fontSize=8, textColor=GRAY_700, leading=11)),
        ])
    t = Table(cls_data, colWidths=[42*mm, 120*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
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

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/db/repository.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Enrichment Repository', S['h2']))
    file_header(story, S, 'backend/app/db/repository.py',
        'Data access layer for email_enrichment, audit_log, tone_profile, and processing_metric tables. '
        'All functions take a SQLAlchemy session as first argument.')

    story.append(method_table([
        ('upsert_enrichment', 'email_id, state, *, account_id, status, error', 'Insert or update enrichment row from pipeline state dict. '
         'Serialises axes, commitments, precedents to JSON.'),
        ('get_enrichment', 'email_id, account_id → EmailEnrichment|None', 'Fetch single enrichment row by email_id + account_id.'),
        ('get_enrichments_bulk', 'email_ids: list, account_id → dict', 'Batch-fetch enrichments in one query (WHERE email_id IN …). '
         'Returns dict keyed by email_id — critical for inbox page performance.'),
        ('list_enrichments', '*, account_id, priority, limit, offset → list', 'Paginated list with optional priority filter.'),
        ('delete_enrichment', 'email_id, account_id → None', 'Hard delete (GDPR right-to-erasure).'),
        ('write_audit', 'email_id, action, *, actor, details, account_id', 'Appends one audit log row. Never updates or deletes audit records.'),
        ('record_priority_override', 'email_id, sender, override_priority, ...', 'Saves user priority correction. Also sets enrichment.status="done" '
         'AND mailbox_message.state="done" so email disappears from active inbox.'),
        ('get_sender_priority_hint', 'sender, *, account_id → str|None', 'Returns learned priority for a sender (from overrides). '
         'Used to bias triage scoring.'),
        ('get_sender_priority_hints_bulk', 'senders: list, account_id → dict', 'Batch version of above for inbox page (one query for all senders).'),
        ('get_audit_log', 'email_id, limit → list', 'Fetches audit trail for one email.'),
        ('record_metric', 'email_id, stage, duration_ms, *, success, sla_met, account_id', 'Persists per-stage latency metric for SLA monitoring.'),
        ('get_tone_profile', 'account_id → ToneProfile|None', 'Fetch tone profile for an account.'),
        ('save_tone_profile', 'account_id, profile: dict → None', 'Upsert tone profile (8 stylometric features).'),
        ('purge_expired', 'retention_days: int → int', 'Deletes enrichments older than retention_days. Returns count of rows deleted.'),
    ], accent=PURPLE))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/db/mailbox_repo.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Mailbox Repository', S['h2']))
    file_header(story, S, 'backend/app/db/mailbox_repo.py',
        'Data access for the mailbox mirror: MailboxMessage and MailboxSyncState tables. '
        'Handles delta cursor persistence and state-preserving upserts.')

    story.append(method_table([
        ('get_sync_state', 'account_id, folder → MailboxSyncState|None', 'Fetches delta cursor, backfill status, and last sync timestamp.'),
        ('set_sync_status', 'account_id, folder, status, error → None', 'Updates last_status and last_error (for monitoring).'),
        ('set_sync_cursor', 'account_id, folder, *, delta_cursor, backfill_done, status', 'Persists the new cursor after a successful delta sync.'),
        ('recount', 'account_id, folder → int', 'Recomputes exact message_count from the DB (after upserts/tombstones).'),
        ('upsert_messages', 'account_id, folder, messages: list → (new, updated)', 'Batch upserts envelope rows. Crucially: if row.state == "done", preserves it '
         '(does NOT reset to "active" — prevents done emails from reappearing after sync).'),
        ('tombstone_messages', 'account_id, removed_ids: list → int', 'Sets state="deleted" for emails removed from the provider mailbox.'),
        ('list_page', 'account_id, folder, limit, offset → list', 'LEFT OUTER JOIN mailbox_message + email_enrichment. '
         'Filters: state="active" AND (enrichment.status IS NULL OR enrichment.status != "done"). '
         'Returns envelope + triage data combined for the inbox page.'),
    ], accent=TEAL))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/graph/state.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('LangGraph State', S['h2']))
    file_header(story, S, 'backend/app/graph/state.py',
        'Defines EmailAgentState TypedDict — the single shared state object '
        'flowing through all 6 pipeline nodes.')

    story.append(Paragraph('State Fields:', S['h3']))
    fields = [
        ('Input fields', 'email_id, sender, subject, body, received_at'),
        ('PII masking (after ingest)', 'masked_body, masked_subject, mask_mapping: dict[str, str]'),
        ('Triage outputs', 'axes: list[AxisScore], dynamic_weights: dict[str, float], composite_score: float, priority: str, email_type: str, approval_mode: str, triage_reasoning: str'),
        ('Commitment outputs', 'commitments: list[CommitmentItem], commitment_reasoning: str'),
        ('Calendar outputs', 'conflict_summary: str, calendar_events: list[CalendarEvent]'),
        ('RAG/Draft outputs', 'draft_reply: str, precedents: list[PrecedentItem]'),
        ('Control fields', 'current_step: str, errors: list[str], approved: bool'),
    ]
    for label, value in fields:
        story.append(Paragraph(f'<b>{label}:</b> <font name="Courier" size="7.5">{value}</font>', S['body']))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/graph/pipeline.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('LangGraph Pipeline Assembly', S['h2']))
    file_header(story, S, 'backend/app/graph/pipeline.py',
        'Assembles the StateGraph from imported node functions. '
        'Defines edges: ingest → {triage ‖ commitment ‖ rag} → calendar → gate. '
        'Exposes run_pipeline() for both sync and streaming execution.')

    story.append(method_table([
        ('build_mailmind_graph', 'index_documents: list → CompiledGraph', 'Creates StateGraph, registers 6 nodes, adds parallel edges, compiles. '
         'index_documents are passed into rag_node via closure for RAG retrieval.'),
        ('run_pipeline', 'email_payload: dict, index_documents: list, stream: bool, parallel: bool → dict|Generator', 'Main entry point. '
         'stream=True → returns SSE-compatible generator; stream=False → runs synchronously and returns full state dict. '
         'parallel=True uses asyncio.gather for triage+commitment+rag nodes.'),
    ], accent=RED))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/agents/nodes.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Pipeline Nodes', S['h2']))
    file_header(story, S, 'backend/app/agents/nodes.py',
        'The 6 agentic pipeline node functions and their helpers. '
        'Each node receives EmailAgentState and returns a partial state update dict. '
        'LLM calls use Azure OpenAI with Groq as fallback.')

    story.append(method_table([
        ('_get_llm', 'temperature: float, deployment: str → AzureChatOpenAI|ChatGroq|None', 'LRU-cached factory. Tries Azure OpenAI first, then Groq, then None. '
         'Cached so the SDK client is not re-instantiated per call.'),
        ('_with_max_tokens', 'llm, max_tokens: int → BaseChatModel', 'Applies max_tokens limit in a provider-agnostic way (kwargs differ between Azure and Groq).'),
        ('_dispatch_tool', 'tool_call: ToolCall → Any', 'Executes an LLM tool call returned by triage_node\'s tool-calling loop.'),
        ('_priority_from_score', 'composite: float → str', 'Maps 0–100 composite score to CRITICAL / HIGH / MEDIUM / LOW string.'),
        ('_normalise_weights', 'weights: dict → dict', 'Repairs LLM-returned dynamic_weights so they sum to exactly 1.0.'),
        ('_is_automated_sender', 'sender: str, body: str → bool', 'Detects no-reply / automated sender patterns.'),
        ('_dampen_automated_action', 'axes, sender, body → axes', 'Lowers action axis score for automated senders to prevent false HIGH priorities.'),
        ('ingest_node', 'state: EmailAgentState → dict', 'Node 1: masks PII in subject + body with PIISanitizer, returns masked_body, '
         'masked_subject, mask_mapping.'),
        ('triage_node', 'state: EmailAgentState → dict', 'Node 2: calls gpt-4o-mini with tool-calling schema for 5-axis scoring. '
         'Returns axes, dynamic_weights, composite_score, priority, email_type, approval_mode, triage_reasoning.'),
        ('commitment_node', 'state: EmailAgentState → dict', 'Node 3: calls CommitmentService.extract() on masked_body. '
         'Returns commitments list with deadlines and confidence scores.'),
        ('calendar_node', 'state: EmailAgentState → dict', 'Node 5: deterministic conflict detection — cross-references commitment deadlines '
         'against calendar events. Returns conflict_summary.'),
        ('rag_node', 'state: EmailAgentState, index_documents: list → dict', 'Node 4: embeds masked_body with ada-002, searches ChromaDB (threshold 0.78), '
         'then generates draft via DraftService with RAG context injected. Returns draft_reply, precedents.'),
        ('gate_node', 'state: EmailAgentState → dict', 'Node 6: approval checkpoint. In streaming mode is a no-op pass-through; '
         'in human-in-the-loop mode waits for /api/agent/approve/{email_id}. Sets approved=True.'),
    ], accent=RED))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/queue/queue.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Email Queue', S['h2']))
    file_header(story, S, 'backend/app/queue/queue.py',
        'Queue abstraction layer. In development uses an in-memory deque; '
        'in production uses Redis BLPOP for durable, multi-worker job dispatch.')

    story.append(method_table([
        ('EmailQueue.__init__', 'backend: str = settings.queue_backend', 'Selects backend: "memory" → deque, "redis" → Redis BLPOP.'),
        ('EmailQueue.enqueue', 'job: dict → None', 'Adds a job (email_id, account_id, provider) to the queue.'),
        ('EmailQueue.dequeue', '→ dict|None', 'Pops next job (BLPOP blocks for 1s in Redis mode). Returns None when empty.'),
        ('EmailQueue.size', '→ int', 'Returns current queue depth.'),
        ('EmailQueue.clear', '→ None', 'Drains the queue (used in tests).'),
    ], accent=GREEN))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/workers/enrichment.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Enrichment Worker', S['h2']))
    file_header(story, S, 'backend/app/workers/enrichment.py',
        'Background worker that dequeues enrichment jobs and runs the commitment+calendar+RAG nodes. '
        'Supports graceful shutdown via SIGTERM, exponential backoff retry, and SLA metrics.')

    story.append(method_table([
        ('_load_rag_index', '→ list', 'Loads ChromaDB index documents from disk for rag_node.'),
        ('_restore_field', 'value: Any, mapping: dict → Any', 'Restores PII tokens in a single field value.'),
        ('_restore_pii', 'state: dict → dict', 'Restores all PII tokens in the full state dict after LLM calls.'),
        ('EnrichmentWorker.process_one', 'job: dict → dict', 'Runs the enrichment subgraph (commitment → calendar → rag) for one email job. '
         'Reads existing triage state from DB, then runs Phase 2 nodes. Persists result.'),
        ('EnrichmentWorker.run', '→ None', 'Infinite loop: dequeue → process_one with exponential backoff retry (3 attempts, 30s base). '
         'Catches SIGTERM for graceful shutdown.'),
    ], accent=GREEN))

    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════════════════════
    # backend/app/observability.py
    # ══════════════════════════════════════════════════════════════════════════
    story.append(Paragraph('Observability', S['h2']))
    file_header(story, S, 'backend/app/observability.py',
        'Global exception handlers, request ID middleware, and optional Sentry integration.')

    story.append(method_table([
        ('init_observability', 'app: FastAPI → None', 'Registers: unhandled exception handler (500 JSON response), '
         'request ID injection (X-Request-ID header), optional Sentry init if SENTRY_DSN is set.'),
    ], accent=GRAY_700))

    doc.build(story, onFirstPage=hf, onLaterPages=hf)
    print(f'[OK] {OUT}')

build()
