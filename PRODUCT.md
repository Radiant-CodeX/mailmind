# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary: people on a university campus**, starting with SRMIST KTR — students (placement drives, exams, fees, attendance, faculty requests), faculty (student requests, HOD and exam-cell duties, committee work) and administrative staff (circulars, approvals, bookings). Email is their primary official channel and critical mail is buried among club promotions, newsletters and portal noise.
- **Secondary: professionals** (freelancers, founders) whose work lives in email — the landing page's "At work" track.
- Job: open the inbox, see the few emails that genuinely need them, act on them (reply, register, pay, attend), and trust that nothing with a hard deadline slipped by.

## Product Purpose

MailMind sits on top of Gmail and does the reading-ahead: it ranks mail by what actually needs the reader, explains why, turns promises and deadlines into dated tasks, flags calendar clashes, and drafts replies in the user's own voice for them to review and send. Success is a user who reads only what matters and never misses an irreversible deadline.

Built for the Vision2Web hackathon, Category 3 (Institution Innovation, SRMIST KTR): the submission must show login, a user dashboard, a request/action workflow, status tracking, a basic admin module and a working demo.

## Positioning

An inbox that knows campus stakes: the Controller of Examinations outranks a club, a placement registration cut-off is a hard deadline, "debarred" and "attendance shortage" are urgent — while every ranking stays explainable on five named axes (deadline, authority, sentiment, thread risk, action) instead of a black box. Nothing is ever sent without the user, personal details are masked before any AI sees them, and it works with the student's own free AI key or none at all.

## Operating Context

- Gmail only (including Google Workspace campus accounts); multiple accounts per user, each with its own voice and history.
- Laptop-first three-pane use; must collapse to a usable single column on phones.
- Mock mode serves a realistic SRMIST student demo inbox with no Google account (used for judging demos).
- Hosted: frontend on Vercel proxying `/api/*` to a FastAPI backend on Render; Supabase Postgres (ap-south-1).

## Capabilities and Constraints

- Five-axis explainable triage per email (CRITICAL / HIGH / MEDIUM / LOW) with per-axis scores and a one-line reason; campus categories (placement, exams, academics, fees, administrative, events, research, campus life, personal, promotions, other).
- Priority override / "Done" feedback loop that learns per sender.
- Commitment extraction → human-approved Google Tasks + Calendar events, with calendar conflict detection.
- Draft replies in three styles using Tone DNA (learned from sent mail) and RAG precedents; approval required before any send.
- Bring-your-own AI key (OpenRouter, Groq, Gemini, OpenAI, Ollama, custom) via `/api/settings/ai`; campus profile (student / faculty / staff, department, year) via `/api/settings/profile`; everything degrades to rule-based scoring with no key.
- PII masking (Presidio + regex) before any model call; demoable in the Privacy view.
- Client information architecture (confirmed): Mail, Tasks and Calendar are primary. Privacy demo, AI key, campus profile, metrics, evaluation and RAG settings live under Settings. Tasks carries a "Needs action → In progress → Done" status workflow for the hackathon's request/workflow and status-tracking requirement. The existing `/admin` page is the admin module.
- Outlook / Microsoft sign-in has been removed from the backend.

## Brand Commitments

- Name: MailMind, by Radiants (team RadiantCodeX). Logo glyph in `frontend/components/shared/LogoGlyph.tsx`.
- Voice (from the landing page): plain, calm, second-person, no hype — "Read what matters. The rest can wait." "Nothing leaves your account without you."
- Binding reference for the client: scape.app — a calm, native-feeling inbox (quiet sidebar, Important vs Full inbox, day-grouped rows, inline drafts).

## Evidence on Hand

- Landing page copy and personas: `frontend/components/landing/Landing.tsx`.
- Demo inbox content: `backend/app/services/campus_demo_data.py`.
- No real user testimonials, adoption numbers or institutional endorsements exist; do not fabricate them.

## Product Principles

1. Show the few that need you first; never hide or delete the rest.
2. Every ranking is explainable — the reason is one glance away.
3. The human decides: drafts wait, commitments need approval, nothing sends on its own.
4. Private by construction — mask before the model, keep accounts separate.
5. Works on day one with no AI key; AI makes it better, not possible.

## Accessibility & Inclusion

Keyboard-operable mail triage (the list, detail and draft actions), visible focus, WCAG AA contrast in light and dark, and respect for reduced motion.
