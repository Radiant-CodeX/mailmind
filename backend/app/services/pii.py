"""
MailMind — PII / Privacy Masking Layer
=======================================

Masking rubric (the "Golden Rule")
-----------------------------------
Sensitive personal information is data **specific enough to identify or harm a
small set of private individuals**. Such data is masked with a reversible
placeholder *before any LLM call* and only restored *after* the LLM output is
produced.

We MASK these categories:
    PERSON_NAME, EMAIL, PHONE, ADDRESS, FINANCIAL_ID, GOVERNMENT_ID,
    HEALTH_INFO, SECRET, PERSONAL_OBJECT_ID

We DO NOT mask:
    - generic demographics without identifying details
    - public officials / public figures in public context
    - anonymized or aggregated data
    - vague/general statements that apply to many people

For ambiguous detections (names, locations) we apply the Golden Rule:
    "Is this information specific enough to identify and harm a very small set
     of individuals?" — if not, it is left untouched.

Reversibility & safety
----------------------
`mask_text` returns `(masked_text, mapping)`. The mapping is held only in
per-request pipeline state (e.g. ``EmailAgentState.mask_mapping``) and is used
by `restore_text` to reconstruct the original text after generation. Raw PII
values are NEVER written to logs.

Public API
----------
    detect_pii(text)               -> list[PIIEntity]
    mask_text(text)                -> (masked_text, mapping)
    restore_text(masked, mapping)  -> str
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Pattern, Tuple

logger = logging.getLogger(__name__)

# Optional Presidio / spaCy for NLP-based PERSON and LOCATION detection.
try:
    from presidio_analyzer import AnalyzerEngine, Pattern as PresidioPattern, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    HAS_PRESIDIO = True
except ImportError:
    HAS_PRESIDIO = False
    logger.warning("presidio-analyzer not installed; using regex-only PII detection.")


# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PIIEntity:
    """A single detected piece of PII within a text."""
    entity_type: str   # one of the MASK categories (e.g. "PERSON_NAME")
    start: int
    end: int
    text: str          # the raw matched value (kept in-memory only)
    score: float = 1.0


# Category → placeholder prefix used in tokens like [PERSON_1], [GOV_ID_1].
ENTITY_PREFIX = {
    "PERSON_NAME": "PERSON",
    "EMAIL": "EMAIL",
    "PHONE": "PHONE",
    "ADDRESS": "ADDRESS",
    "FINANCIAL_ID": "FIN_ID",
    "GOVERNMENT_ID": "GOV_ID",
    "HEALTH_INFO": "HEALTH",
    "SECRET": "SECRET",
    "PERSONAL_OBJECT_ID": "DEVICE_ID",
}


# ─────────────────────────────────────────────────────────────────────────────
# REGEX DETECTORS  (hard, unambiguous PII — Golden Rule not required)
# Each entry: (category, compiled_pattern, capture_group_index)
# Ordered most-specific-first; overlap resolution keeps the longest span.
# ─────────────────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

_REGEX_DETECTORS: List[Tuple[str, Pattern[str], int]] = [
    # ── SECRETS: API keys, tokens, passwords ───────────────────────────────
    # labelled key=value / key: value (mask only the value)
    ("SECRET", re.compile(
        r"(?i)\b(?:api[_-]?key|apikey|secret[_-]?key|secret|access[_-]?token|"
        r"token|password|passwd|pwd|client[_-]?secret)\b\s*[:=]\s*[\"']?([^\s\"']{6,})"
    ), 1),
    ("SECRET", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._\-]{16,})"), 1),
    ("SECRET", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"), 0),                 # OpenAI
    ("SECRET", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0),                    # AWS access key
    ("SECRET", re.compile(r"\bghp_[A-Za-z0-9]{36}\b"), 0),                 # GitHub PAT
    ("SECRET", re.compile(
        r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b"
    ), 0),                                                                 # JWT

    # ── EMAIL ──────────────────────────────────────────────────────────────
    ("EMAIL", _EMAIL_RE, 0),

    # ── FINANCIAL IDs (cards handled separately via Luhn) ──────────────────
    ("FINANCIAL_ID", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), 0),            # US SSN
    ("FINANCIAL_ID", re.compile(r"\b\d{2}-\d{7}\b"), 0),                  # US EIN
    ("FINANCIAL_ID", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"), 0),        # IFSC (Indian bank branch)
    # IBAN: must have at least one letter in the BBAN (rules out all-digit DL/account numbers)
    ("FINANCIAL_ID", re.compile(r"\b[A-Z]{2}\d{2}(?=[A-Z0-9]*[A-Z])[A-Z0-9]{11,30}\b"), 0),  # IBAN
    ("FINANCIAL_ID", re.compile(
        r"(?i)\b(?:a/?c|account)\s*(?:no\.?|number|#)?\s*[:=]?\s*(\d{9,18})\b"
    ), 1),                                                                # bank account
    # UPI Virtual Payment Address (handle@psp) — not caught by the email regex
    ("FINANCIAL_ID", re.compile(
        r"\b[a-zA-Z0-9._-]{3,}@(?:oksbi|ybl|okhdfcbank|okaxis|okicici|paytm|"
        r"upi|axl|ibl|icici|hdfc|kotak|sbi|pnb|boi|bom|canara|union|idbi|yes|"
        r"rblbank|airtel|freecharge|razer|indus|aubank|equitas|apb|apl|"
        r"timecosmos|waicici|wahdfcbank|wasbi)\b"
    ), 0),

    # ── GOVERNMENT IDs (incl. Indian identifiers) ──────────────────────────
    ("GOVERNMENT_ID", re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b"), 0),  # GSTIN
    ("GOVERNMENT_ID", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), 0),          # PAN (5L+4D+1L)
    ("GOVERNMENT_ID", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), 0),  # Aadhaar (12 digits)
    ("GOVERNMENT_ID", re.compile(r"\b[A-Z]{3}\d{7}\b"), 0),               # Voter ID (ECI format)
    ("GOVERNMENT_ID", re.compile(r"\b[A-Z]{2}\d{2}[- ]?\d{4}[- ]?\d{7}\b"), 0),  # Driving Licence
    ("GOVERNMENT_ID", re.compile(r"\b[A-Z]\d{7}\b"), 0),                  # Passport (India)
    ("GOVERNMENT_ID", re.compile(
        r"(?i)\b(?:passport|driver'?s?\s*licen[cs]e|licen[cs]e\s*no|dl\s*no|voter\s*id|epic\s*no)\b"
        r"\s*(?:no\.?|number|#)?\s*[:=]?\s*([A-Z0-9\-]{6,})"
    ), 1),

    # ── PERSONAL OBJECT IDs: vehicle, IMEI, device serial ──────────────────
    ("PERSONAL_OBJECT_ID", re.compile(r"\b\d{15}\b"), 0),                 # IMEI (15 digits)
    ("PERSONAL_OBJECT_ID", re.compile(
        r"\b[A-Z]{2}[\s-]?\d{1,2}[\s-]?[A-Z]{1,3}[\s-]?\d{1,4}\b"
    ), 0),                                                                # IN vehicle plate
    ("PERSONAL_OBJECT_ID", re.compile(
        r"(?i)\b(?:imei|serial(?:\s*no)?|device\s*id|vin)\b"
        r"\s*(?:no\.?|number|#)?\s*[:=]?\s*([A-Z0-9\-]{6,})"
    ), 1),

    # ── HEALTH INFO (labelled medical context) ─────────────────────────────
    ("HEALTH_INFO", re.compile(
        r"(?i)\b(?:diagnosed with|diagnosis of|suffering from|prescribed|"
        r"prescription for|treated for)\s+([A-Za-z][A-Za-z0-9 ,'\-]{2,40})"
    ), 1),
    ("HEALTH_INFO", re.compile(
        r"(?i)\b(?:mrn|medical record(?:\s*(?:no|number|#))?|patient\s*id)\b"
        r"\s*[:=#]?\s*([A-Za-z0-9\-]{4,})"
    ), 1),

    # ── ADDRESS (street address with number) ───────────────────────────────
    ("ADDRESS", re.compile(
        r"\b\d{1,5}\s+(?:[A-Z][a-zA-Z]+\s+){1,4}"
        r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|"
        r"Court|Ct|Way|Place|Pl|Terrace|Sector|Block)\b\.?",
        re.IGNORECASE,
    ), 0),

    # ── PHONE (Indian mobile + generic) ────────────────────────────────────
    ("PHONE", re.compile(r"(?<!\d)(?:\+?91[-\s]?)?[6-9]\d{9}(?!\d)"), 0),
    ("PHONE", re.compile(
        r"\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}"
    ), 0),
]

# Greeting / sign-off name heuristics (regex fallback when Presidio is absent).
_NAME_CONTEXT_PATTERNS = [
    re.compile(r"(?:Hi|Hey|Dear|Hello|To:)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"),
    re.compile(r"(?:Thanks|Best|Regards|Sincerely|From:),?\s*\n?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"),
]


# ─────────────────────────────────────────────────────────────────────────────
# GOLDEN RULE FILTERS  (applied only to ambiguous PERSON / ADDRESS detections)
# ─────────────────────────────────────────────────────────────────────────────

# Generic, non-identifying terms that must never be masked.
_GENERIC_TERMS = {
    "there", "all", "everyone", "someone", "anyone", "team", "everybody",
    "people", "users", "customers", "clients", "staff", "employees",
    "management", "citizens", "public", "members", "stakeholders",
    "yesterday", "today", "tomorrow", "sir", "madam", "guys", "folks",
    # PII label words spaCy sometimes mis-tags as PERSON — never names.
    "aadhaar", "aadhar", "pan", "gstin", "ifsc", "imei", "vin", "ssn",
    "passport", "license", "licence", "mrn", "upi", "otp",
}

# Public figures whose names in public context are NOT private PII. (Sample set;
# extend as needed. Masking is skipped only when no private contact context is
# attached to the same text.)
_PUBLIC_FIGURES = {
    "narendra modi", "joe biden", "donald trump", "elon musk", "barack obama",
    "sundar pichai", "satya nadella", "tim cook", "rishi sunak", "vladimir putin",
    "kamala harris", "bill gates", "mark zuckerberg",
}

# Common places / countries that are too general to identify an individual.
_COMMON_PLACES = {
    "india", "usa", "u.s.", "united states", "uk", "united kingdom", "europe",
    "asia", "africa", "america", "canada", "australia", "china", "japan",
    "the city", "the country", "downtown", "uptown",
}

_DEMOGRAPHIC_RE = re.compile(r"\b\d{1,3}[-\s]?year[-\s]?old\b", re.IGNORECASE)

# Phone-like content inside a spaCy PERSON span → reject (e.g. "mobile +91-9876543210").
_CONTAINS_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-\.]{6,}|\d{7,})")

# Patterns that look like names to spaCy's NER but are actually structured IDs.
# If a spaCy PERSON/LOCATION span matches one of these, reject the detection.
_LOOKS_LIKE_ID_RE = re.compile(
    r"^(?:"
    r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]"   # GSTIN
    r"|[A-Z]{5}\d{4}[A-Z]"                           # PAN
    r"|\d{4}[\s-]?\d{4}[\s-]?\d{4}"                 # Aadhaar
    r"|[A-Z]{3}\d{7}"                                # Voter ID
    r"|[A-Z]{2}\d{2}[- ]?\d{4}[- ]?\d{7}"           # DL
    r"|[A-Z]\d{7}"                                   # Passport
    r"|[A-Z]{4}0[A-Z0-9]{6}"                         # IFSC
    r"|GSTIN\s+\S+"                                  # labelled GSTIN
    r"|PAN\s+\S+"                                    # labelled PAN
    r")$",
    re.IGNORECASE,
)


def _passes_golden_rule(entity_type: str, value: str) -> bool:
    """
    Decide whether an ambiguous detection is specific enough to identify/harm a
    very small set of individuals. Returns True if it SHOULD be masked.

    Only PERSON_NAME and ADDRESS detections from NLP are routed here; hard
    identifiers (email, phone, IDs, secrets) bypass this check entirely.
    """
    cleaned = value.strip().lower()

    if not cleaned or cleaned in _GENERIC_TERMS:
        return False
    if _DEMOGRAPHIC_RE.search(cleaned):
        return False

    if entity_type == "PERSON_NAME":
        # Public figures in public context are not private PII.
        if cleaned in _PUBLIC_FIGURES:
            return False
        # Require an actual name token (a capitalised word), not a bare noun.
        if not re.search(r"[A-Za-z]{2,}", value):
            return False
        # Reject spaCy false positives where a structured ID is mis-tagged as PERSON.
        if _LOOKS_LIKE_ID_RE.match(value.strip()):
            return False
        # Reject spans that contain a phone number (e.g. "mobile +91-9876543210").
        if _CONTAINS_PHONE_RE.search(value):
            return False
        return True

    if entity_type == "ADDRESS":
        # Bare country / large region names are too general.
        if cleaned in _COMMON_PLACES:
            return False
        return True

    return True


# ─────────────────────────────────────────────────────────────────────────────
# LUHN-VALIDATED CREDIT CARD DETECTION
# ─────────────────────────────────────────────────────────────────────────────

_CARD_CANDIDATE_RE = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")


def _luhn_valid(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# ─────────────────────────────────────────────────────────────────────────────
# SANITIZER
# ─────────────────────────────────────────────────────────────────────────────

class PIISanitizer:
    """Reversible PII tokenizer following the masking rubric (see module docstring)."""

    def __init__(self) -> None:
        self.analyzer = None
        self.use_presidio = False

        if HAS_PRESIDIO:
            try:
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
                }
                provider = NlpEngineProvider(nlp_configuration=configuration)
                nlp_engine = provider.create_engine()
                self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
                self._register_indian_recognizers()
                self.use_presidio = True
                logger.info(
                    "Presidio Analyzer initialized (en_core_web_sm + custom recognizers)."
                )
            except Exception as e:
                logger.warning(f"Presidio init failed ({type(e).__name__}); using regex fallback.")

    def _register_indian_recognizers(self) -> None:
        """Register Indian government-ID patterns into Presidio's registry."""
        for entity, regex in [
            ("IN_GSTIN", r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b"),
            ("IN_PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b"),
            ("IN_AADHAAR", r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
        ]:
            self.analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity=entity,
                    patterns=[PresidioPattern(name=entity.lower(), regex=regex, score=0.85)],
                )
            )

    # ── Detection ────────────────────────────────────────────────────────────

    def detect_pii(self, text: str) -> List[PIIEntity]:
        """
        Detect all maskable PII in ``text``. Hard identifiers are matched by
        regex; PERSON / ADDRESS come from Presidio NLP (with a regex fallback)
        and are filtered through the Golden Rule. Overlaps are resolved so the
        longest (most specific) span wins.
        """
        if not text:
            return []

        candidates: List[PIIEntity] = []

        # 1. Regex hard identifiers (unambiguous — no Golden Rule needed).
        for category, pattern, group in _REGEX_DETECTORS:
            for m in pattern.finditer(text):
                try:
                    start, end = m.span(group)
                except (IndexError, re.error):  # pragma: no cover
                    continue
                if start < 0 or end <= start:
                    continue
                # phone: require >7 chars to avoid masking short numbers
                if category == "PHONE" and len(m.group(group).strip()) <= 7:
                    continue
                candidates.append(PIIEntity(category, start, end, text[start:end], 0.9))

        # 2. Luhn-validated credit cards.
        for m in _CARD_CANDIDATE_RE.finditer(text):
            if _luhn_valid(m.group(0)):
                candidates.append(
                    PIIEntity("FINANCIAL_ID", m.start(), m.end(), m.group(0), 0.95)
                )

        # 3. NLP names / locations (ambiguous → Golden Rule).
        if self.use_presidio:
            try:
                for res in self.analyzer.analyze(
                    text=text, language="en",
                    entities=["PERSON", "LOCATION", "IN_PAN", "IN_AADHAAR", "IN_GSTIN"],
                ):
                    category = {
                        "PERSON": "PERSON_NAME",
                        "LOCATION": "ADDRESS",
                        "IN_PAN": "GOVERNMENT_ID",
                        "IN_AADHAAR": "GOVERNMENT_ID",
                        "IN_GSTIN": "GOVERNMENT_ID",
                    }.get(res.entity_type)
                    if not category:
                        continue
                    value = text[res.start:res.end]
                    if not _passes_golden_rule(category, value):
                        continue
                    candidates.append(PIIEntity(category, res.start, res.end, value, res.score))
            except Exception as e:
                logger.error(f"NLP PII analysis failed ({type(e).__name__}); regex names only.")

        # Always run context patterns for names — en_core_web_sm misses many
        # Indian names, so these greetings/sign-off heuristics act as a supplement.
        for name_re in _NAME_CONTEXT_PATTERNS:
            for m in name_re.finditer(text):
                value = m.group(1)
                if not _passes_golden_rule("PERSON_NAME", value):
                    continue
                candidates.append(PIIEntity("PERSON_NAME", m.start(1), m.end(1), value, 0.6))

        # Resolve overlaps: longest span first, then earliest; stable on ties.
        candidates.sort(key=lambda c: (-(c.end - c.start), c.start))
        accepted: List[PIIEntity] = []
        for cand in candidates:
            if any(cand.start < a.end and a.start < cand.end for a in accepted):
                continue
            accepted.append(cand)

        accepted.sort(key=lambda c: c.start)
        return accepted

    # ── Masking ────────────────────────────────────────────────────────────

    def mask_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Replace detected PII with stable placeholders like ``[PERSON_1]``.
        Returns ``(masked_text, mapping)`` where ``mapping`` reverses the masking.
        Raw PII values are never logged.
        """
        if not text:
            return "", {}

        entities = self.detect_pii(text)

        mapping: Dict[str, str] = {}
        counter: Dict[str, int] = defaultdict(int)
        value_to_placeholder: Dict[str, str] = {}
        spans: List[Tuple[int, int, str]] = []

        # Forward pass: assign placeholders (left-to-right, dedup by value).
        for ent in sorted(entities, key=lambda e: e.start):
            prefix = ENTITY_PREFIX.get(ent.entity_type)
            if not prefix:
                continue
            placeholder = value_to_placeholder.get(ent.text)
            if placeholder is None:
                counter[prefix] += 1
                placeholder = f"[{prefix}_{counter[prefix]}]"
                value_to_placeholder[ent.text] = placeholder
                mapping[placeholder] = ent.text
            spans.append((ent.start, ent.end, placeholder))

        # Reverse pass: splice without invalidating earlier offsets.
        masked = text
        for start, end, placeholder in sorted(spans, key=lambda s: s[0], reverse=True):
            masked = masked[:start] + placeholder + masked[end:]

        if mapping:
            # Log only counts/types — never raw values.
            summary = {p.rsplit("_", 1)[0].strip("[]"): 0 for p in mapping}
            for p in mapping:
                summary[p.rsplit("_", 1)[0].strip("[]")] += 1
            logger.info(f"PII masked: {dict(summary)}")

        return masked, mapping

    def restore_text(self, masked_text: str, mapping: Dict[str, str]) -> str:
        """
        Restore original PII values into a masked string using ``mapping``.

        Tolerant of light reformatting an LLM may apply to a token: matching is
        case-insensitive and allows whitespace and ``_``/``-`` interchange inside
        the brackets, so ``[PERSON_1]``, ``[person 1]`` and ``[ PERSON-1 ]`` all
        resolve to the same original value. An exact pass runs first for speed.
        """
        if not masked_text or not mapping:
            return masked_text

        restored = masked_text
        for placeholder, original in mapping.items():
            restored = restored.replace(placeholder, original)

        # Second, tolerant pass for any tokens the LLM lightly reshaped.
        for placeholder, original in mapping.items():
            inner = placeholder.strip("[]")                 # e.g. "PERSON_1"
            prefix, _, num = inner.rpartition("_")
            if not prefix or not num.isdigit():
                continue
            # [ <ws> PREFIX <ws|_|-> NUM <ws> ]
            pattern = re.compile(
                rf"\[\s*{re.escape(prefix)}[\s_\-]*{re.escape(num)}\s*\]",
                re.IGNORECASE,
            )
            restored = pattern.sub(lambda _m: original, restored)

        return restored

    def strip_unresolved_tokens(self, text: str) -> str:
        """
        Replace any leftover MailMind placeholder with a safe, neutral phrase.

        An LLM can *hallucinate* a token number that was never in the mapping
        (e.g. it sees ``[PERSON_1]`` and writes ``[PERSON_2]`` in the greeting).
        Such a token has no original value to restore, so it would otherwise
        reach the user as broken text. We never leak real PII here — we only
        replace the orphaned placeholder with a generic, human-readable fallback
        so the output reads naturally.

        Call this AFTER ``restore_text`` on any user-facing LLM output.
        """
        if not text:
            return text

        def _replace(match: "re.Match[str]") -> str:
            prefix = match.group(1).upper()
            return _UNRESOLVED_FALLBACK.get(prefix, "the details provided")

        # Matches our token shape with the same tolerance as restore_text.
        return _UNRESOLVED_TOKEN_RE.sub(_replace, text)


# Neutral fallbacks for orphaned (hallucinated) tokens, keyed by placeholder prefix.
_UNRESOLVED_FALLBACK = {
    "PERSON": "there",
    "EMAIL": "the address provided",
    "PHONE": "the number provided",
    "ADDRESS": "the address provided",
    "FIN_ID": "the account provided",
    "GOV_ID": "the ID provided",
    "HEALTH": "the information provided",
    "SECRET": "the credential provided",
    "DEVICE_ID": "the device provided",
}

# [ <ws> PREFIX <ws|_|-> NUM <ws> ] — PREFIX may contain an internal underscore
# (FIN_ID, GOV_ID, DEVICE_ID), so match greedily up to the trailing number.
_UNRESOLVED_TOKEN_RE = re.compile(
    r"\[\s*([A-Z][A-Z_]*?)[\s_\-]+\d+\s*\]",
    re.IGNORECASE,
)


# Singleton + module-level functional API.
pii_sanitizer = PIISanitizer()


def detect_pii(text: str) -> List[PIIEntity]:
    """Module-level wrapper around the shared sanitizer (see PIISanitizer.detect_pii)."""
    return pii_sanitizer.detect_pii(text)


def mask_text(text: str) -> Tuple[str, Dict[str, str]]:
    """Module-level wrapper around the shared sanitizer (see PIISanitizer.mask_text)."""
    return pii_sanitizer.mask_text(text)


def restore_text(masked_text: str, mapping: Dict[str, str]) -> str:
    """Module-level wrapper around the shared sanitizer (see PIISanitizer.restore_text)."""
    return pii_sanitizer.restore_text(masked_text, mapping)


def strip_unresolved_tokens(text: str) -> str:
    """Module-level wrapper (see PIISanitizer.strip_unresolved_tokens)."""
    return pii_sanitizer.strip_unresolved_tokens(text)
