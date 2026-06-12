from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus.flowables import Flowable

OUTPUT = "MailMind_Architecture_Reference.pdf"

# ── Colour palette ────────────────────────────────────────────────────────────
DARK_BG    = colors.HexColor("#1e1e2e")
ACCENT     = colors.HexColor("#6366f1")
ACCENT2    = colors.HexColor("#0ea5e9")
H1_COLOR   = colors.HexColor("#e0e0ff")
H2_COLOR   = colors.HexColor("#a5b4fc")
H3_COLOR   = colors.HexColor("#818cf8")
BODY_COLOR = colors.HexColor("#1a1a2e")
CODE_BG    = colors.HexColor("#1a1a2e")
CODE_FG    = colors.HexColor("#c9d1d9")
CODE_BORDER= colors.HexColor("#30363d")
MUTED      = colors.HexColor("#64748b")
TABLE_H_BG = colors.HexColor("#312e81")
TABLE_R_BG = colors.HexColor("#f1f5f9")
TABLE_A_BG = colors.HexColor("#e8eaf6")
RULE_COLOR = colors.HexColor("#6366f1")

# ── Document setup ────────────────────────────────────────────────────────────
doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    leftMargin=18*mm, rightMargin=18*mm,
    topMargin=20*mm, bottomMargin=20*mm,
    title="MailMind Architecture & User Workflow Reference",
    author="MailMind",
)

W = A4[0] - 36*mm   # usable width

# ── Styles ────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

sTitle = S("DocTitle",
    fontName="Helvetica-Bold", fontSize=26, leading=32,
    textColor=ACCENT, alignment=TA_CENTER, spaceAfter=4)

sSubtitle = S("DocSubtitle",
    fontName="Helvetica", fontSize=11, leading=14,
    textColor=MUTED, alignment=TA_CENTER, spaceAfter=20)

sH1 = S("H1",
    fontName="Helvetica-Bold", fontSize=17, leading=22,
    textColor=ACCENT, spaceBefore=18, spaceAfter=6)

sH2 = S("H2",
    fontName="Helvetica-Bold", fontSize=13, leading=17,
    textColor=H2_COLOR, spaceBefore=14, spaceAfter=4)

sH3 = S("H3",
    fontName="Helvetica-Bold", fontSize=11, leading=15,
    textColor=H3_COLOR, spaceBefore=10, spaceAfter=3)

sBody = S("Body",
    fontName="Helvetica", fontSize=9.5, leading=14,
    textColor=BODY_COLOR, spaceAfter=5)

sBullet = S("Bullet",
    fontName="Helvetica", fontSize=9.5, leading=13,
    textColor=BODY_COLOR, spaceAfter=2,
    leftIndent=12, bulletIndent=0)

sCode = S("Code",
    fontName="Courier", fontSize=7.8, leading=11.5,
    textColor=CODE_FG, backColor=CODE_BG,
    leftIndent=8, rightIndent=8,
    spaceBefore=4, spaceAfter=4,
    borderPad=6)

sLabel = S("Label",
    fontName="Helvetica-Bold", fontSize=8.5, leading=11,
    textColor=ACCENT2, spaceAfter=1)

sNote = S("Note",
    fontName="Helvetica-Oblique", fontSize=8.5, leading=12,
    textColor=MUTED, alignment=TA_CENTER, spaceAfter=6)

# ── Helper: code block ────────────────────────────────────────────────────────
def code_block(text):
    """Return a styled code-block table."""
    lines = text.strip("\n")
    safe = (lines
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
        .replace(" ", "&nbsp;"))
    p = Paragraph(safe, sCode)
    t = Table([[p]], colWidths=[W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), CODE_BG),
        ("BOX",        (0,0), (-1,-1), 0.6, CODE_BORDER),
        ("TOPPADDING",    (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
    ]))
    return t

# ── Helper: section rule ──────────────────────────────────────────────────────
def rule():
    return HRFlowable(width="100%", thickness=1, color=RULE_COLOR, spaceAfter=6, spaceBefore=2)

