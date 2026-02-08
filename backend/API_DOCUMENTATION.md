# Backend API Documentation

## Overview

This document provides comprehensive documentation for all backend APIs in the Project Inside application.

**Base URL**: `http://localhost:8000` (development)  
**API Version**: `v1`  
**API Prefix**: `/v1`

## Authentication

Most endpoints require authentication using JWT Bearer tokens. Include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

### Token Types

- **Access Token**: Short-lived (15 minutes default), used for API requests
- **Refresh Token**: Long-lived (30 days default), used to obtain new access tokens

### Public Endpoints

The following endpoints do not require authentication:
- `GET /health`
- `POST /v1/auth/signup`
- `POST /v1/auth/login`
- `POST /v1/auth/refresh`

---

## Table of Contents

1. [Health Check](#health-check)
2. [Authentication](#authentication-endpoints)
3. [Users](#users-endpoints)
4. [Relationships](#relationships-endpoints)
5. [Onboarding](#onboarding-endpoints)
6. [Contacts](#contacts-endpoints)
7. [Consent](#consent-endpoints)
8. [Sessions](#sessions-endpoints)
9. [Activities](#activities-endpoints)
10. [Reports](#reports-endpoints)
11. [Pokes (Nudges)](#pokes-endpoints)
12. [Voice](#voice-endpoints)
13. [WebSocket](#websocket-endpoints)
14. [History](#history-endpoints)
15. [Devices](#devices-endpoints)

---

## Health Check

### GET /health

Check API health status.

**Authentication**: Not required

**Response**:
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## Authentication Endpoints

### POST /v1/auth/signup

Register a new user account.

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "display_name": "John Doe"  // Optional
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Responses**:
- `400 Bad Request`: Email already registered
- `422 Unprocessable Entity`: Invalid request format

**Example**:
```bash
curl -X POST http://localhost:8000/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "display_name": "John Doe"
  }'
```

---

### POST /v1/auth/login

Authenticate and receive access tokens.

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Responses**:
- `401 Unauthorized`: Incorrect email or password
- `403 Forbidden`: User account is inactive

**Example**:
```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

---

### POST /v1/auth/refresh

Refresh access token using refresh token.

**Authentication**: Not required

**Request Body**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Error Responses**:
- `401 Unauthorized`: Invalid refresh token

**Example**:
```bash
curl -X POST http://localhost:8000/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "your_refresh_token_here"
  }'
```

---

## Users Endpoints

### GET /v1/users/me

Get current authenticated user's profile.

**Authentication**: Required

**Response** (200 OK):
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "display_name": "John Doe",
  "pronouns": "he/him",
  "communication_style": "BALANCED",  // GENTLE, BALANCED, or DIRECT
  "goals": ["improve_communication", "build_trust"],
  "privacy_tier": "STANDARD"
}
```

**Example**:
```bash
curl -X GET http://localhost:8000/v1/users/me \
  -H "Authorization: Bearer <access_token>"
```

---

### PATCH /v1/users/me

Update current user's profile.

**Authentication**: Required

**Request Body** (all fields optional):
```json
{
  "display_name": "John Doe",
  "pronouns": "he/him",
  "communication_style": "BALANCED",  // GENTLE, BALANCED, or DIRECT
  "goals": ["improve_communication", "build_trust"],
  "privacy_tier": "STANDARD"
}
```

**Response** (200 OK):
```json
{
  "id": "user_123",
  "email": "user@example.com",
  "display_name": "John Doe",
  "pronouns": "he/him",
  "communication_style": "BALANCED",
  "goals": ["improve_communication", "build_trust"],
  "privacy_tier": "STANDARD"
}
```

**Example**:
```bash
curl -X PATCH http://localhost:8000/v1/users/me \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "John Doe",
    "pronouns": "he/him",
    "communication_style": "BALANCED"
  }'
```

---

## Relationships Endpoints

### POST /v1/relationships

Create a new relationship.

**Authentication**: Required

**Request Body**:
```json
{
  "type": "romantic",  // romantic, family, friendship, professional
  "member_ids": ["user_123", "user_456"]
}
```

**Response** (200 OK):
```json
{
  "id": "rel_789",
  "type": "romantic",
  "status": "PENDING"  // PENDING, ACTIVE, INACTIVE
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/v1/relationships \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "romantic",
    "member_ids": ["user_123", "user_456"]
  }'
```

---

### GET /v1/relationships

List all relationships for the current user.

**Authentication**: Required

**Response** (200 OK):
```json
[
  {
    "id": "rel_789",
    "type": "romantic",
    "status": "ACTIVE"
  },
  {
    "id": "rel_790",
    "type": "friendship",
    "status": "PENDING"
  }
]
```

**Example**:
```bash
curl -X GET http://localhost:8000/v1/relationships \
  -H "Authorization: Bearer <access_token>"
```

---

### POST /v1/relationships/{relationship_id}/invites

Create and send an invite for a relationship.

**Authentication**: Required

**Path Parameters**:
- `relationship_id` (string): The relationship ID

**Request Body**:
```json
{
  "email": "invitee@example.com",
  "role": "partner",  // Optional
  "message": "Join me on Project Inside!"  // Optional
}
```

**Response** (200 OK):
```json
{
  "invite_id": "inv_123",
  "status": "PENDING",
  "expires_at": "2026-02-27T00:00:00Z"
}
```

**Error Responses**:
- `403 Forbidden`: User is not a member of this relationship

**Example**:
```bash
curl -X POST http://localhost:8000/v1/relationships/rel_789/invites \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "invitee@example.com",
    "role": "partner",
    "message": "Join me on Project Inside!"
  }'
```

---

### GET /v1/relationships/{relationship_id}/invites

Get all invites for a relationship.

**Authentication**: Required

**Path Parameters**:
- `relationship_id` (string): The relationship ID

**Response** (200 OK):
```json
[
  {
    "invite_id": "inv_123",
    "email": "invitee@example.com",
    "role": "partner",
    "status": "PENDING",
    "expires_at": "2026-02-27T00:00:00Z",
    "created_at": "2026-01-27T00:00:00Z"
  }
]
```

**Error Responses**:
- `403 Forbidden`: User is not a member of this relationship

**Example**:
```bash
curl -X GET http://localhost:8000/v1/relationships/rel_789/invites \
  -H "Authorization: Bearer <access_token>"
```

---

### DELETE /v1/relationships/{relationship_id}

Delete a relationship.

**Authentication**: Required

**Path Parameters**:
- `relationship_id` (string): The relationship ID

**Response** (200 OK):
```json
{
  "ok": true
}
```

**Error Responses**:
- `400 Bad Request`: Cannot delete relationship (e.g., user is not creator)
- `403 Forbidden`: User is not authorized to delete this relationship

**Example**:
```bash
curl -X DELETE http://localhost:8000/v1/relationships/rel_789 \
  -H "Authorization: Bearer <access_token>"
```

---

## Onboarding Endpoints

### GET /v1/onboarding/status

Get onboarding status and determine next step.

**Authentication**: Required

**Response** (200 OK):
```json
{
  "has_profile": true,
  "has_voiceprint": false,
  "pending_invites": 2,
  "active_relationships": 1,
  "next_step": "voice_enrollment"  // or null if complete
}
```

**Possible next_step values**:
- `profile` - Complete user profile
- `voice_enrollment` - Complete voice enrollment
- `invite_contacts` - Invite contacts to relationships
- `null` - Onboarding complete

**Example**:
```bash
curl -X GET http://localhost:8000/v1/onboarding/status \
  -H "Authorization: Bearer <access_token>"
```

---

### POST /v1/onboarding/complete

Mark an onboarding step as complete.

**Authentication**: Required

**Request Body**:
```json
{
  "step": "profile"  // profile, voice_enrollment, invite_contacts
}
```

**Response** (200 OK):
```json
{
  "ok": true
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/v1/onboarding/complete \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "step": "profile"
  }'
```

---

## Contacts Endpoints

### POST /v1/contacts/lookup

Lookup a contact by email address.

**Authentication**: Required

**Request Body**:
```json
{
  "email": "contact@example.com"
}
```

**Response** (200 OK):
```json
{
  "status": "EXISTS",  // EXISTS, NOT_FOUND, or BLOCKED
  "user": {
    "id": "user_123",
    "display_name": "Jane Doe"
  }
}
```

**Status Values**:
- `EXISTS`: User found and can be invited
- `NOT_FOUND`: Email not registered
- `BLOCKED`: Email domain is blocked

**Example**:
```bash
curl -X POST http://localhost:8000/v1/contacts/lookup \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "contact@example.com"
  }'
```

---

## Consent Endpoints

### GET /v1/relationships/{relationship_id}/consent/templates

Get available consent templates for a relationship.

**Authentication**: Required

**Path Parameters**:
- `relationship_id` (string): The relationship ID

**Response** (200 OK):
```json
[
  {
    "template_id": "basic",
    "title": "Basic Consent",
    "description": "Standard consent for relationship features",
    "scopes": ["read_profile", "send_nudges"]
  },
  {
    "template_id": "full",
    "title": "Full Consent",
    "description": "Complete access to all features",
    "scopes": ["read_profile", "send_nudges", "view_sessions", "view_reports"]
  }
]
```

**Example**:
```bash
curl -X GET http://localhost:8000/v1/relationships/rel_789/consent/templates \
  -H "Authorization: Bearer <access_token>"
```

---

### PUT /v1/relationships/{relationship_id}/consent/me

Update consent settings for the current user in a relationship.

**Authentication**: Required

**Path Parameters**:
- `relationship_id` (string): The relationship ID

**Request Body**:
```json
{
  "scopes": ["read_profile", "send_nudges", "view_sessions"],
  "status": "ACTIVE"  // ACTIVE or INACTIVE
}
```

**Response** (200 OK):
```json
{
  "ok": true,
  "version": 2
}
```

**Example**:
```bash
curl -X PUT http://localhost:8000/v1/relationships/rel_789/consent/me \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "scopes": ["read_profile", "send_nudges"],
    "status": "ACTIVE"
  }'
```

---

### GET /v1/relationships/{relationship_id}/consent

Get consent information for all members of a relationship.

**Authentication**: Required

**Path Parameters**:
- `relationship_id` (string): The relationship ID

**Response** (200 OK):
```json
{
  "relationship_status": "ACTIVE",
  "members": [
    {
      "user_id": "user_123",
      "member_status": "ACTIVE",
      "consent_status": "ACTIVE",
      "scopes": ["read_profile", "send_nudges"]
    },
    {
      "user_id": "user_456",
      "member_status": "PENDING",
      "consent_status": "PENDING",
      "scopes": []
    }
  ]
}
```

**Example**:
```bash
curl -X GET http://localhost:8000/v1/relationships/rel_789/consent \
  -H "Authorization: Bearer <access_token>"
```

---

## Sessions Endpoints

### POST /v1/sessions

Create a new coaching session.

**Authentication**: Required

**Request Body**:
```json
{
  "relationship_id": "rel_789",
  "participants": ["user_123", "user_456"]  // Optional, defaults to relationship members
}
```

**Response** (200 OK):
```json
{
  "id": "session_123",
  "status": "ACTIVE"  // ACTIVE, FINALIZED, ARCHIVED
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/v1/sessions \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "relationship_id": "rel_789",
    "participants": ["user_123", "user_456"]
  }'
```

---

### POST /v1/sessions/{session_id}/finalize

Finalize a session and enqueue report generation.

**Authentication**: Required

**Path Parameters**:
- `session_id` (string): The session ID

**Response** (200 OK):
```json
{
  "ok": true
}
```

**Error Responses**:
- `403 Forbidden`: User is not a participant in this session

**Example**:
```bash
curl -X POST http://localhost:8000/v1/sessions/session_123/finalize \
  -H "Authorization: Bearer <access_token>"
```

---

### GET /v1/sessions/{session_id}/report

Get session report (may be pending if not yet generated).

**Authentication**: Required

**Path Parameters**:
- `session_id` (string): The session ID

**Response** (200 OK):
```json
{
  "sid": "session_123",
  "summary": "Session analysis summary...",
  "moments": [
    {
      "timestamp_ms": 5000,
      "type": "speaking_rate_high",
      "message": "Speaking rate was elevated"
    }
  ],
  "action_items": [
    "Practice active listening",
    "Take breaks during conversations"
  ]
}
```

**Error Responses**:
- `403 Forbidden`: User is not a participant in this session

**Example**:
```bash
curl -X GET http://localhost:8000/v1/sessions/session_123/report \
  -H "Authorization: Bearer <access_token>"
```

---

## Activities Endpoints

### GET /v1/activities/suggestions

Get activity suggestions for a relationship.

**Authentication**: Required

**Query Parameters**:
- `rid` (string, required): Relationship ID

**Response** (200 OK):
```json
[
  {
    "id": "activity_1",
    "title": "Daily Check-in",
    "description": "Spend 10 minutes each day checking in with each other"
  },
  {
    "id": "activity_2",
    "title": "Gratitude Exercise",
    "description": "Share three things you're grateful for"
  }
]
```

**Example**:
```bash
curl -X GET "http://localhost:8000/v1/activities/suggestions?rid=rel_789" \
  -H "Authorization: Bearer <access_token>"
```

---

## Reports Endpoints

### GET /v1/reports/{session_id}/report

Get session report (alternative endpoint).

**Authentication**: Required

**Path Parameters**:
- `session_id` (string): The session ID

**Response** (200 OK):
```json
{
  "sid": "session_123",
  "summary": "Session analysis summary...",
  "moments": [
    {
      "timestamp_ms": 5000,
      "type": "speaking_rate_high",
      "message": "Speaking rate was elevated"
    }
  ],
  "action_items": [
    {
      "item": "Practice active listening",
      "priority": "high"
    }
  ]
}
```

**Example**:
```bash
curl -X GET http://localhost:8000/v1/reports/session_123/report \
  -H "Authorization: Bearer <access_token>"
```

---

## Pokes Endpoints

### POST /v1/pokes

Send a poke (nudge) to another user in a relationship.

**Authentication**: Required

**Request Body**:
```json
{
  "relationship_id": "rel_789",
  "receiver_id": "user_456",
  "type": "love"  // love, miss_you, sorry, good_morning, good_night
}
```

**Response** (200 OK):
```json
{
  "id": "poke_123"
}
```

**Rate Limiting**: Maximum 1 poke per 10 seconds per (session_id, user_id)

**Example**:
```bash
curl -X POST http://localhost:8000/v1/pokes \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "relationship_id": "rel_789",
    "receiver_id": "user_456",
    "type": "love"
  }'
```

---

### GET /v1/pokes

List all pokes for a relationship.

**Authentication**: Required

**Query Parameters**:
- `rid` (string, required): Relationship ID

**Response** (200 OK):
```json
[
  {
    "id": "poke_123",
    "type": "love",
    "sender_id": "user_123",
    "receiver_id": "user_456",
    "created_at": "2026-01-27T12:00:00Z"
  }
]
```

**Example**:
```bash
curl -X GET "http://localhost:8000/v1/pokes?rid=rel_789" \
  -H "Authorization: Bearer <access_token>"
```

---

## Voice Endpoints

### POST /v1/voice/enrollment/start

Start a voice enrollment session.

**Authentication**: Required

**Response** (200 OK):
```json
{
  "enrollment_id": "enroll_123",
  "upload_url": null  // Optional, if direct upload URL is provided
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/v1/voice/enrollment/start \
  -H "Authorization: Bearer <access_token>"
```

---

### PUT /v1/voice/enrollment/{enrollment_id}/audio

Upload audio chunk for voice enrollment.

**Authentication**: Required

**Path Parameters**:
- `enrollment_id` (string): The enrollment ID

**Request**: Multipart form data
- `audio` (file): WAV audio file

**Response** (200 OK):
```json
{
  "ok": true
}
```

**Error Responses**:
- `403 Forbidden`: Enrollment does not belong to user
- `404 Not Found`: Enrollment not found

**Example**:
```bash
curl -X PUT http://localhost:8000/v1/voice/enrollment/enroll_123/audio \
  -H "Authorization: Bearer <access_token>" \
  -F "audio=@recording.wav"
```

---

### POST /v1/voice/enrollment/{enrollment_id}/complete

Complete voice enrollment and generate voice profile.

**Authentication**: Required

**Path Parameters**:
- `enrollment_id` (string): The enrollment ID

**Response** (200 OK):
```json
{
  "voice_profile_id": "profile_123",
  "quality_score": 0.85
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/v1/voice/enrollment/enroll_123/complete \
  -H "Authorization: Bearer <access_token>"
```

---

### POST /v1/voice/identify

Identify speaker from audio sample.

**Authentication**: Required

**Request**: Multipart form data
- `candidate_user_ids` (string): Comma-separated list of user IDs to match against
- `audio` (file): WAV audio file

**Response** (200 OK):
```json
{
  "user_id": "user_123",  // null if no match
  "similarity_score": 0.92
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/v1/voice/identify \
  -H "Authorization: Bearer <access_token>" \
  -F "candidate_user_ids=user_123,user_456" \
  -F "audio=@sample.wav"
```

---

## WebSocket Endpoints

### WebSocket /v1/sessions/{session_id}/ws

Real-time coaching session WebSocket connection.

**Authentication**: Required (via query parameter)

**Connection URL**:
```
ws://localhost:8000/v1/sessions/{session_id}/ws?token=<access_token>
```

**Path Parameters**:
- `session_id` (string): The session ID

**Query Parameters**:
- `token` (string, required): Access token

**Connection Requirements**:
- Session must be in `ACTIVE` status
- User must be a participant in the session

**Message Format**:

**Client → Server** (Feature Frame):
```json
{
  "type": "client.feature_frame",
  "sid": "session_123",
  "payload": {
    "timestamp_ms": 5000,
    "speaking_rate": 2.5,
    "overlap_ratio": 0.3
  }
}
```

**Server → Client** (Session State):
```json
{
  "type": "server.session_state",
  "sid": "session_123",
  "payload": {
    "sid": "session_123",
    "participants": ["user_123", "user_456"]
  }
}
```

**Server → Client** (Nudge):
```json
{
  "type": "server.nudge",
  "sid": "session_123",
  "payload": {
    "nudge_type": "slow_down",
    "message": "Consider slowing your speaking rate",
    "timestamp_ms": 5000
  }
}
```

**Server → Client** (Error):
```json
{
  "type": "server.error",
  "sid": "session_123",
  "payload": {
    "code": "BAD_REQUEST",
    "message": "Invalid message type"
  }
}
```

**Rate Limiting**: Maximum 1 nudge per 10 seconds per (session_id, user_id)

**Example** (JavaScript):
```javascript
const token = "your_access_token";
const sessionId = "session_123";
const ws = new WebSocket(`ws://localhost:8000/v1/sessions/${sessionId}/ws?token=${token}`);

ws.onopen = () => {
  console.log("Connected to session");
  
  // Send feature frame
  ws.send(JSON.stringify({
    type: "client.feature_frame",
    sid: sessionId,
    payload: {
      timestamp_ms: 5000,
      speaking_rate: 2.5,
      overlap_ratio: 0.3
    }
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Received:", message);
  
  if (message.type === "server.nudge") {
    // Handle nudge
    console.log("Nudge:", message.payload);
  }
};
```

---

## History Endpoints

### GET /v1/history/sessions

Get session history for the current user.

**Authentication**: Required

**Query Parameters**:
- `limit` (integer, optional): Number of sessions to return (default: 20, max: 100)

**Response** (200 OK):
```json
[
  {
    "id": "session_123",
    "relationship_id": "rel_789",
    "status": "FINALIZED",
    "created_at": "2026-01-27T12:00:00Z"
  }
]
```

**Example**:
```bash
curl -X GET "http://localhost:8000/v1/history/sessions?limit=10" \
  -H "Authorization: Bearer <access_token>"
```

---

## Devices Endpoints

### POST /v1/devices/push-token

Register push notification token for device.

**Authentication**: Required

**Request Body**:
```json
{
  "token": "device_push_token_here",
  "platform": "ios"  // "ios" or "android"
}
```

**Response** (200 OK):
```json
{
  "ok": true
}
```

**Note**: Currently logs the token (MVP). Full device management to be implemented.

**Example**:
```bash
curl -X POST http://localhost:8000/v1/devices/push-token \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "device_push_token_here",
    "platform": "ios"
  }'
```

---

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "detail": "Error message describing what went wrong"
}
```

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "User is not authorized to perform this action"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 422 Unprocessable Entity
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error"
}
```

---

## Rate Limiting

### Pokes (Nudges)
- **Limit**: 1 poke per 10 seconds per (session_id, user_id)
- **Storage**: Redis-based rate limiting
- **Behavior**: Rate-limited requests are silently ignored (no error returned)

---

## WebSocket Real-time Coaching

The real-time coaching engine analyzes feature frames and sends nudges based on:

### Speaking Rate Threshold
- **Default**: 2.0 words per second
- **Nudge**: Sent when speaking rate exceeds threshold
- **Configurable**: Via `SR_THRESHOLD` environment variable

### Overlap Ratio Threshold
- **Default**: 0.25 (25% overlap)
- **Nudge**: Sent when overlap ratio exceeds threshold
- **Configurable**: Via `OR_THRESHOLD` environment variable

### Nudge Types
- `slow_down`: Speaking rate too high
- `reduce_overlap`: Too much interruption/overlap
- `take_turn`: Opportunity to speak detected

---

## Configuration

Key environment variables:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: JWT signing key
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access token expiry (default: 15)
- `REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token expiry (default: 30)
- `CORS_ORIGINS`: Allowed CORS origins (comma-separated)
- `SR_THRESHOLD`: Speaking rate threshold for nudges (default: 2.0)
- `OR_THRESHOLD`: Overlap ratio threshold for nudges (default: 0.25)
- `VOICEPRINT_API_URL`: Voiceprint API service URL
- `STORE_FRAMES`: Store feature frames in database (default: false)

---

## Notes

- All timestamps are in ISO 8601 format (UTC)
- All IDs are UUIDs (string format)
- WebSocket connections require the session to be in `ACTIVE` status
- Session finalization enqueues a background job to generate the report
- Voice enrollment requires multiple audio uploads before completion
- Consent templates are relationship-type specific
- Relationship types: `romantic`, `family`, `friendship`, `professional`
- Communication styles: `GENTLE`, `BALANCED`, `DIRECT` (mapped from 0.0, 0.5, 1.0)

---

## Support

For issues or questions, refer to:
- Backend README: `/backend/README.md`
- API Contracts: `/contracts/api_contracts.md`
- WebSocket Messages: `/contracts/websocket_messages.json`
