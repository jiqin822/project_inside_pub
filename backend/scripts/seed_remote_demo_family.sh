#!/usr/bin/env bash
# Run migrations, seed Love Map prompts, and seed the demo family against the
# database given by DATABASE_URL (e.g. your DigitalOcean managed Postgres).
#
# Run with: bash scripts/seed_remote_demo_family.sh   (do not use: python ...)
#
# Usage (from backend/):
#   DATABASE_URL="postgresql://user:pass@host:25060/defaultdb?sslmode=require" bash scripts/seed_remote_demo_family.sh
#
# Or export DATABASE_URL first, then:
#   bash scripts/seed_remote_demo_family.sh
#
# If you run this INSIDE the app container (e.g. DigitalOcean run command), the
# app database user must already have been granted schema public rights;
# otherwise migrations fail with "permission denied for schema public".
# See docs/DEPLOY_DIGITALOCEAN.md "Permission denied for schema public".
# Grant rights from your machine as admin, then re-run this script.
#
# If you get SSL certificate verify failed (e.g. seeding from Mac to DigitalOcean):
#   export DATABASE_SSL_VERIFY=false
set -e
cd "$(dirname "$0")/.."
if [ -z "${DATABASE_URL}" ]; then
  echo "Error: DATABASE_URL is not set."
  echo "Example: export DATABASE_URL='postgresql://user:pass@host:25060/defaultdb?sslmode=require'"
  exit 1
fi
echo "Using DATABASE_URL (host only): $(echo "$DATABASE_URL" | sed -E 's|://[^@]+@|://***@|')"
echo ""
echo "1/3 Running migrations..."
alembic upgrade head
echo ""
echo "2/3 Seeding Love Map prompts..."
python scripts/seed_love_map_prompts.py
echo ""
echo "3/3 Seeding demo family..."
python scripts/seed_demo_family.py
echo ""
echo "Done. See docs/FAMILY_DEMO_CREDENTIALS.md for login details."
