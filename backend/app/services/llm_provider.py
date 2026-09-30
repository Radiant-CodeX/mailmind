"""
Pluggable LLM provider layer (bring-your-own-key).
===================================================

Every AI call in MailMind — triage, classification, commitment extraction,
drafting, embeddings — resolves its model through this module. Any
OpenAI-compatible endpoint works: OpenRouter, Groq, Google Gemini, OpenAI,
a local Ollama server, or a custom base URL.

Resolution order for each call:
  1. The signed-in user's own AI settings (their saved API key + models).
  2. The server default (LLM_* environment variables).
  3. None → callers use their deterministic rule-based fallbacks.

How the current user is known
-----------------------------
``SessionContextMiddleware`` stores the raw ``mm_session`` cookie in a
ContextVar at the start of every request (no DB hit). The first time an LLM is
actually needed, the token is resolved to a user id and that user's settings
are loaded — both cached briefly. Background jobs with no request (the
enrichment worker) bind the user explicitly with ``use_ai_user(user_id)``.
Worker threads spawned from a request must be submitted through
``request_context.run_in_context`` so they inherit the binding.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import logging
import math
import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Iterator

from app.config.settings import settings

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Provider presets
# ─────────────────────────────────────────────────────────────────────────────

# Every preset speaks the OpenAI chat-completions protocol, so one client
# (langchain_openai.ChatOpenAI / openai.OpenAI) covers them all. Suggested models
# are defaults only — users can type any model id their provider serves.
PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_chat_model": "meta-llama/llama-3.3-70b-instruct:free",
        "default_triage_model": "meta-llama/llama-3.3-70b-instruct:free",
        "suggested_models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "deepseek/deepseek-chat-v3-0324:free",
            "mistralai/mistral-7b-instruct:free",
        ],
        "key_url": "https://openrouter.ai/keys",
        "free_tier": True,
        "supports_embeddings": False,
        "notes": "One key, hundreds of models. Model ids ending in ':free' cost nothing.",
    },
    "groq": {
        "label": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_chat_model": "llama-3.3-70b-versatile",
        "default_triage_model": "llama-3.1-8b-instant",
        "suggested_models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "key_url": "https://console.groq.com/keys",
        "free_tier": True,
        "supports_embeddings": False,
        "notes": "Very fast inference with a generous free tier.",
    },
    "gemini": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_chat_model": "gemini-2.0-flash",
        "default_triage_model": "gemini-2.0-flash",
        "suggested_models": ["gemini-2.0-flash", "gemini-1.5-flash"],
        "key_url": "https://aistudio.google.com/app/apikey",
        "free_tier": True,
        "supports_embeddings": True,
        "default_embedding_model": "text-embedding-004",
        "notes": "Free API key from Google AI Studio.",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_chat_model": "gpt-4o-mini",
        "default_triage_model": "gpt-4o-mini",
        "suggested_models": ["gpt-4o-mini", "gpt-4o"],
        "key_url": "https://platform.openai.com/api-keys",
        "free_tier": False,
        "supports_embeddings": True,
        "default_embedding_model": "text-embedding-3-small",
        "notes": "Paid, pay-as-you-go.",
    },
    "ollama": {
        "label": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "default_chat_model": "llama3.1",
        "default_triage_model": "llama3.1",
        "suggested_models": ["llama3.1", "qwen2.5", "mistral"],
        "key_url": "https://ollama.com/download",
        "free_tier": True,
        "supports_embeddings": True,
        "default_embedding_model": "nomic-embed-text",
        "requires_key": False,
        "notes": "Runs on your own machine — nothing leaves it. No key needed.",
    },
    "custom": {
        "label": "Custom (OpenAI-compatible)",
        "base_url": "",
        "default_chat_model": "",
        "default_triage_model": "",
        "suggested_models": [],
        "key_url": "",
        "free_tier": False,
        "supports_embeddings": False,
        "notes": "Any endpoint that implements the OpenAI chat-completions API.",
    },
}


def provider_catalog() -> list[dict[str, Any]]:
    """Public, key-free description of the supported providers (for the UI)."""
    return [
        {
            "id": pid,
            "label": p["label"],
            "base_url": p["base_url"],
            "default_chat_model": p["default_chat_model"],
            "default_triage_model": p["default_triage_model"],
            "suggested_models": p["suggested_models"],
            "key_url": p["key_url"],
            "free_tier": p["free_tier"],
            "supports_embeddings": p["supports_embeddings"],
            "default_embedding_model": p.get("default_embedding_model"),
            "requires_key": p.get("requires_key", True),
            "notes": p["notes"],
        }
        for pid, p in PROVIDER_PRESETS.items()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Config model
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AIConfig:
    """A fully-resolved model configuration for one caller."""

    provider: str
    base_url: str
    api_key: str
    chat_model: str
    triage_model: str
    embedding_model: str = ""   # empty → local embeddings
    source: str = "server"      # "user" | "server"

    @property
    def fingerprint(self) -> str:
        """Stable cache key that never exposes the raw API key."""
        raw = f"{self.base_url}|{self.api_key}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def model_for(self, purpose: str) -> str:
        if purpose == "triage":
            return self.triage_model or self.chat_model
        return self.chat_model

    def redacted(self) -> dict[str, Any]:
        """Serialisable view with the key masked (safe to return to clients)."""
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key_hint": mask_key(self.api_key),
            "chat_model": self.chat_model,
            "triage_model": self.triage_model,
            "embedding_model": self.embedding_model,
            "source": self.source,
        }


def mask_key(key: str) -> str:
    """Show only enough of a key to recognise it: 'sk-or-…a1b2'."""
    if not key:
        return ""
    if len(key) <= 8:
        return "…" + key[-2:]
    return f"{key[:6]}…{key[-4:]}"


def build_config(
    *,
    provider: str,
    api_key: str,
    base_url: str | None = None,
    chat_model: str | None = None,
    triage_model: str | None = None,
    embedding_model: str | None = None,
    source: str = "user",
) -> AIConfig:
    """Fill a partial user/server spec in from the provider preset."""
    provider = (provider or "custom").strip().lower()
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])
    chat = (chat_model or "").strip() or preset["default_chat_model"]
    return AIConfig(
        provider=provider,
        base_url=(base_url or "").strip() or preset["base_url"],
        api_key=(api_key or "").strip(),
        chat_model=chat,
        triage_model=(triage_model or "").strip() or preset["default_triage_model"] or chat,
        embedding_model=(embedding_model or "").strip(),
        source=source,
    )


def _is_usable(cfg: AIConfig | None) -> bool:
    if cfg is None or not cfg.base_url or not cfg.chat_model:
        return False
    requires_key = PROVIDER_PRESETS.get(cfg.provider, {}).get("requires_key", True)
    return bool(cfg.api_key) or not requires_key


def server_default_config() -> AIConfig | None:
    """The deployment-wide default model (LLM_* env vars), if configured.

    For convenience, a bare GROQ_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY
    is also picked up when LLM_API_KEY is unset.
    """
    provider = settings.llm_provider
    key = settings.llm_api_key
    if not key:
        for name, env_key in (
            ("openrouter", settings.openrouter_api_key),
            ("groq", settings.groq_api_key),
            ("openai", settings.openai_api_key),
        ):
            if env_key:
                if not settings.llm_provider_explicit:
                    provider = name
                key = env_key
                break
    cfg = build_config(
        provider=provider,
        api_key=key,
        base_url=settings.llm_base_url,
        chat_model=settings.llm_chat_model,
        triage_model=settings.llm_triage_model,
        embedding_model=settings.llm_embedding_model,
        source="server",
    )
    return cfg if _is_usable(cfg) else None


# ─────────────────────────────────────────────────────────────────────────────
# Request-scoped identity → per-user config
# ─────────────────────────────────────────────────────────────────────────────

_session_token: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mailmind_ai_session_token", default=None
)
_ai_user_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "mailmind_ai_user_id", default=None
)

_TOKEN_TTL = 300.0
_CONFIG_TTL = 60.0
_token_user_cache: dict[str, tuple[float, str | None]] = {}
_user_config_cache: dict[str, tuple[float, AIConfig | None]] = {}
_cache_lock = threading.Lock()


def set_session_token(token: str | None) -> contextvars.Token:
    """Bind the raw mm_session cookie for this request (called by middleware)."""
    return _session_token.set(token)


def reset_session_token(tok: contextvars.Token) -> None:
    _session_token.reset(tok)


@contextlib.contextmanager
def use_ai_user(user_id: str | None) -> Iterator[None]:
    """Explicitly bind a user for AI resolution (background jobs, tests)."""
    tok = _ai_user_id.set(user_id)
    try:
        yield
    finally:
        _ai_user_id.reset(tok)


def _user_id_from_token(token: str) -> str | None:
    now = time.monotonic()
    key = hashlib.sha256(token.encode()).hexdigest()
    with _cache_lock:
        hit = _token_user_cache.get(key)
        if hit and hit[0] > now:
            return hit[1]
    user_id: str | None = None
    try:
        from app.db.base import get_session
        from app.services.session_service import DBSessionBackend

        with get_session() as db:
            if db is not None:
                user_id = DBSessionBackend(db).get_user_id(token)
    except Exception as exc:  # never let identity lookup break an AI call
        logger.debug("[llm] session → user lookup failed: %s", exc)
    with _cache_lock:
        _token_user_cache[key] = (now + _TOKEN_TTL, user_id)
    return user_id


def current_ai_user_id() -> str | None:
    """User the current AI call runs on behalf of (explicit binding wins)."""
    explicit = _ai_user_id.get()
    if explicit:
        return explicit
    token = _session_token.get()
    return _user_id_from_token(token) if token else None


def _load_user_config(user_id: str) -> AIConfig | None:
    now = time.monotonic()
    with _cache_lock:
        hit = _user_config_cache.get(user_id)
        if hit and hit[0] > now:
            return hit[1]
    cfg: AIConfig | None = None
    try:
        from app.services.user_settings import load_ai_config

        cfg = load_ai_config(user_id)
    except Exception as exc:
        logger.warning("[llm] could not load AI settings for user %s: %s", user_id, exc)
    with _cache_lock:
        _user_config_cache[user_id] = (now + _CONFIG_TTL, cfg)
    return cfg


def invalidate_user_config(user_id: str) -> None:
    """Drop cached settings so a just-saved key takes effect immediately."""
    with _cache_lock:
        _user_config_cache.pop(user_id, None)


def resolve_config() -> AIConfig | None:
    """The config the current call should use, or None (→ deterministic)."""
    user_id = current_ai_user_id()
    if user_id:
        cfg = _load_user_config(user_id)
        if _is_usable(cfg):
            return cfg
    return server_default_config()


def llm_available() -> bool:
    return resolve_config() is not None


# ─────────────────────────────────────────────────────────────────────────────
# Chat models
# ─────────────────────────────────────────────────────────────────────────────

_chat_cache: dict[tuple, Any] = {}


def _default_headers(cfg: AIConfig) -> dict[str, str] | None:
    # OpenRouter uses these for attribution / its app leaderboard (optional).
    if cfg.provider == "openrouter":
        return {"HTTP-Referer": settings.frontend_origin, "X-Title": "MailMind"}
    return None


def build_chat_model(
    cfg: AIConfig,
    *,
    temperature: float = 0.1,
    purpose: str = "chat",
    max_tokens: int | None = None,
    timeout: float | None = None,
):
    """Construct (and cache) a LangChain chat model for an explicit config."""
    from langchain_openai import ChatOpenAI

    model = cfg.model_for(purpose)
    key = (cfg.fingerprint, model, round(temperature, 2), max_tokens, timeout)
    llm = _chat_cache.get(key)
    if llm is None:
        kwargs: dict[str, Any] = dict(
            model=model,
            api_key=cfg.api_key or "not-needed",
            base_url=cfg.base_url,
            temperature=temperature,
            max_retries=1,
            timeout=timeout or settings.llm_timeout_seconds,
        )
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        headers = _default_headers(cfg)
        if headers:
            kwargs["default_headers"] = headers
        llm = ChatOpenAI(**kwargs)
        _chat_cache[key] = llm
        logger.info(
            "[llm] chat model ready provider=%s model=%s source=%s temp=%.1f",
            cfg.provider, model, cfg.source, temperature,
        )
    return llm


def get_chat_model(
    temperature: float = 0.1,
    *,
    purpose: str = "chat",
    max_tokens: int | None = None,
):
    """Chat model for the current caller, or None when no AI is configured."""
    cfg = resolve_config()
    if cfg is None:
        return None
    return build_chat_model(cfg, temperature=temperature, purpose=purpose, max_tokens=max_tokens)


def active_model_label(purpose: str = "chat") -> str:
    """Human-readable 'provider/model' for logs and reasoning strings."""
    cfg = resolve_config()
    if cfg is None:
        return "rule-based"
    return f"{cfg.provider}:{cfg.model_for(purpose)}"


# ─────────────────────────────────────────────────────────────────────────────
# Output parsing helpers (free models are less disciplined than gpt-4o)
# ─────────────────────────────────────────────────────────────────────────────

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def clean_text(content: Any) -> str:
    """Normalise a model reply: flatten content parts, drop reasoning blocks."""
    if isinstance(content, list):  # some providers return content parts
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part) for part in content
        )
    text = str(content or "")
    return _THINK_RE.sub("", text).strip()


def parse_json(content: Any) -> Any:
    """Extract the first JSON object/array from a model reply.

    Handles markdown fences, <think> blocks, and prose before/after the JSON.
    Raises ValueError when no parseable JSON is present.
    """
    text = _FENCE_RE.sub("", clean_text(content)).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                continue
    raise ValueError("model reply contained no parseable JSON")


def invoke_json(
    system_prompt: str,
    user_prompt: str,
    *,
    purpose: str = "chat",
    temperature: float = 0.0,
    max_tokens: int | None = None,
    config: dict | None = None,
) -> Any:
    """One-shot JSON call against the current caller's model.

    Returns the parsed JSON, or raises (RuntimeError when no model is
    configured) so callers can fall back to their deterministic path.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_chat_model(temperature, purpose=purpose, max_tokens=max_tokens)
    if llm is None:
        raise RuntimeError("No AI model configured")
    response = llm.invoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        config=config,
    )
    return parse_json(response.content)


