"""Live integration verifier for MailMind.

Run this against your REAL Gmail + model configuration to confirm production
wiring before go-live. It does NOT mutate your mailbox (read-only checks + one
tiny chat-completion ping to the server-default model).

Usage (from backend/):
    python scripts/verify_live.py

It reads configuration from your .env (USE_MOCK_MAIL must be false). Each
check prints PASS / FAIL with a reason; the process exits non-zero if any
required check fails, so it can gate a deploy pipeline.
"""
from __future__ import annotations

import sys
from typing import Callable

# Ensure `app` is importable when run as `python scripts/verify_live.py`.
sys.path.insert(0, ".")

from app.config.settings import settings  # noqa: E402

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class Reporter:
    def __init__(self) -> None:
        self.failures = 0
        self.warnings = 0

    def ok(self, name: str, detail: str = "") -> None:
        print(f"{GREEN}PASS{RESET}  {name}" + (f" — {detail}" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self.failures += 1
        print(f"{RED}FAIL{RESET}  {name}" + (f" — {detail}" if detail else ""))

    def warn(self, name: str, detail: str = "") -> None:
        self.warnings += 1
        print(f"{YELLOW}WARN{RESET}  {name}" + (f" — {detail}" if detail else ""))

    def section(self, title: str) -> None:
        print(f"\n=== {title} ===")


def check(rep: Reporter, name: str, fn: Callable[[], str | None], *, required: bool = True) -> None:
    """Run a check fn; it returns a detail string on success or raises on failure."""
    try:
        detail = fn() or ""
        rep.ok(name, detail)
    except Exception as exc:  # noqa: BLE001 - we want to surface any failure cleanly
        (rep.fail if required else rep.warn)(name, str(exc))


def main() -> int:
    rep = Reporter()
    print("MailMind — Live Integration Verifier")

    # ── 1. Configuration ──────────────────────────────────────────────────────
    rep.section("Configuration")
    if settings.use_mock_mail:
        rep.fail("USE_MOCK_MAIL is false", "currently TRUE — set USE_MOCK_MAIL=false in .env to run live checks")
        print("\nAborting: cannot verify live integration while in mock mode.")
        return 1
    rep.ok("USE_MOCK_MAIL is false")

    required_env = {
        "GOOGLE_CLIENT_ID": settings.google_client_id,
        "GOOGLE_CLIENT_SECRET": settings.google_client_secret,
        "TOKEN_ENCRYPTION_KEY": settings.token_encryption_key,
    }
    for key, val in required_env.items():
        check(rep, f"{key} present", lambda v=val: "set" if v else (_ for _ in ()).throw(ValueError("missing")))

    if settings.approval_token == "secret-approval-token":
        rep.fail("APPROVAL_TOKEN is non-default", "still using the default token — set a strong APPROVAL_TOKEN")
    else:
        rep.ok("APPROVAL_TOKEN is non-default")

    # ── 2. Gmail ──────────────────────────────────────────────────────────────
    rep.section("Gmail (process-level session from the last Google sign-in)")
    from app.services.gmail import GmailClient, has_google_session

    if not has_google_session():
        rep.warn("Gmail session", "no cached Google session — sign in once through the app, then re-run")
    else:
        client = GmailClient()
        check(rep, "Read Inbox", lambda: f"{len(client.get_inbox_emails(limit=1))} message(s) readable")
        check(rep, "Read Sent", lambda: f"{len(client.fetch_sent_emails(days=30))} message(s)")
        check(rep, "Read Calendar", lambda: f"{len(client.fetch_calendar())} upcoming event(s)", required=False)
        check(rep, "Read Tasks", lambda: f"{len(client.list_tasks(limit=1))} task(s)", required=False)

    # ── 3. AI model (server default) ──────────────────────────────────────────
    rep.section("AI model (server default)")
    from app.services.llm_provider import server_default_config, test_config

    cfg = server_default_config()
    if cfg is None:
        rep.warn("Server default model", "LLM_API_KEY not set — users must add their own key "
                 "(or triage runs on rule-based scoring)")
    else:
        def _llm() -> str:
            result = test_config(cfg)
            if not result.get("ok"):
                raise RuntimeError(result.get("error"))
            return f"{cfg.provider}:{cfg.chat_model} responded in {result['latency_ms']} ms"

        check(rep, "Chat completion", _llm)

    # ── Summary ───────────────────────────────────────────────────────────────
    rep.section("Summary")
    if rep.failures:
        print(f"{RED}{rep.failures} required check(s) failed{RESET}, {rep.warnings} warning(s).")
        print("Fix the FAIL items above before going live.")
        return 1
    print(f"{GREEN}All required checks passed{RESET}" + (f", {rep.warnings} warning(s)." if rep.warnings else "."))
    print("MailMind is wired for live production traffic.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
