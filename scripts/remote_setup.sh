#!/usr/bin/env bash
# One-click setup on the remote VM: install nginx, Postgres, Redis, Node; prompt for .env; install backend and frontend (no Docker).
# Usage: on the VM, clone the repo then run: ./scripts/remote_setup.sh [--domain DOMAIN] [--api-base URL] [--backend-env FILE] [--frontend-env FILE]
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN=""
API_BASE=""
BACKEND_ENV_FILE=""
FRONTEND_ENV_FILE=""

usage() {
  echo "Usage: $0 [--domain DOMAIN] [--api-base URL] [--backend-env FILE] [--frontend-env FILE]"
  echo "  Run this script on the remote VM (e.g. after cloning: cd /opt/project_inside && sudo ./scripts/remote_setup.sh)"
  echo "  --domain        Public domain (e.g. https://app.example.com) for CORS_ORIGINS, APP_PUBLIC_URL, VITE_API_BASE_URL"
  echo "  --api-base      Override API base URL for frontend (default: same as --domain)"
  echo "  --backend-env   Use existing backend .env file instead of prompting"
  echo "  --frontend-env  Use existing frontend env (VITE_API_BASE_URL) instead of prompting"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)   DOMAIN="$2"; shift 2 ;;
    --api-base) API_BASE="$2"; shift 2 ;;
    --backend-env)  BACKEND_ENV_FILE="$2"; shift 2 ;;
    --frontend-env) FRONTEND_ENV_FILE="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# Must be run from repo (backend and deploy exist)
if [[ ! -d "$REPO_ROOT/backend" ]] || [[ ! -d "$REPO_ROOT/deploy" ]]; then
  echo "ERROR: Run from repo root (expected backend/ and deploy/). Current REPO_ROOT: $REPO_ROOT"
  exit 1
fi

SUDO=""
[[ $(id -u) -ne 0 ]] && SUDO="sudo"

# API-key / secret keys we prompt for only when value is empty or a placeholder
PROMPT_KEYS=(SECRET_KEY GEMINI_API_KEY OPENAI_API_KEY SENDGRID_API_KEY GOOGLE_APPLICATION_CREDENTIALS_JSON)

value_not_present() {
  local val="$1"
  [[ -z "$val" ]] && return 0
  [[ "$val" == *"change-me"* ]] && return 0
  [[ "$val" == *"your-project"* ]] && return 0
  [[ "$val" == *"YOUR_PROJECT"* ]] && return 0
  return 1
}

prompt_value() {
  local key="$1" desc="$2" default="$3" secret="${4:-}"
  local val
  if [[ -n "$secret" ]]; then
    echo -n "$key (${desc}): " >&2
    read -r -s val
    echo "" >&2
  else
    echo -n "$key (${desc}) [${default}]: " >&2
    read -r val
  fi
  if [[ -z "$val" ]]; then
    val="$default"
  fi
  echo "$val"
}

build_backend_env() {
  if [[ -n "$BACKEND_ENV_FILE" ]] && [[ -f "$BACKEND_ENV_FILE" ]]; then
    cat "$BACKEND_ENV_FILE"
    return
  fi

  local example_file="$REPO_ROOT/backend/.env.example"
  if [[ ! -f "$example_file" ]]; then
    echo "ERROR: $example_file not found" >&2
    exit 1
  fi

  local base_url="${API_BASE:-$DOMAIN}"
  [[ -z "$base_url" ]] && base_url="http://localhost"
  local cors_override="[\"${base_url}\"]"
  local app_public_override="$base_url"

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^[[:space:]]*# ]] || [[ "$line" =~ ^[[:space:]]*$ ]]; then
      echo "$line"
      continue
    fi
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      val="${val#\"}"
      val="${val%\"}"

      if [[ "$key" == "CORS_ORIGINS" ]] && [[ -n "$DOMAIN" ]]; then
        echo "CORS_ORIGINS=$cors_override"
        continue
      fi
      if [[ "$key" == "APP_PUBLIC_URL" ]] && [[ -n "$DOMAIN" ]]; then
        echo "APP_PUBLIC_URL=$app_public_override"
        continue
      fi
      if [[ "$key" == "DATABASE_URL" ]]; then
        echo "DATABASE_URL=postgresql+asyncpg://project_inside:postgres@localhost:5432/project_inside"
        continue
      fi

      need_prompt=false
      for k in "${PROMPT_KEYS[@]}"; do
        if [[ "$k" == "$key" ]] && value_not_present "$val"; then
          need_prompt=true
          break
        fi
      done

      if [[ "$need_prompt" == true ]]; then
        case "$key" in
          SECRET_KEY) val=$(prompt_value "$key" "JWT secret (change in production!)" "$val" "secret") ;;
          GEMINI_API_KEY) val=$(prompt_value "$key" "Gemini API key (optional)" "") ;;
          OPENAI_API_KEY) val=$(prompt_value "$key" "OpenAI API key (optional)" "") ;;
          SENDGRID_API_KEY) val=$(prompt_value "$key" "SendGrid API key (optional)" "") ;;
          GOOGLE_APPLICATION_CREDENTIALS_JSON) val=$(prompt_value "$key" "GCP SA JSON string (optional)" "") ;;
          *) val="$val" ;;
        esac
      fi
      echo "${key}=${val}"
    else
      echo "$line"
    fi
  done < "$example_file"
}