# ─────────────────────────────────────────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_EMBEDDING_DIM = 384
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are as at be been but by can could do does for from had has have hi hello i if in "
    "into is it its me my no not of on or our please regards so that the their them then there "
    "these they this to up us was we were what when which will with would you your dear thanks "
    "thank best all any also am".split()
)
_SUFFIXES = ("ations", "ation", "ings", "ing", "ions", "ion", "ers", "ed", "es", "s")


def _stem(word: str) -> str:
    """Tiny suffix stripper so 'registration' and 'register' share a feature."""
    for suffix in _SUFFIXES:
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def local_embed(text: str, dim: int = LOCAL_EMBEDDING_DIM) -> list[float]:
    """Free, offline embedding: hashed stemmed unigrams + bigrams, sublinear tf, L2-norm.

    Far better than character codes for "have I handled an email like this
    before?" retrieval, needs no API key, and is deterministic across restarts.
    """
    words = [_stem(w) for w in _WORD_RE.findall((text or "").lower())
             if len(w) > 1 and w not in _STOPWORDS]
    vec = [0.0] * dim
    if not words:
        return vec
    counts: dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    for a, b in zip(words, words[1:]):
        bigram = f"{a}_{b}"
        counts[bigram] = counts.get(bigram, 0) + 1
    for term, n in counts.items():
        h = int(hashlib.md5(term.encode()).hexdigest(), 16)
        sign = 1.0 if (h >> 1) & 1 else -1.0
        vec[h % dim] += sign * (1.0 + math.log(n))
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


