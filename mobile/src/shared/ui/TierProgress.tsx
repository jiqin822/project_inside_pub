import React from 'react';
import { Star, Lock } from 'lucide-react';

interface TierProgressProps {
  tier: number;
  stars: number; // 0-3
  isLocked?: boolean;
  isCurrent?: boolean;
  className?: string;
}

export const TierProgress: React.FC<TierProgressProps> = ({
  tier,
  stars,
  isLocked = false,
  isCurrent = false,
  className = '',
}) => {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span className="text-xs font-bold text-slate-700 uppercase">Tier {tier}</span>
      {isLocked ? (
        <Lock size={14} className="text-slate-400" />
      ) : (
        <div className="flex gap-0.5">
          {[1, 2, 3].map((star) => (
            <Star
              key={star}
              size={12}
              className={star <= stars ? 'fill-yellow-400 text-yellow-500' : 'text-slate-300'}
            />
          ))}
        </div>
      )}
      {isCurrent && (
        <span className="text-[10px] font-bold text-indigo-600 uppercase">Current</span>
      )}
    </div>
  );
};
