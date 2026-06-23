"""Part 1: Cover page, TOC placeholder, Executive Summary, System Architecture diagrams."""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Flowable

W, H = A4

# ── Palette ───────────────────────────────────────────────────────────────────
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

OUT = os.path.join(os.path.dirname(__file__), 'part1_overview.pdf')

# ── Styles ────────────────────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()
    S = {}
    S['h1'] = ParagraphStyle('h1', fontName='Helvetica-Bold', fontSize=22,
        textColor=NAVY, spaceAfter=10, spaceBefore=20)
    S['h2'] = ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=15,
        textColor=NAVY, spaceAfter=6, spaceBefore=14, borderPad=4)
    S['h3'] = ParagraphStyle('h3', fontName='Helvetica-Bold', fontSize=11,
        textColor=GRAY_900, spaceAfter=4, spaceBefore=10)
    S['body'] = ParagraphStyle('body', fontName='Helvetica', fontSize=9,
        textColor=GRAY_700, spaceAfter=4, leading=14)
    S['small'] = ParagraphStyle('small', fontName='Helvetica', fontSize=8,
        textColor=GRAY_500, spaceAfter=2, leading=12)
    S['code'] = ParagraphStyle('code', fontName='Courier', fontSize=8,
        textColor=GRAY_900, backColor=GRAY_100, spaceAfter=2, leading=12,
        leftIndent=8, rightIndent=8)
    S['center'] = ParagraphStyle('center', fontName='Helvetica', fontSize=9,
        textColor=GRAY_700, alignment=TA_CENTER)
    S['label'] = ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=8,
        textColor=GRAY_500, spaceAfter=2)
    S['bullet'] = ParagraphStyle('bullet', fontName='Helvetica', fontSize=9,
        textColor=GRAY_700, leftIndent=16, spaceAfter=2, leading=13)
    return S

# ── Canvas diagram helpers ────────────────────────────────────────────────────
class DiagramFlowable(Flowable):
    """Base for inline canvas-drawn diagrams."""
    def __init__(self, width, height, draw_fn):
        super().__init__()
        self.width = width
        self.height = height
        self._draw_fn = draw_fn

    def draw(self):
        self._draw_fn(self.canv, self.width, self.height)

def arrow(c, x1, y1, x2, y2, color=GRAY_700, lw=1.2):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x1, y1, x2, y2)
    # arrowhead
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    size = 5
    c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - size * math.cos(ang - 0.4), y2 - size * math.sin(ang - 0.4))
    p.lineTo(x2 - size * math.cos(ang + 0.4), y2 - size * math.sin(ang + 0.4))
    p.close()
    c.drawPath(p, fill=1, stroke=0)

def box(c, x, y, w, h, fill=LIGHT_BLUE, stroke=BLUE, text='', text_color=GRAY_900,
        font='Helvetica-Bold', font_size=8, radius=4):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)
    if text:
        c.setFillColor(text_color)
        c.setFont(font, font_size)
        lines = text.split('\n')
        line_h = font_size + 2
        total = line_h * len(lines)
        start_y = y + h/2 + total/2 - line_h + 2
        for i, ln in enumerate(lines):
            c.drawCentredString(x + w/2, start_y - i * line_h, ln)

def diamond(c, cx, cy, hw, hh, fill=ORANGE_LT, stroke=ORANGE, text='', font_size=8):
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(1)
    p = c.beginPath()
    p.moveTo(cx, cy + hh)
    p.lineTo(cx + hw, cy)
    p.lineTo(cx, cy - hh)
    p.lineTo(cx - hw, cy)
    p.close()
    c.drawPath(p, fill=1, stroke=1)
    if text:
        c.setFillColor(GRAY_900)
        c.setFont('Helvetica', font_size)
        c.drawCentredString(cx, cy - 3, text)

def label(c, x, y, text, font_size=7, color=GRAY_500, align='center'):
    c.setFillColor(color)
    c.setFont('Helvetica', font_size)
    if align == 'center':
        c.drawCentredString(x, y, text)
    elif align == 'left':
        c.drawString(x, y, text)
    else:
        c.drawRightString(x, y, text)