# ── Helper: data table ────────────────────────────────────────────────────────
def data_table(headers, rows, col_widths=None):
    if col_widths is None:
        col_widths = [W / len(headers)] * len(headers)
    hstyle = ParagraphStyle("TH", fontName="Helvetica-Bold", fontSize=8.5,
                             textColor=colors.white, leading=11)
    bstyle = ParagraphStyle("TD", fontName="Helvetica", fontSize=8.5,
                             textColor=BODY_COLOR, leading=11)
    data = [[Paragraph(h, hstyle) for h in headers]]
    for i, row in enumerate(rows):
        data.append([Paragraph(str(c), bstyle) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0,0), (-1,0), TABLE_H_BG),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [TABLE_R_BG, TABLE_A_BG]),
        ("BOX",    (0,0), (-1,-1), 0.5, colors.HexColor("#c7d2fe")),
        ("GRID",   (0,0), (-1,-1), 0.3, colors.HexColor("#c7d2fe")),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LEFTPADDING",   (0,0), (-1,-1), 7),
        ("RIGHTPADDING",  (0,0), (-1,-1), 7),
    ]
    t.setStyle(TableStyle(style))
    return t

# ── Helper: bullet ────────────────────────────────────────────────────────────
def bullet(text):
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(f"&#8226;&nbsp;&nbsp;{safe}", sBullet)

def labeled(label, text):
    return [
        Paragraph(label, sLabel),
        Paragraph(text, sBody),
    ]

# ═════════════════════════════════════════════════════════════════════════════
# CONTENT
# ═════════════════════════════════════════════════════════════════════════════
story = []

# ── Cover / Title ─────────────────────────────────────────────────────────────
story += [
    Spacer(1, 24),
    Paragraph("MailMind", sTitle),
    Paragraph("Architecture &amp; User Workflow Reference", sSubtitle),
    rule(),
    Paragraph("Generated from codebase &mdash; June 2026", sNote),
    Spacer(1, 8),
]

# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — HIGH-LEVEL OVERVIEW
# ═══════════════════════════════════════════════════════════════════
story += [
    Paragraph("1. High-Level Architecture Overview", sH1),
    rule(),
    Paragraph(
        "MailMind is a two-tier system: a <b>Next.js 16 / React 19</b> frontend and a "
        "<b>FastAPI + LangGraph</b> Python backend. Users authenticate via OAuth (Google or Microsoft), "
        "and the backend routes all email operations through a unified mail-provider interface that "
        "speaks to either Gmail API or Microsoft Graph API.",
        sBody),
    Spacer(1, 6),
]

# ── Layer 1 ───────────────────────────────────────────────────────
story += [
    Paragraph("Layer 1: Auth &amp; Entry Point", sH2),
    bullet("<b>OAuth Login</b> — Google/Microsoft OAuth 2.0 popup flow, session persistence"),
    bullet("<b>Session State</b> — Active provider (MS/Google), access tokens cached in-process, user principal name"),
    bullet("<b>Mail Provider Client</b> — Microsoft Graph API, Gmail API, unified interface"),
    bullet("<b>Dashboard Entry</b> — Auth check on mount, redirect if unauthenticated, load user profile"),
    Spacer(1, 4),
]

# ── Layer 2 ───────────────────────────────────────────────────────
story += [
    Paragraph("Layer 2: Frontend (React / Next.js)", sH2),
    Paragraph("<b>Layout Components</b>", sH3),
    bullet("Sidebar (folder navigation), Header (user profile, theme toggle), Theme toggle"),
    Paragraph("<b>Inbox View</b>", sH3),
    bullet("EmailList, pagination, search/filter, sort options, triage score badges"),
    Paragraph("<b>Email Detail Panel</b>", sH3),
    bullet("ThreadView, DraftPanel (3 styles), triage axis breakdown, PrecedentList"),
    Paragraph("<b>AI Pipeline UI</b>", sH3),
    bullet("Triage score display, CommitmentGate, draft approval, calendar conflict badges, CalendarView"),
    Paragraph("<b>Utilities</b>", sH3),
    bullet("ComposeWindow, TasksView, RAGSettingsView, EvaluationView"),
    Paragraph("<b>API Hooks &amp; State</b>", sH3),
    bullet("<code>useEmails</code> (pagination), <code>useEmailDetail</code> (classification + draft), <code>useCommitments</code>, <code>useCalendar</code>"),
    Spacer(1, 4),
]

