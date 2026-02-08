# Notification Panel Behavior Plan (match inside/App.tsx)

## Goal
Replicate the **behavior** of the floating button + side panel in `inside/App.tsx` without changing the current **look** of the mobile Notification button.

## Current Button (keep unchanged)
- **Location**: Fixed bottom-right (already aligned with inside).
- **Style**: `w-8 h-8`, white bg, slate-900 border, Bell icon, optional count badge.
- **Click**: Opens side panel (`toggleSidePanel(true)`).

## Behavior in inside/App.tsx (to replicate)

1. **On button click**
   - Open the side panel.
   - Show **Notifications** view first (default).

2. **Single panel, two internal views**
   - **Notifications view** (default)
     - Header: "Inbox" / "Notification Center" + unread count badge.
     - Settings (gear) icon → switch to Settings view.
     - X → close panel.
     - Filter pills: all, message, alert, reward, system.
     - List: each item has type icon, title, message, "Xm ago"; unread styling (e.g. left border).
     - Footer: "Mark All as Read".
   - **Settings view**
     - Header: Back arrow (→ Notifications), "Config" / "System Settings", X to close.
     - User block: avatar, "Project Lead", name, "Edit Profile" (closes panel + opens edit profile).
     - Section: "Global Preferences" with toggles (Smart Nudges, Haptics, Stealth Mode).
     - Version line: "Inside.OS v1.2.0".
     - Footer: "System Logout" button.

3. **Panel container**
   - Same drawer: `fixed inset-y-0 right-0 w-80`, dark theme, slide-in; one DOM container that switches content by view.

## Implementation Plan

| Step | Task |
|------|------|
| 1 | **NotificationCenterPanel**: Add internal state `view: 'notifications' \| 'settings'`. Reset to `'notifications'` when panel opens (e.g. `useEffect` when `isOpen` becomes true). |
| 2 | **Notifications view**: Keep existing list. Add header with Settings icon (switch to settings). Add filter pills (all + types that exist in mobile `Notification.type`: system, etc.). Add "Mark All as Read" footer. Optionally add `markAllRead` to realtime store. |
| 3 | **Settings view**: New content in same panel. Header: Back (→ notifications), "System Settings", X. User block + "Edit Profile" (call `onEditProfile` then `onClose`). Global Preferences (Smart Nudges, Haptics, Stealth Mode) using `preferences` + `onTogglePreference` from props. Version line. Logout button using `onLogout` from props. |
| 4 | **DashboardHome**: Pass to NotificationCenterPanel: `onLogout`, `onEditProfile`, `preferences`, `onTogglePreference` (reintroduce from user/session and profile update). Do **not** change the floating button JSX or classNames. |
| 5 | **Realtime store** (optional): Add `markAllRead()` that sets `read: true` on all notifications so "Mark All as Read" works. |

## Files to touch
- `mobile/src/features/dashboard/components/NotificationCenterPanel.tsx` — two-view panel UI and logic.
- `mobile/src/features/dashboard/screens/DashboardHome.tsx` — pass props for Settings view (no button style change).
- `mobile/src/stores/realtime.store.ts` — optional `markAllRead`.
- `mobile/src/shared/ui/NotificationList.tsx` — optional: support filter by type and read state for list styling.

## What stays unchanged
- Floating button: className, icon (Bell), size, badge, position, title — **no changes**.
