import React from 'react';

interface XpBarProps {
  value: number;
  max: number;
  showLabel?: boolean;
  className?: string;
}

export const XpBar: React.FC<XpBarProps> = ({ value, max, showLabel = true, className = '' }) => {
  const percentage = Math.min((value / max) * 100, 100);

  return (
    <div className={`space-y-1 ${className}`}>
      {showLabel && (
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-700 uppercase">XP</span>
          <span className="text-xs text-slate-900 font-mono">{value}/{max}</span>
        </div>
      )}
      <div className="w-full bg-slate-200 h-3 rounded-full overflow-hidden border-2 border-slate-300">
        <div
          className="h-full bg-indigo-600 transition-all duration-300"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};
