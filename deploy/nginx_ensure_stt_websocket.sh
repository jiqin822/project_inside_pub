#!/usr/bin/env bash
# Ensure Nginx has WebSocket proxy for /v1/stt/stream/ and /v1/stt-v2/stream/ (fixes 405 on Live Coach).
# Run on the VM: cd /opt/project_inside && sudo ./deploy/nginx_ensure_stt_websocket.sh
# Edits every project_inside config (including certbot's -le-ssl.conf if present) so HTTPS also gets the STT locations.
set -e

SUDO=""
[[ $(id -u) -ne 0 ]] && SUDO="sudo"

SNIPPET=$(mktemp)
trap 'rm -f "$SNIPPET"' EXIT
cat > "$SNIPPET" <<'SNIP'
    # STT and STT v2 WebSocket (required for Live Coach)
    location /v1/stt/stream/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
    location /v1/stt-v2/stream/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
SNIP

# All configs that may define server blocks for this app (including certbot SSL-only file)
CONFIGS=(
  /etc/nginx/sites-available/project_inside
  /etc/nginx/sites-available/project_inside-le-ssl.conf
  /etc/nginx/conf.d/project_inside.conf
)
MODIFIED=0
FOUND=0
for CONF in "${CONFIGS[@]}"; do
  if [[ ! -f "$CONF" ]]; then
    continue
  fi
  FOUND=1
  # Only add if this file has a server block that proxies /v1/ to the backend
  if ! grep -q "location /v1/" "$CONF" 2>/dev/null; then
    continue
  fi
  echo "Ensuring STT WebSocket locations in $CONF"
  NEWCONF=$(mktemp)
  trap 'rm -f "$SNIPPET" "$NEWCONF"' EXIT
  $SUDO awk -v snippet="$SNIPPET" '
    function emit_snippet() {
      while ((getline line < snippet) > 0) print line
      close(snippet)
    }
    /^[[:space:]]*server[[:space:]]*\{/ {
      in_server = 1
      depth = 1
      has_v1 = 0
      has_stt = 0
      print
      next
    }
    {
      line = $0
      if (in_server) {
        if (line ~ /location \/v1\//) has_v1 = 1
        if (line ~ /location \/v1\/stt\/stream\//) has_stt = 1
        linecopy = line
        opens = gsub(/\{/, "", linecopy)
        closes = gsub(/\}/, "", linecopy)
        new_depth = depth + opens - closes
        if (new_depth == 0) {
          if (has_v1 && !has_stt) emit_snippet()
          in_server = 0
        }
        depth = new_depth
      }
      print
    }
  ' "$CONF" > "$NEWCONF"
  if ! $SUDO cmp -s "$NEWCONF" "$CONF"; then
    $SUDO cp "$NEWCONF" "$CONF"
    MODIFIED=1
  else
    echo "STT WebSocket locations already present in $CONF"
  fi
  rm -f "$NEWCONF"
done

if [[ $FOUND -eq 0 ]]; then
  echo "No project_inside Nginx config found. Run setup_https.sh <domain> first."
  exit 1
fi
if [[ $MODIFIED -eq 1 ]]; then
  $SUDO nginx -t && $SUDO systemctl reload nginx
  echo "Done. Live Coach STT WebSocket should work now."
else
  $SUDO nginx -t && $SUDO systemctl reload nginx
fi
