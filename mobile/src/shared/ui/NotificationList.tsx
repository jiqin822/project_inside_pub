import React from 'react';
import { useRealtimeStore } from '../../stores/realtime.store';
import { Notification } from '../types/domain';
import { X } from 'lucide-react';

interface NotificationListProps {
  maxItems?: number;
  className?: string;
}

export const NotificationList: React.FC<NotificationListProps> = ({
  maxItems = 50,
  className = '',
}) => {
  const { notifications, dismissNotification } = useRealtimeStore();

  // Keep only the most recent notifications
  const displayedNotifications = notifications.slice(-maxItems);

  if (displayedNotifications.length === 0) {
    return (
      <div className={`text-center py-8 text-slate-400 ${className}`}>
        <p className="text-xs font-mono uppercase">No notifications</p>
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {displayedNotifications.map((notification) => (
        <div
          key={notification.id}
          className="bg-white border-2 border-slate-200 p-3 flex items-start justify-between hover:border-slate-400 transition-colors"
        >
          <div className="flex-1">
            {notification.type === 'activity_invite' && (
              <p className="text-[9px] font-bold uppercase text-indigo-600 mb-0.5">Activity invite</p>
            )}
            {notification.type === 'lounge_invite' && (
              <p className="text-[9px] font-bold uppercase text-teal-600 mb-0.5">Chat invite</p>
            )}
            <p className="text-xs font-bold text-slate-900">{notification.message}</p>
            <p className="text-[10px] text-slate-500 font-mono mt-1">
              {new Date(notification.timestamp).toLocaleTimeString()}
            </p>
          </div>
          <button
            onClick={() => dismissNotification(notification.id)}
            className="text-slate-400 hover:text-slate-600 transition-colors ml-2"
            aria-label="Dismiss notification"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
};