# ── Layer 3 ───────────────────────────────────────────────────────
story += [
    Paragraph("Layer 3: Backend (FastAPI + LangGraph)", sH2),
    Paragraph("<b>API Routers (6 total)</b>", sH3),
    bullet("Auth Routes — MS/Google OAuth, quick login, logout"),
    bullet("Email Routes — List/get, compose, reply, archive, trash"),
    bullet("AI Routes — Triage (batch), classify, draft generation"),
    bullet("RAG Routes — Retrieve precedents, inject context, RAG settings"),
    bullet("Calendar Routes — Fetch events, create event, commitments"),
    bullet("Compliance Routes — Monitoring/metrics, health/readiness, evaluation"),
    Spacer(1, 4),
    Paragraph("<b>LangGraph Agentic Pipeline (Linear DAG)</b>", sH3),
    code_block(
"""[START]
   |
   v
ingest_node     <- PII masking, payload validation, queue management
   |
   v
triage_node     <- 5-axis scoring (GPT-4o): deadline, authority, sentiment, decay, action
   |
   v
commitment_node <- Commitment extraction (GPT-4o structured output), deadline detection
   |
   v
calendar_node   <- Calendar conflict detection (deterministic)
   |
   v
rag_node        <- RAG precedent retrieval + context injection + draft generation (GPT-4o)
   |
   v
gate_node       <- Human-in-the-loop approval checkpoint
   |
   v
[END]"""),
    Spacer(1, 4),
    Paragraph("<b>Core Services</b>", sH3),
    bullet("<code>ClassificationService</code> — GPT-4o email priority (CRITICAL/HIGH/Normal)"),
    bullet("<code>CommitmentService</code> — Structured LLM output for tasks + deadlines"),
    bullet("<code>DraftService</code> — RAG-augmented reply generation"),
    bullet("<code>ToneDNAService</code> — Learn user voice from sent mail"),
    bullet("<code>GraphClient</code> / <code>GmailClient</code> — Unified mail provider interface"),
    bullet("<code>RetrievalService</code> + ChromaDB — Vector similarity search for precedents"),
    bullet("<code>PII Masking</code> — Strip PII before indexing/LLM calls"),
    bullet("<code>Scorers</code> — Deadline, Authority, Sentiment, Decay, ActionType"),
    Spacer(1, 4),
    Paragraph("<b>Infrastructure</b>", sH3),
    bullet("Email Queue (async, webhook + polling)"),
    bullet("Database (optional SQLAlchemy ORM persistence)"),
    bullet("In-process caching (dict-based, TTL-based expiry)"),
    bullet("Middleware: CORS, rate limiting, security headers"),
    bullet("Observability: structured logging, optional Sentry"),
    PageBreak(),
]

# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — COMPLETE USER WORKFLOW
# ═══════════════════════════════════════════════════════════════════
story += [
    Paragraph("2. Complete User Workflow", sH1),
    rule(),
]

