import os
from urllib.parse import urlparse

from dotenv import load_dotenv

from app.config.keyvault import load_keyvault_into_env

# Load .env for local dev, then let Key Vault (if configured) take precedence.
load_dotenv()
load_keyvault_into_env()

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
    # Public HTTPS base URL of THIS backend, used as the Graph webhook
    # notificationUrl. When unset, webhook subscriptions are skipped and the
    # mirror stays fresh via on-mount + scheduled delta sync instead.
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    use_chroma: bool = _bool_env("USE_CHROMA", True)
    rag_similarity_threshold: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.78"))
    commitment_confidence_threshold: float = float(os.getenv("COMMITMENT_CONFIDENCE_THRESHOLD", "0.80"))
    approval_token: str = os.getenv("APPROVAL_TOKEN", "secret-approval-token")
    # Private-beta access control. ADMIN_TOKEN gates the /api/admin/* endpoints
    # (waitlist approvals + feedback viewing). bootstrap_allowed_emails are always
    # allowed to sign in regardless of waitlist status, so the owner can never be
    # locked out by their own gate.
    admin_token: str = os.getenv("ADMIN_TOKEN", "change-me-admin-token")
    bootstrap_allowed_emails: str = os.getenv(
        "BOOTSTRAP_ALLOWED_EMAILS", "radiantcodex@outlook.com"
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
    # Azure / Graph configuration
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")
    azure_client_secret: str = os.getenv("AZURE_CLIENT_SECRET", "")
    azure_user_upn: str = os.getenv("AZURE_USER_UPN", "")
    # Azure only permits https or http://localhost redirect URIs (not 127.0.0.1).
    azure_redirect_uri: str = os.getenv(
        "AZURE_REDIRECT_URI", "https://api.radiantsofficial.com/api/auth/microsoft/callback"
    )
    # Space-separated scopes used when acquiring Graph tokens
    graph_scopes: str = os.getenv("GRAPH_SCOPES", "Mail.ReadWrite Mail.Send Calendars.ReadWrite Tasks.ReadWrite")
    # Allow switching between the mock Graph client and a real Azure integration
    use_mock_graph: bool = _bool_env("USE_MOCK_GRAPH", True)

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

    # OpenAI / Azure OpenAI Configuration
    # Store the raw env value; use azure_openai_base_endpoint for SDK calls.
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    azure_openai_chat_deployment: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    # Triage uses gpt-4o-mini by default (faster, cheaper); heavier nodes (commitments, RAG) use gpt-4o
    azure_openai_triage_deployment: str = os.getenv("AZURE_OPENAI_TRIAGE_DEPLOYMENT", "gpt-4o-mini")
    azure_openai_embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    # Groq is the fallback LLM when Azure OpenAI is not configured.
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")

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
    # How many emails to triage in parallel per inbox page. gpt-4o-mini has
    # generous TPM headroom, so a higher fan-out drains a cold inbox faster;
    # lower it if Azure starts returning 429s.
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

    @property
    def azure_openai_base_endpoint(self) -> str:
        """Return only scheme+host from the endpoint, stripping any deployment path or query params.

        The Azure OpenAI SDK requires a base URL like
          https://<resource>.openai.azure.com/
        but users sometimes paste the full chat-completions path instead.
        """
        url = self.azure_openai_endpoint
        if not url:
            return ""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return url  # not parseable, return as-is
        return f"{parsed.scheme}://{parsed.netloc}/"


settings = Settings()

