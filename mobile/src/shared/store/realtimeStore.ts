import { create } from 'zustand';
import { EmojiReaction, Notification } from '../types/domain';

interface RealtimeState {
  wsConnected: boolean;
  receivedEmojis: Record<string, EmojiReaction>;
  notifications: Notification[];
  quietMode: boolean;

  // Actions
  setWsConnected: (connected: boolean) => void;
  addEmojiReaction: (userId: string, emoji: string, senderId: string) => void;
  removeEmojiReaction: (userId: string) => void;
  addNotification: (notification: Notification) => void;
  dismissNotification: (id: string) => void;
  setQuietMode: (enabled: boolean) => void;
  clearNotifications: () => void;
}

export const useRealtimeStore = create<RealtimeState>((set) => ({
  wsConnected: false,
  receivedEmojis: {},
  notifications: [],
  quietMode: false,

  setWsConnected: (connected) => set({ wsConnected: connected }),

  addEmojiReaction: (userId, emoji, senderId) => set((state) => ({
    receivedEmojis: {
      ...state.receivedEmojis,
      [userId]: {
        emoji,
        senderId,
        timestamp: Date.now(),
        isAnimating: true,
      },
    },
  })),

  removeEmojiReaction: (userId) => set((state) => {
    const newEmojis = { ...state.receivedEmojis };
    delete newEmojis[userId];
    return { receivedEmojis: newEmojis };
  }),

  addNotification: (notification) => set((state) => ({
    notifications: [...state.notifications, notification].slice(-50), // Keep last 50
  })),

  dismissNotification: (id) => set((state) => ({
    notifications: state.notifications.filter((n) => n.id !== id),
  })),

  setQuietMode: (enabled) => set({ quietMode: enabled }),

  clearNotifications: () => set({ notifications: [] }),
}));