# ── Phase 1 ───────────────────────────────────────────────────────
story += [
    Paragraph("Phase 1: Authentication &amp; Session Initialization", sH2),
    Paragraph("Step 1.1 — User Visits Login Page", sH3),
    code_block(
"""User navigates to mailmind.com
  v
Frontend loads: app/page.tsx (LoginPage component)
  |-- Checks localStorage for "remembered login"
  |     └─ rememberMe key + email stored from previous session
  |-- Calls checkAuthStatus() -> GET /api/auth/status
  |     └─ Backend checks if active session exists
  └── Sets authStatus = "ready"

If authenticated from existing session:
  └─ Router redirects to /dashboard immediately"""),

    Paragraph("Step 1.2 — User Selects OAuth Provider", sH3),
    code_block(
"""User enters email: tarun@gmail.com
  |-- Frontend detects domain -> "gmail" -> provider = "google"
  |-- Frontend opens OAuth popup window (synchronously to preserve gesture)
  └── User clicks "Continue with Google"

Frontend calls: POST /auth/google/login-initiate

Backend (app/services/gmail.py):
  |-- Generates state = random UUID
  |     └─ Stored in memory: google_auth_status[state]
  |-- Calls build_auth_url(state)
  |     └─ Returns Google consent URL with:
  |        client_id, redirect_uri, scope, state
  └── Returns: { status: "pending", auth_url: "...", state: "abc123" }

Frontend:
  |-- Navigates popup to auth_url
  └── Starts polling: POST /api/auth/google/poll (every 2.5s)"""),

    Paragraph("Step 1.3 — OAuth Callback &amp; Token Exchange", sH3),
    code_block(
"""User completes Google OAuth consent
  └─ Google redirects to: /api/auth/google/callback?code=AUTH_CODE&state=abc123

Backend (google_callback):
  |-- Calls exchange_code(code)
  |     |-- POST to Google token endpoint
  |     |-- Sends: code, client_id, client_secret, grant_type=authorization_code
  |     └─ Receives: access_token, refresh_token, expires_in, id_token
  |-- Decodes id_token (JWT) -> extracts email + profile
  |-- Stores refresh token:
  |     └─ ~/.cache/google_credentials.json  (for Quick Login)
  |-- Updates google_auth_status[state] = { status: "success", email }
  |-- Calls set_provider("google", "tarun@gmail.com")
  └── Returns HTML "Connected" screen -> closes popup after 1.2s

Frontend polling detects success -> router.push("/dashboard")"""),

    Paragraph("Step 1.4 — Session Persistence", sH3),
    code_block(
"""Backend storage:
  |-- In-memory: _user_token_cache
  |     └─ { access_token, refresh_token, expires_at }
  |-- File system: ~/.cache/google_credentials.json
  └── Optional DB: users table { email, provider, token_hash, last_login }

Frontend storage:
  |-- localStorage["remembered_login"] = { email, provider }
  └── sessionStorage: preserved for tab duration"""),
    Spacer(1, 4),
]

# ── Phase 2 ───────────────────────────────────────────────────────
story += [
    Paragraph("Phase 2: Dashboard Load &amp; Inbox Initialization", sH2),
    Paragraph("Step 2.1 — Dashboard Mount", sH3),
    code_block(
"""Frontend (app/dashboard/page.tsx):
  |-- useEffect on mount -> checkAuthStatus() -> GET /api/auth/status
  |     └─ Backend validates token expiry, returns user_principal_name
  |-- If authenticated:
  |     |-- setAuthenticated(true), setUserEmail, setProvider
  |     |-- userStorage.setUser("tarun@gmail.com")
  |     |     └─ Scopes all localStorage to this user
  |     |         (prevents cross-account data leaks)
  |     └─ setCheckingAuth(false) -> stops loading spinner
  └── If not authenticated -> router.push("/")"""),

    Paragraph("Step 2.2 — Initial Email List Fetch", sH3),
    code_block(
"""useEmails hook -> fetchEmails()
  └── POST /api/mailbox?folder=inbox&limit=50

Backend (get_mailbox):
  |-- Validates user via Depends(get_current_user)
  |-- Calls client = get_mail_client() -> singleton GmailClient
  |-- Calls client.list_emails(folder="inbox", limit=50)
  |     └─ GET https://www.googleapis.com/gmail/v1/users/me/messages
  |            ?q=in:inbox&maxResults=50
  └── Returns EmailPage: { emails: [50 items], page_token: "...", has_next: true }"""),

    Paragraph("Step 2.3 — Triage Score Batch Fetch", sH3),
    code_block(
"""Frontend sends POST /api/triage/batch with 50 email payloads

Backend (triage_batch):
  |-- Creates shared scorers dict (reused across batch)
  |-- For each email -> cache check:
  |     Key: f"id:{current_user}:{email_id}"
  |     If HIT  -> return cached TriageResult instantly
  |     If MISS -> compute all 5 axes:
  |
  |  1. DeadlineScorer
  |     Regex: "by 3pm", "EOD", "ASAP"
  |     < 4 hours  -> score 1.0 (CRITICAL)
  |     < 24 hours -> score 0.7
  |
  |  2. SenderAuthorityScorer
  |     CEO/manager domain  -> 0.9
  |     Unknown sender      -> 0.2
  |
  |  3. SentimentScorer  (spaCy NLP)
  |     "urgent","ASAP"     -> 0.9
  |     Positive tone       -> 0.3
  |
  |  4. ThreadAgeDecayScorer
  |     < 1 hour old        -> 1.0
  |     > 24 hours old      -> 0.3
  |
  |  5. ActionTypeScorer
  |     "FYI"               -> 0.2
  |     "Review"            -> 0.6
  |     "Approval needed"   -> 0.9
  |
  |-- CompositeAggregator: weighted average of 5 axes
  |     >= 0.75  -> "Critical"  (red badge)
  |     0.5-0.75 -> "High"      (orange badge)
  |     < 0.5    -> "Normal"    (gray badge)
  |
  └── Cache write: triage_cache.set(key, result)  [TTL: 1 hour]
      Optional DB write: triage_cache table"""),
    PageBreak(),
]

