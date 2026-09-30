"""
Tests for the Vision2Web changes: pluggable AI providers (bring-your-own-key),
per-user encrypted settings, and campus-aware triage.

No network: model calls are either absent (deterministic paths) or patched.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ["DATABASE_URL"] = ""

from app.config.settings import settings  # noqa: E402
from app.services import campus, llm_provider  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# Provider layer
# ─────────────────────────────────────────────────────────────────────────────


def test_build_config_fills_preset_defaults():
    cfg = llm_provider.build_config(provider="groq", api_key="gsk_test")
    assert cfg.base_url == "https://api.groq.com/openai/v1"
    assert cfg.chat_model and cfg.triage_model
    assert cfg.model_for("triage") == cfg.triage_model


def test_server_default_picks_up_provider_named_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "llm_provider_explicit", False)
    monkeypatch.setattr(settings, "openrouter_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", "gsk_from_env")
    monkeypatch.setattr(settings, "openai_api_key", "")
    cfg = llm_provider.server_default_config()
    assert cfg is not None and cfg.provider == "groq" and cfg.api_key == "gsk_from_env"


def test_server_default_none_without_any_key(monkeypatch):
    for attr in ("llm_api_key", "openrouter_api_key", "groq_api_key", "openai_api_key"):
        monkeypatch.setattr(settings, attr, "")
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    assert llm_provider.server_default_config() is None


def test_mask_key_never_reveals_full_key():
    hint = llm_provider.mask_key("sk-or-v1-abcdefghijklmnop1234")
    assert hint.endswith("1234") and "abcdefghijklmnop" not in hint


@pytest.mark.parametrize("reply", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    '<think>let me reason</think>{"a": 1}',
    'Sure! Here is the JSON: {"a": 1} Hope that helps.',
])
def test_parse_json_tolerates_free_model_noise(reply):
    assert llm_provider.parse_json(reply) == {"a": 1}


def test_parse_json_raises_without_json():
    with pytest.raises(ValueError):
        llm_provider.parse_json("no json here")


def test_local_embeddings_rank_related_text_higher():
    from app.services.rag import cosine_similarity

    a = llm_provider.local_embed("Register for the placement drive before the deadline")
    b = llm_provider.local_embed("Reminder: placement drive registration deadline is today")
    c = llm_provider.local_embed("Hostel mess menu for the weekend")
    assert cosine_similarity(a, b) > cosine_similarity(a, c)
    assert cosine_similarity(a, b) >= settings.rag_local_similarity_threshold


def test_no_model_means_deterministic_triage():
    from app.agents.nodes import ingest_node, triage_node

    state = {
        "email_id": "t1", "sender": "placement@srmist.edu.in",
        "subject": "Campus drive — registration closes today 5 PM",
        "body": "Eligible students must register on the placement portal before 5 PM today. "
                "Late registrations will not be entertained.",
        "received_at": "2026-09-30T04:00:00Z", "errors": [],
    }
    with patch("app.services.llm_provider.resolve_config", return_value=None):
        state.update(ingest_node(state))
        result = triage_node(state)
    assert result["email_type"] == "placement"
    assert result["priority"] in {"CRITICAL", "HIGH"}


def test_triage_uses_model_output_when_configured():
    from app.agents.nodes import ingest_node, triage_node

    fake_reply = SimpleNamespace(content=(
        '<think>hmm</think>{"email_type":"Exams","axes":['
        '{"axis":"deadline","score":0.9,"explanation":"d"},'
        '{"axis":"authority","score":1.0,"explanation":"a"},'
        '{"axis":"sentiment","score":0.8,"explanation":"s"},'
        '{"axis":"thread_risk","score":0.9,"explanation":"t"},'
        '{"axis":"action","score":0.9,"explanation":"x"}],'
        '"overall_reasoning":"Hall ticket window closes soon."}'
    ))

    class FakeLLM:
        def invoke(self, messages, config=None):
            prompt = messages[0].content
            assert "university inbox" in prompt and "placement" in prompt
            return fake_reply

    state = {"email_id": "t2", "sender": "coe@srmist.edu.in", "subject": "Hall tickets",
             "body": "Download your hall ticket.", "received_at": "2026-09-30T04:00:00Z", "errors": []}
    state.update(ingest_node(state))
    with patch("app.agents.nodes._get_llm", return_value=FakeLLM()):
        result = triage_node(state)
    assert result["email_type"] == "exams"          # normalised from "Exams"
    assert result["priority"] == "CRITICAL"
    assert result["triage_reasoning"] == "Hall ticket window closes soon."


# ─────────────────────────────────────────────────────────────────────────────
# Campus knowledge
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("sender,expected_min", [
    ("coe@srmist.edu.in", 0.95),
    ("hod.cse@srmist.edu.in", 0.9),
    ("placement@srmist.edu.in", 0.9),
    ("ab1234@srmist.edu.in", 0.3),
])
def test_campus_authority(sender, expected_min):
    assert campus.score_authority(sender)["raw_score"] >= expected_min


def test_titles_from_personal_addresses_are_not_trusted():
    assert campus.score_authority("Dean Smith <dean@gmail.com>")["raw_score"] <= 0.25


def test_keywords_match_whole_words_only():
    # 'hod' must not match 'method'; 'fee' must not match 'feedback'.
    assert campus.categorize("x@gmail.com", "The method", "Your feedback on the coffee") != "fees"
    assert campus.score_authority("x@srmist.edu.in", "New method")["raw_score"] < 0.9


@pytest.mark.parametrize("subject,body,expected", [
    ("Hall ticket download", "End semester exam hall tickets are available", "exams"),
    ("Zoho drive", "Register for the placement drive, shortlist next week", "placement"),
    ("Semester fee", "Last date to pay the tuition fee without late fee", "fees"),
    ("50% off", "Limited time discount. Unsubscribe", "promotions"),
])
def test_categorize(subject, body, expected):
    assert campus.categorize("someone@example.com", subject, body) == expected


def test_normalise_category_aliases():
    assert campus.normalise_category("Placements") == "placement"
    assert campus.normalise_category("exam") == "exams"
    assert campus.normalise_category("something weird") == "other"


def test_indian_date_format_parsed_day_first():
    from app.tools.email_tools import score_deadline_axis

    result = score_deadline_axis.invoke({
        "body": "Submit the form on or before 03/10/2026.", "subject": "",
        "received_at": "2026-09-30T04:00:00Z",
    })
    assert "03 Oct" in result["explanation"]


def test_noreply_campus_mail_keeps_action_score():
    from app.agents.nodes import _dampen_automated_action

    axes = [{"axis": "action", "raw_score": 0.9, "explanation": ""}]
    kept = _dampen_automated_action(axes, "noreply@srmist.edu.in",
                                    "Register on the portal. Do not reply.", "Course registration")
    assert kept[0]["raw_score"] == 0.9
    damped = _dampen_automated_action([{"axis": "action", "raw_score": 0.9, "explanation": ""}],
                                      "noreply@shop.com", "Big sale! unsubscribe", "Sale")
    assert damped[0]["raw_score"] < 0.2


def test_draft_etiquette_student_to_faculty():
    text = campus.draft_etiquette({"role": "student"}, "coe@srmist.edu.in")
    assert "Dear" in text and "slang" in text


# ─────────────────────────────────────────────────────────────────────────────
# Per-user settings (encrypted BYOK) against a throwaway SQLite database
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet

    from app.db import base
    from app.db.models import User
    from app.services import token_encryption

    monkeypatch.setattr(settings, "database_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(token_encryption, "_fernet", None)
    base.reset_engine()
    base.init_db()
    with base.get_session() as s:
        s.add(User(id="u1", email="student@srmist.edu.in", primary_email="student@srmist.edu.in"))
        s.commit()
    yield "u1"
    base.reset_engine()
    token_encryption._fernet = None
    llm_provider.invalidate_user_config("u1")


def test_user_key_is_encrypted_and_used(sqlite_db):
    from app.db.base import get_session
    from app.db.models import UserPreferences
    from app.services import user_settings

    cfg = user_settings.validate_ai_input({"provider": "groq", "api_key": "gsk_secret_value_123"})
    user_settings.save_ai_settings(sqlite_db, cfg)

    with get_session() as s:
        row = s.get(UserPreferences, sqlite_db)
        assert row.ai_api_key_enc and "gsk_secret_value_123" not in row.ai_api_key_enc

    view = user_settings.get_ai_settings_view(sqlite_db)
    assert view["own"]["provider"] == "groq"
    assert "gsk_secret_value_123" not in str(view)

    with llm_provider.use_ai_user(sqlite_db):
        resolved = llm_provider.resolve_config()
    assert resolved.source == "user" and resolved.api_key == "gsk_secret_value_123"

    user_settings.clear_ai_settings(sqlite_db)
    assert user_settings.get_ai_settings_view(sqlite_db)["own"] is None


def test_update_without_key_keeps_saved_key(sqlite_db):
    from app.services import user_settings

    user_settings.save_ai_settings(
        sqlite_db, user_settings.validate_ai_input({"provider": "groq", "api_key": "gsk_keep_me"}))
    cfg = user_settings.validate_ai_input(
        {"provider": "groq", "chat_model": "llama-3.1-8b-instant"},
        existing_key=user_settings.existing_api_key(sqlite_db))
    assert cfg.api_key == "gsk_keep_me" and cfg.chat_model == "llama-3.1-8b-instant"


def test_saving_key_requires_encryption_key(sqlite_db, monkeypatch):
    from app.services import token_encryption, user_settings

    monkeypatch.setattr(settings, "token_encryption_key", "")
    monkeypatch.setattr(token_encryption, "_fernet", None)
    cfg = user_settings.validate_ai_input({"provider": "groq", "api_key": "gsk_x"})
    with pytest.raises(user_settings.SettingsError):
        user_settings.save_ai_settings(sqlite_db, cfg)


def test_campus_profile_roundtrip(sqlite_db):
    from app.services import user_settings

    saved = user_settings.save_campus_profile(sqlite_db, {"role": "faculty", "department": "CSE",
                                                          "year_of_study": 3})
    assert saved == {"role": "faculty", "department": "CSE", "year_of_study": None}
    assert user_settings.load_campus_profile(sqlite_db)["role"] == "faculty"
    with pytest.raises(user_settings.SettingsError):
        user_settings.save_campus_profile(sqlite_db, {"role": "principal"})


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/v1",
    "http://localhost:11434/v1",
    "https://169.254.169.254/latest",
    "https://10.0.0.5/v1",
    "ftp://example.com",
])
def test_internal_endpoints_blocked(url, monkeypatch):
    from app.services import user_settings

    monkeypatch.setattr(settings, "allow_local_llm_endpoints", False)
    with pytest.raises(user_settings.SettingsError):
        user_settings.validate_base_url(url)


def test_local_endpoints_allowed_when_opted_in(monkeypatch):
    from app.services import user_settings

    monkeypatch.setattr(settings, "allow_local_llm_endpoints", True)
    user_settings.validate_base_url("http://localhost:11434/v1")  # no raise


def test_unknown_provider_rejected():
    from app.services import user_settings

    with pytest.raises(user_settings.SettingsError):
        user_settings.validate_ai_input({"provider": "azure", "api_key": "x"})


# ─────────────────────────────────────────────────────────────────────────────
# Settings API
# ─────────────────────────────────────────────────────────────────────────────


def test_settings_api_flow(sqlite_db):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=sqlite_db)
    try:
        with TestClient(app) as c:
            providers = c.get("/api/settings/ai/providers").json()["providers"]
            assert {"openrouter", "groq", "gemini"} <= {p["id"] for p in providers}

            with patch("app.services.llm_provider.test_config",
                       return_value={"ok": False, "error": "The API key was rejected by the provider (401)."}):
                bad = c.put("/api/settings/ai", json={"provider": "groq", "api_key": "gsk_bad"})
            assert bad.status_code == 400 and "rejected" in bad.json()["detail"]

            with patch("app.services.llm_provider.test_config",
                       return_value={"ok": True, "model": "m", "latency_ms": 10}):
                ok = c.put("/api/settings/ai", json={"provider": "groq", "api_key": "gsk_good_key_9999"})
            assert ok.status_code == 200
            body = ok.json()
            assert body["own"]["api_key_hint"].endswith("9999")
            assert "gsk_good_key_9999" not in ok.text

            assert c.get("/api/settings/ai").json()["effective"]["source"] == "user"
            assert c.delete("/api/settings/ai").json()["own"] is None

            prof = c.put("/api/settings/profile", json={"role": "student", "year_of_study": 3})
            assert prof.status_code == 200 and prof.json()["year_of_study"] == 3

            cats = c.get("/api/campus/categories").json()["categories"]
            assert cats[0]["id"] == "placement"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_routine_notifications_rank_low():
    from app.services import campus

    assert campus.notification_kind(
        "UPI/IMPS/MB Transaction Alert",
        "An amount of INR 500.00 has been DEBITED on 30/09/26 from your account XXX284.",
    ) == "transaction"
    assert campus.notification_kind("Your OTP", "Your one-time password is 482913.") == "otp"
    # Real warnings are never treated as routine.
    assert campus.notification_kind("Suspicious transaction", "Your card has been blocked.") is None
    # Campus mail is untouched.
    assert campus.notification_kind("Nimbus drive", "Register before 5 PM today.") is None
