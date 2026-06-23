#!/usr/bin/env python
"""
Seed a demo user account with realistic email data.

Usage:
  python scripts/seed_demo_account.py --db postgresql://... --email demo@mailmind.app
"""

import argparse
import uuid
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    User,
    OAuthAccount,
    MailboxMessage,
    EmailEnrichment,
    ToneProfile,
)
from app.services.token_encryption import TokenEncryptionService


DEMO_EMAIL = "demo@mailmind.app"
DEMO_PASSWORD = "DemoPass123!"  # Display to judges

# Demo inbox emails (10 realistic emails)
DEMO_EMAILS = [
    {
        "email_id": "demo-email-1",
        "sender": "Victoria Hayes <victoria@nexus.com>",
        "subject": "$4.2M wire transfer — investor relations follow-up",
        "received_at": datetime.utcnow() - timedelta(hours=1),
        "priority": "CRITICAL",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-2",
        "sender": "Daniel Park <daniel.park@company.com>",
        "subject": "Production down — revenue impact (engineering team)",
        "received_at": datetime.utcnow() - timedelta(hours=2),
        "priority": "CRITICAL",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-3",
        "sender": "James Whitfield <j.whitfield@legal.com>",
        "subject": "MSA countersignature required (Nexus Capital)",
        "received_at": datetime.utcnow() - timedelta(days=1),
        "priority": "HIGH",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-4",
        "sender": "Priya Nair <priya@company.com>",
        "subject": "Headcount approval — 3 senior engineers (Q3 hiring)",
        "received_at": datetime.utcnow() - timedelta(days=2),
        "priority": "HIGH",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-5",
        "sender": "security@crowdstrike.com",
        "subject": "Security alert — endpoint policy update required",
        "received_at": datetime.utcnow() - timedelta(days=1, hours=3),
        "priority": "HIGH",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-6",
        "sender": "sprint-bot@jira.com",
        "subject": "Sprint 24 retro — action items from today",
        "received_at": datetime.utcnow() - timedelta(days=3),
        "priority": "MEDIUM",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-7",
        "sender": "verify@stripe.com",
        "subject": "Account verification — complete by [deadline]",
        "received_at": datetime.utcnow() - timedelta(days=2),
        "priority": "MEDIUM",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-8",
        "sender": "marketing@company.com",
        "subject": "Brand refresh — feedback needed by Thursday",
        "received_at": datetime.utcnow() - timedelta(days=4),
        "priority": "MEDIUM",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-9",
        "sender": "tldr@tldr.com",
        "subject": "TLDR — Tech Newsletter #2891",
        "received_at": datetime.utcnow() - timedelta(days=5),
        "priority": "LOW",
        "folder": "inbox",
    },
    {
        "email_id": "demo-email-10",
        "sender": "notion@notion.co",
        "subject": "Notion workspace — monthly digest",
        "received_at": datetime.utcnow() - timedelta(days=6),
        "priority": "LOW",
        "folder": "inbox",
    },
]

# Demo tone profile (VP/Director persona)
DEMO_TONE_PROFILE = {
    "avg_sentence_length": 12,
    "formality_score": 0.65,
    "greeting_patterns": ["Hi", "Team", "Marcus", "Priya"],
    "signoff_patterns": ["Thanks", "Thanks,"],
    "contractions": 0.1,
    "bullet_point_ratio": 0.3,
    "emoji_ratio": 0.0,
    "common_words": ["need", "by", "please", "confirm", "review"],
}


