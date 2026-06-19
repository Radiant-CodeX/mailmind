"""Part 4: Services, API routes, and frontend documentation."""
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
from reportlab.lib.enums import TA_CENTER

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

OUT = os.path.join(os.path.dirname(__file__), 'part4_services.pdf')

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
    c.drawString(15, H - 14, 'MailMind — Technical Documentation · Services & API Reference')
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
    data = [['Method / Function', 'Parameters', 'Description']]
    for name, params, desc in methods:
        data.append([
            Paragraph(f'<font name="Courier-Bold" size="7.5">{name}</font>',
                ParagraphStyle('m', fontName='Courier-Bold', fontSize=7.5, textColor=GRAY_900)),
            Paragraph(f'<font name="Courier" size="7">{params}</font>',
                ParagraphStyle('p', fontName='Courier', fontSize=7, textColor=GRAY_500)),
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

def route_table(routes, accent=BLUE):
    data = [['Method', 'Path', 'Auth', 'Description']]
    for method, path, auth, desc in routes:
        mc = GREEN if method == 'GET' else BLUE if method == 'POST' else ORANGE if method == 'PUT' else RED
        data.append([
            Paragraph(f'<b>{method}</b>',
                ParagraphStyle('mt', fontName='Helvetica-Bold', fontSize=8)),
            Paragraph(f'<font name="Courier" size="7">{path}</font>',
                ParagraphStyle('pt', fontName='Courier', fontSize=7, textColor=GRAY_900)),
            Paragraph(auth, ParagraphStyle('at', fontName='Helvetica', fontSize=7, textColor=GRAY_500)),
            Paragraph(desc, ParagraphStyle('dt', fontName='Helvetica', fontSize=8, textColor=GRAY_700, leading=11)),
        ])
    t = Table(data, colWidths=[14*mm, 58*mm, 18*mm, 72*mm])
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

def fh(story, S, filepath, purpose):
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

    # ── SERVICES SECTION ─────────────────────────────────────────────────────
    story.append(Paragraph('Backend Services Documentation', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'The services layer contains all business logic. Each service is a standalone class '
        'or module imported by nodes, routes, or the enrichment worker.',
        S['body']
    ))
    story.append(PageBreak())

    # ── PII SERVICE ───────────────────────────────────────────────────────────
    story.append(Paragraph('PII Masking Service', S['h2']))
    fh(story, S, 'backend/app/services/pii.py',
       'Reversible PII masking using Microsoft Presidio NER + spaCy en_core_web_sm. '
       'Replaces detected entities with sequential tokens (<ENTITY_0>, <ENTITY_1>, ...) '
       'and stores a mapping for restoration after LLM calls. Masks subject and body only (not sender).')

    story.append(method_table([
        ('PIISanitizer.__init__', 'use_presidio: bool = True', 'Initialises Presidio AnalyzerEngine + spaCy. Falls back to regex-only mode if Presidio unavailable.'),
        ('detect_pii', 'text: str → list[PIIEntity]', 'Returns list of detected PII spans (PERSON, EMAIL, PHONE, LOCATION, ORG, etc.) with start/end offsets.'),
        ('mask_text', 'text: str → (masked: str, mapping: dict)', 'Replaces PII spans with <ENTITY_N> tokens. Returns masked text + token-to-value mapping for later restoration.'),
        ('restore_text', 'masked: str, mapping: dict → str', 'Substitutes all <ENTITY_N> tokens back with original values.'),
        ('strip_unresolved_tokens', 'text: str → str', 'Safety net: removes any <ENTITY_N> tokens that have no mapping entry (LLM hallucinated token).'),
        ('pii_sanitizer (module)', '— (singleton)', 'Module-level singleton. Import pii_sanitizer and call mask_text() / restore_text() directly.'),
    ], accent=RED))

    story.append(Spacer(1, 8))

    # ── TONE DNA ──────────────────────────────────────────────────────────────
    story.append(Paragraph('Tone DNA Service', S['h2']))
    fh(story, S, 'backend/app/services/tone_dna.py',
       'Builds a 8-feature stylometric profile from a user\'s sent email history. '
       'Profile is stored in tone_profile table and injected as a system prefix in every draft.')

    story.append(method_table([
        ('_avg_sentence_length', 'text: str → float', 'Average word count per sentence across the email body.'),
        ('_formality_score', 'text: str → float', 'Ratio of formal markers (therefore, regarding, sincerely) vs informal (hey, wanna, gonna).'),
        ('_greeting_patterns', 'texts: list[str] → list[str]', 'Extracts most common greeting phrases (Hi X, Dear X, Hello X).'),
        ('_signoff_patterns', 'texts: list[str] → list[str]', 'Extracts most common sign-off phrases (Thanks, Best, Regards).'),
        ('_contraction_rate', 'text: str → float', 'Fraction of words that are contractions (it\'s, don\'t, we\'re).'),
        ('_bullet_preference', 'text: str → float', 'Fraction of emails using bullet lists or numbered lists.'),
        ('_emoji_rate', 'text: str → float', 'Average emoji count per email.'),
        ('_top_vocabulary', 'texts: list[str], n: int → list[str]', 'Most frequently used non-stopword tokens.'),
        ('build_profile', 'emails: list[str] → dict', 'Orchestrates all 8 feature extractors. Returns profile dict with sample_size.'),
        ('ToneDNAService.ingest_and_build', 'account_id: str, graph_client → dict', 'Fetches sent emails via provider, calls build_profile(), saves to DB.'),
        ('ToneDNAService.load_profile', 'account_id: str → dict|None', 'Loads stored profile from tone_profile table.'),
        ('ToneDNAService.save_profile', 'account_id: str, profile: dict → None', 'Upserts profile to DB.'),
    ], accent=ORANGE))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ── DRAFT SERVICE ──────────────────────────────────────────────────────────
    story.append(Paragraph('Draft Service', S['h2']))
    fh(story, S, 'backend/app/services/draft_service.py',
       'Generates AI draft replies using GPT-4o, injecting Tone DNA style prefix and RAG precedents.')

    story.append(method_table([
        ('_get_llm_client', '→ AzureChatOpenAI|ChatGroq', 'Returns cached LLM instance (Azure first, Groq fallback).'),
        ('_get_clean_name', 'sender: str → str', 'Extracts first name from "John Smith <john@co.com>" format.'),
        ('_get_user_display_name', 'email: str → str', 'Derives first name from email prefix.'),
        ('DraftService.generate_draft', 'email_text, style, sender, subject, current_user_email, account_id → (draft, citations)', 'Main method. '
         'Loads Tone DNA profile for account, fetches RAG precedents, builds system prompt with style prefix, calls GPT-4o. '
         'Styles: standard | formal | indepth.'),
        ('DraftService.generate_compose', 'recipient, subject, context, account_id → str', 'Generates a new outbound email (not a reply). '
         'Still uses Tone DNA prefix for style consistency.'),
    ], accent=TEAL))

    story.append(Spacer(1, 8))

    # ── COMMITMENTS SERVICE ────────────────────────────────────────────────────
    story.append(Paragraph('Commitment Service', S['h2']))
    fh(story, S, 'backend/app/services/commitments.py',
       'Extracts action items and deadlines from email text using GPT-4o structured output. '
       'Caches results by email_id. Falls back to regex when LLM is unavailable.')

    story.append(method_table([
        ('CommitmentService._get_llm_client', '→ (client, model_name)', 'Azure → Groq → None fallback chain.'),
        ('CommitmentService._fallback_extract', 'masked_email_text: str → list', 'Regex-based extraction: looks for patterns like "by [date]", "please [verb]", "deadline:".'),
        ('CommitmentService.extract', 'masked_email_text, thread_summary, email_id → list[CommitmentItem]', 'Main method. Checks cache first (by email_id or text hash). '
         'Calls GPT-4o with few-shot examples for structured CommitmentItem output. '
         'Each item: id, commitment, deadline, confidence, approved, conflict_badge.'),
        ('CommitmentService.confirm_commitment', 'commitment_id, email_id, account_id → bool', 'Creates calendar event for a confirmed commitment via provider API.'),
    ], accent=ORANGE))

    story.append(Spacer(1, 8))

    # ── RAG SERVICE ────────────────────────────────────────────────────────────
    story.append(Paragraph('RAG / Vector Retrieval Service', S['h2']))
    fh(story, S, 'backend/app/services/rag.py',
       'Local vector index using ChromaDB (file-based JSON). Embeds with text-embedding-ada-002. '
       'Cosine similarity threshold 0.78 for retrieval.')

    story.append(method_table([
        ('mask_pii', 'text: str → str', 'Lightweight regex PII redaction before indexing sent emails.'),
        ('cosine_similarity', 'a: list, b: list → float', 'Pure-Python dot product / magnitude similarity.'),
        ('EmbeddingProvider.embed', 'text: str → list[float]', 'Calls Azure text-embedding-ada-002. Falls back to _deterministic() if unavailable.'),
        ('EmbeddingProvider._deterministic', 'text: str → list[float]', 'Hash-based pseudo-embedding for offline/test mode.'),
        ('ChromaDBIndex.index', 'documents: list[dict] → None', 'Batch indexes documents to JSON store.'),
        ('ChromaDBIndex.search', 'vector: list, top_k: int, threshold: float → list[PrecedentItem]', 'Cosine similarity search. Returns items above threshold, ranked by score.'),
        ('ChromaDBIndex.upsert', 'document: dict → None', 'Add or update single document.'),
        ('ChromaDBIndex.trim', 'max_size: int → None', 'Removes oldest documents when index exceeds max_size.'),
        ('RetrievalService.retrieve', 'query: str, account_id: str, top_k: int → list[PrecedentItem]', 'Embeds query, searches account-scoped index, returns precedents.'),
    ], accent=GREEN))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ── CALENDAR SERVICE ──────────────────────────────────────────────────────
    story.append(Paragraph('Calendar Service', S['h2']))
    fh(story, S, 'backend/app/services/calendar_service.py',
       'Deterministic (no LLM) calendar conflict detection. '
       'Compares commitment deadlines against fetched calendar events.')

    story.append(method_table([
        ('check_calendar_conflict', 'commitment_deadline: datetime, events: list[CalendarEvent] → (bool, str)', 'Returns (has_conflict, conflict_detail). '
         'A conflict exists when commitment_deadline falls within any event time window ± 30-minute buffer.'),
    ], accent=PURPLE))

    story.append(Spacer(1, 8))

    # ── SYNC SERVICE ──────────────────────────────────────────────────────────
    story.append(Paragraph('Sync Service', S['h2']))
    fh(story, S, 'backend/app/services/sync_service.py',
       'Manages the server-side mailbox mirror. Supports full backfill (first sync) '
       'and cursor-based delta sync for incremental updates.')

    story.append(method_table([
        ('SyncService._apply_changes', 'account_id, folder, result → (new_count, updated, removed)', 'Applies upserts and tombstones from a provider response to the DB.'),
        ('SyncService.backfill', 'account: OAuthAccount, folder: str → dict', 'Full enumeration on first sync. Fetches all emails, stores envelopes, '
         'saves initial delta cursor. Ensures webhook subscription.'),
        ('SyncService.delta_sync', 'account: OAuthAccount, folder: str → dict', 'Incremental sync using stored delta cursor. Falls back to backfill if cursor missing or expired.'),
    ], accent=INDIGO))

    story.append(Spacer(1, 8))

    # ── GRAPH CLIENT ──────────────────────────────────────────────────────────
    story.append(Paragraph('Microsoft Graph Client', S['h2']))
    fh(story, S, 'backend/app/services/graph.py',
       'Microsoft Graph API client (~90KB). Handles Outlook mail, calendar, and delta sync. '
       'USE_MOCK_GRAPH=true returns rich mock data for development.')

    story.append(method_table([
        ('GraphClient.__init__', 'access_token, refresh_token, use_mock: bool', 'Initialises with token credentials and mock flag.'),
        ('GraphClient.get_inbox_emails', 'folder, limit → list[EmailItem]', 'MOCK: returns 10 emails (CRITICAL×2, HIGH×3, MEDIUM×3, LOW×2). '
         'REAL: calls /me/mailFolders/{folder}/messages.'),
        ('GraphClient.get_calendar_events', 'days_ahead: int → list[CalendarEvent]', 'MOCK: returns 5 events overlapping email deadlines. '
         'REAL: calls /me/calendar/calendarView.'),
        ('GraphClient.fetch_sent_emails', 'limit: int → list[str]', 'MOCK: returns 55 emails (20 rich VP/Director persona + 35 fillers). '
         'REAL: calls /me/mailFolders/SentItems/messages.'),
        ('GraphClient.get_email_body', 'email_id: str → str', 'Fetches full HTML/text body for an email.'),
        ('GraphClient.send_reply', 'email_id, body → None', 'Sends reply via Graph /me/messages/{id}/reply.'),
        ('GraphClient.get_delta', 'folder, delta_link → dict', 'Fetches delta changes using provided deltaLink cursor.'),
        ('GraphClient._days_ago', 'n: int → str', 'Helper: ISO date string N days in the past.'),
        ('GraphClient.ensure_subscription', 'webhook_url, account_id → str', 'Creates or renews Graph change notification subscription.'),
    ], accent=BLUE))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ── GMAIL CLIENT ──────────────────────────────────────────────────────────
    story.append(Paragraph('Gmail Client', S['h2']))
    fh(story, S, 'backend/app/services/gmail.py',
       'Gmail API client (~61KB). Handles inbox, sent mail, and Pub/Sub watch. '
       'Mock mode returns matching emails for dev.')

    story.append(method_table([
        ('GmailClient.__init__', 'credentials, use_mock: bool', 'Initialises Google OAuth2 credentials.'),
        ('GmailClient.get_inbox_emails', 'limit: int → list[EmailItem]', 'MOCK: 10 emails (gmail-1 to gmail-10) with matching triage profiles. '
         'REAL: Gmail messages.list + get per message.'),
        ('GmailClient.fetch_sent_emails', 'limit: int → list[str]', 'MOCK: 50 emails (15 rich + 35 fillers). REAL: Sent label messages.'),
        ('GmailClient.get_email_body', 'message_id: str → str', 'Decodes base64url email body from Gmail API.'),
        ('GmailClient.send_reply', 'thread_id, body, to → None', 'Sends reply via Gmail messages.send.'),
        ('GmailClient.watch', 'topic_name: str → dict', 'Starts Gmail Push notifications via Cloud Pub/Sub watch.'),
        ('GmailClient.get_history', 'history_id: str → dict', 'Fetches history.list for delta sync since historyId cursor.'),
        ('GmailClient._mock_inbox', '→ list', 'Returns 10 hardcoded realistic inbox emails with bodies, senders, and deadlines.'),
    ], accent=RED))

    story.append(Spacer(1, 8))

    # ── SESSION SERVICE ───────────────────────────────────────────────────────
    story.append(Paragraph('Session Service', S['h2']))
    fh(story, S, 'backend/app/services/session_service.py',
       'Manages user sessions and Quick Login tokens. '
       'Session tokens are SHA-256 hashed before storage.')

    story.append(method_table([
        ('SessionService.create_session', 'user_id: UUID → str', 'Generates secure random token, SHA-256 hashes it, stores UserSession row with 24h TTL. Returns raw token.'),
        ('SessionService.validate_session', 'token: str → UserSession|None', 'Hashes token, looks up UserSession, checks expiry.'),
        ('SessionService.extend_session', 'token: str → None', 'Updates last_seen_at and optionally extends expires_at.'),
        ('SessionService.revoke_session', 'token: str → None', 'Deletes UserSession row (logout).'),
        ('SessionService.create_quick_login', 'user_id, device_id → str', 'Creates 7-day QuickLoginToken for auto-resume.'),
        ('SessionService.validate_quick_login', 'token: str → QuickLoginToken|None', 'Validates long-lived token, checks status and expiry.'),
    ], accent=TEAL))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ── API ROUTES ────────────────────────────────────────────────────────────
    story.append(Paragraph('API Routes Documentation', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))

    # Main routes
    story.append(Paragraph('Main Routes (backend/app/api/routes.py)', S['h2']))
    fh(story, S, 'backend/app/api/routes.py',
       'OAuth callbacks, inbox listing, email operations. '
       'The _finish_oauth_connect() function is the core post-OAuth flow (upsert user, create session, set cookie).')

    story.append(route_table([
        ('GET', '/api/auth/status', 'Session', 'Returns authenticated user info, default account, and list of connected accounts.'),
        ('GET', '/api/auth/microsoft', 'None', 'Initiates Microsoft OAuth — redirects to Azure Entra ID consent screen.'),
        ('GET', '/api/auth/microsoft/callback', 'None', 'Exchanges auth code, upserts user/account, sets mm_session cookie.'),
        ('GET', '/api/auth/google', 'None', 'Initiates Google OAuth — redirects to Google consent screen.'),
        ('GET', '/api/auth/google/callback', 'None', 'Exchanges code, upserts user/account, sets mm_session cookie.'),
        ('POST', '/api/auth/logout', 'Session', 'Revokes session, clears cookie.'),
        ('POST', '/api/inbox', 'Session', 'Lists inbox emails. Joins mailbox_message + enrichment. Supports folder, sort, filter, pagination.'),
        ('GET', '/api/inbox/{email_id}', 'Session', 'Fetches full email body + metadata from provider.'),
        ('POST', '/api/draft', 'Session', 'Calls DraftService.generate_draft() with specified style.'),
        ('POST', '/api/reply', 'Session', 'Sends reply via provider API (Graph.send_reply or Gmail.send_reply).'),
        ('POST', '/api/compose', 'Session', 'Generates and optionally sends a new outbound email.'),
        ('POST', '/api/commitments/extract', 'Session', 'Calls CommitmentService.extract() on provided email text.'),
        ('POST', '/api/commitments/confirm', 'Session', 'Creates calendar event for confirmed commitment.'),
        ('PUT', '/api/priority/{email_id}', 'Session', 'Records priority override — sets enrichment + mailbox_message to done state.'),
        ('PUT', '/api/tone-dna/build', 'Session', 'Triggers ToneDNAService.ingest_and_build() for the default account.'),
        ('GET', '/api/tone-dna/preview', 'Session', 'Returns current Tone DNA profile for display.'),
        ('GET', '/api/user/accounts', 'Session', 'Lists all connected OAuthAccounts for the user.'),
    ], accent=NAVY))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # Agent routes
    story.append(Paragraph('Agent Routes (backend/app/api/agent_routes.py)', S['h2']))
    fh(story, S, 'backend/app/api/agent_routes.py',
       'LangGraph pipeline API endpoints. Supports full pipeline, streaming (SSE), '
       'triage-only, enrichment-only, and human-in-the-loop approval.')

    story.append(route_table([
        ('GET', '/api/agent/health', 'None', 'Returns LLM provider status and pipeline readiness.'),
        ('POST', '/api/agent/process', 'Session', 'Runs full 6-node pipeline synchronously. Returns complete enriched state.'),
        ('POST', '/api/agent/stream', 'Session', 'Streaming pipeline via SSE. Yields JSON events per node completion.'),
        ('POST', '/api/agent/triage', 'Session', 'Runs ingest + triage nodes only (Phase 1). Returns axes, priority, score.'),
        ('POST', '/api/agent/enrich', 'Session', 'Runs commitment + calendar + RAG nodes (Phase 2). Returns commitments, draft, precedents.'),
        ('POST', '/api/agent/batch', 'Session', 'Triage multiple emails in parallel (uses asyncio.gather, max TRIAGE_MAX_WORKERS concurrent).'),
        ('GET', '/api/agent/approve/{email_id}', 'Session', 'Checks approval status for gated email.'),
        ('POST', '/api/agent/approve/{email_id}', 'Session+Token', 'Approves gated email. Requires X-Approval-Token header.'),
    ], accent=BLUE))

    story.append(Spacer(1, 8))

    # Sync routes
    story.append(Paragraph('Sync Routes (backend/app/api/sync_routes.py)', S['h2']))
    story.append(route_table([
        ('POST', '/webhooks/graph', 'client_state', 'Receives Microsoft Graph change notifications. Verifies client_state, triggers delta_sync.'),
        ('POST', '/webhooks/gmail', 'token param', 'Receives Gmail Pub/Sub push. Verifies ?token=, decodes historyId, triggers delta_sync.'),
        ('POST', '/api/subscriptions/ensure', 'Session', 'Creates Graph webhook subscription for authenticated account.'),
        ('POST', '/api/subscriptions/renew', 'Admin', 'Renews expiring Graph subscriptions (cron job target).'),
    ], accent=TEAL))

    story.append(Spacer(1, 8))

    # Waitlist routes
    story.append(Paragraph('Waitlist Routes (backend/app/api/waitlist_routes.py)', S['h2']))
    story.append(route_table([
        ('POST', '/api/waitlist/join', 'None', 'Adds email to waitlist (status=pending). Returns position.'),
        ('GET', '/api/waitlist/status', 'None', 'Check if email is approved (for login gate).'),
        ('POST', '/api/admin/waitlist/approve/{email}', 'X-Admin-Token', 'Approves waitlisted email — allows sign in.'),
        ('POST', '/api/admin/waitlist/reject/{email}', 'X-Admin-Token', 'Rejects waitlisted email.'),
        ('GET', '/api/admin/feedback', 'X-Admin-Token', 'Lists all product feedback submissions.'),
    ], accent=ORANGE))

    story.append(Spacer(1, 8))

    # Other routes
    story.append(Paragraph('Other Routes', S['h2']))
    story.append(route_table([
        ('GET', '/api/demo/login', 'None', 'Returns HTML one-click demo login page.'),
        ('POST', '/api/demo/login', 'None', 'Creates session for demo@mailmind.app. No waitlist gate.'),
        ('POST', '/api/pii/preview', 'Session', 'Runs PII detection on provided text and returns masked output + entity list.'),
        ('POST', '/api/feedback', 'Session', 'Stores product feedback (rating, category, message).'),
        ('GET', '/api/health', 'None', 'Liveness probe (always 200).'),
        ('GET', '/api/ready', 'None', 'Readiness probe (checks DB connection).'),
        ('GET', '/api/metrics', 'None', 'Prometheus-format metrics (requests, latency, SLA).'),
        ('GET', '/api/compliance/audit/{email_id}', 'Session', 'Returns audit trail for an email.'),
        ('DELETE', '/api/compliance/data/{user_id}', 'Session', 'GDPR right-to-erasure — deletes all user data.'),
    ], accent=GRAY_700))

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # ── FRONTEND DOCUMENTATION ────────────────────────────────────────────────
    story.append(Paragraph('Frontend Documentation', S['h1']))
    story.append(HRFlowable(width='100%', color=BLUE, thickness=1.5, spaceAfter=8))
    story.append(Paragraph(
        'Next.js 15 App Router frontend with TypeScript, Tailwind CSS, GSAP animations, and SSE streaming.',
        S['body']
    ))

    # Pages
    story.append(Paragraph('App Pages (frontend/app/)', S['h2']))
    pages_data = [
        ['Page File', 'Route', 'Purpose'],
        ['app/page.tsx', '/', 'Landing page with WebGL hero, GSAP animations, 6 feature cards, pipeline visualization, waitlist form'],
        ['app/layout.tsx', '/', 'Root layout: Geist fonts, global CSS, SEO metadata, error boundary, Vercel Analytics'],
        ['app/dashboard/page.tsx', '/dashboard', 'Main inbox dashboard: email list + detail panel side-by-side. Auth guard.'],
        ['app/login/page.tsx', '/login', 'OAuth login page with Google and Microsoft provider buttons'],
        ['app/admin/page.tsx', '/admin', 'Admin panel: waitlist approval, feedback list. Requires admin token.'],
        ['app/privacy/page.tsx', '/privacy', 'PII masking demo and privacy information page'],
        ['app/terms/page.tsx', '/terms', 'Terms of service legal document'],
    ]
    t = Table(pages_data, colWidths=[48*mm, 28*mm, 86*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (0, -1), 'Courier', 8),
        ('FONT', (1, 1), (-1, -1), 'Helvetica', 8),
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

    story.append(Spacer(1, 8))

    # Key Components
    story.append(Paragraph('Key Components', S['h2']))
    comp_data = [
        ['Component', 'Location', 'Purpose'],
        ['EmailList', 'components/inbox/', 'Main inbox list with pagination, sort, filter chips, priority badges, SSE triage streaming'],
        ['EmailListItem', 'components/inbox/', 'Single email row: sender, subject, snippet, priority badge, score bar, action buttons'],
        ['EmailDetail', 'components/detail/', 'Full email view: HTML body (sanitized), triage explainer, commitments gate, draft panel, precedents'],
        ['DraftPanel', 'components/detail/', 'Draft generation UI: style selector (standard/formal/indepth), edit area, send button'],
        ['CommitmentGate', 'components/commitments/', 'Modal for approving commitments: deadline, confidence, conflict badge, approve/dismiss actions'],
        ['PrecedentList', 'components/detail/', 'Shows top 3 RAG-retrieved similar past emails with similarity scores'],
        ['PipelineVisualization', 'components/pipeline/', 'Interactive 6-node pipeline diagram for landing page presentation mode'],
        ['HeroCanvas', 'components/landing/', 'Three.js WebGL animated hero — particle pipeline visualization'],
        ['WaitlistForm', 'components/landing/', 'Email waitlist signup with success/error states'],
        ['Header', 'components/layout/', 'Top navigation: logo, account switcher, logout, settings'],
        ['Sidebar', 'components/layout/', 'Folder navigation: INBOX, SENT, DRAFTS, priority filters'],
        ['PriorityBadge', 'components/inbox/', 'Color-coded CRITICAL/HIGH/MEDIUM/LOW badge chip'],
        ['TriageScoreBar', 'components/inbox/', 'Visual bar showing composite score 0-100'],
        ['PriorityOverrideMenu', 'components/inbox/', 'Dropdown to manually change email priority or mark done'],
        ['FilterMenu', 'components/inbox/', 'Priority filter (ALL/CRITICAL/HIGH/MEDIUM/LOW) with counts'],
        ['ComposeWindow', 'components/inbox/', 'Full compose window for new email drafts'],
        ['ErrorBoundary', 'components/shared/', 'React error boundary with fallback UI and error reporting'],
        ['FeedbackModal', 'components/shared/', 'Product feedback form: rating, category, message'],
    ]
    t2 = Table(comp_data, colWidths=[44*mm, 38*mm, 80*mm])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (0, -1), 'Courier', 7.5),
        ('FONT', (1, 1), (-1, -1), 'Helvetica', 8),
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
    story.append(t2)

    story.append(Spacer(1, 8))
    story.append(PageBreak())

    # Hooks
    story.append(Paragraph('Custom React Hooks', S['h2']))
    story.append(method_table([
        ('useEmails', 'accountId, defaultFolder, pageSize', 'Manages entire inbox state: emails list, total, pagination (page index, next/prev), '
         'sort key, filters (priority, folder), selected email. Calls /api/inbox with params.'),
        ('useEmailDetail', 'email, enabled, currentUserEmail, onTriageEnriched', 'Two-phase loading hook. Phase 1: reads triage from email object instantly. '
         'Phase 2: calls /api/agent/enrich to load commitments + draft + precedents. Caches in localStorage.'),
        ('useAuthFlow', '—', 'Manages OAuth flow state: loading, error, provider. Calls /api/auth/status on mount.'),
        ('useInboxCache', 'accountId', 'localStorage-based inbox cache: stores last 100 email envelopes with TTL.'),
    ], accent=PURPLE))

    story.append(Spacer(1, 8))

    # API lib
    story.append(Paragraph('API Client (frontend/lib/api.ts)', S['h2']))
    fh(story, S, 'frontend/lib/api.ts',
       'Fetch wrapper for all backend calls. Automatically includes credentials (cookies). '
       'Base URL from NEXT_PUBLIC_API_URL env var or relative (/api/...).')

    story.append(method_table([
        ('apiFetch', 'input: RequestInfo, init?: RequestInit → Response', 'Wraps native fetch with credentials:"include" and base URL resolution.'),
        ('enrichEmail', 'payload: EmailPayload → Enrichment', 'POST /api/agent/enrich — Phase 2 enrichment.'),
        ('triageEmail', 'payload → TriageResult', 'POST /api/agent/triage — Phase 1 triage.'),
        ('triageWithRetry', 'payload, maxRetries: number → TriageResult', 'Triage with exponential backoff (3 retries, 1s/2s/4s).'),
        ('generateEmailDraft', 'payload: DraftRequest → DraftResponse', 'POST /api/draft — generate AI draft reply.'),
        ('sendEmailReply', 'payload: ReplyRequest → void', 'POST /api/reply — send reply via provider.'),
        ('fetchMailboxMessage', 'emailId: string → MailboxMessage', 'GET /api/inbox/{emailId} — fetch full email body.'),
        ('fetchAttachments', 'emailId: string → Attachment[]', 'GET /api/inbox/{emailId}/attachments.'),
    ], accent=TEAL))

    doc.build(story, onFirstPage=hf, onLaterPages=hf)
    print(f'[OK] {OUT}')

build()
