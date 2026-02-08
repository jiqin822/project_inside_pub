import React, { useEffect } from 'react';
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

interface ToastProps {
  message: string;
  type?: ToastType;
  duration?: number;
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({
  message,
  type = 'info',
  duration = 3000,
  onClose,
}) => {
  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(onClose, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const typeConfig = {
    success: {
      icon: <CheckCircle size={18} className="text-green-600" />,
      bg: 'bg-green-50 border-green-200',
      text: 'text-green-800',
    },
    error: {
      icon: <AlertCircle size={18} className="text-red-600" />,
      bg: 'bg-red-50 border-red-200',
      text: 'text-red-800',
    },
    warning: {
      icon: <AlertCircle size={18} className="text-yellow-600" />,
      bg: 'bg-yellow-50 border-yellow-200',
      text: 'text-yellow-800',
    },
    info: {
      icon: <Info size={18} className="text-blue-600" />,
      bg: 'bg-blue-50 border-blue-200',
      text: 'text-blue-800',
    },
  };

  const config = typeConfig[type];

  return (
    <div
      className={`fixed top-4 right-4 z-50 ${config.bg} border-2 ${config.text} p-4 shadow-lg rounded-lg flex items-center gap-3 min-w-[300px] max-w-md animate-slide-in-right`}
    >
      {config.icon}
      <p className="flex-1 text-sm font-bold">{message}</p>
      <button
        onClick={onClose}
        className="text-slate-400 hover:text-slate-600 transition-colors"
        aria-label="Dismiss"
      >
        <X size={16} />
      </button>
    </div>
  );
};
