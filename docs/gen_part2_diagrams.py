"""Part 2: LangGraph pipeline, auth flow, email processing flow, sync flow, DB ER diagram."""
import os, math
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

W, H = A4

DARK_NAVY  = HexColor('#0f172a')
NAVY       = HexColor('#1e3a5f')
BLUE       = HexColor('#2563eb')
LIGHT_BLUE = HexColor('#dbeafe')
SKY        = HexColor('#38bdf8')
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

OUT = os.path.join(os.path.dirname(__file__), 'part2_diagrams.pdf')

def make_styles():
    S = {}
    S['h1'] = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=22,
        textColor=NAVY, spaceAfter=10, spaceBefore=20)
    S['h2'] = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=14,
        textColor=NAVY, spaceAfter=6, spaceBefore=14)
    S['h3'] = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=11,
        textColor=GRAY_900, spaceAfter=4, spaceBefore=10)
    S['body'] = ParagraphStyle('body', fontName='Helvetica', fontSize=9,
        textColor=GRAY_700, spaceAfter=4, leading=14)
    S['small'] = ParagraphStyle('small', fontName='Helvetica', fontSize=8,
        textColor=GRAY_500, spaceAfter=2, leading=12)
    S['caption'] = ParagraphStyle('caption', fontName='Helvetica', fontSize=8,
        textColor=GRAY_500, alignment=TA_CENTER, spaceAfter=8)
    return S

class DiagramFlowable(Flowable):
    def __init__(self, width, height, draw_fn):
        super().__init__()
        self.width = width
        self.height = height
        self._draw_fn = draw_fn
    def draw(self):
        self._draw_fn(self.canv, self.width, self.height)

def arrow(c, x1, y1, x2, y2, color=GRAY_700, lw=1.2, dashed=False):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    if dashed:
        c.setDash(4, 3)
    else:
        c.setDash()
    c.line(x1, y1, x2, y2)
    c.setDash()
    ang = math.atan2(y2 - y1, x2 - x1)
    size = 5
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - size * math.cos(ang - 0.4), y2 - size * math.sin(ang - 0.4))
    p.lineTo(x2 - size * math.cos(ang + 0.4), y2 - size * math.sin(ang + 0.4))
    p.close()
    c.drawPath(p, fill=1, stroke=0)

def box(c, x, y, w, h, fill=LIGHT_BLUE, stroke=BLUE, text='',
        text_color=GRAY_900, font='Helvetica-Bold', font_size=8, radius=4):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    if text:
        c.setFillColor(text_color)
        c.setFont(font, font_size)
        lines = text.split('\n')
        lh = font_size + 2
        total = lh * len(lines)
        sy = y + h/2 + total/2 - lh + 1
        for i, ln in enumerate(lines):
            c.drawCentredString(x + w/2, sy - i * lh, ln)

def lbl(c, x, y, text, sz=7, col=GRAY_500, align='c'):
    c.setFillColor(col)
    c.setFont('Helvetica', sz)
    if align == 'c':
        c.drawCentredString(x, y, text)
    elif align == 'l':
        c.drawString(x, y, text)
    else:
        c.drawRightString(x, y, text)

