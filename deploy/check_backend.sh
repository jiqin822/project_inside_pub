#!/usr/bin/env bash
# Check backend connectivity and configuration
# Usage: sudo ./deploy/check_backend.sh

set -e

SUDO=""
[[ $(id -u) -ne 0 ]] && SUDO="sudo"

echo "=== Backend Connectivity Check ==="
echo ""

# Check backend service status
echo "1. Backend service status:"
$SUDO systemctl status project_inside_backend.service --no-pager -l || echo "  ⚠️  Service not running or not found"
echo ""

# Check backend logs (last 20 lines)
echo "2. Recent backend logs:"
$SUDO journalctl -u project_inside_backend.service -n 20 --no-pager || echo "  ⚠️  No logs found"
echo ""

# Check if backend is listening on port 8000
echo "3. Backend listening on port 8000:"
if netstat -tuln 2>/dev/null | grep -q ":8000 " || ss -tuln 2>/dev/null | grep -q ":8000 "; then
  echo "  ✅ Port 8000 is listening"
else
  echo "  ❌ Port 8000 is NOT listening"
fi
echo ""

# Test backend health endpoint directly
echo "4. Testing backend health endpoint (direct):"
if curl -s http://127.0.0.1:8000/v1/health > /dev/null 2>&1; then
  echo "  ✅ Backend responds at http://127.0.0.1:8000/v1/health"
  curl -s http://127.0.0.1:8000/v1/health | head -5
else
  echo "  ❌ Backend does NOT respond at http://127.0.0.1:8000/v1/health"
fi
echo ""

# Check Nginx status
echo "5. Nginx status:"
$SUDO systemctl status nginx --no-pager -l | head -10 || echo "  ⚠️  Nginx not running"
echo ""

# Test Nginx proxy
echo "6. Testing Nginx proxy to backend:"
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "127.0.0.1")
if curl -s "http://$SERVER_IP/v1/health" > /dev/null 2>&1; then
  echo "  ✅ Nginx proxies to backend at http://$SERVER_IP/v1/health"
  curl -s "http://$SERVER_IP/v1/health" | head -5
else
  echo "  ❌ Nginx does NOT proxy to backend at http://$SERVER_IP/v1/health"
fi
echo ""

# Check CORS settings
echo "7. CORS configuration:"
if [[ -f /etc/project_inside/backend.env ]]; then
  CORS_ORIGINS=$(grep "^CORS_ORIGINS=" /etc/project_inside/backend.env 2>/dev/null | cut -d= -f2- || echo "")
  if [[ -n "$CORS_ORIGINS" ]]; then
    echo "  CORS_ORIGINS=$CORS_ORIGINS"
  else
    echo "  ⚠️  CORS_ORIGINS not set in /etc/project_inside/backend.env"
  fi
else
  echo "  ⚠️  /etc/project_inside/backend.env not found"
fi
echo ""

# Check frontend build VITE_API_BASE_URL
echo "8. Frontend build configuration:"
if [[ -f /var/www/project_inside/index.html ]]; then
  # Try to extract VITE_API_BASE_URL from built files
  if grep -q "VITE_API_BASE_URL" /var/www/project_inside/index.html 2>/dev/null || grep -q "164.92.87.236" /var/www/project_inside/index.html 2>/dev/null; then
    echo "  ✅ Frontend files found at /var/www/project_inside"
    echo "  Check browser console for actual VITE_API_BASE_URL value"
  else
    echo "  ⚠️  Frontend files found but API URL not detected in HTML"
  fi
else
  echo "  ❌ Frontend files not found at /var/www/project_inside"
fi
echo ""

# Check Nginx configuration
echo "9. Nginx configuration:"
NGINX_CONF="/etc/nginx/sites-available/project_inside"
if [[ -f "$NGINX_CONF" ]]; then
  echo "  ✅ Nginx config found at $NGINX_CONF"
  echo "  Proxy settings:"
  grep -A 5 "location /v1/" "$NGINX_CONF" | head -6 || echo "    ⚠️  /v1/ location not found"
else
  echo "  ⚠️  Nginx config not found at $NGINX_CONF"
fi
echo ""

echo "=== Summary ==="
echo "If backend is not responding:"
echo "  1. Check logs: sudo journalctl -u project_inside_backend.service -f"
echo "  2. Restart backend: sudo systemctl restart project_inside_backend.service"
echo ""
echo "If CORS errors:"
echo "  1. Update CORS_ORIGINS in /etc/project_inside/backend.env"
echo "  2. Restart backend: sudo systemctl restart project_inside_backend.service"
echo ""
echo "If frontend can't connect:"
echo "  1. Rebuild frontend with correct VITE_API_BASE_URL"
echo "  2. Ensure backend is accessible at the URL specified in VITE_API_BASE_URL"
