import React, { useState, useEffect } from 'react';
import { X, AlertCircle, Info } from 'lucide-react';
import { useRealtimeStore } from '../store/realtimeStore';

interface Nudge {
  id: string;
  message: string;
  type: 'warning' | 'encouragement' | 'insight' | 'info';
  timestamp: number;
}

interface RateLimitedNudgeProps {
  nudges: Nudge[];
  maxDisplay?: number;
  autoDismissDelay?: number;
}

export const RateLimitedNudge: React.FC<RateLimitedNudgeProps> = ({
  nudges,
  maxDisplay = 3,
  autoDismissDelay = 5000,
}) => {
  const { quietMode, dismissNotification } = useRealtimeStore();
  const [displayedNudges, setDisplayedNudges] = useState<Nudge[]>([]);

  useEffect(() => {
    if (quietMode) {
      setDisplayedNudges([]);
      return;
    }

    // Show only the most recent nudges, limited by maxDisplay
    const recentNudges = nudges
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, maxDisplay);

    setDisplayedNudges(recentNudges);

    // Auto-dismiss after delay
    if (autoDismissDelay > 0) {
      const timers = recentNudges.map((nudge) =>
        setTimeout(() => {
          setDisplayedNudges((prev) => prev.filter((n) => n.id !== nudge.id));
        }, autoDismissDelay)
      );

      return () => {
        timers.forEach(clearTimeout);
      };
    }
  }, [nudges, maxDisplay, autoDismissDelay, quietMode]);

  if (displayedNudges.length === 0) return null;

  const getNudgeConfig = (type: Nudge['type']) => {
    switch (type) {
      case 'warning':
        return {
          icon: <AlertCircle size={16} className="text-yellow-600" />,
          bg: 'bg-yellow-50 border-yellow-200',
          text: 'text-yellow-800',
        };
      case 'encouragement':
        return {
          icon: <Info size={16} className="text-green-600" />,
          bg: 'bg-green-50 border-green-200',
          text: 'text-green-800',
        };
      case 'insight':
        return {
          icon: <Info size={16} className="text-blue-600" />,
          bg: 'bg-blue-50 border-blue-200',
          text: 'text-blue-800',
        };
      default:
        return {
          icon: <Info size={16} className="text-slate-600" />,
          bg: 'bg-slate-50 border-slate-200',
          text: 'text-slate-800',
        };
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm">
      {displayedNudges.map((nudge) => {
        const config = getNudgeConfig(nudge.type);
        return (
          <div
            key={nudge.id}
            className={`${config.bg} ${config.text} border-2 p-3 rounded-lg shadow-lg flex items-start gap-2 animate-slide-in-right`}
          >
            {config.icon}
            <div className="flex-1">
              <p className="text-xs font-bold">{nudge.message}</p>
            </div>
            <button
              onClick={() => {
                setDisplayedNudges((prev) => prev.filter((n) => n.id !== nudge.id));
                dismissNotification(nudge.id);
              }}
              className="text-slate-400 hover:text-slate-600 transition-colors"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
};
