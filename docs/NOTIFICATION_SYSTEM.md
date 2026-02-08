# Notification System Documentation

## Overview

The notification system provides in-app and (optionally) device notifications for events such as hearts from partners, escalation alerts from the Live Coach, and future sources (market, therapy, system). It consists of a **backend** (REST API, persistence, real-time push) and a **mobile** client (Zustand store, Notification Center panel, and feature-triggered toasts).

---

## Architecture

### High-level flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ TRIGGERS                                                                     │
│ • User A sends heart to User B  →  Backend creates notification for B        │
│ • POST /v1/notifications (create)  →  Backend creates for current user      │
│ • Live Coach escalation  →  Frontend calls addNotificationFromEvent (local)  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ BACKEND                                                                      │
│ • NotificationRepository: create, list_by_user, count_unread, mark_read      │
│ • REST: GET/POST /v1/notifications, GET unread-count, PATCH read, send-heart│
│ • After create/send-heart: ws_manager.send_to_user(user_id, notification.new)│
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │ WebSocket /v1/interaction/notifications │
                    │ (same connection: emoji pokes + notification.new)        │
                    └───────────────────┬───────────────────┘
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ MOBILE                                                                       │
│ • Realtime store: notifications[], addNotification, addNotificationFromEvent │
│ • NotificationCenterPanel: reads from store, filters by type, mark all read  │
│ • App passes addNotification to screens; Live Coach calls it on escalation   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Backend

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **Model** | `backend/app/infra/db/models/notification.py` | `NotificationModel`: id, user_id, type, title, message, read, created_at |
| **Repository** | `backend/app/infra/db/repositories/notification_repo.py` | create, list_by_user(limit, type?), count_unread, get, mark_read, mark_all_read |
| **API** | `backend/app/api/notifications/routes_notifications.py` | REST routes; after create/send-heart calls `ws_manager.send_to_user` with `notification.new` |
| **WebSocket** | `backend/app/api/interaction/routes_ws.py` | `/notifications` accepts connections with `?token=...`, registers with `ws_manager` as `session_id = user_{user_id}` |
| **WS manager** | `backend/app/infra/realtime/ws_manager.py` | Maps user_id → sessions; `send_to_user(user_id, message)` broadcasts to all connections for that user |

### Frontend

| Piece | Location | Responsibility |
|-------|----------|----------------|
| **Types** | `mobile/src/shared/types/domain.ts` | `Notification` (id, type, message, timestamp, read, title?, actionUrl?); `AddNotificationFn` |
| **Store** | `mobile/src/stores/realtime.store.ts` | notifications array; addNotification, addNotificationFromEvent, markAllRead, dismissNotification; currently **seeded with mock data**, not yet synced with backend list |
| **API client** | `mobile/src/shared/api/apiService.ts` | sendHeart (POST /notifications/send-heart); connectWebSocket (ws to /v1/interaction/notifications) |
| **Panel** | `mobile/src/features/dashboard/components/NotificationCenterPanel.tsx` | Inbox UI: filters (all, message, alert, reward, system), unread badge, mark all read; reads from store only |
| **App** | `mobile/App.tsx` | Defines addNotification → addNotificationFromEvent; passes it to Dashboard, Live Coach, etc.; connects WebSocket and handles emoji poke + (if implemented) notification.new |

---

## Notification types

Used in both backend and frontend for categorization and filtering:

| Type | Typical use |
|------|-------------|
| `message` | Hearts, direct messages, voice memos |
| `alert` | Escalation / conflict detection (Live Coach) |
| `reward` | XP, tokens, goals, purchases |
| `system` | App updates, quests, system messages |

Domain type in `domain.ts` also includes: `emoji`, `transaction`, `invite`, `nudge` for future or legacy use.

---

## What actions trigger notifications

### 1. Send heart (backend + real-time push)

- **Who:** User A sends a heart to a partner/loved one (User B).
- **Where:** Watch app, or phone UI, calls `apiService.sendHeart(targetUserId)` → `POST /v1/notifications/send-heart` with `target_user_id`.
- **Backend:** Validates A and B are in a relationship; creates a notification for **B** (user_id = B) with type `message`, title "Heart", message e.g. "{A's name} sent you a heart". Then calls `ws_manager.send_to_user(B, { type: "notification.new", payload: {...} })`.
- **Frontend (B):** If B has the app open and connected to the WebSocket, they can receive `notification.new` and add it to the store (handler for `notification.new` can be added in App.tsx / useWebSocket). The Notification Center shows items from the store; **currently the mobile app does not fetch the notification list from the backend** (it uses mock or local-only data).

### 2. Create notification via API (backend + real-time push)

