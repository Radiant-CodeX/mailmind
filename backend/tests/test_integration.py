"""End-to-end API integration tests (mock mode).

These exercise the real FastAPI app via TestClient — routing, middleware,
serialization, and the service layer — without hitting Azure. They are the
safety net for the full request path that unit tests in test_services.py don't
cover.
"""
import os

# Force mock mode BEFORE the app/settings are imported.
os.environ["USE_MOCK_GRAPH"] = "true"
os.environ["APPROVAL_TOKEN"] = "test-approval-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config.settings import settings  # noqa: E402

settings.use_mock_graph = True
settings.approval_token = "test-approval-token"

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    # Context-manager form runs lifespan (sets up app.state.email_queue).
    with TestClient(app) as c:
        yield c


# ── Health / readiness ────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "mock"


def test_ready(client):
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["ready"] is True


# ── Mail folders stay isolated ────────────────────────────────────────────────

def test_inbox_returns_emails(client):
    r = client.get("/api/emails?limit=10")
    assert r.status_code == 200
    emails = r.json()
    assert isinstance(emails, list)
    assert len(emails) > 0
    assert {"email_id", "sender", "subject", "body"} <= set(emails[0].keys())


@pytest.mark.parametrize("folder", ["sent", "drafts", "spam", "trash"])
def test_other_folders_return_lists(client, folder):
    r = client.get(f"/api/emails/{folder}?limit=10")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_inbox_and_sent_do_not_share_ids(client):
    inbox = client.get("/api/emails?limit=10").json()
    sent = client.get("/api/emails/sent?limit=10").json()
    inbox_ids = {e["email_id"] for e in inbox}
    sent_ids = {e["email_id"] for e in sent}
    # In mock mode sent uses msg-sent-* ids and inbox uses email-* ids.
    assert inbox_ids.isdisjoint(sent_ids)


# ── Triage / classification ───────────────────────────────────────────────────

