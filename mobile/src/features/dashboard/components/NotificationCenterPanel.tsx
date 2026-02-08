import React, { useState, useEffect, useRef } from 'react';
import { X, Bell, Settings, Sliders, ArrowLeft, LogOut, Zap, Eye, MessageCircle, Gift, AlertTriangle, Calendar, Heart } from 'lucide-react';
import { useRealtimeStore } from '../../../stores/realtime.store';
import { useSessionStore } from '../../../stores/session.store';
import { useUiStore } from '../../../stores/ui.store';
import { apiService } from '../../../shared/api/apiService';
import type { Notification } from '../../../shared/types/domain';

/** Filter options: all + message, alert, reward, system, activity_invite, lounge_invite */
type NotifFilter = 'all' | 'message' | 'alert' | 'reward' | 'system' | 'activity_invite' | 'lounge_invite';

/** Yellow: activities, Green: bounties, Blue: offer redemption, Orange: emotion/emoji, Magenta: love map, Purple: therapist, Grey: system */
function getNotificationColor(n: Notification): { border: string; icon: string; dot: string } {
  if (n.type === 'activity_invite') return { border: 'border-yellow-500', icon: 'text-yellow-400', dot: 'bg-yellow-500' };
  if (n.type === 'lounge_invite') return { border: 'border-teal-500', icon: 'text-teal-400', dot: 'bg-teal-500' };
  if (n.type === 'love_map') return { border: 'border-fuchsia-500', icon: 'text-fuchsia-400', dot: 'bg-fuchsia-500' };
  if (n.type === 'therapist') return { border: 'border-violet-500', icon: 'text-violet-400', dot: 'bg-violet-500' };
  if (n.type === 'emotion' || n.type === 'emoji') return { border: 'border-orange-500', icon: 'text-orange-400', dot: 'bg-orange-500' };
  if (n.type === 'transaction') {
    const title = (n.title ?? '').toLowerCase();
    if (title.includes('offer purchased') || title.includes('purchase')) return { border: 'border-blue-500', icon: 'text-blue-400', dot: 'bg-blue-500' };
    return { border: 'border-green-500', icon: 'text-green-400', dot: 'bg-green-500' };
  }
  if (n.type === 'reward') return { border: 'border-green-500', icon: 'text-green-400', dot: 'bg-green-500' };
  if (n.type === 'scrapbook') return { border: 'border-amber-500', icon: 'text-amber-400', dot: 'bg-amber-500' };
  return { border: 'border-slate-500', icon: 'text-slate-400', dot: 'bg-slate-500' };
}

/** Max scrapbook notifications to show before muting the rest (dedupe). */
const SCRAPBOOK_DEDUPE_MAX = 3;

/** Don't show read notifications older than this in the list (badge still counts all unread). */
const READ_NOTIF_MAX_AGE_MS = 12 * 60 * 60 * 1000; // 1 day

function filterRecentOrUnread(notifications: Notification[]): Notification[] {
  const now = Date.now();
  return notifications.filter(
    (n) => !n.read || (now - (n.timestamp ?? 0)) <= READ_NOTIF_MAX_AGE_MS
  );
}

/**
 * Apply scrapbook dedupe: if there are many scrapbook notifications, show only the first N
 * and a single "X more scrapbook updates" placeholder so the list doesn't get flooded.
 */
function applyScrapbookDedupe(notifications: Notification[]): (Notification & { _mutedPlaceholder?: boolean })[] {
  const scrapbook = notifications.filter((n) => n.type === 'scrapbook');
  if (scrapbook.length <= SCRAPBOOK_DEDUPE_MAX) return notifications;
  const rest = notifications.filter((n) => n.type !== 'scrapbook');
  const scrapbookByNewest = [...scrapbook].sort((a, b) => (b.timestamp ?? 0) - (a.timestamp ?? 0));
  const toShow = scrapbookByNewest.slice(0, SCRAPBOOK_DEDUPE_MAX);
  const mutedCount = scrapbook.length - SCRAPBOOK_DEDUPE_MAX;
  const placeholder: Notification & { _mutedPlaceholder?: boolean } = {
    id: '__scrapbook_more__',
    type: 'scrapbook',
    title: 'Scrapbook',
    message: `${mutedCount} more scrapbook update${mutedCount === 1 ? '' : 's'}`,
    read: true,
    timestamp: Date.now(),
    _mutedPlaceholder: true,
  };
  const combined = [...rest, ...toShow, placeholder].sort((a, b) => (b.timestamp ?? 0) - (a.timestamp ?? 0));
  return combined;
}

