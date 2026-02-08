#!/usr/bin/env bash
# Install backend on host: Python 3.12, venv, requirements, migrations, systemd service.
# Usage: run from repo root on the VM (e.g. after clone). Requires /etc/project_inside/backend.env.
# Run as root or with sudo.
set -e

SUDO=""
[[ $(id -u) -ne 0 ]] && SUDO="sudo"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
VENV_DIR="$BACKEND_DIR/.venv"
REQUIREMENTS_FILE="${REQUIREMENTS_FILE:-requirements-do.txt}"

echo "=== Project Inside backend install (Python 3.12) ==="

# Require Python 3.12 (and venv module for pip in venv)
if ! command -v python3.12 &>/dev/null; then
  echo "Installing Python 3.12..."
  if command -v apt-get &>/dev/null; then
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq software-properties-common
    $SUDO add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
  elif command -v yum &>/dev/null; then
    $SUDO yum install -y python3.12 python3.12-devel 2>/dev/null || $SUDO dnf install -y python3.12 python3.12-devel
  else
    echo "ERROR: Could not install Python 3.12. Install python3.12 and run this script again."
    exit 1
  fi
fi

PYTHON="$(command -v python3.12)"
VERSION="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$VERSION" != "3.12" ]]; then
  echo "ERROR: python3.12 must be 3.12.x, got $VERSION"
  exit 1
fi
echo "Using $PYTHON ($VERSION)"

# On Debian/Ubuntu ensure python3.12-venv is installed so venv has pip
if command -v apt-get &>/dev/null; then
  if ! "$PYTHON" -c "import ensurepip" 2>/dev/null; then
    echo "Installing python3.12-venv for pip in venv..."
    $SUDO apt-get install -y -qq python3.12-venv 2>/dev/null || true
  fi
fi

# Env file must exist (populated by remote_setup.sh or manually)
if [[ ! -f /etc/project_inside/backend.env ]]; then
  echo "ERROR: /etc/project_inside/backend.env not found. Create it or run remote_setup.sh with env prompts."
  exit 1
fi
$SUDO mkdir -p /etc/project_inside

# Venv (create or recreate if bin/pip missing, e.g. incomplete venv or wrong Python)
if [[ ! -x "$VENV_DIR/bin/pip" ]]; then
  if [[ -d "$VENV_DIR" ]]; then
    echo "Removing incomplete venv at $VENV_DIR..."
    rm -rf "$VENV_DIR"
  fi
  echo "Creating venv at $VENV_DIR..."
  "$PYTHON" -m venv "$VENV_DIR"
  if [[ ! -x "$VENV_DIR/bin/pip" ]]; then
    echo "ERROR: venv created but pip not found. Install python3.12-venv (apt) or ensure python3.12 has ensurepip."
    exit 1
  fi
fi
"$VENV_DIR/bin/pip" install --upgrade pip -q

# Requirements (default: requirements-do.txt; set REQUIREMENTS_FILE=requirements-full.txt for full STT)
REQ_PATH="$BACKEND_DIR/$REQUIREMENTS_FILE"
if [[ ! -f "$REQ_PATH" ]]; then
  echo "ERROR: $REQ_PATH not found"
  exit 1
fi
echo "Installing from $REQUIREMENTS_FILE..."
"$VENV_DIR/bin/pip" install -r "$REQ_PATH" -q

# Alembic migrations (export only DATABASE_URL; do not source full .env - CORS_ORIGINS etc. have shell-special chars)
if grep -q '^DATABASE_URL=' /etc/project_inside/backend.env 2>/dev/null; then
  DATABASE_URL=$(grep '^DATABASE_URL=' /etc/project_inside/backend.env | sed 's/^DATABASE_URL=//')
  export DATABASE_URL
fi
cd "$BACKEND_DIR"
echo "Running migrations..."
"$VENV_DIR/bin/alembic" upgrade head

# Systemd unit (use actual repo path; repo may be in /root/project_inside or /opt/project_inside)
sed "s|/opt/project_inside|$REPO_ROOT|g" "$REPO_ROOT/deploy/backend.service" | $SUDO tee /etc/systemd/system/project_inside_backend.service > /dev/null
$SUDO systemctl daemon-reload
$SUDO systemctl enable project_inside_backend.service
$SUDO systemctl restart project_inside_backend.service

echo "=== Backend install complete ==="
echo "  Venv: $VENV_DIR"
echo "  Service: project_inside_backend.service (port 8000)"
$SUDO systemctl status project_inside_backend.service --no-pager || true
