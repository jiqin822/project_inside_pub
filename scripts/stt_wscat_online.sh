#!/usr/bin/env bash
# STT WebSocket test: login (get JWT), create session, connect with wscat.
# Uses se-ai.live and dev family Sam's credentials by default.
# Requires: curl, jq, wscat (npm install -g wscat)
set -e

BASE_URL="${BASE_URL:-https://se-ai.live}"
EMAIL="${EMAIL:-sam.rivera@demo.inside.app}"
PASSWORD="${PASSWORD:-DemoFamily2025!}"
# v1 or v2 (stream path only; session is always created via /v1/stt/session)
STT_VERSION="${STT_VERSION:-v2}"

echo "Using BASE_URL=$BASE_URL EMAIL=$EMAIL STT_VERSION=$STT_VERSION"

# 1. Login and get access_token
echo "Logging in..."
RESP=$(curl -s -X POST "$BASE_URL/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
TOKEN=$(echo "$RESP" | jq -r '.access_token')
if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "Login failed. Response: $RESP"
  exit 1
fi
echo "Got JWT (length ${#TOKEN})"

# 2. Create STT session
echo "Creating STT session..."
SESS_RESP=$(curl -s -X POST "$BASE_URL/v1/stt/session" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"candidate_user_ids":[]}')
SESSION_ID=$(echo "$SESS_RESP" | jq -r '.session_id')
if [[ -z "$SESSION_ID" || "$SESSION_ID" == "null" ]]; then
  echo "Create session failed. Response: $SESS_RESP"
  exit 1
fi
echo "Session ID: $SESSION_ID"

# 3. WebSocket URL and connect
WS_BASE="${BASE_URL/https/wss}"
WS_BASE="${WS_BASE/http/ws}"
if [[ "$STT_VERSION" == "v2" ]]; then
  STREAM_PATH="/v1/stt-v2/stream"
else
  STREAM_PATH="/v1/stt/stream"
fi
WS_URL="${WS_BASE}${STREAM_PATH}/${SESSION_ID}?token=${TOKEN}"
echo "Connecting to STT WebSocket..."
echo "URL (token redacted): ${WS_BASE}${STREAM_PATH}/${SESSION_ID}?token=..."
exec wscat -c "$WS_URL"