interface NotificationCenterPanelProps {
  isOpen: boolean;
  onClose: () => void;
  /** When set (e.g. from push tap), scroll to this notification and then clear. */
  openToNotificationId?: string | null;
  /** Called when user clicks a notification; use to navigate to the event (e.g. Activities Planned tab). */
  onNotificationClick?: (notification: Notification) => void;
  onLogout?: () => void;
  onEditProfile?: () => void;
  preferences?: { notifications: boolean; hapticFeedback: boolean; privacyMode: boolean };
  onTogglePreference?: (key: 'notifications' | 'hapticFeedback' | 'privacyMode') => void;
  user?: { name: string; id: string };
}

export const NotificationCenterPanel: React.FC<NotificationCenterPanelProps> = ({
  isOpen,
  onClose,
  openToNotificationId,
  onNotificationClick,
  onLogout,
  onEditProfile,
  preferences = { notifications: true, hapticFeedback: true, privacyMode: false },
  onTogglePreference,
  user: userProp,
}) => {
  const { me: userFromStore } = useSessionStore();
  const user = userProp ?? userFromStore ?? null;
  const { notifications, markAllRead, markNotificationRead, mergeNotificationsFromApi, dismissNotification } = useRealtimeStore();
  const setOpenToNotificationId = useUiStore((s) => s.setOpenToNotificationId);
  const listRef = useRef<HTMLDivElement>(null);
  const swipeStartRef = useRef<{ id: string; x: number; y: number } | null>(null);
  const [view, setView] = useState<'notifications' | 'settings'>('notifications');
  const [notifFilter, setNotifFilter] = useState<NotifFilter>('all');

  const SWIPE_THRESHOLD_PX = 60;

  const handleSwipeStart = (e: React.PointerEvent, id: string) => {
    if (e.button !== 0 && e.pointerType === 'mouse') return;
    swipeStartRef.current = { id, x: e.clientX, y: e.clientY };
    const onPointerUp = (upEv: PointerEvent) => {
      document.removeEventListener('pointerup', onPointerUp);
      const start = swipeStartRef.current;
      if (!start || start.id !== id) return;
      const dx = upEv.clientX - start.x;
      const dy = upEv.clientY - start.y;
      if (dx < -SWIPE_THRESHOLD_PX && Math.abs(dx) > Math.abs(dy)) {
        dismissNotification(id);
        apiService.deleteNotification(id).catch((e) => console.warn('[NotificationCenter] Delete failed:', e));
        if (navigator.vibrate) navigator.vibrate(15);
      }
      swipeStartRef.current = null;
    };
    document.addEventListener('pointerup', onPointerUp);
  };

  useEffect(() => {
    if (isOpen) {
      setView('notifications');
    }
  }, [isOpen]);

  // Fetch notifications from API when panel opens so invitee sees lounge_invite etc. (real-time
  // WebSocket may have no session when invitee was not connected).
  useEffect(() => {
    if (!isOpen) return;
    apiService.listNotifications(50)
      .then((list) => mergeNotificationsFromApi(list))
      .catch((e) => console.warn('[NotificationCenter] Fetch on open failed:', e));
  }, [isOpen, mergeNotificationsFromApi]);

  // Push tap: ensure notification is in list, scroll to it, then clear openToNotificationId
  useEffect(() => {
    if (!isOpen || !openToNotificationId || !listRef.current) return;
    const id = openToNotificationId;
    const hasIt = notifications.some((n) => n.id === id);
    const scrollAndClear = () => {
      const el = listRef.current?.querySelector(`[data-notification-id="${id}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      setOpenToNotificationId(null);
    };
    if (hasIt) {
      requestAnimationFrame(scrollAndClear);
    } else {
      apiService.listNotifications(50).then((list) => {
        mergeNotificationsFromApi(list);
        setTimeout(scrollAndClear, 150);
      }).catch((e) => {
        console.warn('[NotificationCenter] Failed to fetch notifications:', e);
        setOpenToNotificationId(null);
      });
    }
  }, [isOpen, openToNotificationId, notifications, mergeNotificationsFromApi, setOpenToNotificationId]);

  const unreadCount = notifications.filter((n) => !n.read).length;
  const recentOrUnread = filterRecentOrUnread(notifications);
  const filteredByType =
    notifFilter === 'all'
      ? recentOrUnread
      : recentOrUnread.filter((n) => n.type === notifFilter);
  const filteredNotifications = applyScrapbookDedupe(filteredByType);

  if (!isOpen) return null;

  const filterOptions: NotifFilter[] = ['all', 'message', 'alert', 'reward', 'system', 'activity_invite', 'lounge_invite'];
  const filterLabel: Record<NotifFilter, string> = {
    all: 'All',
    message: 'Message',
    alert: 'Alert',
    reward: 'Reward',
    system: 'System',
    activity_invite: 'Activity',
    lounge_invite: 'Chat invite',
  };

  return (
    <div
      className={`fixed inset-y-0 right-0 w-80 bg-slate-900 text-white shadow-2xl transform transition-transform duration-300 ease-in-out z-50 flex flex-col ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      {/* === NOTIFICATIONS VIEW === */}
      {view === 'notifications' && (
        <>
          <div className="p-6 border-b border-slate-800 bg-slate-950 flex justify-between items-center shrink-0">
            <div>
              <h2 className="font-mono text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
                Inbox
              </h2>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-black uppercase tracking-tight">Notification Center</h3>
                {unreadCount > 0 && (
                  <span className="bg-red-500 text-white text-[9px] font-bold px-1.5 rounded">
                    {unreadCount}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
                <X size={24} />
              </button>
            </div>
          </div>

          {/* Filters — match inside/App.tsx */}
          <div className="p-4 border-b border-slate-800 flex gap-2 overflow-x-auto no-scrollbar shrink-0">
            {filterOptions.map((f) => (
              <button
                key={f}
                onClick={() => setNotifFilter(f)}
                className={`px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full border transition-colors whitespace-nowrap ${
                  notifFilter === f
                    ? 'bg-white text-slate-900 border-white'
                    : 'bg-slate-800 text-slate-400 border-slate-700 hover:border-slate-500'
                }`}
              >
                {filterLabel[f]}
              </button>
            ))}
          </div>

          {/* List — match inside/App.tsx: type icon + title, message, time */}
          <div ref={listRef} className="flex-1 overflow-y-auto p-4 space-y-3" style={{ minHeight: 0 }}>
            {filteredNotifications.length === 0 && (
              <div className="text-center py-10 text-slate-600 text-xs font-mono uppercase">
                No notifications found.
              </div>
            )}
            {filteredNotifications.map((n) => {
              const colors = getNotificationColor(n);
              const isMutedPlaceholder = n.id === '__scrapbook_more__' || (n as { _mutedPlaceholder?: boolean })._mutedPlaceholder;
              const isClickable = onNotificationClick && !isMutedPlaceholder;
              return (
              <div
                key={n.id}
                data-notification-id={isMutedPlaceholder ? undefined : n.id}
                role={isClickable ? 'button' : undefined}
                tabIndex={isClickable ? 0 : undefined}
                onPointerDown={!isMutedPlaceholder ? (e) => handleSwipeStart(e, n.id) : undefined}
                style={{ touchAction: 'pan-y' }}
                onClick={
                  isClickable
                    ? () => {
                        markNotificationRead(n.id);
                        apiService.markNotificationRead(n.id).catch((e) => console.warn('[NotificationCenter] Mark read failed:', e));
                        onNotificationClick(n);
                      }
                    : undefined
                }
                onKeyDown={
                  isClickable
                    ? (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          markNotificationRead(n.id);
                          apiService.markNotificationRead(n.id).catch((e) => console.warn('[NotificationCenter] Mark read failed:', e));
                          onNotificationClick(n);
                        }
                      }
                    : undefined
                }
                className={`p-4 bg-slate-800 border-l-4 ${n.read ? 'border-slate-600 opacity-60' : colors.border} ${isMutedPlaceholder ? 'opacity-70 cursor-default' : 'hover:bg-slate-700'} transition-colors group relative ${openToNotificationId === n.id ? 'ring-2 ring-slate-400' : ''} ${isClickable ? 'cursor-pointer' : ''}`}
              >
                {!n.read && (
                  <div className={`absolute top-2 right-2 w-2 h-2 ${colors.dot} rounded-full`} />
                )}
                <div className="flex items-start gap-3">
                  <div className={`mt-0.5 shrink-0 ${colors.icon}`}>
                    {n.type === 'alert' ? (
                      <AlertTriangle size={16} />
                    ) : n.type === 'message' ? (
                      <MessageCircle size={16} />
                    ) : n.type === 'reward' ? (
                      <Gift size={16} />
                    ) : n.type === 'activity_invite' ? (
                      <Calendar size={16} />
                    ) : n.type === 'lounge_invite' ? (
                      <MessageCircle size={16} />
                    ) : n.type === 'love_map' ? (
                      <Heart size={16} />
                    ) : n.type === 'therapist' ? (
                      <MessageCircle size={16} />
                    ) : n.type === 'emotion' || n.type === 'emoji' ? (
                      <MessageCircle size={16} />
                    ) : n.type === 'scrapbook' ? (
                      <Calendar size={16} />
                    ) : (
                      <Zap size={16} />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h4 className="text-xs font-bold uppercase text-white mb-0.5">
                      {n.title ?? n.type}
                    </h4>
                    <p className="text-[11px] text-slate-300 leading-snug font-medium">{n.message}</p>
                    <span className="text-[9px] font-mono text-slate-500 mt-2 block">
                      {Math.floor((Date.now() - n.timestamp) / 60000)}m ago
                    </span>
                  </div>
                </div>
              </div>
            );
            })}
          </div>

          {/* Footer — Mark All as Read: persist on backend then refetch so badge stays 0 across reloads */}
          <div className="p-4 border-t border-slate-800 bg-slate-950 shrink-0">
            <button
              onClick={() => {
                markAllRead();
                apiService
                  .markAllNotificationsRead()
                  .then(() => apiService.listNotifications(50).then(mergeNotificationsFromApi))
                  .catch((e) => console.warn('[NotificationCenter] Mark all read failed:', e));
              }}
              className="w-full text-[10px] font-bold uppercase tracking-widest text-slate-500 hover:text-white transition-colors"
            >
              Mark All as Read
            </button>
          </div>
        </>
      )}

      {/* === SETTINGS VIEW === */}
      {view === 'settings' && (
        <>
          <div className="p-6 border-b border-slate-800 bg-slate-950 flex justify-between items-center shrink-0">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setView('notifications')}
                className="text-slate-400 hover:text-white transition-colors"
              >
                <ArrowLeft size={20} />
              </button>
              <div>
                <h2 className="font-mono text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">
                  Config
                </h2>
                <h3 className="text-lg font-black uppercase tracking-tight">System Settings</h3>
              </div>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
              <X size={24} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto" style={{ minHeight: 0 }}>
            <div className="p-6 border-b border-slate-800 bg-slate-900/50">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-white text-slate-900 rounded-lg flex items-center justify-center font-bold text-xl border-2 border-slate-400">
                  {user?.name?.charAt(0) ?? '?'}
                </div>
                <div>
                  <div className="text-xs font-mono text-slate-500 uppercase">Project Lead</div>
                  <div className="font-bold">{user?.name ?? 'User'}</div>
                  {onEditProfile && (
                    <button
                      onClick={onEditProfile}
                      className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 mt-1"
                    >
                      <Settings size={10} /> Edit Profile
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="p-4 bg-slate-800/50 border-b border-slate-700">
              <h3 className="font-bold text-slate-400 flex items-center gap-2 text-xs uppercase tracking-widest">
                <Sliders size={14} /> Global Preferences
              </h3>
            </div>
            <div className="divide-y divide-slate-800">
              <div className="p-4 flex items-center justify-between hover:bg-slate-800 transition-colors">
                <div className="flex items-center gap-3">
                  <Bell size={18} className="text-slate-400" />
                  <div>
                    <p className="text-sm font-bold text-white uppercase">Smart Nudges</p>
                    <p className="text-[10px] text-slate-500 font-mono">Wearable Alerts</p>
                  </div>
                </div>
                {onTogglePreference && (
                  <button
                    onClick={() => onTogglePreference('notifications')}
                    className={`w-10 h-5 transition-colors relative border-2 ${
                      preferences.notifications ? 'bg-green-500 border-green-600' : 'bg-slate-700 border-slate-600'
                    }`}
                  >
                    <div
                      className={`w-3 h-3 bg-white shadow-sm absolute top-0.5 transition-all ${
                        preferences.notifications ? 'left-5' : 'left-0.5'
                      }`}
                    />
                  </button>
                )}
              </div>
              <div className="p-4 flex items-center justify-between hover:bg-slate-800 transition-colors">
                <div className="flex items-center gap-3">
                  <Zap size={18} className="text-slate-400" />
                  <div>
                    <p className="text-sm font-bold text-white uppercase">Haptics</p>
                    <p className="text-[10px] text-slate-500 font-mono">Tactile Feedback</p>
                  </div>
                </div>
                {onTogglePreference && (
                  <button
                    onClick={() => onTogglePreference('hapticFeedback')}
                    className={`w-10 h-5 transition-colors relative border-2 ${
                      preferences.hapticFeedback ? 'bg-green-500 border-green-600' : 'bg-slate-700 border-slate-600'
                    }`}
                  >
                    <div
                      className={`w-3 h-3 bg-white shadow-sm absolute top-0.5 transition-all ${
                        preferences.hapticFeedback ? 'left-5' : 'left-0.5'
                      }`}
                    />
                  </button>
                )}
              </div>
              <div className="p-4 flex items-center justify-between hover:bg-slate-800 transition-colors">
                <div className="flex items-center gap-3">
                  <Eye size={18} className="text-slate-400" />
                  <div>
                    <p className="text-sm font-bold text-white uppercase">Stealth Mode</p>
                    <p className="text-[10px] text-slate-500 font-mono">Mask Dashboard</p>
                  </div>
                </div>
                {onTogglePreference && (
                  <button
                    onClick={() => onTogglePreference('privacyMode')}
                    className={`w-10 h-5 transition-colors relative border-2 ${
                      preferences.privacyMode ? 'bg-green-500 border-green-600' : 'bg-slate-700 border-slate-600'
                    }`}
                  >
                    <div
                      className={`w-3 h-3 bg-white shadow-sm absolute top-0.5 transition-all ${
                        preferences.privacyMode ? 'left-5' : 'left-0.5'
                      }`}
                    />
                  </button>
                )}
              </div>
            </div>
            <div className="p-6 text-center mt-4">
              <p className="text-[9px] font-mono text-slate-500 mb-2 uppercase">Inside.OS v1.2.0</p>
            </div>
          </div>

          {onLogout && (
            <div className="p-6 border-t border-slate-800 bg-slate-950 space-y-3 shrink-0">
              <button
                onClick={() => {
                  onClose();
                  onLogout();
                }}
                className="w-full py-3 text-rose-500 hover:text-white hover:bg-rose-900 transition-all text-xs font-mono uppercase tracking-widest flex items-center justify-center gap-2 border border-dashed border-rose-900/30 hover:border-rose-500"
              >
                <LogOut size={14} /> System Logout
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};
