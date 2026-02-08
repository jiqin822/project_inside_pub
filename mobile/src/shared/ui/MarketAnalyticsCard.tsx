import React from 'react';
import { ShoppingBag } from 'lucide-react';

export interface MarketAnalyticsCardProps {
  /** Wallet balance for this relationship context */
  balance: number;
  /** Currency symbol, e.g. "🪙" */
  currencySymbol: string;
  /** Currency name for header, e.g. "Love Tokens" */
  currencyName: string;
  /** Total transaction count (lifetime vol) */
  totalTransactions: number;
  /** Count of spend/rewards redeemed */
  spendCount: number;
  /** Count of earn/quests completed */
  earnCount: number;
}

export const MarketAnalyticsCard: React.FC<MarketAnalyticsCardProps> = ({
  balance,
  currencySymbol,
  currencyName,
  totalTransactions,
  spendCount,
  earnCount,
}) => {
  return (
    <div className="bg-white border-2 border-slate-200 overflow-hidden">
      <div className="bg-slate-50 border-b border-slate-200 p-3 flex justify-between items-center">
        <h3 className="font-bold text-slate-700 text-xs uppercase tracking-widest flex items-center gap-2">
          <ShoppingBag size={14} className="text-emerald-500" /> Market Analytics
        </h3>
        <div className="text-[10px] font-mono text-slate-400">ECONOMY: {currencyName}</div>
      </div>
      <div className="grid grid-cols-2 divide-x divide-slate-100">
        <div className="p-4 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Wallet Balance</div>
          <div className="text-3xl font-black text-slate-900 font-mono tracking-tighter">
            {balance} <span className="text-sm text-slate-400">{currencySymbol}</span>
          </div>
        </div>
        <div className="p-4 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Lifetime Vol.</div>
          <div className="text-3xl font-black text-slate-900 font-mono tracking-tighter">
            {totalTransactions} <span className="text-sm text-slate-400">TX</span>
          </div>
        </div>
      </div>
      <div className="border-t border-slate-100 p-4 flex justify-around">
        <div className="text-center">
          <div className="text-[9px] font-mono text-slate-400 uppercase">Rewards Redeemed</div>
          <div className="font-bold text-slate-700">{spendCount}</div>
        </div>
        <div className="text-center">
          <div className="text-[9px] font-mono text-slate-400 uppercase">Quests Completed</div>
          <div className="font-bold text-slate-700">{earnCount}</div>
        </div>
      </div>
    </div>
  );
};