# ── DIAGRAM 1: System Architecture ───────────────────────────────────────────
def draw_system_arch(c, W, H):
    """Full system architecture: users → frontend → backend → Azure/Supabase."""
    c.setFillColor(GRAY_100)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Title
    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, H - 16, 'MailMind — System Architecture')

    # ── Layer positions ──────────────────────────────────────────────────────
    # Browsers / users  (top)
    # Frontend: Next.js 15 on Vercel  (row 1)
    # Backend: FastAPI on Azure Container Apps  (row 2)
    # Data layer: Supabase + Redis + ChromaDB  (row 3)
    # AI layer: Azure OpenAI + Groq  (row 4)
    # Observability: LangSmith + OTel  (row 5, bottom)

    lx = 10  # left x
    bw = W - 20  # band width

    BAND_COLORS = {
        'sky': HexColor('#e0f2fe'), 'blue': HexColor('#dbeafe'),
        'navy': HexColor('#e0e7ff'), 'purple': HexColor('#ede9fe'),
        'green': HexColor('#d1fae5'), 'orange': HexColor('#fef3c7'),
    }

    def band(y, h, color, color_key, title):
        c.setFillColor(BAND_COLORS[color_key])
        c.rect(lx, y, bw, h, fill=1, stroke=0)
        c.setFillColor(color)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(lx + 4, y + h - 10, title)

    band(H - 45,  30, SKY,    'sky',    'CLIENT LAYER')
    band(H - 105, 55, BLUE,   'blue',   'PRESENTATION LAYER  (Vercel CDN)')
    band(H - 195, 85, NAVY,   'navy',   'APPLICATION LAYER  (Azure Container Apps)')
    band(H - 285, 85, PURPLE, 'purple', 'DATA LAYER  (Supabase · Redis · ChromaDB)')
    band(H - 375, 85, GREEN,  'green',  'AI / ML LAYER  (Azure OpenAI · Groq · spaCy)')
    band(H - 435, 55, ORANGE, 'orange', 'OBSERVABILITY  (LangSmith · OpenTelemetry)')

    # ── CLIENT ───────────────────────────────────────────────────────────────
    for i, (lbl, x) in enumerate([('Chrome', W*0.25), ('Safari', W*0.5), ('Edge', W*0.75)]):
        box(c, x-28, H-43, 56, 20, fill=WHITE, stroke=SKY, text=lbl, font_size=8)

    # ── FRONTEND ─────────────────────────────────────────────────────────────
    fy = H - 100
    box(c, 20,  fy, 110, 42, fill=LIGHT_BLUE, stroke=BLUE,
        text='Next.js 15\nApp Router\nTypeScript + Tailwind', font_size=7)
    box(c, 140, fy, 90,  42, fill=LIGHT_BLUE, stroke=BLUE,
        text='GSAP + Three.js\nAnimations\nWebGL Hero', font_size=7)
    box(c, 240, fy, 90,  42, fill=LIGHT_BLUE, stroke=BLUE,
        text='SSE Client\nReal-time\nStreaming', font_size=7)
    box(c, 340, fy, 80,  42, fill=LIGHT_BLUE, stroke=BLUE,
        text='Vercel\nEdge CDN\nGlobal', font_size=7)

    arrow(c, W*0.5, H-45, W*0.5, H-58, color=BLUE)
    arrow(c, W*0.5, H-58, W*0.5, H-45, color=BLUE)

    # ── BACKEND ──────────────────────────────────────────────────────────────
    bey = H - 190
    box(c, 10,  bey, 78, 72, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='FastAPI 0.115\nUvicorn ASGI\nPython 3.12', font_size=7)
    box(c, 95,  bey, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='LangGraph\n6-Node DAG', font_size=7)
    box(c, 95,  bey+36, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='SSE Streaming\n2.8s p95', font_size=7)
    box(c, 172, bey, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='Presidio PII\nMasking', font_size=7)
    box(c, 172, bey+36, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='Tone DNA\nStylometrics', font_size=7)
    box(c, 249, bey, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='OAuth 2.0\nGoogle + MSFT', font_size=7)
    box(c, 249, bey+36, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='Rate Limiter\n100 req/min', font_size=7)
    box(c, 326, bey, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='Webhook\nSync Engine', font_size=7)
    box(c, 326, bey+36, 70, 32, fill=HexColor('#e0e7ff'), stroke=NAVY,
        text='Enrichment\nWorker Queue', font_size=7)

    arrow(c, W*0.5, H-105, W*0.5, H-118, color=NAVY)

    # ── DATA LAYER ────────────────────────────────────────────────────────────
    dy = H - 280
    box(c, 10,  dy, 100, 68, fill=PURPLE_LT, stroke=PURPLE,
        text='Supabase\nPostgreSQL\n15 Tables\nSession Pooler', font_size=7)
    box(c, 118, dy, 80,  68, fill=PURPLE_LT, stroke=PURPLE,
        text='Redis 7\nAOF Queue\nEnrichment\nBacklog', font_size=7)
    box(c, 206, dy, 90,  68, fill=PURPLE_LT, stroke=PURPLE,
        text='ChromaDB\nVector Index\nRAG Precedents\ntext-ada-002', font_size=7)
    box(c, 304, dy, 90,  68, fill=PURPLE_LT, stroke=PURPLE,
        text='Azure Key Vault\nFernet Tokens\nOAuth Secrets\nSession Keys', font_size=7)

    arrow(c, W*0.5, H-195, W*0.5, H-212, color=PURPLE)

    # ── AI LAYER ──────────────────────────────────────────────────────────────
    ay = H - 370
    box(c, 10,  ay, 90, 68, fill=GREEN_LT, stroke=GREEN,
        text='Azure OpenAI\ngpt-4o\nDraft + Commit\nExtraction', font_size=7)
    box(c, 108, ay, 90, 68, fill=GREEN_LT, stroke=GREEN,
        text='Azure OpenAI\ngpt-4o-mini\nTriage Scoring\n5-Axis', font_size=7)
    box(c, 206, ay, 90, 68, fill=GREEN_LT, stroke=GREEN,
        text='Azure OpenAI\ntext-ada-002\nEmbeddings\nRAG Index', font_size=7)
    box(c, 304, ay, 90, 68, fill=GREEN_LT, stroke=GREEN,
        text='Groq LLM\nFallback\nLlama 3.3 70B\nHigh Avail.', font_size=7)

    arrow(c, W*0.5, H-285, W*0.5, H-300, color=GREEN)

    # ── OBSERVABILITY ─────────────────────────────────────────────────────────
    oy = H - 432
    box(c, 10,  oy, 120, 40, fill=ORANGE_LT, stroke=ORANGE,
        text='LangSmith\nLLM Trace + Eval', font_size=7)
    box(c, 138, oy, 100, 40, fill=ORANGE_LT, stroke=ORANGE,
        text='OpenTelemetry\nSLA Metrics', font_size=7)
    box(c, 246, oy, 100, 40, fill=ORANGE_LT, stroke=ORANGE,
        text='Audit Logger\nCompliance Trail', font_size=7)
    box(c, 354, oy, 40,  40, fill=ORANGE_LT, stroke=ORANGE,
        text='Sentry\nErrors', font_size=7)

    arrow(c, W*0.5, H-375, W*0.5, H-392, color=ORANGE)

    # External arrows (right side)
    c.setStrokeColor(GRAY_500)
    c.setLineWidth(0.7)
    c.setDash(3, 3)
    c.line(W - 8, H - 150, W - 8, H - 380)
    c.setDash()
    c.setFillColor(GRAY_500)
    c.setFont('Helvetica', 7)
    c.saveState()
    c.translate(W - 4, H - 265)
    c.rotate(90)
    c.drawCentredString(0, 0, 'Azure Entra ID OAuth')
    c.restoreState()