_embed_unavailable: set[str] = set()


def uses_remote_embeddings() -> bool:
    cfg = resolve_config()
    return bool(cfg and cfg.embedding_model and cfg.fingerprint not in _embed_unavailable)


def similarity_threshold() -> float:
    """RAG match threshold for the embedder in use.

    Dense model embeddings score related texts ~0.75-0.9; sparse local hashed
    embeddings score them ~0.3-0.6, so each needs its own cut-off.
    """
    if uses_remote_embeddings():
        return settings.rag_similarity_threshold
    return settings.rag_local_similarity_threshold


def embed_text(text: str) -> list[float]:
    """Embed with the caller's embedding model if configured, else locally."""
    cfg = resolve_config()
    if cfg and cfg.embedding_model and cfg.fingerprint not in _embed_unavailable:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=cfg.api_key or "not-needed", base_url=cfg.base_url,
                            max_retries=0, timeout=8.0)
            resp = client.embeddings.create(model=cfg.embedding_model,
                                            input=[(text or " ").replace("\n", " ")])
            return list(resp.data[0].embedding)
        except Exception as exc:
            # Permanent-looking failures disable remote embeddings for this key.
            _embed_unavailable.add(cfg.fingerprint)
            logger.warning("[llm] embedding model unavailable (%s) — using local embeddings",
                           str(exc)[:120])
    return local_embed(text)