# ── DIAGRAM: LangGraph 6-Node Pipeline ───────────────────────────────────────
def draw_langgraph(c, W, H):
    c.setFillColor(GRAY_100)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, H - 14, 'LangGraph Pipeline — 6-Node DAG (EmailAgentState)')

    # Layout: ingest (top center) → 3 parallel (triage | commitment | rag) → calendar → gate (bottom)
    cx = W / 2
    bw = 88
    bh = 44

    # Node positions
    n_ingest   = (cx - bw/2, H - 70)
    n_triage   = (cx - bw - 60, H - 148)
    n_commit   = (cx - bw/2,    H - 148)
    n_rag      = (cx + 60,       H - 148)
    n_calendar = (cx - bw/2,    H - 220)
    n_gate     = (cx - bw/2,    H - 292)

    # Draw nodes
    box(c, *n_ingest, bw, bh, fill=INDIGO_LT, stroke=INDIGO,
        text='1. INGEST\nPII Masking\nPresidio + spaCy')
    box(c, *n_triage, bw, bh, fill=RED_LT, stroke=RED,
        text='2. TRIAGE\n5-Axis Scoring\ngpt-4o-mini')
    box(c, *n_commit, bw, bh, fill=ORANGE_LT, stroke=ORANGE,
        text='3. COMMITMENT\nExtraction\ngpt-4o')
    box(c, *n_rag, bw, bh, fill=GREEN_LT, stroke=GREEN,
        text='4. RAG\nPrecedent + Draft\ngpt-4o')
    box(c, *n_calendar, bw, bh, fill=PURPLE_LT, stroke=PURPLE,
        text='5. CALENDAR\nConflict Detection\nDeterministic')
    box(c, *n_gate, bw, bh, fill=TEAL_LT, stroke=TEAL,
        text='6. GATE\nApproval\nHuman-in-loop')

    # Edges
    in_cx = n_ingest[0] + bw/2
    in_bot = n_ingest[1]
    arrow(c, in_cx, in_bot, n_triage[0] + bw/2,  n_triage[1] + bh, color=RED)
    arrow(c, in_cx, in_bot, n_commit[0] + bw/2,  n_commit[1] + bh, color=ORANGE)
    arrow(c, in_cx, in_bot, n_rag[0] + bw/2,     n_rag[1] + bh,    color=GREEN)

    # Parallel annotation
    c.setFillColor(GRAY_500)
    c.setFont('Helvetica', 7)
    c.drawCentredString(W/2, H - 128, '⟵  Parallel Fan-out (asyncio.gather)  ⟶')

    # All three feed into calendar
    cal_cx = n_calendar[0] + bw/2
    cal_top = n_calendar[1] + bh
    arrow(c, n_triage[0] + bw/2, n_triage[1], cal_cx, cal_top, color=PURPLE)
    arrow(c, n_commit[0] + bw/2, n_commit[1], cal_cx, cal_top, color=PURPLE)
    arrow(c, n_rag[0] + bw/2,   n_rag[1],    cal_cx, cal_top, color=PURPLE)

    # Calendar → Gate
    gate_top = n_gate[1] + bh
    arrow(c, cal_cx, n_calendar[1], cal_cx, gate_top, color=TEAL)

    # START node
    box(c, cx - 20, H - 28, 40, 16, fill=NAVY, stroke=NAVY,
        text='START', text_color=WHITE, font_size=7, radius=8)
    arrow(c, cx, H - 28, cx, n_ingest[1] + bh, color=NAVY)

    # END node
    box(c, cx - 20, n_gate[1] - 22, 40, 16, fill=GRAY_700, stroke=GRAY_700,
        text='END', text_color=WHITE, font_size=7, radius=8)
    arrow(c, cx, n_gate[1], cx, n_gate[1] - 22 + 16, color=GRAY_700)

    # State fields annotations
    c.setFillColor(GRAY_100)
    c.setStrokeColor(GRAY_200)
    c.setLineWidth(0.5)
    ann_x = 10
    ann_y = H - 310
    ann_w = W - 20
    c.roundRect(ann_x, ann_y, ann_w, 80, 4, fill=1, stroke=1)
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 8)
    c.drawString(ann_x + 6, ann_y + 68, 'EmailAgentState (TypedDict) — key fields flowing through the pipeline:')
    state_fields = [
        'Input: email_id, sender, subject, body, received_at',
        'After Ingest: masked_body, masked_subject, mask_mapping',
        'After Triage: axes[5], dynamic_weights, composite_score, priority, email_type, approval_mode, triage_reasoning',
        'After Commit: commitments[], commitment_reasoning',
        'After Calendar: conflict_summary',
        'After RAG: draft_reply, precedents[]',
        'After Gate: approved (bool)',
    ]
    c.setFont('Helvetica', 7)
    c.setFillColor(GRAY_700)
    for i, f in enumerate(state_fields):
        c.drawString(ann_x + 8, ann_y + 56 - i * 9, f'• {f}')

    # Latency badge
    box(c, W - 100, H - 30, 95, 22, fill=GREEN_LT, stroke=GREEN,
        text='p95 Latency: 2.8s\n(parallel fan-out)', font_size=7)

