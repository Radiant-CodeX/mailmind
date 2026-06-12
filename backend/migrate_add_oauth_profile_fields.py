#!/usr/bin/env python3
"""
Migration: Add OAuth profile fields to oauth_accounts table.

This script safely adds the following columns if they don't already exist:
- display_name (String 255)
- given_name (String 128)
- family_name (String 128)
- picture_url (Text)
"""

import sys
from sqlalchemy import text, inspect, MetaData, Table, Column, String, Text

def migrate():
    from app.db.database import engine

    # Get inspector to check existing columns
    inspector = inspect(engine)
    existing_cols = {col['name'] for col in inspector.get_columns('oauth_accounts')}

    print(f"[migrate] Existing columns in oauth_accounts: {existing_cols}")

    # Columns to add
    columns_to_add = [
        ('display_name', 'VARCHAR(255)'),
        ('given_name', 'VARCHAR(128)'),
        ('family_name', 'VARCHAR(128)'),
        ('picture_url', 'TEXT'),
    ]

    with engine.begin() as conn:
        for col_name, col_type in columns_to_add:
            if col_name in existing_cols:
                print(f"[migrate] Column {col_name} already exists, skipping")
                continue

            try:
                stmt = f"ALTER TABLE oauth_accounts ADD COLUMN {col_name} {col_type}"
                print(f"[migrate] Executing: {stmt}")
                conn.execute(text(stmt))
                print(f"[migrate] ✅ Added column {col_name}")
            except Exception as e:
                print(f"[migrate] ❌ Failed to add {col_name}: {e}")
                return False

    print("[migrate] ✅ Migration complete!")
    return True

if __name__ == '__main__':
    try:
        success = migrate()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"[migrate] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
