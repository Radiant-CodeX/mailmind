#!/usr/bin/env python3
"""
Comprehensive schema audit: compare Supabase tables to v3 ORM models.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, future=True)

# Expected columns per v3 model
EXPECTED_SCHEMA = {
    "users": {
        "id": "VARCHAR(36)",
        "primary_email": "VARCHAR(320)",
        "display_name": "VARCHAR(255)",
        "created_at": "TIMESTAMP",
        "last_login_at": "TIMESTAMP",
    },
    "oauth_accounts": {
        "id": "VARCHAR(36)",
        "user_id": "VARCHAR(36)",
        "provider": "VARCHAR(32)",
        "provider_account_id": "VARCHAR(255)",
        "account_email": "VARCHAR(320)",
        "access_token_enc": "TEXT",  # v2 uses _enc suffix
        "refresh_token_enc": "TEXT",  # v2 uses _enc suffix
        "token_expires_at": "TIMESTAMP",
        "nickname": "VARCHAR(64)",
        "color": "VARCHAR(7)",
        "is_default": "BOOLEAN",
        "sync_enabled": "BOOLEAN",
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    },
    "user_sessions": {
        # Note: token_hash is the PK in v2 Supabase (no separate id column)
        "token_hash": "VARCHAR(64)",
        "user_id": "VARCHAR(36)",
        "expires_at": "TIMESTAMP",
        "created_at": "TIMESTAMP",
        "last_seen_at": "TIMESTAMP",
    },
    "devices": {
        "id": "VARCHAR(36)",
        "user_id": "VARCHAR(36)",
        "fingerprint": "VARCHAR(64)",
        "user_agent": "VARCHAR(1024)",
        "accept_language": "VARCHAR(256)",
        "last_used": "TIMESTAMP",
        "created_at": "TIMESTAMP",
    },
    "quick_login_tokens": {
        "id": "VARCHAR(36)",
        "user_id": "VARCHAR(36)",
        "device_id": "VARCHAR(36)",
        "token_hash": "VARCHAR(64)",
        "expires_at": "TIMESTAMP",
        "status": "VARCHAR(20)",
        "created_at": "TIMESTAMP",
    },
    "tone_profile": {
        "account_id": "VARCHAR(36)",
        "profile": "JSON",
        "sample_size": "INTEGER",
        "created_at": "TIMESTAMP",
        "updated_at": "TIMESTAMP",
    },
    "audit_log": {
        "id": "INTEGER",
        "email_id": "VARCHAR(512)",
        "account_id": "VARCHAR(36)",
        "action": "VARCHAR(40)",
        "actor": "VARCHAR(64)",
        "details": "JSON",
        "created_at": "TIMESTAMP",
    },
    "processing_metric": {
        "id": "INTEGER",
        "email_id": "VARCHAR(512)",
        "account_id": "VARCHAR(36)",
        "stage": "VARCHAR(40)",
        "latency_ms": "INTEGER",
        "created_at": "TIMESTAMP",
    },
}

print("=" * 100)
print("COMPREHENSIVE SCHEMA AUDIT: SUPABASE vs v3 ORM")
print("=" * 100)

inspector = inspect(engine)
actual_tables = {t: inspector.get_columns(t) for t in inspector.get_table_names()}

all_good = True

for table_name, expected_cols in EXPECTED_SCHEMA.items():
    print(f"\n[{table_name}]")

    if table_name not in actual_tables:
        print(f"  ERROR: Table does not exist!")
        all_good = False
        continue

    actual_cols = {col["name"]: col["type"] for col in actual_tables[table_name]}

    # Check for missing columns
    missing = set(expected_cols.keys()) - set(actual_cols.keys())
    if missing:
        print(f"  MISSING COLUMNS: {', '.join(missing)}")
        all_good = False
    else:
        print(f"  OK: All {len(expected_cols)} expected columns present")

    # Check for extra columns
    extra = set(actual_cols.keys()) - set(expected_cols.keys())
    if extra:
        print(f"  EXTRA COLUMNS: {', '.join(extra)} (v2 legacy, will be ignored)")

    # Show column breakdown
    for col in sorted(expected_cols.keys()):
        if col in actual_cols:
            print(f"    [OK] {col:30} {str(actual_cols[col]):30}")
        else:
            print(f"    [MISSING] {col:30}")
            all_good = False

print("\n" + "=" * 100)
if all_good:
    print("STATUS: ALL TABLES OK - Ready for v3 deployment")
else:
    print("STATUS: SCHEMA MISMATCH - See errors above")
print("=" * 100)
