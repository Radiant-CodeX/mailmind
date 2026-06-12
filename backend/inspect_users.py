#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, future=True)

with engine.connect() as conn:
    # Check users table schema
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY ordinal_position
    """))

    print("USERS TABLE COLUMNS:")
    for row in result:
        print(f"  {row[0]:20} {row[1]:20} nullable={row[2]}")

    # Check sample users data
    print("\nSAMPLE USERS:")
    result = conn.execute(text("SELECT * FROM users LIMIT 2"))
    rows = result.fetchall()
    for row in rows:
        print(f"  {row}")
