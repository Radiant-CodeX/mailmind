from dotenv import load_dotenv

from app.config.settings import settings

load_dotenv()

# Export settings instance
__all__ = ["settings"]

# Expose constants for backward compatibility with old code
AZURE_OPENAI_API_KEY = settings.azure_openai_api_key
AZURE_OPENAI_ENDPOINT = settings.azure_openai_endpoint
AZURE_OPENAI_DEPLOYMENT_NAME = settings.azure_openai_chat_deployment
AZURE_OPENAI_API_VERSION = settings.azure_openai_api_version

TENANT_ID = settings.azure_tenant_id or "common"
CLIENT_ID = settings.azure_client_id
GRAPH_SCOPE = [s for s in settings.graph_scopes.split()]

FRONTEND_ORIGIN = settings.frontend_origin
