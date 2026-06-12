"""
MailMind v2 — Tone DNA Service (DNA-01 to DNA-05)

How it works
------------
1. **Ingest**: fetch up to 180 days of the user's *sent* mail via the active
   mail provider (Microsoft Graph or Gmail).
2. **Analyse**: run 8 pure-Python stylometric measures over the combined body
   text — no ML model required (see `build_profile` for the feature list).
3. **Persist**: write the resulting dict to the DB (`tone_profile` table keyed
   by `user_email`) AND to a per-user JSON file under `data/tone_dna/` as a
   fast fallback for when the DB is unreachable or not configured.
4. **Inject**: `get_system_prefix()` converts the profile into a Tone DNA
   system-prompt prefix that DraftService prepends before every LLM call so
   the generated reply sounds like the user wrote it.
5. **Refresh**: a background thread re-runs the ingest 7 days after every
   successful build so the profile tracks how the user's style evolves.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Per-user file path (fallback / dev-mode cache) ───────────────────────────

def _profile_path(account_id: str) -> Path:
    """Deterministic per-account path that avoids special chars in filenames."""
    slug = hashlib.md5(account_id.strip().lower().encode()).hexdigest()
    return Path("data/tone_dna") / f"{slug}.json"


# ── Constants ─────────────────────────────────────────────────────────────────

CONTEXT_OVERRIDES = {
    "complaint":      {"formality_delta": +0.15},
    "congratulation": {"formality_delta": -0.10},
    "urgent":         {"formality_delta": +0.10},
}

FORMALITY_MARKERS = [
    "please", "kindly", "regarding", "pursuant", "hereby",
    "sincerely", "dear", "accordingly", "therefore", "thus",
]
INFORMAL_MARKERS = [
    "hey", "hi", "thanks", "yeah", "yep", "ok", "sure", "np",
    "btw", "fyi", "lol", "asap",
]


# ── Feature extractors ────────────────────────────────────────────────────────

def _avg_sentence_length(text: str) -> float:
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def _formality_score(text: str) -> float:
    lower = text.lower()
    words = lower.split()
    if not words:
        return 0.5
    formal = sum(1 for m in FORMALITY_MARKERS if m in lower)
    informal = sum(1 for m in INFORMAL_MARKERS if m in lower)
    return round(max(0.0, min(1.0, 0.5 + (formal - informal) * 0.05)), 3)


def _greeting_patterns(texts: list[str]) -> list[str]:
    patterns: dict[str, int] = {}
    for text in texts:
        m = re.match(r"^(Hi|Hey|Dear|Hello|Good morning|Good afternoon)\s+(\w+)", text, re.I)
        if m:
            key = f"{m.group(1).capitalize()} {{name}}"
            patterns[key] = patterns.get(key, 0) + 1
    return [k for k, _ in sorted(patterns.items(), key=lambda x: -x[1])[:5]]


def _signoff_patterns(texts: list[str]) -> list[str]:
    patterns: dict[str, int] = {}
    for text in texts:
        m = re.search(r"\n(Best|Thanks|Regards|Sincerely|Cheers|Kind regards)[,.]?", text, re.I)
        if m:
            key = f"{m.group(1).capitalize()},"
            patterns[key] = patterns.get(key, 0) + 1
    return [k for k, _ in sorted(patterns.items(), key=lambda x: -x[1])[:5]]


def _contraction_rate(text: str) -> float:
    contractions = re.findall(r"\b\w+'\w+\b", text)
    words = text.split()
    return round(len(contractions) / len(words), 3) if words else 0.0


def _bullet_preference(text: str) -> float:
    lines = text.split("\n")
    bullet_lines = sum(1 for line in lines if line.strip().startswith(("-", "*", "•", "·")))
    return round(bullet_lines / max(len(lines), 1), 3)


def _emoji_rate(text: str) -> float:
    emoji_pattern = re.compile(
        "[\U0001F300-\U0001F9FF\U00002600-\U000027BF]+", flags=re.UNICODE
    )
    emojis = emoji_pattern.findall(text)
    words = text.split()
    return round(len(emojis) / len(words), 4) if words else 0.0


def _top_vocabulary(texts: list[str], n: int = 100) -> list[str]:
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "is", "it", "this", "that", "i", "you",
        "we", "be", "are", "was", "were", "have", "has", "had",
    }
    freq: dict[str, int] = {}
    for text in texts:
        for word in re.findall(r"\b[a-z]{3,}\b", text.lower()):
            if word not in stopwords:
                freq[word] = freq.get(word, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]


# ── Profile build / load / save ───────────────────────────────────────────────

def build_profile(emails: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute the 8 stylometric features from a list of sent-email dicts.

    Each dict must have at least a ``"body"`` key.  Returns the full profile
    dict (does NOT write to disk or DB — callers do that).
    """
    bodies = [str(e.get("body", "")) for e in emails if e.get("body")]
    all_text = "\n\n".join(bodies)

    return {
        "profile_version": 3,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sample_size": len(bodies),
        "features": {
            "avg_sentence_length":    round(_avg_sentence_length(all_text), 2),
            "formality_score":        _formality_score(all_text),
            "greeting_patterns":      _greeting_patterns(bodies),
            "signoff_patterns":       _signoff_patterns(bodies),
            "contraction_rate":       _contraction_rate(all_text),
            "bullet_point_preference": _bullet_preference(all_text),
            "vocabulary_top_100":     _top_vocabulary(bodies),
            "emoji_rate":             _emoji_rate(all_text),
        },
        "context_overrides": CONTEXT_OVERRIDES,
    }


