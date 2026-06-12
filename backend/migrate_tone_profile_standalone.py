#!/usr/bin/env python3
"""
Standalone tone_profile v2→v3 migration (no app dependencies).

Requires: sqlalchemy, python-dotenv
Install:  pip install sqlalchemy python-dotenv
"""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()

import os
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    logger.error("DATABASE_URL not found in .env")
    sys.exit(1)

logger.info(f"Connecting to database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine)

def migrate():
    """Migrate tone_profile data from v2 (user_email) to v3 (account_id)."""
    session = SessionLocal()
    try:
        # 1. Check if tone_profile_v2 exists
        result = session.execute(
            text("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'tone_profile_v2')")
        )
        has_v2 = result.scalar()

        if not has_v2:
            logger.info("No tone_profile_v2 table found. Nothing to migrate.")
            return

        # 2. Fetch v2 profiles
        v2_profiles = session.execute(
            text("SELECT user_email, profile, sample_size FROM tone_profile_v2")
        ).fetchall()

        if not v2_profiles:
            logger.info("No profiles found in tone_profile_v2.")
            return

        logger.info(f"Found {len(v2_profiles)} tone profiles to migrate.")

        migrated = 0
        skipped = 0

        for user_email, profile_json, sample_size in v2_profiles:
            logger.debug(f"Processing {user_email}...")

            # 3. Find user by primary_email
            user = session.execute(
                text("SELECT id FROM users WHERE primary_email = :email"),
                {"email": user_email}
            ).first()

            if not user:
                logger.warning(f"User not found for {user_email} — skipping.")
                skipped += 1
                continue

            user_id = user[0]

            # 4. Find user's default account (or first)
            account = session.execute(
                text("SELECT id FROM oauth_accounts WHERE user_id = :user_id AND is_default = true LIMIT 1"),
                {"user_id": user_id}
            ).first()

            if not account:
                account = session.execute(
                    text("SELECT id FROM oauth_accounts WHERE user_id = :user_id LIMIT 1"),
                    {"user_id": user_id}
                ).first()

            if not account:
                logger.warning(f"No OAuth account found for user {user_email} — skipping.")
                skipped += 1
                continue

            account_id = account[0]

            # 5. Insert or update v3 tone_profile
            try:
                # Convert profile to JSON if it's a string
                if isinstance(profile_json, str):
                    profile_data = json.loads(profile_json)
                else:
                    profile_data = profile_json

                session.execute(
                    text("""
                        INSERT INTO tone_profile (account_id, profile, sample_size)
                        VALUES (:account_id, :profile, :sample_size)
                        ON CONFLICT (account_id) DO UPDATE
                        SET profile = :profile, sample_size = :sample_size
                    """),
                    {
                        "account_id": account_id,
                        "profile": json.dumps(profile_data),
                        "sample_size": sample_size or 0,
                    },
                )
                migrated += 1
                logger.info(f"✓ Migrated {user_email} → account {account_id}")
            except Exception as e:
                logger.error(f"Failed to migrate {user_email}: {e}")
                skipped += 1

        session.commit()
        logger.info(f"\n✅ Migration complete: {migrated} migrated, {skipped} skipped.")

        # 6. Ask about dropping v2 table
        response = input("\nDrop tone_profile_v2 table? (yes/no): ").strip().lower()
        if response == "yes":
            try:
                session.execute(text("DROP TABLE tone_profile_v2"))
                session.commit()
                logger.info("✓ tone_profile_v2 dropped.")
            except Exception as e:
                logger.error(f"Failed to drop tone_profile_v2: {e}")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
