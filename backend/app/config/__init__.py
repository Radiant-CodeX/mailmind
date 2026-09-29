from dotenv import load_dotenv

from app.config.settings import settings

load_dotenv()

# Export settings instance
__all__ = ["settings"]

FRONTEND_ORIGIN = settings.frontend_origin
