#!/usr/bin/env python3
"""
Migrate tone_profile data from v2 (user_email PK) to v3 (account_id FK).

This script is only needed if you have an existing Supabase v2 database with
tone profiles. It maps each user_email to the user's default OAuthAccount and
migrates the profile data.

Usage:
    python migrate_tone_profile_v2_to_v3.py
"""

import logging
import sys
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.base import get_session, init_db, is_persistence_enabled
from app.db.models import OAuthAccount, User

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def migrate_tone_profiles() -> None:
    """Migrate tone_profile data from v2 (user_email) to v3 (account_id)."""
    if not is_persistence_enabled():
        logger.error("Database not configured. Set DATABASE_URL first.")
        sys.exit(1)

    with get_session() as session:
        if session is None:
            logger.error("Failed to connect to database.")
            sys.exit(1)

        logger.info("Starting tone_profile v2→v3 migration...")

        try:
            # 1. Check if tone_profile_v2 exists
            result = session.execute(
                text("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'tone_profile_v2')")
            )
            has_v2 = result.scalar()

            if not has_v2:
                logger.info("No tone_profile_v2 table found. Migration not needed.")
                return

            # 2. Fetch all v2 tone profiles
            v2_profiles = session.execute(
                text("SELECT user_email, profile, sample_size FROM tone_profile_v2")
            ).fetchall()

            logger.info(f"Found {len(v2_profiles)} tone profiles in v2 format.")

            migrated = 0
            skipped = 0

            for user_email, profile, sample_size in v2_profiles:
                # 3. Resolve user_email to account_id
                user = session.query(User).filter_by(primary_email=user_email).first()
                if not user:
                    logger.warning(f"User not found for email {user_email} — skipping.")
                    skipped += 1
                    continue

                # 4. Find the user's default account (or first if none marked default)
                account = session.query(OAuthAccount).filter_by(
                    user_id=user.id, is_default=True
                ).first()
                if not account:
                    account = session.query(OAuthAccount).filter_by(user_id=user.id).first()

                if not account:
                    logger.warning(f"No OAuth account found for user {user_email} — skipping.")
                    skipped += 1
                    continue

                # 5. Insert or update v3 tone_profile
                try:
                    session.execute(
                        text("""
                            INSERT INTO tone_profile (account_id, profile, sample_size)
                            VALUES (:account_id, :profile, :sample_size)
                            ON CONFLICT (account_id) DO UPDATE
                            SET profile = :profile, sample_size = :sample_size
                        """),
                        {
                            "account_id": account.id,
                            "profile": profile,
                            "sample_size": sample_size or 0,
                        },
                    )
                    migrated += 1
                    logger.info(f"Migrated profile for {user_email} → account {account.id}")
                except Exception as e:
                    logger.error(f"Failed to migrate {user_email}: {e}")
                    skipped += 1

            session.commit()

            logger.info(f"Migration complete: {migrated} migrated, {skipped} skipped.")

            # 6. Optional: drop v2 table after confirmation
            response = input(
                "\nDrop tone_profile_v2 table? (yes/no): "
            ).strip().lower()
            if response == "yes":
                try:
                    session.execute(text("DROP TABLE tone_profile_v2"))
                    session.commit()
                    logger.info("tone_profile_v2 dropped.")
                except Exception as e:
                    logger.error(f"Failed to drop tone_profile_v2: {e}")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    init_db(create_tables=False)  # Connect to DB, don't auto-create tables
    migrate_tone_profiles()
