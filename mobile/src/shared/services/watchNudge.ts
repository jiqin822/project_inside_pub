import { Capacitor, registerPlugin } from '@capacitor/core';

export type WatchNudgeSeverity = 'low' | 'medium' | 'high';

export interface WatchNudgePayload {
  reason: string;
  severity: WatchNudgeSeverity;
  speaker?: string;
}

export interface LovedOneForWatch {
  id: string;
  name: string;
  profilePicture?: string | null;
}

interface WatchNudgePlugin {
  nudge(options: WatchNudgePayload): Promise<{ delivered?: boolean } | void>;
  syncLovedOnes(options: { lovedOnes: LovedOneForWatch[] }): Promise<{ ok: boolean; error?: string }>;
  showEmoji(options: { emoji: string; senderName: string }): Promise<{ delivered?: boolean } | void>;
  showEmotion(options: { senderName: string; emotionKind?: string }): Promise<{ delivered?: boolean } | void>;
  addListener(eventName: string, callback: (event: { lovedOneId: string }) => void): Promise<{ remove: () => Promise<void> }>;
}

const WatchNudge = registerPlugin<WatchNudgePlugin>('WatchNudge');

export const canSendWatchNudge = () => {
  return (
    Capacitor.isNativePlatform() &&
    Capacitor.getPlatform() === 'ios' &&
    Capacitor.isPluginAvailable('WatchNudge')
  );
};

export const sendWatchNudge = async (payload: WatchNudgePayload): Promise<boolean> => {
  if (!canSendWatchNudge()) {
    return false;
  }

  try {
    const result = await WatchNudge.nudge(payload);
    if (result && typeof result.delivered === 'boolean') {
      return result.delivered;
    }
    return true;
  } catch (error) {
    console.warn('[WatchNudge] Failed to send watch nudge', error);
    return false;
  }
};

/** Send emoji to watch for full-screen display. Returns true if delivered to watch (or queued). */
export const sendEmojiToWatch = async ({
  emoji,
  senderName,
}: {
  emoji: string;
  senderName: string;
}): Promise<boolean> => {
  if (!canSendWatchNudge()) return false;
  try {
    const result = await WatchNudge.showEmoji({ emoji, senderName });
    if (result && typeof result.delivered === 'boolean') {
      return result.delivered;
    }
    return true;
  } catch (error) {
    console.warn('[WatchNudge] Failed to send emoji to watch', error);
    return false;
  }
};

/** Send emotion to watch for full-screen display (5s). Returns true if delivered to watch (or queued). */
export const sendEmotionToWatch = async ({
  senderName,
  emotionKind,
}: {
  senderName: string;
  emotionKind?: string;
}): Promise<boolean> => {
  if (!canSendWatchNudge()) return false;
  try {
    const result = await WatchNudge.showEmotion({ senderName, emotionKind });
    if (result && typeof result.delivered === 'boolean') {
      return result.delivered;
    }
    return true;
  } catch (error) {
    console.warn('[WatchNudge] Failed to send emotion to watch', error);
    return false;
  }
};

/** Sync loved ones (id, name, profilePicture) to the watch for the grid. Call when user/loved ones are loaded. */
export const syncLovedOnes = async (lovedOnes: LovedOneForWatch[]): Promise<boolean> => {
  if (!canSendWatchNudge()) return false;
  try {
    const result = await WatchNudge.syncLovedOnes({
      lovedOnes: lovedOnes.map((lo) => ({
        id: lo.id,
        name: lo.name,
        profilePicture: lo.profilePicture ?? undefined,
      })),
    });
    return result?.ok === true;
  } catch (error) {
    console.warn('[WatchNudge] Failed to sync loved ones', error);
    return false;
  }
};

/** Register a listener for "send heart" from the watch. Returns an unsubscribe function. */
export const addWatchSendHeartListener = (callback: (lovedOneId: string) => void): (() => void) => {
  if (!canSendWatchNudge()) return () => {};
  let listenerRef: { remove: () => Promise<void> } | null = null;
  WatchNudge.addListener('watchSendHeart', (event: { lovedOneId: string }) => {
    const id = event?.lovedOneId;
    if (id) callback(id);
  }).then((l) => {
    listenerRef = l;
  });
  return () => {
    if (listenerRef) listenerRef.remove().catch(() => {});
    listenerRef = null;
  };
};

/** Register a listener for "send emotion" from the watch. Returns an unsubscribe function. */
export const addWatchSendEmotionListener = (callback: (lovedOneId: string, emotionKind?: string) => void): (() => void) => {
  if (!canSendWatchNudge()) return () => {};
  let listenerRef: { remove: () => Promise<void> } | null = null;
  WatchNudge.addListener('watchSendEmotion', (event: { lovedOneId: string; emotionKind?: string }) => {
    const id = event?.lovedOneId;
    if (id) callback(id, event?.emotionKind);
  }).then((l) => {
    listenerRef = l;
  });
  return () => {
    if (listenerRef) listenerRef.remove().catch(() => {});
    listenerRef = null;
  };
};
