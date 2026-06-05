"""
MailMind v2 — Agentic Pipeline Smoke Test
-------------------------------------------
Runs the full LangGraph pipeline locally without a running FastAPI server.
Uses the deterministic fallback paths (no Azure OpenAI credentials needed).

Run:  python test_pipeline.py
"""

import logging
import os
import sys

from app.graph.pipeline import run_pipeline

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(levelname)s │ %(message)s")


# ── Sample emails for testing ─────────────────────────────────────────────────

EMAILS = [
    {
        "email_id": "test-001",
        "sender": "manager@company.com",
        "subject": "URGENT: Review contract before tomorrow deadline",
        "body": (
            "Hi team, please review and approve the vendor contract by tomorrow at 5 PM. "
            "This is critical — the client is waiting. Also, please confirm the meeting on Friday. "
            "Contact me at manager@company.com or +1-555-0100 if you have questions."
        ),
        "received_at": "2026-06-05T08:00:00Z",
        "calendar_events": [
            {
                "title": "Q2 Review Meeting",
                "start_time": "2026-06-06T17:30:00Z",
                "end_time": "2026-06-06T18:30:00Z",
            }
        ],
    },
    {
        "email_id": "test-002",
        "sender": "newsletter@updates.com",
        "subject": "June Newsletter — Team Updates",
        "body": "FYI: Here is the monthly newsletter with team updates. No action required.",
        "received_at": "2026-06-01T10:00:00Z",
        "calendar_events": [],
    },
    {
        "email_id": "test-003",
        "sender": "ceo@company.com",
        "subject": "Action Required: Board deck needs approval by Friday",
        "body": (
            "Please review and sign off on the board presentation by Friday. "
            "The investors are waiting. This is an emergency — if we miss this deadline we lose the deal."
        ),
        "received_at": "2026-06-05T07:00:00Z",
        "calendar_events": [],
    },
]


def print_result(result: dict) -> None:
    """Pretty-print pipeline output."""
    print("\n" + "═" * 70)
    print(f"  EMAIL ID : {result['email_id']}")
    print(f"  PRIORITY : {result.get('priority', 'N/A')} (score: {result.get('composite_score', 0):.1f})")
    print(f"  APPROVAL : {result.get('approval_mode', 'N/A')}")
    print(f"  STEP     : {result.get('current_step', 'N/A')}")
    print()

    axes = result.get("axes", [])
    if axes:
        print("  AXIS SCORES:")
        for axis in axes:
            bar_len = int(axis["raw_score"] * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"    {axis['axis']:12s} [{bar}] {axis['raw_score']:.2f}  — {axis['explanation']}")
    print()

    commitments = result.get("commitments", [])
    if commitments:
        print(f"  COMMITMENTS ({len(commitments)} extracted):")
        for c in commitments:
            flag = "⚠️ CONFLICT" if c.get("conflict_badge") else "✅"
            print(f"    {flag}  {c['commitment'][:70]}")
            if c.get("deadline"):
                print(f"           Deadline: {c['deadline']} | Confidence: {c['confidence']:.0%}")
            if c.get("conflict_detail"):
                print(f"           {c['conflict_detail']}")
    else:
        print("  COMMITMENTS: None extracted")
    print()

    precedents = result.get("precedents", [])
    if precedents:
        print(f"  PRECEDENTS ({len(precedents)} retrieved):")
        for p in precedents:
            print(f"    [{p['similarity_score']:.2f}] {p['subject']}")
    print()

    draft = result.get("draft_reply", "")
    if draft:
        print("  DRAFT REPLY:")
        for line in draft.split("\n"):
            print(f"    {line}")
    print()

    errors = result.get("errors", [])
    if errors:
        print(f"  ERRORS: {errors}")

    reasoning = result.get("triage_reasoning", "")
    if reasoning:
        print(f"  TRIAGE REASONING: {reasoning[:120]}...")

    print("═" * 70)


def main():
    print("\n🧠 MailMind v2 — LangGraph Agentic Pipeline Smoke Test")
    print("   All nodes running with deterministic fallbacks (no Azure creds required)")

    for email in EMAILS:
        print(f"\n▶  Processing: [{email['email_id']}] {email['subject'][:50]}...")
        try:
            result = run_pipeline(
                email_payload=email,
                index_documents=[],  # No RAG index for smoke test
            )
            print_result(result)
        except Exception as e:
            print(f"\n✗  PIPELINE ERROR for {email['email_id']}: {e}")
            import traceback
            traceback.print_exc()

    print("\n✅ Smoke test complete.\n")


if __name__ == "__main__":
    main()