# ── DIAGRAM 2: Infrastructure Map ────────────────────────────────────────────
def draw_infra_map(c, W, H):
    c.setFillColor(GRAY_100)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    c.setFillColor(NAVY)
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(W/2, H - 16, 'MailMind — Cloud Infrastructure')

    # Azure box
    c.setFillColor(HexColor('#eef2ff'))
    c.setStrokeColor(BLUE)
    c.setLineWidth(1.5)
    c.roundRect(8, 50, W/2 - 16, H - 80, 6, fill=1, stroke=1)
    c.setFillColor(BLUE)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(16, H - 42, 'Microsoft Azure')

    # Azure resources
    azure_items = [
        ('Azure Container Apps', 'Backend (FastAPI)\nAuto-scaling, HTTPS'),
        ('Azure Container Registry', 'Docker image storage\nmailmind-backend:latest'),
        ('Azure Key Vault', 'Fernet encryption keys\nOAuth client secrets'),
        ('Azure Entra ID', 'OAuth 2.0 provider\nEnterprise SSO'),
        ('Azure OpenAI', 'gpt-4o, gpt-4o-mini\ntext-embedding-ada-002'),
        ('Azure Monitor', 'Container logs\nMetrics & alerts'),
    ]
    for i, (title, desc) in enumerate(azure_items):
        row = i // 2
        col = i % 2
        bx = 16 + col * (W/2 - 32)/2 + col * 4
        by = H - 80 - row * 70 - 30
        bw2 = (W/2 - 32)/2 - 4
        box(c, bx, by, bw2, 52, fill=WHITE, stroke=BLUE,
            text=f'{title}\n{desc}', font_size=6.5)

    # Vercel box
    c.setFillColor(HexColor('#f0fdf4'))
    c.setStrokeColor(GREEN)
    c.setLineWidth(1.5)
    c.roundRect(W/2 + 8, H/2 + 10, W/2 - 16, H/2 - 40, 6, fill=1, stroke=1)
    c.setFillColor(GREEN)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(W/2 + 16, H - 42, 'Vercel')
    box(c, W/2 + 16, H - 88, W/2 - 32, 38, fill=WHITE, stroke=GREEN,
        text='Next.js 15 Frontend\nGlobal Edge CDN\nAuto HTTPS', font_size=7)

    # Supabase box
    c.setFillColor(HexColor('#fdf4ff'))
    c.setStrokeColor(PURPLE)
    c.setLineWidth(1.5)
    c.roundRect(W/2 + 8, 100, W/2 - 16, H/2 - 100, 6, fill=1, stroke=1)
    c.setFillColor(PURPLE)
    c.setFont('Helvetica-Bold', 9)
    c.drawString(W/2 + 16, H/2 + 4, 'Supabase (PostgreSQL)')
    supabase_items = [
        'Session Pooler :5432 (IPv4)',
        'pgbouncer transaction mode',
        '15 tables, UUID PKs',
        'Pool: 10 + overflow 20',
    ]
    for i, txt in enumerate(supabase_items):
        c.setFillColor(GRAY_700)
        c.setFont('Helvetica', 7)
        c.drawString(W/2 + 20, H/2 - 12 - i * 13, f'• {txt}')

    # GitHub Actions box (bottom)
    box(c, 8, 8, W - 16, 36, fill=HexColor('#f8fafc'), stroke=GRAY_500,
        text='GitHub Actions CI/CD — lint · typecheck · pytest · docker build · deploy to Azure Container Apps',
        font_size=7.5)

    # Arrows between zones
    arrow(c, W/2 - 2, H/2 + 60, W/2 + 8, H/2 + 60, color=BLUE)
    label(c, W/2 + 4, H/2 + 63, 'HTTPS', 6, GRAY_500)
    arrow(c, W/2 + W/4, H/2 + 10, W/2 + W/4, 100 + (H/2 - 100), color=PURPLE)
    label(c, W/2 + W/4 + 4, H/2 + 54, 'DB', 6, GRAY_500)

