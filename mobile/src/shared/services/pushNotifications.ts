/**
 * Push notification registration and tap handling.
 * Register with backend for FCM/APNs; on tap open app to notification center and scroll to message.
 */
import { Capacitor } from '@capacitor/core';

export type PushTapPayload = { notificationId: string; type?: string };

let registrationListenerRemoved: (() => void) | null = null;
let actionPerformedListenerRemoved: (() => void) | null = null;

/**
 * Register for push, upload token to backend. Call when user is logged in and on native platform.
 * Returns a cleanup function to remove listeners.
 */
export async function registerPushNotifications(
  apiService: { registerPushToken: (token: string, platform: string) => Promise<{ ok: boolean }> }
): Promise<() => void> {
  if (!Capacitor.isNativePlatform()) {
    return () => {};
  }
  try {
    const { PushNotifications } = await import('@capacitor/push-notifications');

    const perm = await PushNotifications.requestPermissions();
    if (perm.receive !== 'granted') {
      console.warn('[Push] Permission not granted:', perm.receive);
      return () => {};
    }

    await PushNotifications.register();

    const platform = Capacitor.getPlatform() === 'ios' ? 'ios' : 'android';

    registrationListenerRemoved = await PushNotifications.addListener(
      'registration',
      async (ev: { value: string }) => {
        const token = ev.value;
        if (!token) return;
        try {
          await apiService.registerPushToken(token, platform);
        } catch (e) {
          console.warn('[Push] Failed to register token with backend:', e);
        }
      }
    );

    return () => {
      registrationListenerRemoved?.();
      registrationListenerRemoved = null;
    };
  } catch (e) {
    console.warn('[Push] Setup failed:', e);
    return () => {};
  }
}

/**
 * Handle push notification tap: open app to dashboard and notification center with the tapped message.
 * Pass a callback that receives { notificationId, type }; typically it sets room to dashboard, opens side panel, sets openToNotificationId.
 */
export async function setupPushTapHandler(
  onTap: (payload: PushTapPayload) => void
): Promise<() => void> {
  if (!Capacitor.isNativePlatform()) {
    return () => {};
  }
  try {
    const { PushNotifications } = await import('@capacitor/push-notifications');

    actionPerformedListenerRemoved = await PushNotifications.addListener(
      'pushNotificationActionPerformed',
      (action: { notification?: { data?: Record<string, string> } }) => {
        const data = action.notification?.data ?? {};
        const notificationId = data.notificationId ?? data.notification_id ?? '';
        if (!notificationId) return;
        onTap({
          notificationId,
          type: data.type,
        });
      }
    );

    return () => {
      actionPerformedListenerRemoved?.();
      actionPerformedListenerRemoved = null;
    };
  } catch (e) {
    console.warn('[Push] Tap handler setup failed:', e);
    return () => {};
  }
}
