import React from 'react';
import { Map as MapIcon } from 'lucide-react';

export interface LoveMapStatusCardProps {
  /** Love Map progress 0–100 */
  loveMapScore: number;
  /** Current depth label, e.g. "Level 1: The Basics" */
  mapLevel: string;
  /** Optional header badge text */
  headerBadge?: string;
}

export const LoveMapStatusCard: React.FC<LoveMapStatusCardProps> = ({
  loveMapScore,
  mapLevel,
  headerBadge = 'CARTOGRAPHY MODULE',
}) => {
  return (
    <div className="bg-white border-2 border-slate-200 overflow-hidden">
      <div className="bg-slate-50 border-b border-slate-200 p-3 flex justify-between items-center">
        <h3 className="font-bold text-slate-700 text-xs uppercase tracking-widest flex items-center gap-2">
          <MapIcon size={14} className="text-rose-500" /> Love Map Status
        </h3>
        <div className="text-[10px] font-mono text-slate-400">{headerBadge}</div>
      </div>
      <div className="p-5 flex items-center gap-6">
        <div className="relative w-24 h-24 flex items-center justify-center shrink-0">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
            <path
              className="text-slate-100"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="text-rose-500 drop-shadow-md"
              strokeDasharray={`${loveMapScore}, 100`}
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              fill="none"
              stroke="currentColor"
              strokeWidth="4"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-black text-slate-900">{loveMapScore}%</span>
          </div>
        </div>
        <div className="flex-1 space-y-3">
          <div>
            <div className="text-[10px] font-bold text-slate-400 uppercase">Current Depth</div>
            <div className="font-bold text-slate-800 uppercase">{mapLevel}</div>
          </div>
          <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
            <div className="bg-rose-500 h-full" style={{ width: `${loveMapScore}%` }}></div>
          </div>
          <div className="text-[9px] font-mono text-slate-400">
            Knowledge Base: {loveMapScore > 50 ? 'EXPANDING' : 'INITIALIZING'}
          </div>
        </div>
      </div>
    </div>
  );
};
