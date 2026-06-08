# ADR 0003 — Reversible PII masking with hallucinated-token neutralisation

- Status: Accepted
- Date: 2026-06-07
- Deciders: MailMind engineering

## Context

Enterprise email contains personal data (names, emails, phones, financial and
government IDs, health info, secrets). Sending it raw to a third-party LLM is a
compliance non-starter. But the LLM still needs enough structure to write a
coherent, personalised reply, and the final output must contain the real values.

## Decision

Mask before the LLM, restore after, using **reversible placeholder tokens** held
only in per-request state.

- **Masking rubric** (the "Golden Rule"): mask only data specific enough to
  identify/harm a small set of individuals. Skip generic demographics, public
  figures in public context, anonymised/aggregated data, vague statements.
- **Stable tokens**: `[PERSON_1]`, `[EMAIL_1]`, `[GOV_ID_1]`, … value-deduplicated
  and numbered left-to-right. Mapping `{token → original}` lives in
  `EmailAgentState.mask_mapping`, never logged.
- **Hybrid detection**: regex for hard identifiers (incl. Indian PAN/Aadhaar/
  GSTIN/IFSC, Luhn-validated cards, API keys/JWT) + Presidio/spaCy NLP for
  names/locations; longest-span wins on overlap.
- **Robust restore**: `restore_text` is tolerant of light LLM reformatting
  (`[person 1]`, `[ PERSON-1 ]`). `strip_unresolved_tokens` then neutralises any
  token the LLM *hallucinated* (a number never in the mapping, e.g. `[PERSON_2]`)
  into a neutral phrase ("there"), so no broken token — and no leaked PII —
  reaches the user.

## Consequences

**Positive**
- LLM never receives raw PII; outputs are faithfully reconstructed.
- Works identically with or without Presidio installed (regex fallback).
- Resilient to real LLM behaviour (token reformatting and hallucination), proven
  by tests (`tests/test_pii.py`, `tests/test_production.py`).

**Negative / trade-offs**
- A hallucinated person token is replaced by a generic word rather than the
  intended name (we choose safety over guessing). Rare in practice with GPT-4o.
- NLP name detection is heuristic; the Golden Rule denylist needs occasional
  tuning (e.g. public-figure list, PII label words mis-tagged as names).

## Alternatives considered

- **Send raw text, rely on the provider's privacy terms.** Unacceptable for
  enterprise compliance. Rejected.
- **Irreversible redaction.** Simpler, but then the draft can't contain the real
  recipient name/details — defeats the product. Rejected.
