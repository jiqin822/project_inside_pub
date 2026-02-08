#!/usr/bin/env bash
# Setup HTTPS for Project Inside using Let's Encrypt (Certbot)
# Usage: sudo ./deploy/setup_https.sh <domain>
# Example: sudo ./deploy/setup_https.sh app.example.com

set -e

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <domain>"
  echo "Example: $0 app.example.com"
  exit 1
fi

DOMAIN="$1"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUDO=""
[[ $(id -u) -ne 0 ]] && SUDO="sudo"

echo "=== Setting up HTTPS for $DOMAIN ==="

# Install certbot if not present
if ! command -v certbot &>/dev/null; then
  echo "Installing certbot..."
  if command -v apt-get &>/dev/null; then
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq certbot python3-certbot-nginx
  elif command -v yum &>/dev/null; then
    $SUDO yum install -y certbot python3-certbot-nginx 2>/dev/null || $SUDO dnf install -y certbot python3-certbot-nginx
  else
    echo "ERROR: Could not install certbot. Install certbot and python3-certbot-nginx manually."
    exit 1
  fi
fi

# Ensure Nginx is running
if ! systemctl is-active --quiet nginx; then
  echo "Starting Nginx..."
  $SUDO systemctl start nginx
fi

# Get certificate (certbot will modify nginx config automatically)
echo "Obtaining SSL certificate for $DOMAIN..."
$SUDO certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" --redirect

# Create HTTPS-enabled nginx config if it doesn't exist
NGINX_CONF="/etc/nginx/sites-available/project_inside"
if [[ -f "$NGINX_CONF" ]]; then
  # Backup original
  $SUDO cp "$NGINX_CONF" "$NGINX_CONF.backup"
  
  # Check if HTTPS is already configured
  if ! grep -q "listen 443" "$NGINX_CONF"; then
    echo "Updating Nginx config for HTTPS..."
    # Create HTTPS version
    $SUDO tee "$NGINX_CONF" > /dev/null <<EOF
# Nginx config for host (no Docker) with HTTPS
# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    root /var/www/project_inside;
    index index.html;

    # SSL certificates (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /v1/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /v1/stt/stream/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
    location /v1/stt-v2/stream/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }

    location /v1/sessions/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }

    location /v1/interaction/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
    }
}
EOF
  fi
fi

# Test and reload Nginx
echo "Testing Nginx configuration..."
$SUDO nginx -t
$SUDO systemctl reload nginx

# Setup auto-renewal (certbot usually does this automatically, but ensure it's enabled)
if ! systemctl is-enabled --quiet certbot.timer 2>/dev/null; then
  echo "Enabling certbot auto-renewal..."
  $SUDO systemctl enable certbot.timer 2>/dev/null || true
  $SUDO systemctl start certbot.timer 2>/dev/null || true
fi

echo "=== HTTPS setup complete ==="
echo "  Site: https://$DOMAIN"
echo "  HTTP redirects to HTTPS automatically"
echo "  Certificate auto-renews via certbot"
echo ""
echo "IMPORTANT: Update your frontend build with the HTTPS URL:"
echo "  cd $REPO_ROOT/mobile"
echo "  VITE_API_BASE_URL=https://$DOMAIN npm run build"
echo "  sudo cp -r dist/. /var/www/project_inside/"