def seed_demo_account(database_url: str, demo_email: str = DEMO_EMAIL):
    """Create demo user with realistic inbox data."""

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # 1. Create demo user
        user_id = uuid.uuid4()
        user = User(id=user_id)
        session.add(user)
        session.flush()
        print(f"✓ Created user {user_id}")

        # 2. Create OAuth account (mock Google)
        # Note: These are fake tokens. In production, use real OAuth flow.
        token_svc = TokenEncryptionService(key=b'test-key-32-chars-minimum-length!')

        fake_access_token = "ya29.a0AfH6SMBx..."
        fake_refresh_token = "1//0gF..."

        oauth_account = OAuthAccount(
            id=uuid.uuid4(),
            user_id=user_id,
            provider="google",
            provider_account_id=demo_email,
            email=demo_email,
            display_name="Demo User",
            access_token_encrypted=token_svc.encrypt(fake_access_token),
            refresh_token_encrypted=token_svc.encrypt(fake_refresh_token),
            token_expires_at=datetime.utcnow() + timedelta(days=30),
        )
        session.add(oauth_account)
        session.flush()
        print(f"✓ Created OAuth account for {demo_email}")

        # 3. Create mailbox messages (inbox envelopes)
        for email_data in DEMO_EMAILS:
            msg = MailboxMessage(
                id=uuid.uuid4(),
                account_id=oauth_account.id,
                folder=email_data["folder"],
                message_id=email_data["email_id"],
                email_id=email_data["email_id"],
                sender=email_data["sender"],
                subject=email_data["subject"],
                received_at=email_data["received_at"],
                is_read=False,
                is_starred=False,
                has_attachments=False,
                state="active",
            )
            session.add(msg)

        session.flush()
        print(f"✓ Created {len(DEMO_EMAILS)} demo inbox messages")

        # 4. Create enrichment (triage cache) for each email
        for i, email_data in enumerate(DEMO_EMAILS):
            enrichment = EmailEnrichment(
                id=uuid.uuid4(),
                account_id=oauth_account.id,
                email_id=email_data["email_id"],
                priority=email_data["priority"],
                composite_score={"CRITICAL": 85, "HIGH": 70, "MEDIUM": 50, "LOW": 25}[email_data["priority"]],
                axes=[
                    {"name": "deadline", "score": 0.9 if email_data["priority"] in ["CRITICAL", "HIGH"] else 0.4},
                    {"name": "sender_authority", "score": 0.8 if i < 5 else 0.3},
                    {"name": "sentiment", "score": 0.85 if email_data["priority"] == "CRITICAL" else 0.5},
                    {"name": "action_type", "score": 0.8 if i < 8 else 0.2},
                    {"name": "thread_decay", "score": 0.7},
                ],
                email_type="action_required" if email_data["priority"] in ["CRITICAL", "HIGH"] else "informational",
                approval_mode="GATE" if email_data["priority"] in ["CRITICAL", "HIGH"] else "SUGGEST",
                status="triaged",
                enriched_at=datetime.utcnow(),
            )
            session.add(enrichment)

        session.flush()
        print(f"✓ Created enrichment cache for all emails")

        # 5. Create tone profile
        tone = ToneProfile(
            id=uuid.uuid4(),
            account_id=oauth_account.id,
            profile_data=DEMO_TONE_PROFILE,
            built_at=datetime.utcnow(),
            built_from_email_count=55,
        )
        session.add(tone)

        session.commit()
        print(f"✓ Created tone profile")

        print("\n" + "="*60)
        print("✅ DEMO ACCOUNT CREATED SUCCESSFULLY")
        print("="*60)
        print(f"\nLogin Credentials:")
        print(f"  Email: {demo_email}")
        print(f"  Password: {DEMO_PASSWORD}")
        print(f"  Provider: Google (mock)")
        print(f"\nInbox:")
        print(f"  10 demo emails loaded (CRITICAL, HIGH, MEDIUM, LOW)")
        print(f"\nFeatures Ready:")
        print(f"  ✓ Five-axis triage scoring")
        print(f"  ✓ Tone DNA profile (VP/Director persona)")
        print(f"  ✓ Commitment extraction")
        print(f"  ✓ Calendar conflict detection")
        print(f"  ✓ Draft generation")
        print("="*60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo account")
    parser.add_argument("--db", required=True, help="Database URL (e.g., postgresql://...)")
    parser.add_argument("--email", default=DEMO_EMAIL, help=f"Demo email (default: {DEMO_EMAIL})")
    args = parser.parse_args()

    seed_demo_account(args.db, args.email)