# ─────────────────────────────────────────────────────────────────────────────
# Connection test
# ─────────────────────────────────────────────────────────────────────────────


def test_config(cfg: AIConfig) -> dict[str, Any]:
    """Make one tiny real call to verify a key/model before saving it."""
    from langchain_core.messages import HumanMessage

    if not _is_usable(cfg):
        return {"ok": False, "error": "Provider, base URL, model and API key are required."}
    started = time.perf_counter()
    try:
        llm = build_chat_model(replace(cfg), temperature=0.0, max_tokens=8, timeout=20.0)
        reply = llm.invoke([HumanMessage(content="Reply with the single word: OK")])
        return {
            "ok": True,
            "model": cfg.chat_model,
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "sample": clean_text(reply.content)[:40],
        }
    except Exception as exc:
        return {"ok": False, "model": cfg.chat_model, "error": _friendly_error(exc)}


def friendly_error(exc: Exception) -> str:
    """Public wrapper: a short, safe explanation of a provider error."""
    return _friendly_error(exc)


def _friendly_error(exc: Exception) -> str:
    msg = str(exc)
    low = msg.lower()
    if "401" in low or "invalid api key" in low or "unauthorized" in low or "incorrect api key" in low:
        return "The API key was rejected by the provider (401). Check that it was copied fully."
    if "404" in low or "not found" in low or "does not exist" in low:
        return "The provider does not recognise that model id (404). Pick one from the suggestions."
    if "per-day" in low or "per day" in low or "daily" in low:
        return ("Your AI provider's daily free limit is used up (429). It resets tomorrow; "
                "on OpenRouter, $10 of credits raises it to 1000 requests a day.")
    if "429" in low or "rate limit" in low:
        return "Rate-limited by the provider (429). The key works, try again in a minute."
    if "timeout" in low or "timed out" in low:
        return "The provider did not respond in time. Check the base URL or try again."
    if "connection" in low:
        return "Could not reach the provider. Check the base URL."
    # Don't echo arbitrary upstream response bodies back to the client.
    return f"The provider returned an error ({type(exc).__name__}). Check the model id and key."