# ── Phase 3 ───────────────────────────────────────────────────────
story += [
    Paragraph("Phase 3: User Opens Email — Full AI Pipeline", sH2),
    Paragraph("Step 3.1 — Email Selection &amp; Mark as Read", sH3),
    code_block(
"""User clicks email -> handleSelectEmail("18a...")
  |-- setSelectedEmailId("18a...")
  |-- If email.isRead === false -> POST /api/emails/18a.../read
  |     Backend: GmailClient.mark_read()
  |       -> POST Gmail API { removeLabelIds: ["UNREAD"] }
  |       -> Optional DB: emails table UPDATE is_read = true
  └── EmailDetail mounts with selectedEmail data"""),

    Paragraph("Step 3.2 — 6 Parallel AI Pipeline Calls (Promise.all)", sH3),
    Paragraph(
        "All 6 calls fire simultaneously via <code>Promise.all</code> in the "
        "<code>useEmailDetail</code> hook. Results are merged into the UI when all resolve (~1.5s).",
        sBody),
    Spacer(1, 3),

    Paragraph("Call 1 — Classification", sH3),
    code_block(
"""POST /api/classify { email_text: "[full email]" }

Backend (ClassificationService.classify):
  |-- Cache check: f"classify:{user}:sha256(email_text)"
  |-- If MISS: GPT-4o call -> "Classify as CRITICAL, HIGH, or NORMAL"
  |-- Cache write: classification_cache.set(key, result) [TTL: 1 hour]
  └── Optional DB write: classifications table"""),

    Paragraph("Call 2 — Triage", sH3),
    code_block(
"""POST /api/triage { email_payload }

Backend: Returns TriageResult
  └─ Usually already cached from the batch fetch -> returns instantly"""),

    Paragraph("Call 3 — Commitment Extraction", sH3),
    code_block(
"""POST /api/commitments/extract { email_text, thread_summary, email_id }

Backend (CommitmentService.extract):
  |-- PII masking (replace emails, SSN, credit cards with [PII_*])
  |-- GPT-4o structured output:
  |     Returns JSON:
  |     { commitments: [
  |         { id, text: "Call client by 3pm",
  |           deadline, type: "call", confidence: 0.95 },
  |         { id, text: "Submit report",
  |           deadline, type: "deliverable", confidence: 0.87 }
  |     ]}
  └── Optional DB write: commitments table (status: "pending")"""),

    Paragraph("Call 4 — Calendar Fetch", sH3),
    code_block(
"""GET /api/calendar?days=7

Backend (CalendarFetcher):
  |-- GmailClient.fetch_calendar()
  |     -> GET https://www.googleapis.com/calendar/v3/calendars/primary/events
  └── Caches result for 5 minutes: calendar_cache[user_id]"""),

    Paragraph("Call 5 — RAG Precedent Retrieval", sH3),
    code_block(
"""POST /api/rag/retrieve { email_text: "[masked email]" }

Backend (RetrievalService):
  |-- Cache check: f"retrieve:{user}:sha256(email_text)"
  |-- If MISS:
  |     |-- Convert email_text to 1536-dim embedding (OpenAI)
  |     |-- Query ChromaDB stored at ./chroma_db/
  |     |     chroma_db/
  |     |       |-- index.json
  |     |       |-- chroma.parquet
  |     |       └── data/documents.json
  |     |-- Cosine similarity search -> top-5 above threshold
  |     └── Returns PrecedentItem[] with similarity scores
  |-- Cache write: precedents_cache.set(key, results)
  └── Optional DB write: retrieval_logs table"""),

    Paragraph("Call 6 — Draft Generation", sH3),
    code_block(
"""POST /api/rag/draft { email_text, style: "standard", sender, subject,
                       current_user_email }

Backend (DraftService.generate_draft):
  |-- Cache check: f"draft:{style}:{user}:sha256(email_text)"
  |-- If MISS:
  |     |-- Load ChromaDB index from disk
  |     |-- PrecedentInjector.inject():
  |     |     Includes original email + 2 similar past emails + user replies
  |     |-- Load Tone DNA profile:
  |     |     ~/.mailmind/tone_dna/tarun@gmail.com.json
  |     |     { formality_score: 0.72, avg_sentence_length: 16,
  |     |       favorite_phrases: ["looking forward", "let me know"],
  |     |       tone_markers: { friendliness: 0.8, urgency: 0.3 } }
  |     |-- GPT-4o call (temperature 0.3)
  |     └── Generates 3 style variants:
  |           Standard:  "Thanks for the update. Ready by 3pm."
  |           Formal:    "Thank you. I will ensure completion by 15:00."
  |           In-Depth:  "Thank you for the update. I appreciate..."
  |-- Cache write: precedents_cache.set(key, DraftResponse)
  └── Optional DB write: draft_cache table"""),

    Paragraph("Step 3.3 — Tone DNA Build (First Use)", sH3),
    code_block(
"""POST /api/tone-dna/build

Backend (ToneDNAService.ingest_and_build):
  |-- Fetch last 90 days of sent emails
  |-- Analyze 50+ emails for:
  |     |-- Formality score (formal vs casual word ratio)
  |     |-- Avg sentence length
  |     |-- Favorite phrases (n-grams appearing 3+ times)
  |     └── Tone markers via spaCy NLP
  |-- Generate profile JSON and write to disk:
  |     ~/.mailmind/tone_dna/tarun@gmail.com.json
  |     { formality_score: 0.72, sample_size: 67,
  |       favorite_phrases: ["looking forward to", "let me know"],
  |       tone_markers: { urgency: 0.3, friendliness: 0.8 } }
  └── Optional DB write: tone_dna_profiles table"""),

    Paragraph("Step 3.4 — Calendar Conflict Detection", sH3),
    code_block(
"""Frontend (CommitmentGate):
  |-- Commitment: "Call client by 3pm" -> deadline 2024-06-11T15:00:00Z
  |-- Calendar event: "Client call" 3pm-4pm
  └── Detects overlap -> ConflictBadge: "Conflicts with 'Client call' at 3pm"

Backend (optional): check_calendar_conflict() in calendar_node
  └─ Marks commitment as has_conflict = true"""),
    PageBreak(),
]

