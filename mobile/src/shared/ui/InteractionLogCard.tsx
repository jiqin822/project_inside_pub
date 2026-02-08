import React from 'react';
import { Activity } from 'lucide-react';
import type { Transaction } from '../types/domain';

export interface InteractionLogCardProps {
  transactions: Transaction[];
  /** Max height for scroll area, default max-h-60 */
  maxHeight?: string;
  /** Max number of items to show, default 10 */
  maxItems?: number;
  /** Empty state message */
  emptyMessage?: string;
}

export const InteractionLogCard: React.FC<InteractionLogCardProps> = ({
  transactions,
  maxHeight = 'max-h-60',
  maxItems = 10,
  emptyMessage = 'No interaction data available.',
}) => {
  const displayList = [...transactions].reverse().slice(0, maxItems);

  return (
    <div className="bg-white border-2 border-slate-200">
      <div className="bg-slate-50 border-b border-slate-200 p-3 flex justify-between items-center">
        <h3 className="font-bold text-slate-700 text-xs uppercase tracking-widest flex items-center gap-2">
          <Activity size={14} className="text-indigo-500" /> Interaction Log
        </h3>
      </div>
      <div className={`divide-y divide-slate-100 overflow-y-auto ${maxHeight}`}>
        {transactions.length === 0 && (
          <div className="p-6 text-center text-[10px] font-mono text-slate-400 uppercase">
            {emptyMessage}
          </div>
        )}
        {displayList.map((tx) => (
          <div
            key={tx.id}
            className="p-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 flex items-center justify-center bg-white border border-slate-200 text-lg">
                {tx.icon}
              </div>
              <div>
                <div className="font-bold text-slate-800 text-xs uppercase">{tx.title}</div>
                <div className="text-[9px] font-mono text-slate-400">
                  {tx.status.replace('_', ' ')} • {new Date(tx.timestamp).toLocaleDateString()}
                </div>
              </div>
            </div>
            <div
              className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded ${
                tx.category === 'earn' ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'
              }`}
            >
              {tx.category === 'earn' ? '+' : '-'}
              {tx.cost}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
