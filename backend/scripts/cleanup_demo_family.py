"""
Remove the demo Rivera family (3 users) and all related data.
Delete Marcus first so the relationships he created are removed,
then Priya, then Sam.

Usage: run with the backend virtualenv so SQLAlchemy 2.x is used (required).

  cd backend
  . venv/bin/activate   # or .venv/bin/activate if you use .venv
  python scripts/cleanup_demo_family.py

Requires DATABASE_URL (in .env or environment) pointing at a running PostgreSQL.
On a remote server (e.g. DigitalOcean droplet), set DATABASE_URL to your
managed database URL, e.g.:
  export DATABASE_URL='postgresql://user:pass@your-db-host:25060/defaultdb?sslmode=require'
  python scripts/cleanup_demo_family.py

If you see "cannot import name 'async_sessionmaker'", you are using system
Python; activate the venv and run again.
"""
import asyncio
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load delete_user module (scripts dir is not a package)
_spec = importlib.util.spec_from_file_location(
    "delete_user",
    Path(__file__).parent / "delete_user.py",
)
_delete_user = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_delete_user)
delete_user_by_email = _delete_user.delete_user_by_email
delete_user_by_email_with_session = _delete_user.delete_user_by_email_with_session

DEMO_EMAILS = [
    "marcus.rivera@demo.inside.app",  # creator of family relationship — delete first
    "priya.rivera@demo.inside.app",
    "sam.rivera@demo.inside.app",
]


async def run_cleanup(session):
    """Remove the 3 demo users using the given session. Caller must commit.
    Deletes Marcus first (relationship creator), then Priya, then Sam."""
    for email in DEMO_EMAILS:
        await delete_user_by_email_with_session(session, email)


async def cleanup_demo_family():
    """CLI entrypoint: open session, run_cleanup, commit."""
    from app.infra.db.base import AsyncSessionLocal
    print("Removing demo family (Marcus, Priya, Sam)...\n")
    async with AsyncSessionLocal() as session:
        await run_cleanup(session)
        await session.commit()
    print("Done. Demo family removed.")


def main():
    try:
        asyncio.run(cleanup_demo_family())
    except OSError as e:
        if "Connect call failed" in str(e) or "Connection refused" in str(e):
            print("Database connection failed: PostgreSQL is not reachable.", file=sys.stderr)
            print("  Set DATABASE_URL to your database (e.g. export DATABASE_URL='postgresql://...').", file=sys.stderr)
            print("  On a remote server, use your managed DB URL; locally, start Postgres or use docker-compose.", file=sys.stderr)
            raise SystemExit(1) from e
        raise


if __name__ == "__main__":
    main()
