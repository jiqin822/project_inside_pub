#!/usr/bin/env bash
# Grant schema public rights to the app user (fix "permission denied for schema public").
# Requires an **admin** connection (e.g. DigitalOcean doadmin), not the app user.
#
# When DATABASE_URL is already set (e.g. in the container) to the **app** user, use
# ADMIN_DATABASE_URL for this run only (same database name as app, e.g. dev-db-193637):
#
#   ADMIN_DATABASE_URL='postgresql://doadmin:ADMIN_PASS@host:25060/dev-db-193637?sslmode=require' TARGET_USER='dev-db-193637' ./scripts/grant_schema_public.sh
#
# Or export the admin URL as DATABASE_URL (from backend/):
#   export DATABASE_URL='postgresql://doadmin:...@host:25060/dev-db-193637?sslmode=require'
#   export TARGET_USER='dev-db-193637'
#   export DATABASE_SSL_VERIFY=false
#   ./scripts/grant_schema_public.sh
set -e
cd "$(dirname "$0")/.."
if [ -z "${ADMIN_DATABASE_URL}" ] && [ -z "${DATABASE_URL}" ]; then
  echo "Error: Set ADMIN_DATABASE_URL or DATABASE_URL to the **admin** connection string (e.g. doadmin)."
  echo "Use the same database name as your app (e.g. .../dev-db-193637?sslmode=require)."
  echo "TARGET_USER (default: dev-db-193637) is the role that will receive schema public rights."
  exit 1
fi
export TARGET_USER="${TARGET_USER:-dev-db-193637}"
python scripts/grant_schema_public.py