# ── Phase 4 ───────────────────────────────────────────────────────
story += [
    Paragraph("Phase 4: User Approves Commitments", sH2),
    Paragraph("Step 4.1 — CommitmentGate UI", sH3),
    code_block(
"""Frontend displays:
  |-- [x] "Call client by 3pm"  [!] (conflicts with existing meeting)
  └── [x] "Submit report"       (Tomorrow 9am)

User reviews, unchecks items to skip, clicks "Confirm"
  └─ POST /api/commitments/confirm  + X-Approval-Token header"""),

    Paragraph("Step 4.2 — Create Calendar Events &amp; Tasks", sH3),
    code_block(
"""Backend (CommitmentService.confirm):
  |-- Validates X-Approval-Token header (CSRF protection)
  |-- For each approved commitment:
  |     If type == "call" / "meeting":
  |       -> Creates calendar event via Gmail/Graph API
  |          POST https://www.googleapis.com/.../events
  |          { title, start, end, description, source: "MailMind" }
  |     If type == "deliverable" / "task":
  |       -> Creates task in Google Tasks / Microsoft To Do
  |          POST .../tasks  { title, dueDateTime, body }
  |-- DB writes:
  |     commitments table UPDATE:
  |       status -> "confirmed", calendar_event_id, task_id,
  |       confirmed_at, confirmed_by
  └── audit_logs table:
      { action: "commitment_confirmed", user_id, email_id, timestamp }

Frontend: Toast "2 items added to calendar" + task/event links"""),
    Spacer(1, 4),
]

