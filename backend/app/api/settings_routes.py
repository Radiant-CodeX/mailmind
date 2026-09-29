"""
User settings API — bring-your-own AI key + campus profile.
===========================================================

  GET    /api/settings/ai/providers   Supported providers, default + suggested models
  GET    /api/settings/ai             Current AI settings (key masked) + effective model
  PUT    /api/settings/ai             Save provider/key/models (tested before saving)
  POST   /api/settings/ai/test        Test a provider/key/model without saving
  DELETE /api/settings/ai             Remove own key → fall back to the server default
  GET    /api/settings/profile        Campus profile (role, department, year)
  PUT    /api/settings/profile        Update campus profile
  GET    /api/campus/categories       Campus email categories (for filters / labels)

The raw API key is write-only: it is accepted on PUT/test, stored encrypted, and
never returned — responses only carry a masked hint such as "sk-or-…a1b2".
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services import campus, llm_provider, user_settings
from app.services.user_settings import SettingsError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["settings"])


class AISettingsRequest(BaseModel):
    provider: str = Field(..., description="openrouter | groq | gemini | openai | ollama | custom")
    api_key: str | None = Field(None, description="Omit to keep the currently saved key")
    base_url: str | None = None
    chat_model: str | None = None
    triage_model: str | None = None
    embedding_model: str | None = None
    # Verify the key with one tiny call before saving (recommended).
    test: bool = True


class CampusProfileRequest(BaseModel):
    role: str = "student"
    department: str | None = None
    year_of_study: int | None = None


def _user_id(current_user: Any) -> str:
    return getattr(current_user, "id", None) or str(current_user)


def _config_from(req: AISettingsRequest, user_id: str) -> llm_provider.AIConfig:
    try:
        return user_settings.validate_ai_input(
            req.model_dump(exclude={"test"}),
            existing_key=user_settings.existing_api_key(user_id),
        )
    except SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── AI settings ───────────────────────────────────────────────────────────────


@router.get("/settings/ai/providers")
def list_providers() -> dict[str, Any]:
    """Providers MailMind can use. No keys involved — safe to show anyone."""
    return {"providers": llm_provider.provider_catalog()}


@router.get("/settings/ai")
def get_ai_settings(current_user=Depends(get_current_user)) -> dict[str, Any]:
    return user_settings.get_ai_settings_view(_user_id(current_user))


@router.post("/settings/ai/test")
def test_ai_settings(req: AISettingsRequest, current_user=Depends(get_current_user)) -> dict[str, Any]:
    """Make one real call with the given settings. Nothing is saved."""
    cfg = _config_from(req, _user_id(current_user))
    return llm_provider.test_config(cfg)


@router.put("/settings/ai")
def save_ai_settings(req: AISettingsRequest, current_user=Depends(get_current_user)) -> dict[str, Any]:
    user_id = _user_id(current_user)
    cfg = _config_from(req, user_id)
    test_result = None
    if req.test:
        test_result = llm_provider.test_config(cfg)
        if not test_result.get("ok"):
            raise HTTPException(status_code=400, detail=test_result.get("error") or "Connection test failed")
    try:
        user_settings.save_ai_settings(user_id, cfg)
    except SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"saved": True, "test": test_result, **user_settings.get_ai_settings_view(user_id)}


@router.delete("/settings/ai")
def delete_ai_settings(current_user=Depends(get_current_user)) -> dict[str, Any]:
    user_id = _user_id(current_user)
    user_settings.clear_ai_settings(user_id)
    return {"cleared": True, **user_settings.get_ai_settings_view(user_id)}


# ── Campus profile ────────────────────────────────────────────────────────────


@router.get("/settings/profile")
def get_profile(current_user=Depends(get_current_user)) -> dict[str, Any]:
    return user_settings.load_campus_profile(_user_id(current_user))


@router.put("/settings/profile")
def save_profile(req: CampusProfileRequest, current_user=Depends(get_current_user)) -> dict[str, Any]:
    try:
        return user_settings.save_campus_profile(_user_id(current_user), req.model_dump())
    except SettingsError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campus/categories")
def list_categories() -> dict[str, Any]:
    """Campus email categories, in display order."""
    return {
        "campus": {"name": campus.settings.campus_name, "short_name": campus.settings.campus_short_name},
        "categories": [
            {"id": c.id, "label": c.label, "description": c.description,
             "high_stakes": c.id in campus.HIGH_STAKES_CATEGORIES}
            for c in campus.CATEGORIES
        ] + [{"id": "other", "label": "Other", "description": "Everything else", "high_stakes": False}],
    }
