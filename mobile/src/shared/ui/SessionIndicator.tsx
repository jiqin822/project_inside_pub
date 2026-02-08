import React from 'react';
import { Mic, MicOff, Square } from 'lucide-react';

interface SessionIndicatorProps {
  isRecording: boolean;
  isActive: boolean;
  onStop: () => void;
  message?: string;
}

export const SessionIndicator: React.FC<SessionIndicatorProps> = ({
  isRecording,
  isActive,
  onStop,
  message,
}) => {
  if (!isActive && !isRecording) return null;

  return (
    <div className="fixed top-4 left-4 z-50 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-3 border-2 border-red-800">
      <div className="flex items-center gap-2">
        {isRecording ? (
          <>
            <Mic size={18} className="animate-pulse" />
            <span className="text-sm font-bold uppercase">Recording</span>
          </>
        ) : (
          <>
            <MicOff size={18} />
            <span className="text-sm font-bold uppercase">Session Active</span>
          </>
        )}
      </div>
      {message && (
        <span className="text-xs opacity-90">{message}</span>
      )}
      <button
        onClick={onStop}
        className="ml-2 px-3 py-1 bg-white text-red-600 text-xs font-bold uppercase hover:bg-red-50 transition-colors flex items-center gap-1"
        aria-label="Stop session"
      >
        <Square size={12} />
        Stop
      </button>
    </div>
  );
};