# ── DIAGRAM: Auth Flow ────────────────────────────────────────────────────────
def draw_auth_flow(c, W, H):
    c.setFillColor(GRAY_100)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, H - 14, 'OAuth Authentication Flow')

    # Swimlane columns
    cols = ['User Browser', 'Next.js\nFrontend', 'FastAPI\nBackend', 'OAuth Provider\n(Google/MSFT)', 'Supabase\nDatabase']
    n = len(cols)
    sw = W / n
    LANE_EVEN = HexColor('#f0f7ff')
    LANE_ODD  = HexColor('#f5f3ff')
    for i, col in enumerate(cols):
        cx2 = i * sw + sw/2
        c.setFillColor(LANE_EVEN if i % 2 == 0 else LANE_ODD)
        c.rect(i * sw, 0, sw, H - 30, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.rect(i * sw, H - 30, sw, 28, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 7.5)
        lines = col.split('\n')
        for j, ln in enumerate(lines):
            c.drawCentredString(cx2, H - 16 - j * 10, ln)
        # vertical dashed line
        c.setStrokeColor(GRAY_200)
        c.setDash(3, 3)
        c.setLineWidth(0.5)
        c.line(cx2, 10, cx2, H - 30)
        c.setDash()

    # Steps
    steps = [
        # (y, from_col, to_col, label, color, note)
        (H - 58,  0, 1, 'Click "Sign in with Google"', BLUE, ''),
        (H - 78,  1, 2, 'GET /api/auth/google', BLUE, ''),
        (H - 98,  2, 3, 'Redirect to OAuth consent screen', GREEN, '302'),
        (H - 118, 3, 0, 'User grants consent → redirect back', GREEN, 'code + state'),
        (H - 138, 0, 2, 'GET /api/auth/google/callback?code=...', BLUE, ''),
        (H - 158, 2, 3, 'Exchange code for tokens', ORANGE, 'POST token endpoint'),
        (H - 178, 3, 2, 'access_token + refresh_token', ORANGE, ''),
        (H - 200, 2, 4, 'Upsert User + OAuthAccount', PURPLE, 'Fernet-encrypt tokens'),
        (H - 220, 4, 2, 'user_id + account_id', PURPLE, ''),
        (H - 240, 2, 4, 'Create UserSession (SHA-256 hash)', TEAL, '24h TTL'),
        (H - 260, 2, 0, 'Set mm_session cookie (HttpOnly)', TEAL, 'SameSite=Lax'),
        (H - 280, 0, 1, 'Redirect → /dashboard', BLUE, ''),
        (H - 300, 1, 2, 'API calls with cookie (credentials:include)', NAVY, 'All subsequent calls'),
    ]

    for (y, fc, tc, lbl_txt, col, note) in steps:
        x1 = fc * sw + sw/2
        x2 = tc * sw + sw/2
        arrow(c, x1, y, x2, y, color=col, lw=1.2)
        mid = (x1 + x2) / 2
        c.setFillColor(col)
        c.setFont('Helvetica', 6.5)
        c.drawCentredString(mid, y + 3, lbl_txt)
        if note:
            c.setFillColor(GRAY_500)
            c.setFont('Helvetica', 6)
            c.drawCentredString(mid, y - 8, f'[{note}]')

    # Security note box
    box(c, 6, 6, W - 12, 28, fill=GREEN_LT, stroke=GREEN,
        text='Security: Fernet-AES-128 token encryption at rest · SHA-256 session hashing · HttpOnly + SameSite cookies · PKCE for OAuth',
        font='Helvetica', font_size=7, text_color=GRAY_700)

# ── DIAGRAM: Email Processing Flow ───────────────────────────────────────────
def draw_email_flow(c, W, H):
    c.setFillColor(GRAY_100)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, H - 14, 'Email Processing Flow — Inbox to Draft')

    # Top-down flow
    steps = [
        (H - 50,  'Email Arrives', 'Webhook (Graph/Gmail) or\ndashboard mount → delta sync', BLUE, LIGHT_BLUE),
        (H - 108, 'Mailbox Mirror', 'SyncService.delta_sync()\nupsert_messages() → mailbox_message', PURPLE, PURPLE_LT),
        (H - 166, 'Inbox Page Load', 'list_page() LEFT JOIN enrichment\nServer-side pagination + sort', INDIGO, INDIGO_LT),
        (H - 224, 'Triage (Phase 1)', 'POST /api/agent/triage\n5-axis scoring gpt-4o-mini\nSSE streaming per email', RED, RED_LT),
        (H - 282, 'Email Selected', 'User clicks email row\nuseEmailDetail hook fires', ORANGE, ORANGE_LT),
        (H - 340, 'Enrichment (Phase 2)', 'POST /api/agent/enrich\ncommitments + calendar + RAG\nPersist to email_enrichment', GREEN, GREEN_LT),
        (H - 398, 'Draft Generated', 'DraftService.generate_draft()\nTone DNA prefix + RAG context\nGPT-4o completion', TEAL, TEAL_LT),
        (H - 438, 'Mark Done / Send', 'record_priority_override(status=done)\nmailbox_message.state = done', GRAY_700, GRAY_200),
    ]

    bw2 = 160
    bh2 = 46
    cx = W / 2 - bw2/2

    for (y, title, desc, stroke_col, fill_col) in steps:
        box(c, cx, y - bh2, bw2, bh2, fill=fill_col, stroke=stroke_col,
            text=f'{title}\n{desc}', font_size=7, text_color=GRAY_900)
        if y != H - 438:
            arrow(c, cx + bw2/2, y - bh2, cx + bw2/2, y - bh2 - 14, color=stroke_col)

    # Side annotations
    anns = [
        (H - 70,  'Graph API / Gmail API', 'l', 10),
        (H - 128, 'DB write (upsert)', 'l', 10),
        (H - 186, 'DB read (paginated)', 'l', 10),
        (H - 244, 'LLM (gpt-4o-mini)', 'l', 10),
        (H - 302, 'Frontend hook', 'l', 10),
        (H - 360, 'LLM (gpt-4o) + ChromaDB', 'l', 10),
        (H - 418, 'Tone DNA profile', 'l', 10),
    ]
    for (y, text, align, x) in anns:
        c.setFillColor(GRAY_500)
        c.setFont('Helvetica', 6.5)
        c.drawString(cx + bw2 + 6, y, f'← {text}')

    # Latency markers
    latencies = [
        (H - 224, '~100ms', RED),
        (H - 340, '<3s', ORANGE),
        (H - 398, '~1.5s', GREEN),
    ]
    for (y, lat, col) in latencies:
        c.setFillColor(col)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(cx - 44, y - bh2/2, lat)