- **Who:** Any authenticated client (or future server-side job) calling `POST /v1/notifications` with body `{ type, title, message }`.
- **Backend:** Creates a notification for the **current user**; then sends `notification.new` to that user via `ws_manager.send_to_user(current_user.id, ...)`.
- **Use case:** Market events, therapy summaries, or other server-driven alerts.

### 3. Live Coach escalation (frontend-only, local store)

- **Who:** Live Coach feature when STT or Gemini reports an escalation (e.g. conflict pattern).
- **Where:** `mobile/src/features/liveCoach/screens/LiveCoachScreen.tsx`: on escalation event, calls `addNotificationFromEvent('alert', 'Escalation Detected', event.message)` (and optionally sends a watch nudge).
- **Effect:** Adds a new notification to the **local** Zustand store only; no backend create. User sees it in the Notification Center and (if permissions granted) can get a browser/device alert.

### 4. Other in-app events (frontend-only)

- **Who:** Activities, Therapist, Rewards, etc., via the `onAddNotification` prop (which maps to `addNotificationFromEvent`).
- **Examples:** "Activity Logged", "Purchase Confirmed", "New Perspective" (mediation data). All add only to the local store.

---

## Backend API reference

### REST (base path: `/v1/notifications`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List notifications for current user (query: `limit`, `type`) |
| GET | `/unread-count` | Returns `{ "unread": number }` |
| POST | `` | Create notification for current user (body: type, title, message); pushes `notification.new` |
| PATCH | `/{notification_id}/read` | Mark one as read |
| POST | `/read-all` | Mark all as read for current user |
| POST | `/send-heart` | Create heart notification for target user (body: target_user_id); pushes `notification.new` to target |

All except create/send-heart are idempotent. Create and send-heart return the created notification; list and unread-count return data for the authenticated user.

### WebSocket

- **URL:** `ws://<host>/v1/interaction/notifications?token=<access_token>` (wss in production).
- **Auth:** JWT in query; server decodes and registers the connection for `user_{user_id}`.
- **Server → client messages:**
  - `connection.established`: `{ type, user_id }` after accept.
  - `notification.new`: `{ type: "notification.new", payload: { id, type, title, message, read, timestamp } }` when a notification is created for this user (via POST create or send-heart).
  - Other types (e.g. emoji/poke) may be sent on the same connection.
- **Client → server:** Optional `ping`; server responds with `pong`.

---

## Frontend integration notes

- **Notification Center panel** reads only from `useRealtimeStore().notifications`. It does **not** yet call the backend to fetch list or unread count; mark-all-read only updates the store.
- **Backend persistence:** Notifications created via POST or send-heart are stored in the DB and pushed in real time. The mobile app can be extended to:
  - Fetch list on panel open: `GET /v1/notifications`
  - Use unread badge: `GET /v1/notifications/unread-count`
  - Mark read: `PATCH /v1/notifications/:id/read`, `POST /v1/notifications/read-all`
  - On WebSocket `notification.new`: call `addNotification(payload)` to prepend to the store (and optionally show a toast).
- **Local-only notifications** (Live Coach escalation, activities, etc.) remain client-only until the app is updated to also call `POST /v1/notifications` for those events if persistence is desired.

---

## Activity invite & lounge invite: in-app toast and push

- **Backend:** `deliver_notification()` is used for both `activity_invite` and `lounge_invite`. It creates the DB row, sends WebSocket `notification.new`, and sends FCM push (when `push_enabled` and credentials are set).
- **In-app toast:** When the client receives `notification.new` over the WebSocket, it calls `showToast()` for both types so the user sees a toast while the app is open. This only runs when the WebSocket is connected; if the app was in the background or disconnected, the user will see the item only after opening the Notification Center (which fetches from the API).
- **Browser / OS notification:** On web, if `Notification.permission === 'granted'`, the client shows a browser notification for both types. On native (Capacitor), push is sent by the backend via FCM; ensure the device has registered a push token and backend has `push_enabled` and `GOOGLE_APPLICATION_CREDENTIALS` set.
- **Push tap:** Tapping an activity_invite or lounge_invite push opens the app to Activities or Lounge respectively and opens the Notification Center panel with the tapped notification scrolled into view.

---

## Related files

- **Contracts:** `contracts/api_contracts.md` (REST + WebSocket notification.new)
- **Backend:** `backend/app/api/notifications/`, `backend/app/infra/db/models/notification.py`, `backend/app/infra/db/repositories/notification_repo.py`, `backend/app/infra/realtime/ws_manager.py`, `backend/app/api/interaction/routes_ws.py`
- **Mobile:** `mobile/src/stores/realtime.store.ts`, `mobile/src/features/dashboard/components/NotificationCenterPanel.tsx`, `mobile/src/shared/api/apiService.ts`, `mobile/App.tsx`, `mobile/src/shared/types/domain.ts`