get_vite_api_base() {
  if [[ -n "$FRONTEND_ENV_FILE" ]] && [[ -f "$FRONTEND_ENV_FILE" ]]; then
    local v
    v=$(grep -E '^VITE_API_BASE_URL=' "$FRONTEND_ENV_FILE" 2>/dev/null | cut -d= -f2-)
    if [[ -n "$v" ]]; then
      echo "$v"
      return
    fi
  fi
  if [[ -n "$API_BASE" ]]; then echo "$API_BASE"; return; fi
  if [[ -n "$DOMAIN" ]]; then echo "$DOMAIN"; return; fi
  echo -n "VITE_API_BASE_URL (API base URL for frontend build) [http://localhost]: " >&2
  read -r v
  echo "${v:-http://localhost}"
}

echo "=== Remote setup (this machine, no Docker) ==="

# Install nginx, Postgres, Redis
if command -v apt-get &>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq nginx postgresql postgresql-contrib redis-server
  $SUDO systemctl enable nginx postgresql redis-server
  $SUDO systemctl start postgresql redis-server 2>/dev/null || true
elif command -v yum &>/dev/null; then
  $SUDO yum install -y nginx postgresql-server redis 2>/dev/null || $SUDO dnf install -y nginx postgresql-server redis
  $SUDO postgresql-setup initdb 2>/dev/null || true
  $SUDO systemctl enable nginx postgresql redis
  $SUDO systemctl start postgresql redis 2>/dev/null || true
else
  echo "ERROR: Unsupported package manager. Install nginx, postgresql, redis and run again."
  exit 1
fi

# Create Postgres user (if missing) and database, set password (always use sudo -u postgres)
sudo -u postgres psql -q -v ON_ERROR_STOP=1 <<'EOSQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'project_inside') THEN
    CREATE USER project_inside WITH PASSWORD 'postgres';
  ELSE
    ALTER USER project_inside WITH PASSWORD 'postgres';
  END IF;
END
$$;
EOSQL
sudo -u postgres psql -q -c "CREATE DATABASE project_inside OWNER project_inside;" 2>/dev/null || true
# Ensure local TCP (127.0.0.1) can use password auth for project_inside (asyncpg connects via TCP)
PG_HBA=$(ls /etc/postgresql/*/main/pg_hba.conf 2>/dev/null | head -1)
if [[ -n "$PG_HBA" ]] && ! grep -q "project_inside.*127.0.0.1" "$PG_HBA" 2>/dev/null; then
  echo "host    project_inside    project_inside    127.0.0.1/32    md5" | $SUDO tee -a "$PG_HBA" > /dev/null
  $SUDO systemctl reload postgresql 2>/dev/null || true
fi

# Backend env
echo "Preparing backend.env..."
$SUDO mkdir -p /etc/project_inside
build_backend_env | $SUDO tee /etc/project_inside/backend.env > /dev/null
# Force DATABASE_URL to use project_inside user (we create this user above; postgres user may not allow TCP auth)
$SUDO sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://project_inside:postgres@localhost:5432/project_inside|' /etc/project_inside/backend.env

# Run backend install (Python 3.12, venv, migrations, systemd)
echo "Running backend install..."
cd "$REPO_ROOT" && $SUDO bash deploy/backend_install.sh

# Node for frontend build
if ! command -v node &>/dev/null || ! node -e "process.exit(process.versions.node.split('.')[0] >= 22 ? 0 : 1)" 2>/dev/null; then
  echo "Installing Node 22..."
  if command -v apt-get &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | $SUDO bash -
    $SUDO apt-get install -y -qq nodejs
  else
    echo "Install Node 22+ manually (e.g. from nodesource) and run this script again."
    exit 1
  fi
fi

# Build frontend
VITE_API_BASE_URL=$(get_vite_api_base)
echo "Building frontend (VITE_API_BASE_URL=$VITE_API_BASE_URL)..."
cd "$REPO_ROOT/mobile"
npm ci --quiet
VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run build

# Serve frontend via nginx
$SUDO mkdir -p /var/www/project_inside
$SUDO cp -r dist/. /var/www/project_inside/
$SUDO chown -R www-data:www-data /var/www/project_inside 2>/dev/null || $SUDO chown -R nginx:nginx /var/www/project_inside 2>/dev/null || true

# Nginx config
if [[ -d /etc/nginx/sites-available ]]; then
  $SUDO cp "$REPO_ROOT/deploy/nginx-host.conf" /etc/nginx/sites-available/project_inside
  $SUDO ln -sf /etc/nginx/sites-available/project_inside /etc/nginx/sites-enabled/
  $SUDO rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
elif [[ -d /etc/nginx/conf.d ]]; then
  $SUDO cp "$REPO_ROOT/deploy/nginx-host.conf" /etc/nginx/conf.d/project_inside.conf
fi
$SUDO nginx -t && $SUDO systemctl reload nginx

echo "=== Remote setup complete (no Docker) ==="
echo "  Backend: systemd project_inside_backend.service (port 8000)"
echo "  Frontend: nginx serving /var/www/project_inside (port 80)"
echo "  Postgres: localhost:5432, DB project_inside, user project_inside"
echo "  Redis: localhost:6379"
echo "  Health: curl http://localhost/v1/health"
