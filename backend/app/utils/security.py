from fastapi import HTTPException, status
from fastapi.security import APIKeyHeader

from app.config.settings import settings

# API key header declaration for approval flows.
approval_key = APIKeyHeader(name="X-Approval-Token", auto_error=False)


def validate_approval_token(token: str | None) -> None:
    """Validate that the approval token matches the configured secret."""
    if token != settings.approval_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid approval token")