# ── DIAGRAM: Sync / Webhook Flow ──────────────────────────────────────────────
def draw_sync_flow(c, W, H):
    c.setFillColor(GRAY_100)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, H - 14, 'Mailbox Sync & Webhook Flow')

    # Two paths: Microsoft Graph (left) and Gmail (right)
    half = W / 2

    # Microsoft path
    c.setFillColor(BLUE)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(half * 0.5, H - 34, 'Microsoft Graph (Outlook)')
    ms_steps = [
        (H - 68,  'Graph Subscription\nCreate/Renew', BLUE, LIGHT_BLUE),
        (H - 118, 'POST /webhooks/graph\nChange notification', BLUE, LIGHT_BLUE),
        (H - 168, 'delta_sync(account, INBOX)', PURPLE, PURPLE_LT),
        (H - 218, 'Graph delta query\n(deltaToken cursor)', BLUE, LIGHT_BLUE),
        (H - 268, 'upsert_messages()\ntombstone deleted', TEAL, TEAL_LT),
        (H - 318, 'Enqueue triage job\nEmailQueue.enqueue()', GREEN, GREEN_LT),
    ]
    bw3 = half * 0.7
    cx3 = (half - bw3) / 2
    for i, (y, txt, sc, fc) in enumerate(ms_steps):
        box(c, cx3, y - 38, bw3, 34, fill=fc, stroke=sc, text=txt, font_size=7)
        if i < len(ms_steps) - 1:
            arrow(c, cx3 + bw3/2, y - 38, cx3 + bw3/2, y - 38 - 10, color=sc)

    # Gmail path
    c.setFillColor(RED)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(half + half * 0.5, H - 34, 'Gmail (Cloud Pub/Sub)')
    gm_steps = [
        (H - 68,  'Gmail Watch\n(Pub/Sub topic)', RED, RED_LT),
        (H - 118, 'POST /webhooks/gmail\nPub/Sub push msg', RED, RED_LT),
        (H - 168, 'delta_sync(account, INBOX)', PURPLE, PURPLE_LT),
        (H - 218, 'Gmail history.list\n(historyId cursor)', RED, RED_LT),
        (H - 268, 'upsert_messages()\ntombstone deleted', TEAL, TEAL_LT),
        (H - 318, 'Enqueue triage job\nEmailQueue.enqueue()', GREEN, GREEN_LT),
    ]
    cx4 = half + (half - bw3) / 2
    for i, (y, txt, sc, fc) in enumerate(gm_steps):
        box(c, cx4, y - 38, bw3, 34, fill=fc, stroke=sc, text=txt, font_size=7)
        if i < len(gm_steps) - 1:
            arrow(c, cx4 + bw3/2, y - 38, cx4 + bw3/2, y - 38 - 10, color=sc)

    # Divider
    c.setStrokeColor(GRAY_200)
    c.setDash(4, 4)
    c.line(half, H - 26, half, 40)
    c.setDash()

    # Convergence note
    box(c, 20, 8, W - 40, 28, fill=GREEN_LT, stroke=GREEN,
        text='Graceful degradation: BACKEND_PUBLIC_URL unset → webhooks skipped, dashboard-mount triggers delta_sync instead',
        font='Helvetica', font_size=7, text_color=GRAY_700)

