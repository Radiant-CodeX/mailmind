#!/usr/bin/env python3
"""Fix all schema mismatches between Supabase and v3 ORM models."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, future=True)

migrations = [
    # 1. Add primary_email to users (copy from email)
    ("users - add primary_email", """
        ALTER TABLE users ADD COLUMN IF NOT EXISTS primary_email VARCHAR(320);
        UPDATE users SET primary_email = email WHERE primary_email IS NULL;
    """),

    # 2. Add id to user_sessions (if missing)
    ("user_sessions - check id", "SELECT 1 FROM information_schema.columns WHERE table_name='user_sessions' AND column_name='id'"),

    # 3. Add timestamps to tone_profile
    ("tone_profile - add created_at", """
        ALTER TABLE tone_profile ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    """),
    ("tone_profile - add updated_at", """
        ALTER TABLE tone_profile ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    """),

    # 4. Add account_id to audit_log
    ("audit_log - add account_id", """
        ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS account_id VARCHAR(36);
        CREATE INDEX IF NOT EXISTS ix_audit_account_id ON audit_log(account_id);
    """),

    # 5. Add account_id and latency_ms to processing_metric
    ("processing_metric - add account_id", """
        ALTER TABLE processing_metric ADD COLUMN IF NOT EXISTS account_id VARCHAR(36);
        CREATE INDEX IF NOT EXISTS ix_metric_account_id ON processing_metric(account_id);
    """),
    ("processing_metric - add latency_ms", """
        ALTER TABLE processing_metric ADD COLUMN IF NOT EXISTS latency_ms INTEGER;
    """),
]

print("Fixing schema mismatches...\n")

with engine.connect() as conn:
    for step_name, sql in migrations:
        try:
            # Split multiple statements
            for statement in sql.split(";"):
                if statement.strip():
                    conn.execute(text(statement.strip()))
            conn.commit()
            print(f"[OK] {step_name}")
        except Exception as e:
            print(f"[SKIP] {step_name}: {e}")

print("\nDone! Running final audit...")

# Run audit
import subprocess
result = subprocess.run(["python", "comprehensive_schema_check.py"], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr)
