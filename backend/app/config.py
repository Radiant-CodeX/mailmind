import os
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API configuration
    API_TITLE: str = "MailMind API"
    
    # LLM Settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_API_TYPE: str = "openai" # "openai" or "azure"
    OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_ENDPOINT: Optional[str] = None
    AZURE_OPENAI_DEPLOYMENT: Optional[str] = None # e.g. "gpt-4o"
    
    # Microsoft Graph Settings (for future live sync)
    MS_GRAPH_CLIENT_ID: Optional[str] = None
    MS_GRAPH_CLIENT_SECRET: Optional[str] = None
    MS_GRAPH_TENANT_ID: Optional[str] = None

    # Load from environment variables and .env file
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
