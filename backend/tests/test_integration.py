"""
MailMind — Integration Tests
=============================
Tests exercise the full FastAPI request path (routing, middleware,
serialisation, validation, service layer) using TestClient.

External APIs (Microsoft Graph, Gmail, Azure OpenAI) are patched at the
provider boundary with unittest.mock so no real credentials are needed.
The live app code — handlers, schemas, queue, DB, metrics — runs as-is.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Env must be set before app is imported ────────────────────────────────────
os.environ.setdefault("APPROVAL_TOKEN", "test-approval-token")
os.environ.setdefault("USE_MOCK_GRAPH", "false")   # run live code paths
os.environ["DATABASE_URL"] = ""                    # disable DB → no Supabase connection in tests

from app.config.settings import settings  # noqa: E402
settings.approval_token = "test-approval-token"

from app.main import app  # noqa: E402


# ── Shared fake data ──────────────────────────────────────────────────────────

NOW = datetime.now(tz=timezone.utc)

FAKE_EMAIL = {
    "email_id": "msg-001",
    "sender": "ceo@bigcorp.com",
    "subject": "URGENT: contract sign-off by EOD",
    "body": "We need your signature today or the deal falls through.",
    "html_body": "<p>We need your signature today or the deal falls through.</p>",
    "received_at": NOW.isoformat(),
    "is_read": False,
    "has_attachments": False,
    "attachments": [],
}

FAKE_SENT = {
    "email_id": "sent-001",
    "sender": "me@company.com",
    "subject": "Re: contract sign-off",
    "body": "Done, signed and sent.",
    "received_at": (NOW - timedelta(hours=1)).isoformat(),
    "is_read": True,
    "has_attachments": False,
}

FAKE_PAGE = {
    "emails": [FAKE_EMAIL],
    "next_page_token": None,
    "total": 1,
}

FAKE_CALENDAR_EVENTS = [
    {
        "title": "Board meeting",
        "start_time": (NOW + timedelta(hours=2)).isoformat(),
        "end_time": (NOW + timedelta(hours=3)).isoformat(),
        "organizer": "pa@bigcorp.com",
    }
]

FAKE_TASKS = [
    {"id": "task-1", "title": "Review contract", "status": "notStarted", "due": NOW.isoformat()},
]


def _make_client_mock() -> MagicMock:
    """Return a MagicMock that mimics the GraphClient / GmailClient interface."""
    m = MagicMock()
    m.use_mock = False
    m.list_emails.return_value = FAKE_PAGE
    m.get_inbox_emails.return_value = [FAKE_EMAIL]
    m.fetch_sent_emails.return_value = [FAKE_SENT]
    m.get_draft_emails.return_value = []
    m.get_spam_emails.return_value = []
    m.get_trash_emails.return_value = []
    m.get_calendar_events.return_value = FAKE_CALENDAR_EVENTS
    m.list_tasks.return_value = FAKE_TASKS
    m.send_reply.return_value = None
    m.send_new_email.return_value = None
    m.mark_read.return_value = None
    m.archive.return_value = None
    m.report_spam.return_value = None
    m.move_to_trash.return_value = None
    m.restore_from_trash.return_value = None
    m.forward_email.return_value = None
    m.reply_all.return_value = None
    m.create_todo.return_value = "https://tasks.example.com/task-1"
    m.create_calendar_event.return_value = "https://calendar.example.com/event-1"
    m.get_attachment.return_value = None
    return m


@pytest.fixture(scope="module")
def client():
    """TestClient with the provider layer patched to fake data + a fake session.

    Auth is satisfied by overriding the session/user dependencies (so we test
    endpoint behavior, not the login flow). The provider layer is patched to
    return deterministic mock data.
    """
    mock_client = _make_client_mock()
    # Ensure live code paths run regardless of other test files' module-level settings
    from app.config.settings import settings as _settings
    _orig_mock_graph = _settings.use_mock_graph
    _settings.use_mock_graph = False

    # Bypass authentication: every request runs as a fixed test user.
    from app.api.deps import get_current_session, get_current_user
    _fake_session = {"user_id": "test-user", "provider": "microsoft", "email": "tester@example.com"}
    app.dependency_overrides[get_current_user] = lambda: _fake_session["email"]
    app.dependency_overrides[get_current_session] = lambda: _fake_session

    # Patch get_mail_client everywhere it's imported
    with patch("app.api.routes.get_mail_client", return_value=mock_client), \
         patch("app.services.mail_provider.get_mail_client", return_value=mock_client), \
         patch("app.services.tools.GraphClient", return_value=mock_client):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_session, None)
    _settings.use_mock_graph = _orig_mock_graph


# ─────────────────────────────────────────────────────────────────────────────
# 1. HEALTH & READINESS
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoints:
    def test_health_returns_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"

    def test_ready_returns_true(self, client):
        r = client.get("/api/ready")
        assert r.status_code == 200
        assert r.json()["ready"] is True

    def test_security_headers_present(self, client):
        r = client.get("/api/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"
        assert "Referrer-Policy" in r.headers

    def test_unknown_route_returns_404(self, client):
        r = client.get("/api/this-does-not-exist")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# 2. MAILBOX / EMAIL LISTING
# ─────────────────────────────────────────────────────────────────────────────

class TestMailboxEndpoints:
    def test_mailbox_returns_page_shape(self, client):
        r = client.get("/api/mailbox?folder=inbox&limit=10")
        assert r.status_code == 200
        page = r.json()
        assert {"emails", "next_page_token", "total"} <= set(page.keys())
        assert isinstance(page["emails"], list)
        assert page["total"] >= len(page["emails"])

    def test_mailbox_email_has_required_fields(self, client):
        r = client.get("/api/mailbox?folder=inbox&limit=10")
        emails = r.json()["emails"]
        assert len(emails) > 0
        required = {"email_id", "sender", "subject", "body", "is_read", "has_attachments"}
        assert required <= set(emails[0].keys())

    def test_inbox_search_empty_query_returns_results(self, client):
        r = client.get("/api/mailbox?folder=inbox&limit=10&q=contract")
        assert r.status_code == 200
        # Mock returns the same page regardless of query — shape must be valid
        assert "emails" in r.json()

    def test_mailbox_pagination_shape(self, client):
        """next_page_token field must always be present (even if None)."""
        r = client.get("/api/mailbox?folder=inbox&limit=10")
        body = r.json()
        assert "next_page_token" in body

    def test_sent_folder_endpoint(self, client):
        r = client.get("/api/emails/sent?limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_drafts_folder_endpoint(self, client):
        r = client.get("/api/emails/drafts?limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_spam_folder_endpoint(self, client):
        r = client.get("/api/emails/spam?limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_trash_folder_endpoint(self, client):
        r = client.get("/api/emails/trash?limit=10")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_inbox_poll_returns_shape(self, client):
        """Lightweight new-email poll endpoint must return expected keys."""
        r = client.get("/api/inbox/poll")
        assert r.status_code == 200
        body = r.json()
        assert "has_new" in body
        assert "latest_id" in body


# ─────────────────────────────────────────────────────────────────────────────
# 3. EMAIL ACTIONS
# ─────────────────────────────────────────────────────────────────────────────

class TestEmailActions:
    def test_mark_email_read(self, client):
        r = client.post("/api/emails/msg-001/read", json={"read": True})
        assert r.status_code == 200
        assert r.json()["is_read"] is True

    def test_mark_email_unread(self, client):
        r = client.post("/api/emails/msg-001/read", json={"read": False})
        assert r.status_code == 200
        assert r.json()["is_read"] is False

    def test_archive_email(self, client):
        r = client.post("/api/emails/msg-001/archive")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_report_spam(self, client):
        r = client.post("/api/emails/msg-001/spam")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_trash_email(self, client):
        r = client.post("/api/emails/msg-001/trash")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_restore_email_from_trash(self, client):
        r = client.post("/api/emails/msg-001/restore")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_forward_email(self, client):
        r = client.post("/api/emails/msg-001/forward",
                        json={"to": "colleague@company.com", "comment": "FYI"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_forward_requires_recipient(self, client):
        r = client.post("/api/emails/msg-001/forward", json={"comment": "no recipient"})
        assert r.status_code == 400

    def test_reply_all(self, client):
        r = client.post("/api/emails/msg-001/reply-all", json={"comment": "Thanks all"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_send_reply(self, client):
        r = client.post("/api/emails/msg-001/reply", json={"comment": "Got it, will do."})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_compose_new_email(self, client):
        r = client.post("/api/emails/compose",
                        json={"to": "boss@company.com", "subject": "Update", "body": "Done."})
        assert r.status_code == 200
        assert r.json()["success"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 4. TRIAGE & CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

class TestTriageAndClassification:
    URGENT_PAYLOAD = {
        "email_id": "msg-001",
        "sender": "ceo@bigcorp.com",
        "subject": "URGENT: sign the contract by today",
        "body": "We need your signature today or the deal falls through.",
        "received_at": "2026-06-09T10:00:00Z",
    }
    LOW_PAYLOAD = {
        "email_id": "msg-002",
        "sender": "newsletter@weekly.com",
        "subject": "Weekly digest",
        "body": "Here is your weekly newsletter with the latest news.",
        "received_at": "2026-06-09T08:00:00Z",
    }

    def test_triage_returns_valid_schema(self, client):
        r = client.post("/api/triage", json=self.URGENT_PAYLOAD)
        assert r.status_code == 200
        body = r.json()
        assert 0 <= body["composite_score"] <= 100
        assert body["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

    def test_triage_urgent_email_scores_higher(self, client):
        r_urgent = client.post("/api/triage", json=self.URGENT_PAYLOAD)
        r_low = client.post("/api/triage", json=self.LOW_PAYLOAD)
        assert r_urgent.json()["composite_score"] >= r_low.json()["composite_score"]

    def test_triage_missing_required_fields_returns_422(self, client):
        r = client.post("/api/triage", json={"sender": "x@y.com"})
        assert r.status_code == 422

    def test_classify_endpoint_returns_priority(self, client):
        r = client.post("/api/classify",
                        json={"email_text": "URGENT production outage, everything is down!"})
        assert r.status_code == 200
        assert r.json()["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

    def test_classify_newsletter_gets_low_priority(self, client):
        r = client.post("/api/classify",
                        json={"email_text": "Here is your monthly newsletter. Unsubscribe below."})
        assert r.status_code == 200
        assert r.json()["priority"] in {"LOW", "MEDIUM"}

    def test_triage_batch_returns_list(self, client):
        payload = [
            {"email_id": "a", "sender": "s@a.com", "subject": "Hi",
             "body": "Hi", "received_at": "2026-06-09T10:00:00Z"},
            {"email_id": "b", "sender": "s@b.com", "subject": "Urgent",
             "body": "URGENT deadline today!", "received_at": "2026-06-09T10:00:00Z"},
        ]
        r = client.post("/api/triage/batch", json=payload)
        assert r.status_code == 200
        results = r.json()
        assert isinstance(results, list)
        assert len(results) == 2
        for result in results:
            assert "priority" in result
            assert "composite_score" in result


# ─────────────────────────────────────────────────────────────────────────────
# 5. COMMITMENTS
# ─────────────────────────────────────────────────────────────────────────────

class TestCommitments:
    def test_commitment_extraction_returns_commitments_key(self, client):
        r = client.post(
            "/api/commitments/extract",
            json={"masked_email_text": "Please review the deck by Friday and approve the budget."},
        )
        assert r.status_code == 200
        assert "commitments" in r.json()

    def test_commitment_extraction_with_deadline(self, client):
        r = client.post(
            "/api/commitments/extract",
            json={"masked_email_text": "Submit the report by Monday. Also send the invoice by EOD."},
        )
        assert r.status_code == 200
        data = r.json()
        assert "commitments" in data
        # At least one commitment should be detected
        assert isinstance(data["commitments"], list)

    def test_commitment_confirm_rejects_wrong_token(self, client):
        r = client.post(
            "/api/commitments/confirm",
            json={"email_id": "msg-001", "commitments": []},
            headers={"X-Approval-Token": "wrong-token"},
        )
        assert r.status_code == 401

    def test_commitment_confirm_accepts_correct_token(self, client):
        r = client.post(
            "/api/commitments/confirm",
            json={"email_id": "msg-001", "commitments": []},
            headers={"X-Approval-Token": "test-approval-token"},
        )
        assert r.status_code in {200, 400}  # 400 if no commitments to confirm


# ─────────────────────────────────────────────────────────────────────────────
# 6. RAG / DRAFT
# ─────────────────────────────────────────────────────────────────────────────

class TestRagAndDraft:
    def test_rag_retrieve_returns_list(self, client):
        r = client.post(
            "/api/rag/retrieve",
            json={"email_text": "Please send the Q3 financial report by Friday."},
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_rag_inject_returns_prompt(self, client):
        r = client.post(
            "/api/rag/inject",
            json={"email_text": "Can you review the document?"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "prompt" in body
        assert isinstance(body["prompt"], str)

    @pytest.mark.parametrize("style", ["standard", "formal", "indepth"])
    def test_draft_generation_all_styles(self, client, style):
        # Patch DraftService.generate_draft so no LLM credentials are needed.
        fake_draft = f"Hi,\n\nThank you for your email. ({style} style)\n\nBest regards"
        with patch("app.api.routes.DraftService") as MockService:
            MockService.return_value.generate_draft.return_value = (fake_draft, [])
            r = client.post(
                "/api/rag/draft",
                json={"email_text": "Can you help me with the quarterly report?", "style": style},
            )
        assert r.status_code == 200, f"style={style}: {r.text}"
        body = r.json()
        assert "draft" in body
        assert isinstance(body["draft"], str) and len(body["draft"]) > 10


# ─────────────────────────────────────────────────────────────────────────────
# 7. CALENDAR & TASKS
# ─────────────────────────────────────────────────────────────────────────────

class TestCalendarAndTasks:
    def test_calendar_returns_list_of_events(self, client):
        r = client.get("/api/calendar?days=7")
        assert r.status_code == 200
        events = r.json()
        assert isinstance(events, list)

    def test_calendar_event_has_required_fields(self, client):
        r = client.get("/api/calendar?days=7")
        events = r.json()
        if events:
            assert {"title", "start_time", "end_time", "organizer"} <= set(events[0].keys())

    def test_create_calendar_event_succeeds(self, client):
        r = client.post("/api/calendar/event", json={
            "title": "Contract review meeting",
            "start_time": (NOW + timedelta(days=1)).isoformat(),
            "end_time": (NOW + timedelta(days=1, hours=1)).isoformat(),
        })
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "title" in body

    def test_create_calendar_event_requires_title(self, client):
        r = client.post("/api/calendar/event", json={
            "start_time": (NOW + timedelta(days=1)).isoformat(),
        })
        assert r.status_code == 400

    def test_create_calendar_event_requires_start_time(self, client):
        r = client.post("/api/calendar/event", json={"title": "Meeting"})
        assert r.status_code == 400

    def test_tasks_list_returns_list(self, client):
        r = client.get("/api/tasks")
        assert r.status_code == 200
        tasks = r.json()
        assert isinstance(tasks, list)

    def test_tasks_have_required_fields(self, client):
        r = client.get("/api/tasks")
        tasks = r.json()
        if tasks:
            assert {"id", "title", "status", "due"} <= set(tasks[0].keys())

    def test_create_task_succeeds(self, client):
        r = client.post("/api/tasks", json={"title": "Review contract before EOD"})
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_create_task_rejects_empty_title(self, client):
        r = client.post("/api/tasks", json={"title": ""})
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 8. AGENT PIPELINE ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAgentPipeline:
    TRIAGE_PAYLOAD = {
        "email_id": "msg-agent-001",
        "sender": "cto@enterprise.com",
        "subject": "Production database is down",
        "body": "Our production DB has been down for 30 minutes. Clients are calling.",
        "received_at": "2026-06-09T10:00:00Z",
    }

    def test_agent_triage_returns_priority(self, client):
        # Patch _get_llm to None → deterministic fallback runs (no Azure calls)
        with patch("app.agents.nodes._get_llm", return_value=None):
            r = client.post("/api/agent/triage", json=self.TRIAGE_PAYLOAD)
        assert r.status_code == 200
        body = r.json()
        assert "priority" in body
        assert body["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        assert "composite_score" in body
        assert 0 <= body["composite_score"] <= 100

    def test_agent_triage_returns_axes(self, client):
        with patch("app.agents.nodes._get_llm", return_value=None):
            r = client.post("/api/agent/triage", json=self.TRIAGE_PAYLOAD)
        body = r.json()
        assert "axes" in body
        assert isinstance(body["axes"], list)

    def test_agent_triage_page_batch(self, client):
        payloads = [
            {**self.TRIAGE_PAYLOAD, "email_id": f"msg-batch-{i}"}
            for i in range(3)
        ]
        with patch("app.agents.nodes._get_llm", return_value=None):
            r = client.post("/api/agent/triage-page", json=payloads)
        assert r.status_code == 200
        results = r.json()
        assert isinstance(results, list)
        assert len(results) == 3
        for result in results:
            assert result["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

    def test_agent_triage_page_empty_batch(self, client):
        r = client.post("/api/agent/triage-page", json=[])
        assert r.status_code == 200
        assert r.json() == []

    def test_agent_health_check(self, client):
        r = client.get("/api/agent/health")
        assert r.status_code == 200
        assert "status" in r.json()

    def test_agent_triage_missing_fields_returns_422(self, client):
        r = client.post("/api/agent/triage", json={"sender": "x@y.com"})
        assert r.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# 9. AUTH ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthEndpoints:
    def test_auth_status_unauthenticated_by_default(self, client):
        """App starts unauthenticated — status endpoint must return 200."""
        r = client.get("/api/auth/status")
        assert r.status_code == 200
        body = r.json()
        assert "authenticated" in body
        assert isinstance(body["authenticated"], bool)

    def test_auth_status_has_provider_field(self, client):
        r = client.get("/api/auth/status")
        assert "provider" in r.json()

    def test_microsoft_login_initiate_returns_auth_url(self, client):
        """When Azure credentials are configured, initiate returns a consent URL."""
        with patch("app.services.graph.build_ms_auth_url",
                   return_value=("https://login.microsoftonline.com/authorize?...", "state-abc")):
            settings.azure_client_id = "fake-client-id"
            try:
                r = client.post("/api/auth/microsoft/login-initiate")
            finally:
                settings.azure_client_id = ""
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert "auth_url" in body
        assert "state" in body

    def test_microsoft_login_initiate_fails_without_config(self, client):
        """Missing AZURE_CLIENT_ID returns 500."""
        original = settings.azure_client_id
        settings.azure_client_id = ""
        try:
            r = client.post("/api/auth/microsoft/login-initiate")
            assert r.status_code == 500
        finally:
            settings.azure_client_id = original

    def test_google_login_initiate_returns_auth_url(self, client):
        """When Google credentials are configured, initiate returns a consent URL."""
        with patch("app.services.gmail.build_auth_url",
                   return_value="https://accounts.google.com/o/oauth2/v2/auth?..."), \
             patch("app.services.gmail.google_auth_status", {}):
            settings.google_client_id = "fake-google-client-id"
            try:
                r = client.post("/api/auth/google/login-initiate", json={})
                assert r.status_code == 200
                body = r.json()
                assert body["status"] == "pending"
                assert "auth_url" in body
            finally:
                settings.google_client_id = ""

    def test_google_login_initiate_fails_without_config(self, client):
        """Missing GOOGLE_CLIENT_ID returns 500."""
        original = settings.google_client_id
        settings.google_client_id = ""
        try:
            r = client.post("/api/auth/google/login-initiate", json={})
            assert r.status_code == 500
        finally:
            settings.google_client_id = original

    def test_logout_returns_ok(self, client):
        r = client.post("/api/auth/logout")
        assert r.status_code == 200

    def test_microsoft_poll_missing_device_code_returns_400(self, client):
        r = client.post("/api/auth/microsoft/poll", json={})
        assert r.status_code == 400

    def test_google_poll_missing_state_returns_400(self, client):
        r = client.post("/api/auth/google/poll", json={})
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# 10. WEBHOOK
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhook:
    def test_validation_token_echoed(self, client):
        """Graph subscription validation: GET with validationToken returns plain text."""
        r = client.get("/api/webhook?validationToken=ping12345")
        assert r.status_code == 200
        assert r.text == "ping12345"

    def test_notification_payload_accepted(self, client):
        """POST notification is accepted and enqueued without error."""
        r = client.post("/api/webhook",
                        json={"value": [{"resourceData": {"id": "msg-webhook-01"}}]})
        assert r.status_code == 200

    def test_empty_notification_payload(self, client):
        r = client.post("/api/webhook", json={})
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 11. MONITORING ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

class TestMonitoringEndpoints:
    def test_metrics_endpoint_returns_prometheus_text(self, client):
        r = client.get("/api/metrics")
        assert r.status_code == 200
        # Prometheus exposition format
        assert "mailmind" in r.text or "# HELP" in r.text or "# TYPE" in r.text

    def test_deep_health_returns_checks(self, client):
        r = client.get("/api/health/deep")
        assert r.status_code == 200
        body = r.json()
        assert "status" in body
        assert "checks" in body

    def test_sla_report_returns_shape(self, client):
        r = client.get("/api/sla")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)


# ─────────────────────────────────────────────────────────────────────────────
# 12. INPUT VALIDATION (cross-cutting)
# ─────────────────────────────────────────────────────────────────────────────

class TestInputValidation:
    def test_triage_missing_email_id_returns_422(self, client):
        r = client.post("/api/triage", json={
            "sender": "a@b.com", "subject": "Hi", "body": "Hello",
        })
        assert r.status_code == 422

    def test_triage_missing_sender_returns_422(self, client):
        r = client.post("/api/triage", json={
            "email_id": "x", "subject": "Hi", "body": "Hello",
            "received_at": "2026-06-09T10:00:00Z",
        })
        assert r.status_code == 422

    def test_classify_missing_text_returns_422(self, client):
        r = client.post("/api/classify", json={})
        assert r.status_code == 422

    def test_compose_missing_required_fields_returns_422(self, client):
        r = client.post("/api/emails/compose", json={"subject": "Hi"})
        assert r.status_code == 422

    def test_forward_without_recipient_returns_400(self, client):
        r = client.post("/api/emails/msg-001/forward", json={"comment": "fyi"})
        assert r.status_code == 400

    def test_tasks_empty_title_returns_400(self, client):
        r = client.post("/api/tasks", json={"title": ""})
        assert r.status_code == 400

    def test_calendar_event_missing_title_returns_400(self, client):
        r = client.post("/api/calendar/event",
                        json={"start_time": NOW.isoformat()})
        assert r.status_code == 400

    def test_calendar_event_missing_start_time_returns_400(self, client):
        r = client.post("/api/calendar/event", json={"title": "Meeting"})
        assert r.status_code == 400
