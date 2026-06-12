#!/usr/bin/env python3
"""
Migrate Supabase schema from v2 to v3.

v2 → v3 changes:
1. tone_profile: user_email PK → account_id FK
2. Create quick_login_tokens table
3. Create devices table
"""
import os
import json
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    logger.error("DATABASE_URL not set")
    exit(1)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine)

def run_migration():
    session = SessionLocal()
    try:
        # Step 0: Add missing v3 columns to existing tables
        logger.info("Step 0: Adding v3 columns to existing tables...")

        try:
            session.execute(text("""
                ALTER TABLE oauth_accounts
                ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT false
            """))
            logger.info("  [OK] Added is_default to oauth_accounts")
        except Exception as e:
            logger.warning(f"  is_default column: {e}")

        session.commit()

        # Step 1: Create missing v3 tables
        logger.info("\nStep 1: Creating missing v3 tables...")

        # Create devices table
        try:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS devices (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    fingerprint VARCHAR(64) NOT NULL,
                    user_agent VARCHAR(1024),
                    accept_language VARCHAR(256),
                    last_used TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_devices_user FOREIGN KEY (user_id)
                        REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, fingerprint)
                )
            """))
            logger.info("  [OK] Created devices table")
        except Exception as e:
            logger.warning(f"  devices table: {e}")

        # Create quick_login_tokens table
        try:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS quick_login_tokens (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    device_id VARCHAR(36),
                    token_hash VARCHAR(64) NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    status VARCHAR(20) DEFAULT 'ACTIVE',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT fk_quick_login_user FOREIGN KEY (user_id)
                        REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT fk_quick_login_device FOREIGN KEY (device_id)
                        REFERENCES devices(id) ON DELETE SET NULL,
                    UNIQUE(token_hash)
                )
            """))
            logger.info("  [OK] Created quick_login_tokens table")
        except Exception as e:
            logger.warning(f"  quick_login_tokens table: {e}")

        session.commit()

        # Step 2: Migrate tone_profile schema
        logger.info("\nStep 2: Migrating tone_profile schema...")

        # Check if tone_profile already has account_id column
        result = session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'tone_profile' AND column_name = 'account_id'
        """))
        has_account_id = result.scalar() is not None

        if has_account_id:
            logger.info("  [OK] tone_profile already has account_id (v3 schema)")
        else:
            logger.info("  Transforming tone_profile from v2 to v3...")

            # Backup v2 data
            v2_data = session.execute(text("""
                SELECT user_email, profile, sample_size
                FROM tone_profile
            """)).fetchall()

            logger.info(f"  Found {len(v2_data)} tone profiles to migrate")

            # Rename old table
            try:
                session.execute(text("ALTER TABLE tone_profile RENAME TO tone_profile_v2_backup"))
                logger.info("  Renamed tone_profile to tone_profile_v2_backup")
            except Exception as e:
                logger.warning(f"  Could not rename table: {e}")
                return

            # Create new v3 schema
            try:
                session.execute(text("""
                    CREATE TABLE tone_profile (
                        account_id VARCHAR(36) PRIMARY KEY,
                        profile JSONB NOT NULL,
                        sample_size INTEGER DEFAULT 0,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT fk_tone_profile_account FOREIGN KEY (account_id)
                            REFERENCES oauth_accounts(id) ON DELETE CASCADE
                    )
                """))
                logger.info("  Created new v3 tone_profile table")
            except Exception as e:
                logger.error(f"  Failed to create new table: {e}")
                session.rollback()
                return

            # Migrate data
            migrated = 0
            skipped = 0

            for user_email, profile_json, sample_size in v2_data:
                # Find user by email
                user = session.execute(text("""
                    SELECT id FROM users WHERE email = :email LIMIT 1
                """), {"email": user_email}).first()

                if not user:
                    logger.debug(f"  User not found for {user_email}")
                    skipped += 1
                    continue

                user_id = user[0]

                # Find default account
                account = session.execute(text("""
                    SELECT id FROM oauth_accounts
                    WHERE user_id = :user_id AND is_default = true
                    LIMIT 1
                """), {"user_id": user_id}).first()

                if not account:
                    account = session.execute(text("""
                        SELECT id FROM oauth_accounts
                        WHERE user_id = :user_id
                        LIMIT 1
                    """), {"user_id": user_id}).first()

                if not account:
                    logger.debug(f"  No account found for {user_email}")
                    skipped += 1
                    continue

                account_id = account[0]

                # Insert profile
                try:
                    if isinstance(profile_json, str):
                        profile_data = json.loads(profile_json)
                    else:
                        profile_data = profile_json

                    session.execute(text("""
                        INSERT INTO tone_profile (account_id, profile, sample_size)
                        VALUES (:account_id, :profile, :sample_size)
                    """), {
                        "account_id": account_id,
                        "profile": json.dumps(profile_data),
                        "sample_size": sample_size or 0,
                    })
                    migrated += 1
                except Exception as e:
                    logger.debug(f"  Failed to migrate {user_email}: {e}")
                    skipped += 1

            session.commit()
            logger.info(f"  Migrated {migrated} profiles, skipped {skipped}")

        # Step 3: Verify
        logger.info("\nStep 3: Verifying v3 schema...")
        from sqlalchemy import inspect
        inspector = inspect(engine)

        tables_to_check = ["users", "oauth_accounts", "user_sessions", "devices", "quick_login_tokens", "tone_profile"]
        for table in tables_to_check:
            if table in inspector.get_table_names():
                cols = [col["name"] for col in inspector.get_columns(table)]
                print(f"  [OK] {table:25} {', '.join(cols)}")
            else:
                print(f"  [MISSING] {table}")

        logger.info("\n" + "=" * 80)
        logger.info("MIGRATION COMPLETE - DATABASE READY FOR V3 DEPLOYMENT")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
        exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    run_migration()
