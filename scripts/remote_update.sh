#!/usr/bin/env bash
# One-click update on the remote VM: pull, reinstall backend, rebuild frontend, reload nginx.
# Usage: on the VM, from repo root: sudo ./scripts/remote_update.sh [--backend-only | --frontend-only] [--no-pull]
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_ONLY=false
FRONTEND_ONLY=false
NO_PULL=false

usage() {
  echo "Usage: $0 [--backend-only] [--frontend-only] [--no-pull]"
  echo "  Run on the remote VM: cd /opt/project_inside && sudo ./scripts/remote_update.sh"
  echo "  --backend-only   Update only backend (pull, install, restart)"
  echo "  --frontend-only  Update only frontend (pull, build, copy to web root)"
  echo "  --no-pull        Skip git pull (use if you deployed another way)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-only)   BACKEND_ONLY=true; shift ;;
    --frontend-only) FRONTEND_ONLY=true; shift ;;
    --no-pull)       NO_PULL=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [[ "$BACKEND_ONLY" == true ]] && [[ "$FRONTEND_ONLY" == true ]]; then
  echo "ERROR: use only one of --backend-only or --frontend-only"
  exit 1
fi

SUDO=""
[[ $(id -u) -ne 0 ]] && SUDO="sudo"

if [[ ! -d "$REPO_ROOT/backend" ]] || [[ ! -d "$REPO_ROOT/deploy" ]]; then
  echo "ERROR: Run from repo root (expected backend/ and deploy/). Current REPO_ROOT: $REPO_ROOT"
  exit 1
fi

# VITE_API_BASE_URL: prefer saved frontend env, then APP_PUBLIC_URL, then repo .env.production. Never overwrite these files.
get_vite_api_base() {
  local v
  if [[ -f /etc/project_inside/frontend.env ]]; then
    v=$(grep -E '^VITE_API_BASE_URL=' /etc/project_inside/frontend.env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
    if [[ -n "$v" ]]; then
      echo "$v"
      return
    fi
  fi
  if [[ -f /etc/project_inside/backend.env ]]; then
    v=$(grep -E '^APP_PUBLIC_URL=' /etc/project_inside/backend.env 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
    if [[ -n "$v" ]]; then
      echo "$v"
      return
    fi
  fi
  if [[ -f "$REPO_ROOT/mobile/.env.production" ]]; then
    v=$(grep -E '^VITE_API_BASE_URL=' "$REPO_ROOT/mobile/.env.production" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
    if [[ -n "$v" ]]; then
      echo "$v"
      return
    fi
  fi
  echo "http://localhost"
}

echo "=== Remote update (no Docker) ==="

if [[ "$NO_PULL" != true ]]; then
  echo "Pulling latest code..."
  cd "$REPO_ROOT"
  git pull
fi

if [[ "$FRONTEND_ONLY" != true ]]; then
  echo "Updating backend..."
  cd "$REPO_ROOT"
  $SUDO bash deploy/backend_install.sh
  echo "Waiting for backend to be ready..."
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/v1/health 2>/dev/null | grep -q 200; then
      echo "Backend is up (health returned 200)."
      break
    fi
    if [[ $i -eq 10 ]]; then
      echo "WARNING: Backend health check did not return 200 after 10 tries."
      echo "  On the VM run: systemctl status project_inside_backend"
      echo "  Logs: journalctl -u project_inside_backend -n 50 --no-pager"
      echo "  If the backend failed to start, fix it before using the web app."
      exit 1
    fi
    sleep 1
  done
fi

if [[ "$BACKEND_ONLY" != true ]]; then
  echo "Building frontend..."
  VITE_API_BASE_URL=$(get_vite_api_base)
  if [[ -z "$VITE_API_BASE_URL" ]] || [[ "$VITE_API_BASE_URL" == "http://localhost" ]]; then
    echo "WARNING: VITE_API_BASE_URL is empty or localhost. Set one of:"
    echo "  - /etc/project_inside/frontend.env with VITE_API_BASE_URL=https://your-domain.com"
    echo "  - APP_PUBLIC_URL in /etc/project_inside/backend.env"
    echo "  - mobile/.env.production in the repo (VITE_API_BASE_URL=...)"
    echo "Proceeding with: $VITE_API_BASE_URL (site may be blank or fail to connect)"
  fi
  echo "  VITE_API_BASE_URL=$VITE_API_BASE_URL"
  cd "$REPO_ROOT/mobile"
  npm ci --quiet
  VITE_API_BASE_URL="$VITE_API_BASE_URL" npm run build

  echo "Deploying frontend to web root..."
  $SUDO mkdir -p /var/www/project_inside
  $SUDO cp -r dist/. /var/www/project_inside/
  $SUDO chown -R www-data:www-data /var/www/project_inside 2>/dev/null || $SUDO chown -R nginx:nginx /var/www/project_inside 2>/dev/null || true
  # Persist so next update uses the same URL (update script never overwrites backend.env or frontend.env)
  $SUDO mkdir -p /etc/project_inside
  echo "VITE_API_BASE_URL=$VITE_API_BASE_URL" | $SUDO tee /etc/project_inside/frontend.env > /dev/null
  echo "Frontend updated (saved VITE_API_BASE_URL to /etc/project_inside/frontend.env)."
fi

# Refresh nginx config (in case nginx-host.conf or paths changed).
# Do not overwrite if HTTPS is already configured (listen 443); otherwise update would remove SSL and break https://.
echo "Reloading nginx..."
NGINX_OVERWRITE=true
if [[ -d /etc/nginx/sites-available ]]; then
  CURRENT_CONF="/etc/nginx/sites-available/project_inside"
  if [[ -f "$CURRENT_CONF" ]] && grep -q "listen 443" "$CURRENT_CONF" 2>/dev/null; then
    echo "  Keeping existing Nginx config (HTTPS already configured)."
    NGINX_OVERWRITE=false
  fi
  if [[ "$NGINX_OVERWRITE" == true ]]; then
    $SUDO cp "$REPO_ROOT/deploy/nginx-host.conf" "$CURRENT_CONF"
    $SUDO ln -sf /etc/nginx/sites-available/project_inside /etc/nginx/sites-enabled/
  fi
elif [[ -d /etc/nginx/conf.d ]]; then
  CURRENT_CONF="/etc/nginx/conf.d/project_inside.conf"
  if [[ -f "$CURRENT_CONF" ]] && grep -q "listen 443" "$CURRENT_CONF" 2>/dev/null; then
    echo "  Keeping existing Nginx config (HTTPS already configured)."
    NGINX_OVERWRITE=false
  fi
  if [[ "$NGINX_OVERWRITE" == true ]]; then
    $SUDO cp "$REPO_ROOT/deploy/nginx-host.conf" "$CURRENT_CONF"
  fi
fi
$SUDO nginx -t && $SUDO systemctl reload nginx

echo "=== Remote update complete ==="
echo "  Health: curl http://localhost/v1/health"
echo ""
echo "If the web app shows 'Cannot connect to server':"
echo "  1) Backend: systemctl status project_inside_backend && journalctl -u project_inside_backend -n 30"
echo "  2) From VM: curl -s http://localhost/v1/health (should return JSON)"
echo "  3) Ensure /etc/project_inside/backend.env has APP_PUBLIC_URL and CORS_ORIGINS for your domain (e.g. https://se-ai.live)"
echo "  4) If using HTTPS, ensure Nginx is configured for 443 and proxies /v1/ to the backend"