# ── Phase 5 ───────────────────────────────────────────────────────
story += [
    Paragraph("Phase 5: Draft Approval &amp; Send", sH2),
    Paragraph("Step 5.1 — User Reviews Draft", sH3),
    code_block(
"""DraftPanel shows 3 style tabs:
  Standard:  "Thanks for the update. I'll have everything ready by 3pm."
  Formal:    "Thank you for the notification. Completion by 15:00."
  In-Depth:  "Thank you for the update. I appreciate the clarity..."

User can: switch styles, edit text inline, view precedent citations, send"""),

    Paragraph("Step 5.2 — Send Reply", sH3),
    code_block(
"""POST /api/emails/18a.../reply { comment: "[edited draft]" }

Backend:
  |-- GmailClient.send_reply()
  |     |-- Constructs reply with In-Reply-To + References headers
  |     └── POST https://www.googleapis.com/gmail/v1/users/me/messages/send
  |-- DB writes:
  |     sent_emails:  { message_id, user_id, to, subject, body, replied_to, sent_at }
  |     emails:       UPDATE { replied: true, reply_sent_at }
  └── Analytics: draft_analytics table
      { email_id, style_selected, time_to_send_ms }

Frontend: Toast "Reply sent" -> inbox refreshes"""),
    Spacer(1, 4),
]

# ── Phase 6 ───────────────────────────────────────────────────────
story += [
    Paragraph("Phase 6: Pagination", sH2),
    code_block(
"""User scrolls to bottom of email list
  └─ useEmails hook detects near-end
  └─ nextPage() -> fetchEmails(page_token="abc123def456")

Backend: Gmail API resumes from token -> returns emails 51-100

Frontend:
  |-- Appends 50 more emails to array
  └── POST /api/triage/batch for new emails (cache hits where possible)"""),
    Spacer(1, 4),
]

# ── Phase 7 ───────────────────────────────────────────────────────
story += [
    Paragraph("Phase 7: Session Persistence &amp; Auto-Resume", sH2),
    code_block(
"""User returns next day (in-process token cache cleared by server restart):

Frontend: localStorage["remembered_login"] found -> calls checkAuthStatus()

Backend:
  |-- _user_token_cache is empty
  |-- Reads ~/.cache/google_credentials.json -> extracts refresh_token
  |-- POST https://oauth2.googleapis.com/token
  |     grant_type=refresh_token -> receives new access_token
  |-- Updates _user_token_cache with new token
  └── Returns { authenticated: true, user_principal_name: "tarun@gmail.com" }

Frontend: quickLogin() -> router.push("/dashboard")  (no re-auth screen)
  └─ userStorage.setUser() restores scoped preferences from previous session"""),
    PageBreak(),
]