# ── BUILD PDF ─────────────────────────────────────────────────────────────────
def build():
    S = make_styles()
    dw = W - 36*mm

    def hf(c, doc):
        c.saveState()
        pg = doc.page
        c.setFillColor(NAVY)
        c.rect(0, H - 22, W, 22, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(15, H - 14, 'MailMind — Technical Documentation')
        c.setFont('Helvetica', 7)
        c.drawRightString(W - 15, H - 14, 'CONFIDENTIAL')
        c.setFillColor(HexColor('#e5e7eb'))
        c.rect(0, 0, W, 18, fill=1, stroke=0)
        c.setFillColor(GRAY_500)
        c.setFont('Helvetica', 7)
        c.drawString(15, 5, 'MailMind v2.0 · Radiant CodeX · 2025')
        c.drawRightString(W - 15, 5, f'Page {pg}')
        c.restoreState()

    doc = SimpleDocTemplate(
        OUT, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=28*mm, bottomMargin=22*mm,
    )

    story = []

    # ── LangGraph Pipeline ────────────────────────────────────────────────────
    story.append(Paragraph('LangGraph Pipeline Architecture', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'MailMind uses a 6-node LangGraph DAG (Directed Acyclic Graph) to process each email. '
        'After ingestion and PII masking, nodes 2–4 (triage, commitment, RAG) run in parallel '
        'using asyncio.gather(), reducing latency by ~60%. '
        'Calendar conflict detection and the approval gate run sequentially after the parallel phase.',
        S['body']
    ))
    story.append(DiagramFlowable(dw, 155*mm, draw_langgraph))
    story.append(Paragraph(
        'Fig 1: The six pipeline nodes, parallel fan-out edges, and EmailAgentState fields. '
        'All nodes share a single TypedDict state object that accumulates results.',
        S['caption']
    ))
    story.append(PageBreak())

    # ── Auth Flow ─────────────────────────────────────────────────────────────
    story.append(Paragraph('OAuth Authentication Flow', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'MailMind supports Google and Microsoft (Entra ID) OAuth 2.0. After the consent redirect, '
        'the backend exchanges the code for tokens, Fernet-encrypts them at rest, '
        'upserts the user/account rows, creates a session with SHA-256 hashed token, '
        'and returns an HttpOnly cookie (SameSite=Lax).',
        S['body']
    ))
    story.append(DiagramFlowable(dw, 155*mm, draw_auth_flow))
    story.append(Paragraph(
        'Fig 2: Swim-lane OAuth flow. Tokens encrypted with Fernet-AES-128; sessions hashed with SHA-256.',
        S['caption']
    ))
    story.append(PageBreak())

    # ── Email Processing Flow ─────────────────────────────────────────────────
    story.append(Paragraph('Email Processing Flow', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'Email processing is split into two user-facing phases. Phase 1 (triage) '
        'runs immediately on inbox load and populates priority badges within ~100ms per email '
        'using SSE streaming. Phase 2 (enrichment) runs when an email is opened, '
        'fetching commitments, calendar conflicts, RAG precedents, and a draft reply.',
        S['body']
    ))
    story.append(DiagramFlowable(dw, 148*mm, draw_email_flow))
    story.append(Paragraph(
        'Fig 3: End-to-end email flow from arrival to draft generation. Side notes show LLM used per stage.',
        S['caption']
    ))
    story.append(PageBreak())

    # ── Sync Flow ─────────────────────────────────────────────────────────────
    story.append(Paragraph('Mailbox Sync & Webhook Flow', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'MailMind maintains a server-side mailbox mirror (MailboxMessage table) synced via '
        'Microsoft Graph delta queries and Gmail history.list. Webhooks trigger near-real-time '
        'delta syncs. If BACKEND_PUBLIC_URL is unset, the system degrades gracefully to '
        'on-mount triggered syncs.',
        S['body']
    ))
    story.append(DiagramFlowable(dw, 135*mm, draw_sync_flow))
    story.append(Paragraph(
        'Fig 4: Side-by-side Microsoft Graph (left) and Gmail (right) webhook and delta sync paths.',
        S['caption']
    ))

    doc.build(story, onFirstPage=hf, onLaterPages=hf)
    print(f'[OK] {OUT}')

build()
