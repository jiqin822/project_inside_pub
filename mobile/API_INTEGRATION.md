# Mobile App API Integration

This document describes the API integration for the mobile TypeScript/React app.

## API Service Layer

Created `services/apiService.ts` - A centralized API service that handles:
- Authentication token management
- All backend API calls
- Error handling
- Token refresh

## Backend API Endpoints Wired

### Authentication
- ✅ `POST /v1/auth/signup` - User registration
- ✅ `POST /v1/auth/login` - User login
- ✅ `POST /v1/auth/refresh` - Token refresh

### User Management
- ✅ `GET /v1/users/me` - Get current user profile
- ✅ `PATCH /v1/users/me` - Update user profile

### Activities
- ✅ `GET /v1/coach/activities/suggestions?rid={relationshipId}` - Get activity suggestions

### Other Endpoints Available (Not Yet Wired)
- `GET /v1/relationships` - List relationships
- `POST /v1/relationships` - Create relationship
- `DELETE /v1/relationships/{id}` - Delete relationship
- `POST /v1/coach/sessions` - Create session
- `POST /v1/coach/sessions/{id}/finalize` - Finalize session
- `GET /v1/coach/sessions/{id}/report` - Get session report
- `GET /v1/history/sessions` - Get session history
- `POST /v1/interaction/pokes` - Send poke
- `GET /v1/interaction/pokes?rid={relationshipId}` - Get pokes
- `GET /v1/onboarding/status` - Get onboarding status
- `POST /v1/onboarding/complete` - Complete onboarding step

## Components Updated

1. **AuthScreen** (`components/AuthScreen.tsx`)
   - Now uses `apiService.signup()` and `apiService.login()`
   - Removed localStorage-based authentication
   - Tokens are stored automatically by apiService

2. **App.tsx**
   - Updated to fetch user profile from backend on mount
   - `handleLoginSuccess` now fetches user from backend
   - Removed localStorage user loading

3. **ActivitiesMode** (`components/ActivitiesMode.tsx`)
   - `handleGenerateQuests` now tries backend API first
   - Falls back to Gemini service if backend fails or no relationship selected

4. **EditProfile** (`components/EditProfile.tsx`)
   - `handleSave` now calls `apiService.updateProfile()`
   - Refreshes user data from backend after update

## Configuration

Set the API base URL via environment variable:
```bash
VITE_API_BASE_URL=http://localhost:8000
```

Or it defaults to `http://localhost:8000`.

## Token Management

- Access tokens are stored in localStorage as `access_token`
- Refresh tokens are stored in localStorage as `refresh_token`
- Tokens are automatically included in API requests via Authorization header
- Use `apiService.clearTokens()` to logout

## Next Steps

To fully wire the mobile app:
1. Wire relationships API for loved ones management
2. Wire rewards/marketplace API endpoints
3. Wire session management for live coaching
4. Wire pokes API for interactions
5. Wire onboarding API for onboarding flow