def test_triage_scoring(client):
    payload = {
        "email_id": "email-1",
        "sender": "ceo@bigcorp.com",
        "subject": "URGENT: sign the contract by today",
        "body": "We need your signature today or the deal falls through.",
        "received_at": "2026-06-06T10:00:00Z",
    }
    r = client.post("/api/triage", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["composite_score"] <= 100
    assert body["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def test_classify(client):
    r = client.post("/api/classify", json={"email_text": "URGENT production outage asap"})
    assert r.status_code == 200
    assert r.json()["priority"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


# ── Draft generation ──────────────────────────────────────────────────────────

def test_draft_generation_styles(client):
    for style in ("standard", "formal", "indepth"):
        r = client.post(
            "/api/rag/draft",
            json={"email_text": "Can you help me with the report?", "style": style},
        )
        assert r.status_code == 200, style
        assert r.json()["draft"].strip()


# ── Commitments ───────────────────────────────────────────────────────────────

def test_commitment_extraction(client):
    r = client.post(
        "/api/commitments/extract",
        json={"masked_email_text": "Please review the deck by Friday and approve the budget."},
    )
    assert r.status_code == 200
    assert "commitments" in r.json()


def test_commitment_confirm_requires_token(client):
    r = client.post(
        "/api/commitments/confirm",
        json={"email_id": "email-1", "commitments": []},
        headers={"X-Approval-Token": "wrong-token"},
    )
    assert r.status_code == 401


# ── Email actions: compose / reply / trash / restore ──────────────────────────

def test_compose_email(client):
    r = client.post(
        "/api/emails/compose",
        json={"to": "a@b.com", "subject": "Hi", "body": "Test body"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_reply_email(client):
    r = client.post("/api/emails/email-1/reply", json={"comment": "Thanks, will do."})
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_trash_and_restore(client):
    t = client.post("/api/emails/email-1/trash")
    assert t.status_code == 200
    assert t.json()["success"] is True

    rs = client.post("/api/emails/email-1/restore")
    assert rs.status_code == 200
    assert rs.json()["success"] is True


# ── Evaluation harness endpoint ───────────────────────────────────────────────

def test_quick_login_mock(client):
    r = client.post("/api/auth/quick-login", json={"email": "radiantcodex@outlook.com"})
    assert r.status_code == 200
    body = r.json()
    assert body["authenticated"] is True
    # In mock mode the status resolves to "mock" and the user is logged in.
    status = client.get("/api/auth/status").json()
    assert status["authenticated"] is True


def test_google_login_and_provider_routing(client):
    # Switching to Google (mock) routes the inbox to the Gmail connector.
    r = client.post("/api/auth/google/login-initiate", json={"email": "demo.user@gmail.com"})
    assert r.status_code == 200
    assert r.json()["authenticated"] is True

    status = client.get("/api/auth/status").json()
    assert status["provider"] == "google"
    assert status["user_principal_name"] == "demo.user@gmail.com"

    inbox = client.get("/api/emails?limit=10").json()
    assert len(inbox) > 0
    assert all(e["email_id"].startswith("gmail-") for e in inbox)

    # Trash + restore work through the Gmail client too.
    assert client.post("/api/emails/gmail-1/trash").json()["success"] is True
    assert client.post("/api/emails/gmail-1/restore").json()["success"] is True

    # Logout resets the provider back to Microsoft (default).
    client.post("/api/auth/logout")
    back = client.get("/api/emails?limit=10").json()
    assert all(e["email_id"].startswith("email-") for e in back)


def test_gmail_client_mock_surface():
    from app.services.gmail import GmailClient
    g = GmailClient()
    assert len(g.get_inbox_emails(5)) > 0
    assert len(g.fetch_sent_emails()) > 0
    # Write operations are no-ops in mock mode (should not raise).
    g.send_new_email("a@b.com", "Hi", "Body")
    g.send_reply("gmail-1", "thanks")
    g.move_to_trash("gmail-1")
    g.restore_from_trash("gmail-1")
    # Calendar/Tasks parity returns shareable links in mock mode.
    assert g.create_todo("gmail-1", "Send the report").startswith("http")
    assert g.create_calendar_event("gmail-1", "Review deck", None).startswith("http")


def test_tasks_and_calendar(client):
    # Microsoft (default) tasks + calendar.
    tasks = client.get("/api/tasks").json()
    assert isinstance(tasks, list) and len(tasks) > 0
    assert {"id", "title", "status", "due"} <= set(tasks[0].keys())

    cal = client.get("/api/calendar?days=3").json()
    assert isinstance(cal, list) and len(cal) > 0
    assert {"title", "start_time", "end_time", "organizer"} <= set(cal[0].keys())

    created = client.post("/api/tasks", json={"title": "Write the report"})
    assert created.status_code == 200 and created.json()["success"] is True
    assert client.post("/api/tasks", json={"title": ""}).status_code == 400


def test_google_calendar_and_tasks_parity(client):
    # Switch to Google and confirm calendar + tasks route to the Gmail client.
    client.post("/api/auth/google/login-initiate", json={"email": "demo.user@gmail.com"})
    cal = client.get("/api/calendar?days=3").json()
    assert any("gmail.com" in e["organizer"] for e in cal)
    tasks = client.get("/api/tasks").json()
    assert any(t["id"].startswith("gtask-") for t in tasks)
    client.post("/api/auth/logout")  # reset provider


def test_teams_endpoints(client):
    teams = client.get("/api/teams").json()
    assert isinstance(teams, list) and len(teams) > 0

    msg = client.post(
        "/api/teams/message",
        json={"team_id": "team-mock-1", "channel_id": "ch-1", "message": "Deploy is green ✅"},
    )
    assert msg.status_code == 200
    assert msg.json()["success"] is True

    meeting = client.post("/api/teams/meeting", json={"subject": "Sprint sync"})
    assert meeting.status_code == 200
    assert meeting.json()["join_url"].startswith("http")

    # Missing identifiers are rejected.
    bad = client.post("/api/teams/message", json={"message": "x"})
    assert bad.status_code == 400


def test_evaluate(client):
    r = client.get("/api/evaluate")
    assert r.status_code == 200
    body = r.json()
    # Either a populated report or a clear "dataset missing" message.
    assert "accuracy" in body or "error" in body


# ── Cross-cutting: security + error handling ──────────────────────────────────

def test_security_headers_present(client):
    r = client.get("/api/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Referrer-Policy" in r.headers


def test_webhook_validation_and_receive(client):
    # Graph subscription validation echoes the token back as plain text.
    v = client.get("/api/webhook?validationToken=ping123")
    assert v.status_code == 200
    assert v.text == "ping123"

    # A notification payload is accepted and enqueued.
    r = client.post("/api/webhook", json={"value": [{"resourceData": {"id": "abc"}}]})
    assert r.status_code == 200


def test_unknown_route_returns_404(client):
    r = client.get("/api/this-does-not-exist")
    assert r.status_code == 404


def test_validation_error_returns_422(client):
    # Missing required fields for triage.
    r = client.post("/api/triage", json={"sender": "x@y.com"})
    assert r.status_code == 422
