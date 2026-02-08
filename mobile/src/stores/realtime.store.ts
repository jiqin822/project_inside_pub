import { create } from "zustand";
import type { Notification, NotificationAction } from "../shared/types/domain";

export type NotificationType = Notification["type"];

/** Mock notification ids to filter out when merging server data (none used by default). */
const MOCK_NOTIFICATION_IDS = new Set<string>([]);
const getDefaultNotifications = (): Notification[] => [];

type EmojiTag = {
  emoji: string;
  senderId: string;
  timestamp: number;
  isAnimating: boolean;
};

export type EmotionTag = {
  senderName: string;
  emotionKind?: string;
  timestamp: number;
};

type RealtimeState = {
  wsStatus: "disconnected" | "connecting" | "connected";
  receivedEmojisByUserId: Record<string, EmojiTag>;
  /** Received emotion notifications keyed by sender user id (shown as tag on sender's icon). */
  receivedEmotionByUserId: Record<string, EmotionTag>;
  notifications: Notification[];

  setWsStatus: (s: RealtimeState["wsStatus"]) => void;
  upsertEmojiTag: (userId: string, tag: EmojiTag) => void;
  clearExpiredEmojiTags: (maxAgeMs: number) => void;
  removeEmojiTag: (userId: string) => void;
  setReceivedEmotion: (senderUserId: string, tag: EmotionTag) => void;
  clearExpiredEmotionTags: (maxAgeMs: number) => void;
  removeEmotionTag: (senderUserId: string) => void;

  // Compatibility helpers used by shared UI/hooks
  setWsConnected: (connected: boolean) => void;
  addEmojiReaction: (userId: string, emoji: string, senderId: string) => void;
  addNotification: (notification: Notification) => void;
  /** Central API: add notification by type/title/message. Handles ID, timestamp, unread. Optional action for click-to-navigate. */
  addNotificationFromEvent: (type: NotificationType, title: string, message: string, action?: NotificationAction) => void;
  /** Merge notifications from API (GET /notifications) by id; keeps last 50. */
  mergeNotificationsFromApi: (items: Array<{ id: string; type: string; title: string; message: string; read: boolean; timestamp: number; action?: NotificationAction }>) => void;
  dismissNotification: (id: string) => void;
  markAllRead: () => void;
  /** Mark a single notification as read (local state only; call API separately). */
  markNotificationRead: (id: string) => void;
  clearNotifications: () => void;
};

export const useRealtimeStore = create<RealtimeState>((set, get) => ({
  wsStatus: "disconnected",
  receivedEmojisByUserId: {},
  receivedEmotionByUserId: {},
  notifications: getDefaultNotifications(),

  setWsStatus: (wsStatus) => set({ wsStatus }),

  upsertEmojiTag: (userId, tag) =>
    set((s) => ({
      receivedEmojisByUserId: { ...s.receivedEmojisByUserId, [userId]: tag },
    })),

  removeEmojiTag: (userId) =>
    set((s) => {
      const next = { ...s.receivedEmojisByUserId };
      delete next[userId];
      return { receivedEmojisByUserId: next };
    }),

  setReceivedEmotion: (senderUserId, tag) =>
    set((s) => ({
      receivedEmotionByUserId: { ...s.receivedEmotionByUserId, [senderUserId]: tag },
    })),

  removeEmotionTag: (senderUserId) =>
    set((s) => {
      const next = { ...s.receivedEmotionByUserId };
      delete next[senderUserId];
      return { receivedEmotionByUserId: next };
    }),

  clearExpiredEmotionTags: (maxAgeMs) => {
    const now = Date.now();
    const current = get().receivedEmotionByUserId;
    const next: typeof current = {};
    for (const [k, v] of Object.entries(current)) {
      if (now - v.timestamp <= maxAgeMs) next[k] = v;
    }
    set({ receivedEmotionByUserId: next });
  },

  setWsConnected: (connected) =>
    set({ wsStatus: connected ? "connected" : "disconnected" }),

  addEmojiReaction: (userId, emoji, senderId) =>
    set((s) => ({
      receivedEmojisByUserId: {
        ...s.receivedEmojisByUserId,
        [userId]: {
          emoji,
          senderId,
          timestamp: Date.now(),
          isAnimating: true,
        },
      },
    })),

  addNotification: (notification) =>
    set((s) => ({
      notifications: [...s.notifications, notification].slice(-50),
    })),

  addNotificationFromEvent: (type, title, message, action) =>
    set((s) => {
      const notification: Notification = {
        id: crypto.randomUUID(),
        type,
        title,
        message,
        timestamp: Date.now(),
        read: false,
        ...(action && Object.keys(action).length > 0 ? { action } : {}),
      };
      return {
        notifications: [...s.notifications, notification].slice(-50),
      };
    }),

  mergeNotificationsFromApi: (items) =>
    set((s) => {
      const byId = new Map(s.notifications.map((n) => [n.id, n]));
      for (const it of items) {
        const allowed: Notification["type"][] = ['emoji', 'transaction', 'invite', 'activity_invite', 'lounge_invite', 'nudge', 'system', 'message', 'alert', 'reward', 'emotion', 'love_map', 'therapist'];
        const type = it.type && allowed.includes(it.type as Notification["type"]) ? (it.type as Notification["type"]) : 'system';
        const action: NotificationAction | undefined =
          it.action && (it.action.inviteId != null || it.action.plannedId != null || it.action.roomId != null)
            ? { inviteId: it.action.inviteId, plannedId: it.action.plannedId, roomId: it.action.roomId }
            : undefined;
        byId.set(it.id, {
          id: it.id,
          type,
          title: it.title,
          message: it.message,
          timestamp: it.timestamp,
          read: it.read,
          ...(action ? { action } : {}),
        });
      }
      let list = Array.from(byId.values()).slice(-50);
      if (items.length > 0) {
        list = list.filter((n) => !MOCK_NOTIFICATION_IDS.has(n.id));
      }
      return { notifications: list };
    }),

  dismissNotification: (id) =>
    set((s) => ({
      notifications: s.notifications.filter((n) => n.id !== id),
    })),

  markAllRead: () =>
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, read: true })),
    })),

  markNotificationRead: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })),

  clearNotifications: () => set({ notifications: [] }),

  clearExpiredEmojiTags: (maxAgeMs) => {
    const now = Date.now();
    const current = get().receivedEmojisByUserId;
    const next: typeof current = {};
    for (const [k, v] of Object.entries(current)) {
      if (now - v.timestamp <= maxAgeMs) next[k] = v;
    }
    set({ receivedEmojisByUserId: next });
  },
}));
