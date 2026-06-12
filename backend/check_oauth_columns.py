#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, future=True)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'oauth_accounts'
        ORDER BY ordinal_position
    """))

    print("OAUTH_ACCOUNTS TABLE COLUMNS:")
    for row in result:
        print(f"  {row[0]:30} {row[1]:20} nullable={row[2]}")
