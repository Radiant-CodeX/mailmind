import os
from urllib.parse import urlparse

from dotenv import load_dotenv

from app.config.keyvault import load_keyvault_into_env

# Load .env for local dev, then let Key Vault (if configured) take precedence.
load_dotenv()
load_keyvault_into_env()


def _bool_env(name: str, default: bool) -> bool:
    """Parse boolean environment variables consistently."""
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


class Settings:
    """Application configuration loaded from environment variables."""

    webhook_validation_token: str = os.getenv("WEBHOOK_VALIDATION_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    use_chroma: bool = _bool_env("USE_CHROMA", True)
    rag_similarity_threshold: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.78"))
    commitment_confidence_threshold: float = float(os.getenv("COMMITMENT_CONFIDENCE_THRESHOLD", "0.80"))
    approval_token: str = os.getenv("APPROVAL_TOKEN", "secret-approval-token")
    chroma_storage_path: str = os.getenv("CHROMA_DATA_PATH", "./data/chroma")
    index_max_size: int = int(os.getenv("RAG_INDEX_MAX_SIZE", "1000"))
    # Azure / Graph configuration
    azure_tenant_id: str = os.getenv("AZURE_TENANT_ID", "")
    azure_client_id: str = os.getenv("AZURE_CLIENT_ID", "")
    azure_client_secret: str = os.getenv("AZURE_CLIENT_SECRET", "")
    azure_user_upn: str = os.getenv("AZURE_USER_UPN", "")
    # Azure only permits https or http://localhost redirect URIs (not 127.0.0.1).
    azure_redirect_uri: str = os.getenv(
        "AZURE_REDIRECT_URI", "http://localhost:8000/api/auth/microsoft/callback"
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

    # OpenAI / Azure OpenAI Configuration
    # Store the raw env value; use azure_openai_base_endpoint for SDK calls.
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    azure_openai_chat_deployment: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    azure_openai_embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

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