# ── BUILD PDF ─────────────────────────────────────────────────────────────────
def build():
    S = make_styles()

    def header_footer(c, doc):
        c.saveState()
        pg = doc.page
        # header bar
        c.setFillColor(NAVY)
        c.rect(0, H - 22, W, 22, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont('Helvetica-Bold', 8)
        c.drawString(15, H - 14, 'MailMind — Technical Documentation')
        c.setFont('Helvetica', 7)
        c.drawRightString(W - 15, H - 14, 'CONFIDENTIAL')
        # footer
        c.setFillColor(GRAY_200)
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
        onFirstPage=header_footer, onLaterPages=header_footer
    )

    story = []

    # ── COVER PAGE ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 40*mm))
    cov_title = ParagraphStyle('cov_title', fontName='Helvetica-Bold', fontSize=32,
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)
    cov_sub = ParagraphStyle('cov_sub', fontName='Helvetica', fontSize=14,
        textColor=BLUE, alignment=TA_CENTER, spaceAfter=6)
    cov_tag = ParagraphStyle('cov_tag', fontName='Helvetica', fontSize=10,
        textColor=GRAY_500, alignment=TA_CENTER, spaceAfter=3)

    story.append(Paragraph('MailMind', cov_title))
    story.append(Paragraph('AI-Powered Enterprise Email Intelligence', cov_sub))
    story.append(HRFlowable(width='80%', color=BLUE, thickness=2, spaceAfter=12))
    story.append(Paragraph('Technical Architecture & Developer Documentation', cov_tag))
    story.append(Spacer(1, 8*mm))

    meta_data = [
        ['Version', 'v2.0.0'],
        ['Date', '2025'],
        ['Stack', 'FastAPI · Next.js 15 · LangGraph · Azure OpenAI · Supabase'],
        ['Team', 'Radiant CodeX'],
        ['License', 'MIT'],
    ]
    t = Table(meta_data, colWidths=[55*mm, 100*mm])
    t.setStyle(TableStyle([
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 9),
        ('FONT', (1, 0), (1, -1), 'Helvetica', 9),
        ('TEXTCOLOR', (0, 0), (0, -1), GRAY_500),
        ('TEXTCOLOR', (1, 0), (1, -1), GRAY_900),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, GRAY_100]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
        ('BORDERRADIUS', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)

    story.append(Spacer(1, 20*mm))
    story.append(Paragraph(
        'This document provides a comprehensive technical reference for the MailMind codebase — '
        'covering system architecture, file structure, per-file API documentation, '
        'LangGraph pipeline design, database schema, and deployment infrastructure.',
        ParagraphStyle('cov_desc', fontName='Helvetica', fontSize=9.5,
            textColor=GRAY_700, alignment=TA_CENTER, leading=15)
    ))
    story.append(PageBreak())

    # ── EXECUTIVE SUMMARY ─────────────────────────────────────────────────────
    story.append(Paragraph('Executive Summary', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))

    story.append(Paragraph(
        'MailMind is an AI-powered enterprise email triage and drafting platform built for busy '
        'executives who receive hundreds of emails per day. It automatically scores every incoming '
        'email across five contextual axes, extracts calendar commitments, detects conflicts, '
        'retrieves relevant precedents, and generates personalised draft replies — all in under 3 seconds.',
        S['body']
    ))
    story.append(Spacer(1, 4))

    kf_data = [
        ['Key Feature', 'Description', 'Tech'],
        ['5-Axis Triage', 'Scores emails on deadline urgency, sender authority, sentiment, action type, thread decay', 'GPT-4o-mini'],
        ['Tone DNA', 'Learns writing style from 50+ sent emails (8 stylometric features)', 'spaCy + custom NLP'],
        ['RAG Drafting', 'Retrieves 3 similar past emails and injects context into draft generation', 'ChromaDB + Ada-002'],
        ['PII Masking', 'Presidio + spaCy reversible token masking before LLM calls', 'Microsoft Presidio'],
        ['Commitment Extraction', 'Extracts action items with deadlines + calendar conflict detection', 'GPT-4o structured'],
        ['Mailbox Mirror', 'Server-side delta sync (cursor-based) + Graph/Gmail webhooks', 'Graph API + Pub/Sub'],
        ['Multi-Account', 'UUID-based user identity, multiple Gmail/Outlook accounts per user', 'PostgreSQL'],
        ['Demo Login', 'One-click seeded demo with 10 emails, full triage cache, VP persona', 'seed_demo_account.py'],
    ]
    t2 = Table(kf_data, colWidths=[42*mm, 88*mm, 38*mm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (0, -1), 'Helvetica-Bold', 8),
        ('FONT', (1, 1), (-1, -1), 'Helvetica', 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), GRAY_700),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GRAY_100]),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t2)

    story.append(Spacer(1, 8))
    story.append(Paragraph('Technology Stack', S['h2']))
    stack_cols = [
        ('Backend', ['FastAPI 0.115', 'Python 3.12', 'LangGraph 0.2', 'LangChain 0.3', 'SQLAlchemy 2.0']),
        ('Frontend', ['Next.js 15', 'TypeScript 5', 'Tailwind CSS 3', 'GSAP 3', 'Three.js']),
        ('AI / ML', ['Azure OpenAI gpt-4o', 'gpt-4o-mini (triage)', 'text-embedding-ada-002', 'Groq Llama 3.3', 'spaCy en_core_web_sm']),
        ('Infrastructure', ['Azure Container Apps', 'Azure Key Vault', 'Supabase PostgreSQL', 'Redis 7 AOF', 'ChromaDB (local)']),
    ]
    row1 = [[Paragraph(f'<b>{col}</b>', S['label'])] for col, _ in stack_cols]
    row2 = [[Paragraph('<br/>'.join(f'• {i}' for i in items), S['small'])] for _, items in stack_cols]
    t3 = Table([row1, row2], colWidths=[W_text/4 for _ in range(4)] if False else None)
    # manual column widths
    cw = (W - 36*mm) / 4
    t3 = Table([row1, row2], colWidths=[cw]*4)
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE),
        ('BACKGROUND', (0, 1), (-1, 1), WHITE),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t3)
    story.append(PageBreak())

    # ── SYSTEM ARCHITECTURE DIAGRAM ───────────────────────────────────────────
    story.append(Paragraph('System Architecture', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'MailMind follows a layered architecture: Next.js frontend on Vercel, '
        'FastAPI backend on Azure Container Apps, and separate data/AI/observability layers. '
        'All traffic is HTTPS; OAuth tokens are Fernet-AES-128 encrypted at rest.',
        S['body']
    ))
    story.append(Spacer(1, 4))
    dw = W - 36*mm
    story.append(DiagramFlowable(dw, 155*mm, draw_system_arch))
    story.append(Spacer(1, 6))
    story.append(PageBreak())

    # ── INFRA DIAGRAM ─────────────────────────────────────────────────────────
    story.append(Paragraph('Cloud Infrastructure', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'All Azure resources live in a single resource group. '
        'Container Apps handle auto-scaling; Key Vault provides secrets management. '
        'GitHub Actions builds and deploys on every push to main.',
        S['body']
    ))
    story.append(Spacer(1, 4))
    story.append(DiagramFlowable(dw, 140*mm, draw_infra_map))

    infra_table = [
        ['Resource', 'SKU / Tier', 'Purpose'],
        ['Azure Container Apps', 'Consumption plan', 'FastAPI backend, auto-scale 0→N replicas'],
        ['Azure Container Registry', 'Basic', 'Docker image storage for backend'],
        ['Azure Key Vault', 'Standard', 'Fernet keys, OAuth secrets'],
        ['Azure Entra ID', 'Free tier', 'Microsoft OAuth 2.0 provider'],
        ['Azure OpenAI', 'S0 (pay-per-token)', 'gpt-4o, gpt-4o-mini, text-embedding-ada-002'],
        ['Azure Monitor', 'Log Analytics workspace', 'Container logs, application metrics'],
        ['Supabase', 'Pro plan', 'PostgreSQL 15, session pooler, pgbouncer'],
        ['Redis Cloud / Upstash', 'Free → Pay-as-go', 'AOF durable queue (prod); in-memory (dev)'],
        ['Vercel', 'Pro plan', 'Next.js frontend, global edge CDN'],
        ['GitHub Actions', 'Free (public repo)', 'CI/CD: lint, test, docker build, deploy'],
    ]
    t4 = Table(infra_table, colWidths=[52*mm, 42*mm, 74*mm])
    t4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), GRAY_700),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, GRAY_100]),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, GRAY_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, GRAY_200),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(Spacer(1, 6))
    story.append(t4)

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f'[OK] {OUT}')

build()
