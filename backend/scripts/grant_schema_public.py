#!/usr/bin/env python3
"""
Grant the app database user full rights on schema public (PostgreSQL 15+ / DigitalOcean).

Must be run with an **admin** connection (e.g. DigitalOcean doadmin), not the app user.

ADMIN_DATABASE_URL = admin connection string (preferred). Use when DATABASE_URL is
already set to the app user (e.g. in the container); the script will use ADMIN_DATABASE_URL
only for this grant and leave DATABASE_URL unchanged.
DATABASE_URL = admin connection string (if ADMIN_DATABASE_URL is not set).
Use the **same database name** as your app (e.g. dev-db-193637), not defaultdb.

TARGET_USER = role to grant to (default: dev-db-193637).

Usage (from backend/):
  # When DATABASE_URL is already the app user (e.g. in container), set admin URL only for this run:
  ADMIN_DATABASE_URL='postgresql://doadmin:...@host:25060/dev-db-193637?sslmode=require' TARGET_USER='dev-db-193637' python scripts/grant_schema_public.py

  # Or export admin URL as DATABASE_URL:
  export DATABASE_URL='postgresql://doadmin:...@host:25060/dev-db-193637?sslmode=require'
  export TARGET_USER='dev-db-193637'
  export DATABASE_SSL_VERIFY=false
  python scripts/grant_schema_public.py
"""
import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.db.base import (
    async_pg_connect_args,
    async_pg_url_without_sslmode,
    normalize_async_pg_url,
)
from app.settings import settings

GRANTS = [
    'GRANT ALL ON SCHEMA public TO "{target}"',
    'GRANT CREATE ON SCHEMA public TO "{target}"',
    'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "{target}"',
    'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "{target}"',
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO "{target}"',
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO "{target}"',
]


def main() -> None:
    target = os.environ.get("TARGET_USER", "dev-db-193637").strip()
    if not re.match(r"^[a-zA-Z0-9_-]+$", target):
        print("Error: TARGET_USER must be alphanumeric, hyphen, or underscore only.", file=sys.stderr)
        sys.exit(1)
    url_str = os.environ.get("ADMIN_DATABASE_URL") or os.environ.get("DATABASE_URL") or getattr(settings, "database_url", None)
    if not url_str:
        print("Error: Set ADMIN_DATABASE_URL or DATABASE_URL to the **admin** connection string (e.g. doadmin).", file=sys.stderr)
        sys.exit(1)

    url = normalize_async_pg_url(url_str)
    engine = create_async_engine(
        async_pg_url_without_sslmode(url),
        connect_args=async_pg_connect_args(url),
        poolclass=NullPool,
    )

    async def run() -> None:
        async with engine.begin() as conn:
            for stmt in GRANTS:
                sql = stmt.format(target=target)
                await conn.execute(text(sql))
                print(f"  OK: {sql.split(' TO ')[0]}")
        await engine.dispose()

    print(f"Granting schema public rights to role: {target}")
    asyncio.run(run())
    print("Done. You can now run migrations/seed as the app user.")


if __name__ == "__main__":
    main()
