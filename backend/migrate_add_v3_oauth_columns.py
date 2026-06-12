#!/usr/bin/env python3
"""
Add missing v3 columns to oauth_accounts table.

v3 adds:
- nickname: VARCHAR(64) — user-defined name like "Personal" or "SRM"
- color: VARCHAR(7) — hex color like "#6366f1"
- sync_enabled: BOOLEAN — whether to sync from this account
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("DATABASE_URL not set")
    exit(1)

engine = create_engine(DATABASE_URL, future=True)

migrations = [
    ("nickname", "ALTER TABLE oauth_accounts ADD COLUMN IF NOT EXISTS nickname VARCHAR(64)"),
    ("color", "ALTER TABLE oauth_accounts ADD COLUMN IF NOT EXISTS color VARCHAR(7)"),
    ("sync_enabled", "ALTER TABLE oauth_accounts ADD COLUMN IF NOT EXISTS sync_enabled BOOLEAN DEFAULT true"),
]

print("Adding missing v3 columns to oauth_accounts...")
with engine.connect() as conn:
    for col_name, sql in migrations:
        try:
            conn.execute(text(sql))
            conn.commit()
            print(f"  [OK] Added {col_name}")
        except Exception as e:
            print(f"  [SKIP] {col_name}: {e}")

print("\nDone!")
