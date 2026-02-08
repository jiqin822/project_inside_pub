# API Contracts

## Base URL
All API endpoints are versioned under `/v1`.

## Authentication
Most endpoints require JWT authentication via Bearer token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## WebSocket Connection
WebSocket endpoint: `ws://localhost:8000/v1/interaction/ws/session?token=<access_token>`

### Message Types

#### Nudge
Sent from server to client when a nudge is generated.
```json
{
  "type": "nudge",
  "nudge_type": "reminder",
  "payload": {
    "message": "Consider checking in with your partner",
    "priority": "medium"
  }
}
```

#### Poke
Sent from server to client when a user receives a poke.
```json
{
  "type": "poke",
  "payload": {
    "from_user_id": "user-123",
    "message": "You got a poke!"
  }
}
```

#### Acknowledgment
Sent from server to client as acknowledgment of received message.
```json
{
  "type": "ack",
  "message": { ... }
}
```

#### notification.new
Sent from server to client when a new notification is created for the user (e.g. via POST /v1/notifications, POST /v1/notifications/send-heart, or POST /v1/notifications/send-emotion). Delivered over the same WebSocket at `ws://.../v1/interaction/notifications?token=<access_token>`.

For `type: "emotion"`, the payload includes `sender_id`, `sender_name`, and `emotion_kind` so the client can show a tag on the sender's icon, send to watch for full-screen 5s, or show a push notification.
```json
{
  "type": "notification.new",
  "payload": {
    "id": "notif-123",
    "type": "message",
    "title": "Heart",
    "message": "Alex sent you a heart",
    "read": false,
    "timestamp": 1738200000000
  }
}
```
Emotion example:
```json
{
  "type": "notification.new",
  "payload": {
    "id": "notif-456",
    "type": "emotion",
    "title": "Love",
    "message": "Alex sent you love",
    "read": false,
    "timestamp": 1738200000000,
    "sender_id": "user-789",
    "sender_name": "Alex",
    "emotion_kind": "love"
  }
}
```

## REST Endpoints

### Admin Module

#### POST /v1/admin/auth/register
Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "user_id": "user-123",
  "email": "user@example.com",
  "access_token": "jwt-token",
  "refresh_token": "refresh-token"
}
```

#### POST /v1/admin/auth/login
Login and get access token.

**Request:** (OAuth2 form data)
- username: email
- password: password

**Response:**
```json
{
  "access_token": "jwt-token",
  "refresh_token": "refresh-token",
  "token_type": "bearer"
}
```

#### GET /v1/admin/auth/me
Get current user information.

**Response:**
```json
{
  "id": "user-123",
  "email": "user@example.com",
  "full_name": "John Doe",
  "is_active": true
}
```

#### POST /v1/admin/relationships
Create a new relationship.

**Request:**
```json
{
  "user2_id": "user-456",
  "relationship_type": "partner"
}
```

#### GET /v1/admin/relationships
List user's relationships.

#### POST /v1/admin/consent
Grant consent.

**Request:**
```json
{
  "relationship_id": "rel-123",
  "consent_type": "coaching"
}
```

### Coach Module

#### POST /v1/coach/activities
Create a new activity.

**Request:**
```json
{
  "relationship_id": "rel-123",
  "activity_type": "message",
  "content": "Hello!",
  "metadata": {}
}
```

#### GET /v1/coach/activities/relationship/{relationship_id}
List activities for a relationship.

### Activity memories (Game Room)

**Visibility:** By default, each memory/scrapbook entry is visible to all participants in the relationship. Completed activities and their scrapbooks are listed per relationship; only relationship members can list or view them.

#### GET /v1/activity/memories
List completed activities for a relationship (Memories tab). Returns aggregated notes, memory entries, and scrapbook layout. Query: `relationship_id`, optional `limit` (1–100).

#### POST /v1/activity/planned/{planned_id}/complete
Mark a planned activity as completed and append to dyad history. The resulting memory is visible to all participants.

#### POST /v1/activity/planned/{planned_id}/scrapbook
Save AI-generated scrapbook layout for a completed planned activity. The scrapbook is visible to all participants.

#### POST /v1/coach/reviews
Create a review job.

**Request:**
```json
{
  "relationship_id": "rel-123",
  "job_type": "daily_review"
}
```

### Interaction Module

#### POST /v1/interaction/pokes
Send a poke to another user.

**Request:**
```json
{
  "to_user_id": "user-456",
  "message": "Hey!"
}
```

### Notifications Module

#### GET /v1/notifications
List notifications for the current user, newest first.

**Query:** optional `limit` (1–100, default 50), optional `type` (message, alert, reward, system).

**Response:** array of:
```json
{
  "id": "notif-123",
  "type": "message",
  "title": "Heart",
  "message": "Alex sent you a heart",
  "read": false,
  "timestamp": 1738200000000
}
```

#### GET /v1/notifications/unread-count
Return unread notification count for the current user.

**Response:**
```json
{
  "unread": 3
}
```

#### POST /v1/notifications
Create a notification for the current user.

**Request:**
```json
{
  "type": "message",
  "title": "Title",
  "message": "Body text"
}
```

#### PATCH /v1/notifications/{notification_id}/read
Mark one notification as read.

#### POST /v1/notifications/read-all
Mark all notifications as read for the current user.

#### POST /v1/notifications/send-heart
Create a heart notification for a loved one. Target must be in a relationship with current user.

**Request:**
```json
{
  "target_user_id": "user-456"
}
```

#### POST /v1/notifications/send-emotion
Create an emotion notification for a loved one. Target must be in a relationship with current user. Recipient can see it on watch as full-screen for 5 seconds, as a tag on the sender's icon in the app, or as a phone push notification.

**Request:**
```json
{
  "target_user_id": "user-456",
  "emotion_kind": "love"
}
```
`emotion_kind` is optional (default `"love"`); e.g. `"love"`, `"hug"`.
