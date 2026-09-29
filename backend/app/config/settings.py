import os

from dotenv import load_dotenv

# Load .env for local dev. In production, inject the same variables through the
# host's secret manager / environment (Railway, Render, Docker, etc.).
load_dotenv()

# Wire LangSmith tracing for LangChain.
# LangChain SDK expects LANGCHAIN_TRACING_V2 and LANGCHAIN_API_KEY.
if os.getenv("LANGSMITH_TRACING", "").lower() in ("1", "true", "yes"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
if os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
if os.getenv("LANGSMITH_PROJECT"):
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGSMITH_PROJECT")
# Region matters: an EU/other-region workspace silently 403s if the SDK posts to
# the default US endpoint. Map a configured endpoint through so it's honoured.
if os.getenv("LANGSMITH_ENDPOINT"):
    os.environ["LANGCHAIN_ENDPOINT"] = os.getenv("LANGSMITH_ENDPOINT")


def _bool_env(name: str, default: bool) -> bool:
    """Parse boolean environment variables consistently."""
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


class Settings:
    """Application configuration loaded from environment variables."""

    # ── Session & token security ───────────────────────────────────────────
    # SESSION_SECRET_KEY: signs the session token before hashing for storage.
    # TOKEN_ENCRYPTION_KEY: Fernet key for encrypting OAuth tokens at rest.
    # Generate both with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "")
    token_encryption_key: str = os.getenv("TOKEN_ENCRYPTION_KEY", "")

    # Session TTLs
    session_ttl_seconds: int = int(os.getenv("SESSION_TTL_SECONDS", str(24 * 60 * 60)))       # 24h
    quick_login_ttl_seconds: int = int(os.getenv("QUICK_LOGIN_TTL_SECONDS", str(7 * 24 * 60 * 60)))  # 7d

    webhook_validation_token: str = os.getenv("WEBHOOK_VALIDATION_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    # Public HTTPS base URL of THIS backend (used for push-notification
    # callbacks). When unset, the mirror stays fresh via on-mount + scheduled
    # delta sync instead.
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    use_chroma: bool = _bool_env("USE_CHROMA", True)
    rag_similarity_threshold: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.78"))
    # Cut-off used with the free local (hashed bag-of-words) embeddings.
    rag_local_similarity_threshold: float = float(os.getenv("RAG_LOCAL_SIMILARITY_THRESHOLD", "0.25"))
    commitment_confidence_threshold: float = float(os.getenv("COMMITMENT_CONFIDENCE_THRESHOLD", "0.80"))
    approval_token: str = os.getenv("APPROVAL_TOKEN", "secret-approval-token")
    # Private-beta access control. ADMIN_TOKEN gates the /api/admin/* endpoints
    # (waitlist approvals + feedback viewing). bootstrap_allowed_emails are always
    # allowed to sign in regardless of waitlist status, so the owner can never be
    # locked out by their own gate.
    admin_token: str = os.getenv("ADMIN_TOKEN", "change-me-admin-token")
    bootstrap_allowed_emails: str = os.getenv(
        "BOOTSTRAP_ALLOWED_EMAILS", ""
    )

    @property
    def bootstrap_allowed_set(self) -> set[str]:
        """Lower-cased set of always-allowed owner emails."""
        return {
            e.strip().lower()
            for e in self.bootstrap_allowed_emails.split(",")
            if e.strip()
        }
    chroma_storage_path: str = os.getenv("CHROMA_DATA_PATH", "./data/chroma")
    index_max_size: int = int(os.getenv("RAG_INDEX_MAX_SIZE", "1000"))
    # Mock mail mode: serve deterministic sample (campus) emails instead of a
    # live Gmail account. USE_MOCK_GRAPH is still honoured for older .env files.
    use_mock_mail: bool = _bool_env("USE_MOCK_MAIL", _bool_env("USE_MOCK_GRAPH", True))

    # Google / Gmail OAuth Configuration
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
    )
    # Gmail push notifications (Cloud Pub/Sub). When gmail_pubsub_topic is unset,
    # Gmail watch is skipped and the mirror stays fresh via on-mount + scheduled
    # delta sync (same graceful degradation as Graph without BACKEND_PUBLIC_URL).
    #   gmail_pubsub_topic — full topic name, e.g. projects/PROJECT/topics/gmail-push
    #   gmail_pubsub_token — shared secret appended as ?token=… to the push
    #                        endpoint URL in the Pub/Sub subscription; verified on
    #                        every notification so only Google can trigger a sync.
    gmail_pubsub_topic: str = os.getenv("GMAIL_PUBSUB_TOPIC", "")
    gmail_pubsub_token: str = os.getenv("GMAIL_PUBSUB_TOKEN", "")

    # ── AI model (server default) ──────────────────────────────────────────
    # Any OpenAI-compatible endpoint. Users can override this with their own
    # key from the AI settings page; this is the fallback for everyone else.
    #   LLM_PROVIDER  openrouter | groq | gemini | openai | ollama | custom
    #   LLM_API_KEY   key for that provider (or set OPENROUTER_API_KEY / GROQ_API_KEY)
    #   LLM_BASE_URL  only needed for "custom" (presets fill it in)
    #   LLM_CHAT_MODEL / LLM_TRIAGE_MODEL  override the preset's default models
    #   LLM_EMBEDDING_MODEL  optional; empty → free local embeddings
    llm_provider: str = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()
    llm_provider_explicit: bool = bool(os.getenv("LLM_PROVIDER", "").strip())
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_chat_model: str = os.getenv("LLM_CHAT_MODEL", "")
    llm_triage_model: str = os.getenv("LLM_TRIAGE_MODEL", "")
    llm_embedding_model: str = os.getenv("LLM_EMBEDDING_MODEL", "")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    # Let users point MailMind at localhost / private-network model servers
    # (Ollama). Off by default: the server makes these calls, so allowing them on
    # a shared deployment would expose internal services (SSRF).
    allow_local_llm_endpoints: bool = _bool_env("ALLOW_LOCAL_LLM_ENDPOINTS", False)
    # Provider-named keys, picked up automatically when LLM_API_KEY is unset.
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # ── Campus context ─────────────────────────────────────────────────────
    # Institution the deployment serves. Domains mark official senders (used by
    # the authority axis); the name is injected into AI prompts.
    campus_name: str = os.getenv("CAMPUS_NAME", "SRM Institute of Science and Technology, Kattankulathur")
    campus_short_name: str = os.getenv("CAMPUS_SHORT_NAME", "SRMIST")
    campus_domains: str = os.getenv("CAMPUS_DOMAINS", "srmist.edu.in,srmuniv.ac.in,srmist.in")

    @property
    def campus_domain_set(self) -> set[str]:
        return {d.strip().lower() for d in self.campus_domains.split(",") if d.strip()}

    # ── Runtime environment ────────────────────────────────────────────────
    app_env: str = os.getenv("APP_ENV", "development")          # development | staging | production
    app_release: str = os.getenv("APP_RELEASE", "mailmind@2.0.0")

    # ── Transport security toggles ─────────────────────────────────────────
    # These default to "on" in production but can be forced off so the app can
    # run behind plain HTTP (e.g. an HTTP-only reverse proxy or port-80 deploy)
    # WITHOUT FastAPI forcing HTTPS.
    #   COOKIE_SECURE=false → auth cookies are sent over HTTP (no Secure flag)
    #   HSTS_ENABLED=false  → never emit Strict-Transport-Security (no forced upgrade)
    cookie_secure: bool = _bool_env("COOKIE_SECURE", os.getenv("APP_ENV", "development").lower() == "production")
    hsts_enabled: bool = _bool_env("HSTS_ENABLED", os.getenv("APP_ENV", "development").lower() == "production")

    # ── Queue backend (Option 2 production architecture) ───────────────────
    # "memory" keeps the dev experience zero-dependency; "redis" enables a
    # durable, multi-worker queue for staging/production.
    queue_backend: str = os.getenv("QUEUE_BACKEND", "memory")   # memory | redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    queue_enrichment_key: str = os.getenv("QUEUE_ENRICHMENT_KEY", "mailmind:queue:enrichment")

    # ── Persistence (Supabase / PostgreSQL) ────────────────────────────────
    # Empty DATABASE_URL → persistence is disabled (results returned inline only).
    database_url: str = os.getenv("DATABASE_URL", "")
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "10"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    # Seconds to wait for a free connection before raising (instead of hanging).
    db_pool_timeout: int = int(os.getenv("DB_POOL_TIMEOUT", "10"))
    # pool_pre_ping issues a liveness "SELECT 1" before handing out each pooled
    # connection. It's a safety net against the pooler dropping idle server
    # connections, but on a remote pooler it adds a full round-trip to every
    # checkout. With the transaction pooler + a short pool_recycle it's
    # unnecessary, so it can be turned off to roughly halve per-request latency.
    db_pool_pre_ping: bool = _bool_env("DB_POOL_PRE_PING", True)
    # Recycle pooled connections older than this many seconds (Supabase/pgbouncer
    # close idle server conns; 30 min keeps us comfortably under that).
    db_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    # ── Triage concurrency ─────────────────────────────────────────────────
    # How many emails to triage in parallel per inbox page. Free-tier keys
    # (OpenRouter/Groq) rate-limit aggressively — lower this if you see 429s.
    triage_max_workers: int = int(os.getenv("TRIAGE_MAX_WORKERS", "8"))

    # ── Worker configuration ───────────────────────────────────────────────
    worker_poll_interval_seconds: float = float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "1.0"))
    worker_max_retries: int = int(os.getenv("WORKER_MAX_RETRIES", "3"))
    worker_retry_base_delay_seconds: int = int(os.getenv("WORKER_RETRY_BASE_DELAY_SECONDS", "30"))

    # ── Observability / metrics ────────────────────────────────────────────
    metrics_enabled: bool = _bool_env("METRICS_ENABLED", True)

    # ── SLA targets (seconds) — used for SLA compliance metrics ────────────
    # Triage is the user-facing critical path; enrichment is the deferred path.
    sla_triage_seconds: float = float(os.getenv("SLA_TRIAGE_SECONDS", "1.5"))
    sla_enrichment_seconds: float = float(os.getenv("SLA_ENRICHMENT_SECONDS", "10.0"))

    # ── Compliance / data governance ───────────────────────────────────────
    data_retention_days: int = int(os.getenv("DATA_RETENTION_DAYS", "90"))
    audit_log_enabled: bool = _bool_env("AUDIT_LOG_ENABLED", True)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def persistence_enabled(self) -> bool:
        return bool(self.database_url)


settings = Settings()

