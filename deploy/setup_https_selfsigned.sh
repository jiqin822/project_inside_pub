#!/usr/bin/env bash
# Setup HTTPS with self-signed certificate (for testing only)
# Browsers will show a security warning, but microphone will work
# Usage: sudo ./deploy/setup_https_selfsigned.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUDO=""
[[ $(id -u) -ne 0 ]] && SUDO="sudo"

echo "=== Setting up HTTPS with self-signed certificate (testing only) ==="

# Create cert directory
CERT_DIR="/etc/nginx/ssl"
$SUDO mkdir -p "$CERT_DIR"

# Generate self-signed certificate if it doesn't exist
if [[ ! -f "$CERT_DIR/project_inside.crt" ]] || [[ ! -f "$CERT_DIR/project_inside.key" ]]; then
  echo "Generating self-signed certificate..."
  $SUDO openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERT_DIR/project_inside.key" \
    -out "$CERT_DIR/project_inside.crt" \
    -subj "/C=US/ST=State/L=City/O=Project Inside/CN=localhost" \
    -addext "subjectAltName=IP:127.0.0.1,DNS:localhost"
  
  $SUDO chmod 600 "$CERT_DIR/project_inside.key"
  $SUDO chmod 644 "$CERT_DIR/project_inside.crt"
fi

# Get server IP (for subjectAltName)
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "127.0.0.1")
echo "Detected server IP: $SERVER_IP"

# Update Nginx config for HTTPS
NGINX_CONF="/etc/nginx/sites-available/project_inside"
if [[ -f "$NGINX_CONF" ]]; then
  $SUDO cp "$NGINX_CONF" "$NGINX_CONF.backup"
  
  $SUDO tee "$NGINX_CONF" > /dev/null <<EOF
# Nginx config for host (no Docker) with HTTPS (self-signed)
# HTTP -> HTTPS redirect
server {
    listen 80 default_server;
    server_name _;
    return 301 https://\$host\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2 default_server;
    server_name _;
    root /var/www/project_inside;
    index index.html;

    # Self-signed SSL certificates
    ssl_certificate $CERT_DIR/project_inside.crt;
    ssl_certificate_key $CERT_DIR/project_inside.key;
    
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

# Test and reload Nginx
echo "Testing Nginx configuration..."
$SUDO nginx -t
$SUDO systemctl reload nginx

echo "=== HTTPS setup complete (self-signed) ==="
echo "  Site: https://$SERVER_IP"
echo "  HTTP redirects to HTTPS automatically"
echo ""
echo "WARNING: Browsers will show a security warning because this is a self-signed certificate."
echo "  - Chrome/Edge: Click 'Advanced' -> 'Proceed to $SERVER_IP (unsafe)'"
echo "  - Safari: Click 'Show Details' -> 'visit this website'"
echo "  - Firefox: Click 'Advanced' -> 'Accept the Risk and Continue'"
echo ""
echo "For production, use Let's Encrypt with a domain:"
echo "  sudo ./deploy/setup_https.sh your-domain.com"
