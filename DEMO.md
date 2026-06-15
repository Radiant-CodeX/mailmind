# MailMind — Judge Demo Playbook

**Goal:** in ~6–8 minutes, show that MailMind is a *production-grade*, *privacy-first*
AI email co-pilot — not a wrapper around an LLM. Lead with the differentiators judges
can't see elsewhere: the **reversible PII masking**, the **5-axis triage**, **Tone DNA
drafts**, and **live production telemetry**.

---

## 0. Before the panel (setup checklist)

- [ ] Backend deployed & warm (hit the app once so Presidio/spaCy is pre-warmed — first triage is then instant).
- [ ] Logged in on an **approved** account (the waitlist gate is live — make sure your demo account is approved or a bootstrap email).
- [ ] Inbox has a few un-triaged emails (so the triage stream animates live) **and** at least one email with rich content for drafting.
- [ ] Browser zoom ~110%, dark theme, sidebar expanded.
- [ ] Have the **Privacy** tab and **Metrics** tab pre-opened in your head (you'll navigate there).
- [ ] One sentence ready for "why this matters": *"Email is where work actually happens, and it's where the most sensitive data lives — so an AI inbox has to be fast, accurate, and private by construction."*

---

## 1. The hook (30 sec)

> "Everyone's seen 'AI summarize my inbox.' The hard problems are: can you trust *what*
> it prioritizes, can it write *as you*, and can you do all that **without shipping your
> customers' personal data to a model provider**? MailMind solves all three. Let me show you."

Open on the **Inbox**.

---

## 2. Live triage — "the inbox sorts itself" (60–90 sec)

1. Click into the inbox / trigger a page load so the **triage stream panel** animates ("Triaging N emails…").
2. Point out priority badges appearing in real time (CRITICAL / HIGH / MEDIUM / LOW).
3. Open one email → show the **5-axis breakdown** (deadline urgency, sender authority,
   sentiment, thread decay, action type) and the composite score.

**Say:** *"Each email is scored on five axes by gpt-4o-mini, then we recompute the composite
in code — we never trust the model's arithmetic. Cache hits return instantly; only genuinely
new emails hit the LLM, and those run concurrently."*

**Talking point — feedback loop:** override a priority on one email → *"That correction is
persisted and fed back, so future emails from this sender are triaged with that learned hint."*

---

## 3. ⭐ THE DIFFERENTIATOR — Privacy & PII masking (90 sec)

This is the part nobody else will have. Go to **Privacy** in the sidebar.

1. The sample email is pre-loaded — packed with a name, phone, email, bank account, IFSC,
   PAN, Aadhaar, street address, credit card, and an API key.
2. Click **🔒 Mask PII**.
3. Two panels appear side-by-side:
   - **Left (Original)** — every piece of PII highlighted by category.
   - **Right (Sent to the LLM)** — the same text with `[PERSON_1]`, `[EMAIL_1]`,
     `[FIN_ID_1]`, `[GOV_ID_1]`, `[SECRET_1]`… tokens.
4. Point at the summary chips: *"N items masked · Engine: Presidio + spaCy NER."*

**Say:** *"This runs on **every** email before any LLM call — it's the same sanitizer the
live pipeline uses, not a demo mock. The model literally never sees a real name, card, or
Aadhaar number. And it's **reversible**: the tokens are restored to real values only *after*
the model responds, so drafts read naturally while raw PII never leaves our backend."*

**If a judge probes "is it really running in prod?":** show the backend logs —
`[app.services.pii] PII masked: {'PERSON': 2, 'EMAIL': 1, 'ADDRESS': 1}` on real emails,
and the startup line `Presidio Analyzer initialized (en_core_web_sm + custom recognizers)`.

**Edit it live** (optional power move): paste a judge's own fake detail (e.g. a phone number)
into the box and re-run — watch it get caught. Proves it's real detection, not a canned response.

---

## 4. Tone DNA drafts — "writes like you" (60 sec)

1. Open an email that warrants a reply → trigger **Generate draft**.
2. Show the draft.

**Say:** *"The draft is written in **your** voice — we build a stylometric 'Tone DNA' profile
from your sent mail (formality, sentence rhythm, common phrases), per account. Crucially, the
draft was generated from the **masked** body — PII was stripped on the way in and restored on
the way out, so it reads perfectly but the model never saw the private bits."*

---

## 5. RAG precedent recall + commitments + calendar (60 sec — pick what's strong)

- **Precedents (RAG):** *"Before drafting, we retrieve how you handled similar emails before
  and inject those decisions as context — your past judgment, recalled. The RAG index stores
  only **masked** bodies, so even our vector store is PII-free."*
- **Commitments:** open the **Tasks** view → *"'I'll send it by Friday' becomes a tracked task
  with a deadline, auto-extracted from threads."*
- **Calendar:** **Calendar** view → *"New commitments are checked against your real calendar so
  conflicts get flagged before you commit."*

---

## 6. ⭐ Production-readiness — Live Metrics (45 sec)

Go to **Metrics**. This is what separates a hackathon toy from a real system.

**Say:** *"This is live production telemetry, not slides."*
- **Parallel pipeline speedup** — measured sequential-vs-parallel from real batches.
- **Cache hit rate** + per-cache breakdown (Redis → DB → LLM, 3-level).
- **Latency p50/p95** per pipeline stage.
- **LLM error rate**, queue depth, uptime, SLA targets.

**Say:** *"We measure ourselves the way an on-call engineer would — percentiles, error rates,
and an honest, apples-to-apples speedup number computed from real runs."*

---

## 7. Architecture / scale close (30 sec)

Pick 2–3 lines:
- *"User-centric identity — one account, multiple connected mailboxes (Gmail + Outlook), with
  per-account Tone DNA and RAG isolation."*
- *"Cookie-based sessions, OAuth only — we never see a password. Tokens encrypted at rest."*
- *"Server-side mailbox mirror with delta sync + client-side IndexedDB score cache, so the
  inbox loads instantly and re-triage is near-free."*
- *"Full request tracing in LangSmith for every LLM call."*
- *"It's invite-only right now — there's a real waitlist + admin approval flow behind it."*

---

## 8. Q&A — anticipated questions & crisp answers

| Question | Answer |
|---|---|
| "Does the PII masking slow things down?" | "It's rule + NER based, pre-warmed at startup, ~tens of ms per email. Cold-start latency was the only cost and we eliminated it by pre-warming spaCy on boot." |
| "What if masking misses something?" | "Two layers: deterministic regex for hard identifiers (cards via Luhn, SSN, PAN, Aadhaar, secrets) **plus** Presidio/spaCy NER for names & locations, filtered by a 'Golden Rule' so we don't over-mask generic terms. Hard IDs never depend on the model." |
| "Why not just trust the LLM to redact?" | "Because you'd have to send the PII to the model to ask it to redact — defeating the purpose. We mask *before* the call, deterministically." |
| "Is the speedup number real?" | "Yes — measured per batch: parallel = concurrent wall-clock, sequential = summed per-email time. We don't fabricate a baseline; the card says 'awaiting data' until real runs exist." |
| "How do you handle multiple accounts?" | "One MailMind identity (UUID), many OAuth accounts. Tone DNA and RAG precedents are isolated per account." |
| "What's the model?" | "gpt-4o-mini for triage (fast, cheap), with a gpt-4o fallback; drafts use the larger deployment. All Azure OpenAI." |

---

## 9. If something breaks (recovery lines)

- **Triage stream doesn't animate:** emails are already cached — *"these are cached from a
  prior run, which is exactly the 3-level cache doing its job; let me show a fresh one"* →
  open the Privacy or Metrics tab instead.
- **A network call hangs:** pivot to the **Privacy** tab (the masking demo is the strongest
  moment anyway) and narrate from there.
- **Backend cold:** the first triage may take a beat — *"that's the model warming up; cached
  paths are sub-second"*.

---

### One-line summary to leave them with
> *"MailMind is an AI inbox that's fast because of real engineering, trustworthy because the
> scoring is auditable, and private because your data is masked before it ever reaches a model."*
