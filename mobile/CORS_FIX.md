# CORS Fix Applied

## Problem
OPTIONS preflight requests were getting 400 Bad Request because:
1. Backend CORS configuration didn't handle `192.168.*.*` wildcard patterns
2. FastAPI's CORSMiddleware doesn't support wildcard patterns directly

## Solution

### Backend Fix (`backend/app/main.py`)
- ✅ Changed CORS configuration to use `allow_origin_regex` for wildcard support
- ✅ Regex pattern matches:
  - `http://localhost:PORT` or `https://localhost:PORT`
  - `http://127.0.0.1:PORT` or `https://127.0.0.1:PORT`
  - `http://192.168.X.X:PORT` or `https://192.168.X.X:PORT`
- ✅ Explicitly allows `OPTIONS` method for preflight requests

### API Service (`mobile/services/apiService.ts`)
- ✅ Already correctly configured:
  - Uses correct endpoint paths (`/auth/login`, `/auth/signup`)
  - Sets `mode: 'cors'` for CORS requests
  - Sets `credentials: 'include'` for cookie/token support
  - Properly sets `Content-Type: application/json` for POST requests

## Testing

After restarting the backend server:
1. ✅ OPTIONS preflight requests should succeed (200 OK)
2. ✅ POST requests to `/v1/auth/login` and `/v1/auth/signup` should work
3. ✅ CORS headers should be properly set
4. ✅ Requests from iPhone (192.168.X.X) should be allowed

## Next Steps

1. **Restart backend server** to apply CORS changes:
   ```bash
   cd backend
   # Stop current server (Ctrl+C)
   make dev
   ```

2. **Test the mobile app** - login/signup should now work without CORS errors

3. **If still having issues**, check:
   - Backend logs for CORS errors
   - Browser console for specific error messages
   - That `VITE_API_BASE_URL` in `.env.local` matches your backend IP
