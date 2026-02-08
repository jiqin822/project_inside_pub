#!/bin/bash
# One-button environment setup: install packages, bring up dependency services,
# align .env ports with docker-compose (postgres on 5433). Idempotent; safe to run multiple times.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$BACKEND_DIR/.." && pwd)"

cd "$BACKEND_DIR"

# Load .env if present (do not overwrite existing env)
if [ -f .env ]; then
  set -a
  . ./.env
  set +a
fi

echo "=== One-button env setup (config: CONFIG_FILE=${CONFIG_FILE:-config.yaml}) ==="
echo ""

# 1. Install packages
if command -v poetry >/dev/null 2>&1 && [ -f pyproject.toml ]; then
  echo "Installing Python dependencies (Poetry)..."
  poetry install
else
  echo "Installing Python dependencies (pip)..."
  pip install -r requirements.txt
fi
echo ""

# 2. Start dependency services (docker-compose)
if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    DCOMPOSE="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    DCOMPOSE="docker-compose"
  else
    echo "WARNING: docker not found or docker compose unavailable. Start postgres and redis manually."
    DCOMPOSE=""
  fi
  if [ -n "$DCOMPOSE" ]; then
    echo "Starting dependency services (postgres, redis)..."
    (cd "$REPO_ROOT" && $DCOMPOSE up -d postgres redis)
    echo ""

    # 3. Port alignment: docker-compose maps postgres to 5433; ensure .env has DATABASE_URL for 5433
    ENV_FILE="$BACKEND_DIR/.env"
    if [ ! -f "$ENV_FILE" ]; then
      touch "$ENV_FILE"
    fi
    if ! grep -q '^DATABASE_URL=' "$ENV_FILE" 2>/dev/null; then
      echo "# Added by setup_env.sh: postgres on host port 5433 (docker-compose)" >> "$ENV_FILE"
      echo "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/project_inside" >> "$ENV_FILE"
      echo "Appended DATABASE_URL (port 5433) to .env"
    elif grep -q 'localhost:5432' "$ENV_FILE" 2>/dev/null; then
      echo "NOTE: .env has DATABASE_URL with port 5432; docker-compose exposes postgres on 5433."
      echo "      Update .env to use port 5433 or set CONFIG_FILE with database_url port 5433."
    fi
  fi
else
  echo "WARNING: docker not found. Start postgres and redis manually (e.g. docker-compose up -d)."
fi

echo ""
echo "=== Setup complete ==="
echo "  Packages: installed"
echo "  Services: postgres and redis (if docker available)"
echo "  Config: .env / CONFIG_FILE=${CONFIG_FILE:-config.yaml}"
echo "  Run readiness check: poetry run python scripts/check_readiness.py (or make ready)"
echo ""
