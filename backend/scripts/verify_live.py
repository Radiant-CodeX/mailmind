"""Live integration verifier for MailMind.

Run this against your REAL Azure tenant to confirm production wiring before
go-live. It does NOT mutate your mailbox (read-only checks + an optional
draft-only OpenAI ping).

Usage (from backend/):
    python scripts/verify_live.py

It reads configuration from your .env (USE_MOCK_GRAPH must be false). Each
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
    if settings.use_mock_graph:
        rep.fail("USE_MOCK_GRAPH is false", "currently TRUE — set USE_MOCK_GRAPH=false in .env to run live checks")
        print("\nAborting: cannot verify live integration while in mock mode.")
        return 1
    rep.ok("USE_MOCK_GRAPH is false")

    required_env = {
        "AZURE_TENANT_ID": settings.azure_tenant_id,
        "AZURE_CLIENT_ID": settings.azure_client_id,
        "AZURE_CLIENT_SECRET": settings.azure_client_secret,
    }
    for key, val in required_env.items():
        check(rep, f"{key} present", lambda v=val: "set" if v else (_ for _ in ()).throw(ValueError("missing")))

    if settings.approval_token == "secret-approval-token":
        rep.fail("APPROVAL_TOKEN is non-default", "still using the default token — set a strong APPROVAL_TOKEN")
    else:
        rep.ok("APPROVAL_TOKEN is non-default")

    # ── 2. Microsoft Graph ────────────────────────────────────────────────────
    rep.section("Microsoft Graph")
    from app.services.graph import GraphClient

    client = GraphClient()

    def _token() -> str:
        tok = client._get_token()
        if not tok:
            raise RuntimeError("no token returned")
        return f"acquired ({len(tok)} chars)"

    check(rep, "Acquire Graph token", _token)

    def _inbox() -> str:
        msgs = client.get_inbox_emails(limit=1)
        return f"{len(msgs)} message(s) readable"

    check(rep, "Read Inbox", _inbox)
    check(rep, "Read Sent Items", lambda: f"{len(client.fetch_sent_emails(days=30))} message(s)")
    check(rep, "Read Drafts", lambda: f"{len(client.get_draft_emails(limit=1))} message(s)", required=False)
    check(rep, "Read Junk/Spam", lambda: f"{len(client.get_spam_emails(limit=1))} message(s)", required=False)
    check(rep, "Read Deleted Items", lambda: f"{len(client.get_trash_emails(limit=1))} message(s)", required=False)

    # ── 3. Azure OpenAI ───────────────────────────────────────────────────────
    rep.section("Azure OpenAI")

    def _openai() -> str:
        if not settings.azure_openai_api_key or not settings.azure_openai_base_endpoint:
            raise RuntimeError("Azure OpenAI not configured (key/endpoint missing)")
        from openai import AzureOpenAI

        oai = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_base_endpoint,
        )
        resp = oai.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=5,
            temperature=0,
        )
        return f"deployment '{settings.azure_openai_chat_deployment}' responded: {resp.choices[0].message.content!r}"

    check(rep, "Azure OpenAI chat completion", _openai)

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