def load_profile(account_id: str) -> dict[str, Any] | None:
    """
    Load the profile for *account_id*.

    Priority:
      1. Database (authoritative — persists across deploys / container restarts)
      2. Local JSON file under ``data/tone_dna/`` (dev-mode fallback)
    """
    # 1. DB
    try:
        from app.db.repository import get_tone_profile
        profile = get_tone_profile(account_id)
        if profile:
            return profile
    except Exception as exc:
        logger.debug("[ToneDNA] DB load skipped: %s", exc)

    # 2. File fallback
    path = _profile_path(account_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[ToneDNA] File load failed for %s: %s", account_id, exc)

    return None


def save_profile(account_id: str, profile: dict[str, Any]) -> None:
    """
    Persist the profile for *account_id* to DB (primary) and local file (fallback).

    Both writes are best-effort — a failure in one does not abort the other.
    """
    # 1. DB
    try:
        from app.db.repository import save_tone_profile
        save_tone_profile(account_id, profile)
        logger.info("[ToneDNA] Profile saved to DB for %s", account_id)
    except Exception as exc:
        logger.warning("[ToneDNA] DB save failed for %s: %s", account_id, exc)

    # 2. File fallback
    try:
        path = _profile_path(account_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("[ToneDNA] File save failed for %s: %s", account_id, exc)


def needs_refresh(profile: dict[str, Any]) -> bool:
    try:
        generated = datetime.fromisoformat(profile["generated_at"].replace("Z", ""))
        return datetime.utcnow() - generated > timedelta(days=7)
    except Exception:
        return True


# ── System-prompt builder ─────────────────────────────────────────────────────

def build_system_prefix(profile: dict[str, Any], context: str = "") -> str:
    """DNA-04: Convert a profile into a Tone DNA system-prompt prefix."""
    f = profile["features"]
    overrides = profile.get("context_overrides", {})

    formality = f["formality_score"]
    for key, delta_dict in overrides.items():
        if key in context.lower():
            formality = round(max(0.0, min(1.0, formality + delta_dict.get("formality_delta", 0))), 3)

    greetings = ", ".join(f["greeting_patterns"][:3]) or "Hi {name}"
    signoffs = ", ".join(f["signoff_patterns"][:3]) or "Best,"

    return (
        f"You are drafting an email that must sound exactly like the user wrote it.\n"
        f"Tone DNA profile:\n"
        f"- Average sentence length: {f['avg_sentence_length']} words\n"
        f"- Formality (0=casual, 1=formal): {formality}\n"
        f"- Typical greetings: {greetings}\n"
        f"- Typical sign-offs: {signoffs}\n"
        f"- Contraction rate: {f['contraction_rate']} "
        f"({'uses contractions' if f['contraction_rate'] > 0.05 else 'avoids contractions'})\n"
        f"- Bullet point usage: {f['bullet_point_preference']} "
        f"({'prefers bullets' if f['bullet_point_preference'] > 0.2 else 'prefers prose'})\n"
        f"- Key vocabulary: {', '.join(f['vocabulary_top_100'][:20])}\n"
        f"Match this style precisely. Do not sound generic.\n\n"
    )


# ── Service class ─────────────────────────────────────────────────────────────

class ToneDNAService:
    """
    DNA-01–05: Ingestion, profiling, DB persistence, injection, weekly refresh.

    Parameters
    ----------
    mail_client:
        An active GraphClient or GmailClient instance for the current user.
        Used to fetch sent mail.  Pass ``get_mail_client()`` at call time —
        never hard-code ``GraphClient()``.
    account_id:
        The OAuthAccount UUID.  Used to scope storage so different accounts
        (including the same user's Gmail vs Outlook) never overwrite each other.
    """

    def __init__(self, mail_client: Any, account_id: str) -> None:
        self.mail_client = mail_client
        self.account_id = account_id
        self._profile: dict[str, Any] | None = None

    def get_profile(self) -> dict[str, Any] | None:
        if self._profile is None:
            self._profile = load_profile(self.account_id)
        if self._profile and needs_refresh(self._profile):
            self._schedule_refresh()
        return self._profile

    def ingest_and_build(self) -> dict[str, Any]:
        """
        DNA-01: Fetch 30 days of sent mail, build + persist the Tone DNA
        profile, then index the same emails into the RAG vector store.

        Both operations share one mail-provider fetch so there is no second
        round-trip to Microsoft Graph / Gmail.
        """
        logger.info("[ToneDNA] Ingesting sent mail for account %s…", self.account_id)
        emails = self.mail_client.fetch_sent_emails(days=30)

        # ── 1. Stylometric profile ────────────────────────────────────────────
        profile = build_profile(emails)
        save_profile(self.account_id, profile)
        self._profile = profile
        logger.info(
            "[ToneDNA] Profile built for %s — %d emails, formality=%.2f",
            self.account_id,
            profile["sample_size"],
            profile["features"]["formality_score"],
        )

        # ── 2. RAG vector index (same emails, no second fetch) ────────────────
        try:
            from app.services.rag import EmbeddingProvider, RAGIndexFactory, mask_pii
            index = RAGIndexFactory()()
            embedder = EmbeddingProvider()
            documents = []
            for email in emails:
                body = email.get("body", "")
                if isinstance(body, dict):
                    body = body.get("content", "")
                masked = mask_pii(str(body or email.get("bodyPreview", "")))
                if not masked.strip():
                    continue
                documents.append({
                    "email_id": email.get("id") or email.get("email_id", ""),
                    "subject": email.get("subject", "No Subject"),
                    "masked_body": masked[:1000],
                    "embedding": embedder.embed(masked),
                })
            if documents:
                index.index(documents)
                logger.info("[ToneDNA] Indexed %d sent emails into RAG for %s", len(documents), self.account_id)
        except Exception as exc:
            logger.warning("[ToneDNA] RAG indexing failed for %s: %s", self.account_id, exc)

        self._schedule_refresh()
        return profile

    def get_system_prefix(self, context: str = "") -> str:
        """DNA-04: Return Tone DNA system-prompt prefix, or empty string if no profile."""
        profile = self.get_profile()
        if not profile:
            return ""
        return build_system_prefix(profile, context)

    def _schedule_refresh(self) -> None:
        """DNA-03: Re-build the profile 7 days from now in a background thread."""
        def _refresh() -> None:
            try:
                self.ingest_and_build()
            except Exception as exc:
                logger.warning("[ToneDNA] Weekly refresh failed for %s: %s", self.account_id, exc)

        t = threading.Timer(timedelta(days=7).total_seconds(), _refresh)
        t.daemon = True
        t.start()
        logger.info("[ToneDNA] Weekly refresh scheduled for %s.", self.account_id)
