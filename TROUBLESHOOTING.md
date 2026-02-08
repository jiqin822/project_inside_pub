# Troubleshooting: "No Internet" Error

## Problem
When trying to signup/login, you get a "No internet connection" error even though you have internet.

## Root Cause
This usually means the Flutter app cannot reach the backend server at the configured IP address.

## Quick Fix Steps

### 1. Check if Backend Server is Running

```bash
cd backend
make dev
```

The server should start and show:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Find Your Current IP Address

Run the helper script:
```bash
./check_server.sh
```

Or manually:
```bash
# macOS
ipconfig getifaddr en0
# or
ipconfig getifaddr en1

# Linux
hostname -I | awk '{print $1}'
```

### 3. Update Flutter App with Correct IP

Once you have your IP (e.g., `192.168.86.241`), run Flutter with:

```bash
cd client
flutter run --dart-define=API_BASE_URL=http://YOUR_IP:8000
```

**For iOS Simulator**, use:
```bash
flutter run -d "iPhone Simulator" --dart-define=API_BASE_URL=http://localhost:8000
```

**For Physical Device**, use your network IP:
```bash
flutter run --dart-define=API_BASE_URL=http://192.168.86.241:8000
```

### 4. Verify Backend is Accessible

Test from your computer:
```bash
curl http://localhost:8000/health
# Should return: {"status":"ok","version":"0.1.0"}

# Test from network IP (replace with your IP)
curl http://192.168.86.241:8000/health
```

### 5. Check Backend CORS Settings

Make sure your backend `settings.py` or `.env` has:
```python
CORS_ORIGINS=["http://localhost:*", "http://127.0.0.1:*", "http://192.168.*.*:*"]
```

This allows connections from any 192.168.x.x IP address.

## Common Issues

### Issue: Port 8005 Already Allocated
**Solution**: Stop the existing voiceprint-api service:
```bash
# Find what's using port 8005
lsof -i :8005

# Kill it or stop docker container
docker stop project_inside_voiceprint_api
# or
kill -9 <PID>
```

### Issue: Backend Starts but Can't Connect
**Check**:
1. Backend is running on `0.0.0.0` (not `127.0.0.1`)
   - Should see: `--host 0.0.0.0` in the uvicorn command
2. Firewall is not blocking port 8000
3. You're on the same network (for physical device)

### Issue: IP Address Changed
If your IP changes (e.g., after reconnecting to WiFi), you need to:
1. Find new IP: `./check_server.sh`
2. Restart Flutter app with new IP

## Testing the Connection

### From Terminal:
```bash
# Test health endpoint
curl http://YOUR_IP:8000/health

# Test signup endpoint (should fail with validation, not connection)
curl -X POST http://YOUR_IP:8000/v1/admin/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","full_name":"Test User"}'
```

### From Flutter App:
The error message should now show the exact URL it's trying to connect to, making debugging easier.

## Quick Reference

**Start Backend:**
```bash
cd backend
make dev
```

**Find IP:**
```bash
./check_server.sh
```

**Run Flutter (Simulator):**
```bash
cd client
flutter run -d "iPhone Simulator" --dart-define=API_BASE_URL=http://localhost:8000
```

**Run Flutter (Physical Device):**
```bash
cd client
flutter run --dart-define=API_BASE_URL=http://YOUR_IP:8000
```
