import os


def _bool_env(name: str, default: bool) -> bool:
    """Parse boolean environment variables consistently."""
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes")


class Settings:
    """Application configuration loaded from environment variables."""

    webhook_validation_token: str = os.getenv("WEBHOOK_VALIDATION_TOKEN", "")
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
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
    # Space-separated scopes used when acquiring Graph tokens
    graph_scopes: str = os.getenv("GRAPH_SCOPES", "Mail.ReadWrite Mail.Send Calendars.ReadWrite Tasks.ReadWrite")
    # Allow switching between the mock Graph client and a real Azure integration
    use_mock_graph: bool = _bool_env("USE_MOCK_GRAPH", True)

    # OpenAI / Azure OpenAI Configuration
    azure_openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_chat_deployment: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    azure_openai_embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")


settings = Settings()

