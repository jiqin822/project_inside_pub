#!/bin/bash

echo "=== Checking Backend Server Status ==="
echo ""

# Check if backend is running on port 8000
echo "1. Checking if backend is running on port 8000..."
if lsof -i :8000 > /dev/null 2>&1; then
    echo "   ✓ Backend is running on port 8000"
    lsof -i :8000 | grep LISTEN
else
    echo "   ✗ Backend is NOT running on port 8000"
    echo "   → Start it with: cd backend && make dev"
fi

echo ""
echo "2. Testing backend health endpoint..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✓ Backend responds at http://localhost:8000"
    curl -s http://localhost:8000/health | head -3
else
    echo "   ✗ Backend does not respond at http://localhost:8000"
fi

echo ""
echo "3. Finding your local IP address..."
# Try different methods to get IP
if command -v ipconfig > /dev/null 2>&1; then
    # macOS
    IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "Not found")
elif command -v hostname > /dev/null 2>&1; then
    # Linux alternative
    IP=$(hostname -I | awk '{print $1}' 2>/dev/null || echo "Not found")
else
    IP="Unable to determine"
fi

if [ "$IP" != "Not found" ] && [ "$IP" != "Unable to determine" ]; then
    echo "   Your local IP: $IP"
    echo "   → Use this in Flutter: --dart-define=API_BASE_URL=http://$IP:8000"
    
    echo ""
    echo "4. Testing backend from network IP..."
    if curl -s http://$IP:8000/health > /dev/null 2>&1; then
        echo "   ✓ Backend responds at http://$IP:8000"
    else
        echo "   ✗ Backend does NOT respond at http://$IP:8000"
        echo "   → Make sure backend is started with: uvicorn app.main:app --host 0.0.0.0 --port 8000"
    fi
else
    echo "   Could not determine IP automatically"
    echo "   → Check your network settings or use: ifconfig | grep 'inet '"
fi

echo ""
echo "5. Checking port 8005 (voiceprint-api)..."
if lsof -i :8005 > /dev/null 2>&1; then
    echo "   ⚠ Port 8005 is already in use (voiceprint-api conflict)"
    echo "   → Stop the existing service or change the port in docker-compose.yml"
    lsof -i :8005 | head -3
else
    echo "   ✓ Port 8005 is available"
fi

echo ""
echo "=== Summary ==="
echo "If backend is running, use one of these URLs in Flutter:"
echo "  - http://localhost:8000 (for simulator)"
echo "  - http://$IP:8000 (for physical device)"
echo ""
echo "Current Flutter config uses: http://192.168.86.241:8000"
echo "If that doesn't work, try: http://$IP:8000"
