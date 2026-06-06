"""
MailMind v2 — Tone DNA Service (DNA-01 to DNA-05)
Builds a stylometric profile from sent mail history.
"""
from __future__ import annotations

import json
import logging
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROFILE_PATH = Path("data/tone_dna_profile.json")

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


def _avg_sentence_length(text: str) -> float:
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
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
    score = 0.5 + (formal - informal) * 0.05
    return round(max(0.0, min(1.0, score)), 3)


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
    if not words:
        return 0.0
    return round(len(contractions) / len(words), 3)


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
    if not words:
        return 0.0
    return round(len(emojis) / len(words), 4)


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


def build_profile(emails: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a Tone DNA profile from a list of sent email dicts."""
    bodies = [str(e.get("body", "")) for e in emails if e.get("body")]
    all_text = "\n\n".join(bodies)

    profile = {
        "profile_version": 2,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sample_size": len(bodies),
        "features": {
            "avg_sentence_length": round(_avg_sentence_length(all_text), 2),
            "formality_score": _formality_score(all_text),
            "greeting_patterns": _greeting_patterns(bodies),
            "signoff_patterns": _signoff_patterns(bodies),
            "contraction_rate": _contraction_rate(all_text),
            "bullet_point_preference": _bullet_preference(all_text),
            "vocabulary_top_100": _top_vocabulary(bodies),
            "emoji_rate": _emoji_rate(all_text),
        },
        "context_overrides": CONTEXT_OVERRIDES,
    }
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile, indent=2))
    logger.info(f"Tone DNA profile built from {len(bodies)} emails.")
    return profile


def load_profile() -> dict[str, Any] | None:
    if PROFILE_PATH.exists():
        return json.loads(PROFILE_PATH.read_text())
    return None


def needs_refresh(profile: dict[str, Any]) -> bool:
    generated = datetime.fromisoformat(profile["generated_at"].replace("Z", ""))
    return datetime.utcnow() - generated > timedelta(days=7)


def build_system_prefix(profile: dict[str, Any], context: str = "") -> str:
    """DNA-04: Build the system prompt prefix from the profile."""
    f = profile["features"]
    overrides = profile.get("context_overrides", {})

    # Apply context-aware formality delta
    formality = f["formality_score"]
    for key, delta_dict in overrides.items():
        if key in context.lower():
            formality = round(
                max(0.0, min(1.0, formality + delta_dict.get("formality_delta", 0))), 3
            )

    greetings = ", ".join(f['greeting_patterns'][:3]) or "Hi {name}"
    signoffs = ", ".join(f['signoff_patterns'][:3]) or "Best,"

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


class ToneDNAService:
    """DNA-01–05: Ingestion, profiling, caching, injection, weekly refresh."""

    def __init__(self, graph_client: Any) -> None:
        self.graph_client = graph_client
        self._profile: dict[str, Any] | None = None

    def get_profile(self) -> dict[str, Any] | None:
        if self._profile is None:
            self._profile = load_profile()
        if self._profile and needs_refresh(self._profile):
            self._schedule_refresh()
        return self._profile

    def ingest_and_build(self) -> dict[str, Any]:
        """DNA-01: Fetch 180 days of sent mail and build profile."""
        logger.info("Tone DNA: ingesting sent mail...")
        emails = self.graph_client.fetch_sent_emails(days=180)
        self._profile = build_profile(emails)
        self._schedule_refresh()
        return self._profile

    def get_system_prefix(self, context: str = "") -> str:
        """DNA-04: Return Tone DNA system prompt prefix."""
        profile = self.get_profile()
        if not profile:
            return ""
        return build_system_prefix(profile, context)

    def _schedule_refresh(self) -> None:
        """DNA-03: Schedule weekly refresh in background."""
        def _refresh():
            try:
                self.ingest_and_build()
            except Exception as e:
                logger.warning(f"Tone DNA weekly refresh failed: {e}")

        delay = timedelta(days=7).total_seconds()
        t = threading.Timer(delay, _refresh)
        t.daemon = True
        t.start()
        logger.info("Tone DNA weekly refresh scheduled.")