# ═══════════════════════════════════════════════════════════════════
# SECTION 3 — CACHING STRATEGY
# ═══════════════════════════════════════════════════════════════════
story += [
    Paragraph("3. Caching Strategy Summary", sH1),
    rule(),
    Paragraph("Layer 1: Browser localStorage (Frontend)", sH2),
    data_table(
        ["Key", "Value", "Persistence"],
        [
            ["`remembered_login`", "{ email, provider }", "Until cleared"],
            ["`userStorage:{user}`", "Search filters, sort, theme", "Until cleared"],
        ],
        col_widths=[W*0.35, W*0.40, W*0.25]
    ),
    Spacer(1, 8),

    Paragraph("Layer 2: In-Process Memory (Backend)", sH2),
    data_table(
        ["Cache", "Key Pattern", "TTL"],
        [
            ["triage_cache",           "id:{user}:{email_id}",        "1 hour"],
            ["classification_cache",   "classify:{user}:{sha256}",    "1 hour"],
            ["precedents_cache",       "retrieve:{user}:{sha256}",    "Indefinite"],
            ["calendar_cache",         "{user_id}",                   "5 minutes"],
            ["google_auth_status",     "{state}",                     "Until OAuth completes"],
            ["ms_auth_status",         "{state}",                     "Until OAuth completes"],
        ],
        col_widths=[W*0.32, W*0.40, W*0.28]
    ),
    Spacer(1, 8),

    Paragraph("Layer 3: File System (Backend)", sH2),
    data_table(
        ["Path", "Content"],
        [
            ["~/.cache/google_credentials.json",        "Google refresh token"],
            ["~/.mailmind/tone_dna/{user}.json",         "Tone DNA profile"],
        ],
        col_widths=[W*0.55, W*0.45]
    ),
    Spacer(1, 8),

    Paragraph("Layer 4: Database (Optional — if DATABASE_URL set)", sH2),
    Paragraph(
        "Tables: <code>emails</code>, <code>triage_cache</code>, <code>classifications</code>, "
        "<code>commitments</code>, <code>tone_dna_profiles</code>, <code>audit_logs</code>, "
        "<code>draft_cache</code>, <code>retrieval_logs</code>",
        sBody),
    Spacer(1, 6),

    Paragraph("Cache Invalidation Rules", sH3),
    bullet("RAG index — Manual refresh via POST /api/rag/settings"),
    bullet("Tone DNA — Manual rebuild via POST /api/tone-dna/build"),
    bullet("Triage / Classification — Auto-expire after 1 hour"),
    bullet("Calendar — Auto-expire after 5 minutes"),
    Spacer(1, 8),
]

# ═══════════════════════════════════════════════════════════════════
# SECTION 4 — END-TO-END TIMELINE
# ═══════════════════════════════════════════════════════════════════
story += [
    Paragraph("4. End-to-End Timeline (Single Email)", sH1),
    rule(),
    code_block(
"""T+0ms:      User clicks email
T+50ms:     Mark as read -> POST /api/emails/{id}/read
T+150ms:    6 parallel AI calls start:
              POST /api/classify              (~500ms)
              POST /api/triage                (~100ms, cached)
              POST /api/commitments/extract   (~1200ms, LLM)
              GET  /api/calendar              (~300ms)
              POST /api/rag/retrieve          (~800ms, embedding + ChromaDB)
              POST /api/rag/draft             (~1500ms, LLM)
T+1500ms:   All calls complete -> full EmailDetail renders
            Triage badge + axes, commitments, calendar conflicts,
            draft (3 styles), precedent citations
T+5000ms:   User clicks "Confirm Commitments"
              -> Calendar events + tasks created (~700ms)
T+5700ms:   User clicks "Send" on draft
              -> Reply delivered via Gmail API (~200ms)
T+5900ms:   Toast: "Reply sent, 2 items added to calendar"

Total: ~6 seconds for the full workflow (LLM + mail provider calls)"""),
    Spacer(1, 8),
]

# ═══════════════════════════════════════════════════════════════════
# SECTION 5 — EXTERNAL INTEGRATIONS
# ═══════════════════════════════════════════════════════════════════
story += [
    Paragraph("5. External Integrations", sH1),
    rule(),
    data_table(
        ["Integration", "Purpose"],
        [
            ["Microsoft Graph API",        "Outlook mail, Calendar, Teams, To Do"],
            ["Gmail API",                  "Gmail mail, Google Calendar, Google Tasks"],
            ["Azure OpenAI (GPT-4o)",      "Classification, triage, commitment extraction, draft generation"],
            ["ChromaDB",                   "Local/cloud vector DB for RAG precedent retrieval"],
            ["spaCy (en_core_web_sm)",     "NLP for sentiment scoring and tone analysis"],
            ["Vercel Analytics",           "Frontend observability"],
            ["Sentry (optional)",          "Backend error tracking and performance monitoring"],
        ],
        col_widths=[W*0.38, W*0.62]
    ),
    Spacer(1, 16),
    rule(),
    Paragraph("Document generated from MailMind codebase &mdash; June 2026", sNote),
]

# ── Build ─────────────────────────────────────────────────────────────────────
doc.build(story)
print(f"PDF written to: {OUTPUT}")
