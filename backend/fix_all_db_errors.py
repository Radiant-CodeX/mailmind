#!/usr/bin/env python3
"""
Comprehensive ORM model audit and auto-fix.
Find all mismatches between ORM models and Supabase schema.
"""
import os
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, future=True)

print("=" * 100)
print("COMPREHENSIVE ORM MODEL AUDIT")
print("=" * 100)

inspector = inspect(engine)

# Expected columns per table (from Supabase schema check)
SUPABASE_SCHEMA = {
    "users": ["id", "created_at", "display_name", "last_login_at", "primary_email"],
    "oauth_accounts": ["id", "user_id", "provider", "provider_account_id", "account_email", "access_token_enc",
                       "refresh_token_enc", "token_expires_at", "nickname", "color", "is_default", "sync_enabled",
                       "created_at", "updated_at"],
    "user_sessions": ["token_hash", "user_id", "provider", "email", "created_at", "expires_at", "last_seen_at"],
    "devices": ["id", "user_id", "fingerprint", "user_agent", "accept_language", "last_used", "created_at"],
    "quick_login_tokens": ["id", "user_id", "device_id", "token_hash", "expires_at", "status", "created_at"],
    "tone_profile": ["account_id", "profile", "sample_size", "created_at", "updated_at"],
    "audit_log": ["id", "email_id", "account_id", "action", "actor", "details", "created_at"],
    "processing_metric": ["id", "email_id", "account_id", "stage", "latency_ms", "created_at"],
}

# Read the models.py file
with open("app/db/models.py", "r") as f:
    models_content = f.read()

# Find all Mapped column definitions for each table
issues = []

for table_name, expected_cols in SUPABASE_SCHEMA.items():
    print(f"\n[{table_name.upper()}]")

    # Find the class definition
    class_pattern = rf"class \w+\(Base\):[^\n]*\n(?:.*?\n)*?__tablename__ = ['\"]?{table_name}"
    if not re.search(class_pattern, models_content):
        print(f"  WARNING: No class found for table {table_name}")
        continue

    # Find all column definitions in the class
    mapped_pattern = r"(\w+): Mapped\[.*?\] = mapped_column\(.*?\)"
    matches = re.findall(mapped_pattern, models_content)

    actual_cols = set()
    for match in matches:
        # Extract the actual Supabase column name (might be different from Python attr)
        # Look for mapped_column("actual_name", ...) pattern
        col_name_pattern = rf"{match}:\s*Mapped\[.*?\]\s*=\s*mapped_column\(['\"]?(\w+)?['\"]?"
        col_match = re.search(col_name_pattern, models_content)
        if col_match and col_match.group(1):
            actual_cols.add(col_match.group(1))
        else:
            actual_cols.add(match)

    # Get actual columns from DB
    db_cols = {col["name"] for col in inspector.get_columns(table_name)}

    print(f"  Expected (Supabase): {', '.join(expected_cols)}")
    print(f"  Actual (Supabase):   {', '.join(sorted(db_cols))}")
    print(f"  ORM has:             {', '.join(sorted(actual_cols))}")

    # Find mismatches
    missing_in_orm = set(expected_cols) - actual_cols
    extra_in_orm = actual_cols - set(expected_cols)

    if missing_in_orm:
        print(f"  ERROR: Missing in ORM: {missing_in_orm}")
        issues.append((table_name, "missing", missing_in_orm))
    if extra_in_orm:
        print(f"  WARNING: Extra in ORM: {extra_in_orm}")
        issues.append((table_name, "extra", extra_in_orm))
    if not missing_in_orm and not extra_in_orm:
        print(f"  OK: All columns match")

print("\n" + "=" * 100)
if issues:
    print(f"FOUND {len(issues)} ISSUES - see above")
    print("=" * 100)
    for table, issue_type, cols in issues:
        print(f"  {table:25} {issue_type:10} {cols}")
else:
    print("ALL MODELS OK - No mismatches found!")
print("=" * 100)
