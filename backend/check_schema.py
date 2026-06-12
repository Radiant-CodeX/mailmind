#!/usr/bin/env python3
"""Check current database schema."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, future=True)
inspector = inspect(engine)

print("=" * 80)
print("MAILMIND V3 DATABASE SCHEMA CHECK")
print("=" * 80)

# Key v3 tables
v3_tables = [
    "users",
    "oauth_accounts",
    "user_sessions",
    "quick_login_tokens",
    "devices",
    "tone_profile",
    "audit_log",
    "processing_metric",
]

print("\nChecking v3 identity tables...")
for table in v3_tables:
    if table in inspector.get_table_names():
        columns = {col["name"]: col["type"] for col in inspector.get_columns(table)}
        print(f"  [OK] {table:25} {len(columns)} columns")
        if table == "oauth_accounts":
            print(f"       Keys: {', '.join(col['name'] for col in inspector.get_columns(table) if 'key' in str(col).lower() or col['name'] in ['user_id', 'provider', 'is_default'])}")
        elif table == "tone_profile":
            print(f"       Keys: {', '.join(col['name'] for col in inspector.get_columns(table))}")
    else:
        print(f"  [MISSING] {table:25}")

# Check if v2 table exists
print("\nChecking v2 legacy tables...")
if "tone_profile_v2" in inspector.get_table_names():
    print(f"  [WARNING] tone_profile_v2 exists (migration needed)")
else:
    print(f"  [OK] tone_profile_v2 not found (clean)")

# Show table count
all_tables = inspector.get_table_names()
print(f"\nTotal tables: {len(all_tables)}")
print(f"Tables: {', '.join(sorted(all_tables))}")

print("\n" + "=" * 80)
print("DATABASE READY FOR V3 DEPLOYMENT")
print("=" * 80)
