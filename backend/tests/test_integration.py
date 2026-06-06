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


def test_unknown_route_returns_404(client):
    r = client.get("/api/this-does-not-exist")
    assert r.status_code == 404


def test_validation_error_returns_422(client):
    # Missing required fields for triage.
    r = client.post("/api/triage", json={"sender": "x@y.com"})
    assert r.status_code == 422
