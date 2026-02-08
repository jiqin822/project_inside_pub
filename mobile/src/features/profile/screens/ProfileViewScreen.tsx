import React, { useState } from 'react';
import { User, Heart, Users, Activity, TrendingUp, BarChart3, ArrowLeft, ChevronRight, BookHeart } from 'lucide-react';
import { RoomHeader } from '../../../shared/ui/RoomHeader';
import { RoomSubTabs, RoomSubTabButton } from '../../../shared/ui/RoomSubTabs';
import { LoveMapStatusCard } from '../../../shared/ui/LoveMapStatusCard';
import { MarketAnalyticsCard } from '../../../shared/ui/MarketAnalyticsCard';
import { InteractionLogCard } from '../../../shared/ui/InteractionLogCard';
import { MemoryScrapbookView } from '../../activities/components/MemoryScrapbookView';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';
import type { LovedOne } from '../../../shared/types/domain';

interface Props {
  onBack: () => void;
}

/** Detail view for a single relationship node (from inside ProfileView) */
const RelationshipDetail: React.FC<{ person: LovedOne; onBack: () => void }> = ({ person, onBack }) => {
  const transactions = person.transactions || [];
  const totalTransactions = transactions.length;
  const spendCount = transactions.filter(t => t.category === 'spend').length;
  const earnCount = transactions.filter(t => t.category === 'earn').length;
  const rawScore = ((person.balance || 0) / 100) + (totalTransactions * 5);
  const loveMapScore = Math.min(Math.floor(rawScore), 100);
  const mapLevel = loveMapScore > 80 ? 'Level 5: Inner World' : loveMapScore > 50 ? 'Level 3: History' : 'Level 1: The Basics';

  return (
    <div className="animate-fade-in space-y-6">
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-slate-500 hover:text-slate-900 mb-2 transition-colors"
      >
        <ArrowLeft size={12} /> Back to Network
      </button>

      <div className="bg-white border-2 border-slate-900 p-6 shadow-[4px_4px_0px_rgba(30,41,59,0.1)] flex items-center gap-6">
        <div className="w-20 h-20 bg-slate-900 text-white flex items-center justify-center font-bold text-3xl border-4 border-slate-100 shadow-inner">
          {person.name.charAt(0)}
        </div>
        <div>
          <h2 className="text-2xl font-black text-slate-900 uppercase tracking-tighter leading-none">{person.name}</h2>
          <p className="text-xs font-mono text-slate-500 uppercase mt-1 bg-slate-100 inline-block px-2 py-0.5">{person.relationship}</p>
        </div>
      </div>

      <LoveMapStatusCard loveMapScore={loveMapScore} mapLevel={mapLevel} />

      <MarketAnalyticsCard
        balance={person.balance ?? 0}
        currencySymbol={person.economy?.currencySymbol ?? '🪙'}
        currencyName={person.economy?.currencyName ?? 'Tokens'}
        totalTransactions={totalTransactions}
        spendCount={spendCount}
        earnCount={earnCount}
      />

      <InteractionLogCard transactions={transactions} />
    </div>
  );
};

// Simple SVG Line Chart Component - Technical Style
const MiniTrendChart: React.FC<{ data: number[], color: string }> = ({ data, color }) => {
    const max = Math.max(...data, 100);
    const min = Math.min(...data, 0);
    const range = max - min || 1;
    const height = 40;
    const width = 100;
    
    const points = data.map((val, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((val - min) / range) * height;
        return `${x},${y}`;
    }).join(' ');

    return (
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
            {/* Grid lines */}
            <line x1="0" y1="0" x2="100" y2="0" stroke="#e2e8f0" strokeWidth="0.5" strokeDasharray="2 2" />
            <line x1="0" y1="20" x2="100" y2="20" stroke="#e2e8f0" strokeWidth="0.5" strokeDasharray="2 2" />
            <line x1="0" y1="40" x2="100" y2="40" stroke="#e2e8f0" strokeWidth="0.5" strokeDasharray="2 2" />

            <polyline 
                fill="none" 
                stroke={color} 
                strokeWidth="1.5" 
                points={points} 
                strokeLinejoin="round" 
            />
            {data.map((val, i) => {
                 const x = (i / (data.length - 1)) * width;
                 const y = height - ((val - min) / range) * height;
                 return <circle key={i} cx={x} cy={y} r="1.5" fill="white" stroke={color} strokeWidth="1.5" />;
            })}
        </svg>
    );
};

export const ProfileView: React.FC<Props> = ({ onBack }) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();

  if (!user) {
    return null; // Should not happen, but guard against it
  }
  const [activeTab, setActiveTab] = useState<'memory' | 'overview' | 'relationships'>('memory');
  const [selectedRelationId, setSelectedRelationId] = useState<string | null>(null);

  const networkNodes: LovedOne[] = relationships.length > 0 ? relationships : user.lovedOnes;

  const weeklyTrend = user.stats?.weeklyTrends || [65, 70, 68, 75, 82, 80, 85];
  const commScore = user.stats?.communicationScore || 78;
  const affectionScore = user.stats?.overallAffection || 85;

  const handleRelationshipBack = () => setSelectedRelationId(null);

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden font-sans relative" style={{ height: '100vh', width: '100vw', paddingTop: 'var(--sat, 0px)' }}>
      {/* Background Grid */}
      <div className="fixed inset-0 z-0 pointer-events-none opacity-20" 
            style={{ 
                backgroundImage: 'linear-gradient(#1e293b 1px, transparent 1px), linear-gradient(90deg, #1e293b 1px, transparent 1px)', 
                backgroundSize: '20px 20px',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0
            }}>
      </div>

      <RoomHeader
        moduleTitle="MODULE: INSIDE OF ME"
        moduleIcon={<User size={12} />}
        title={<>MASTER SUITE <span className="text-sm font-normal text-slate-500 normal-case">[under construction]</span></>}
        subtitle={{ text: 'REFLECTIONS', colorClass: 'text-indigo-600' }}
        onClose={onBack}
        headerRight={
          <div className="w-8 h-8 bg-indigo-600 text-white flex items-center justify-center font-bold text-sm border-2 border-slate-900">
            {user.name.charAt(0)}
          </div>
        }
      />

      {/* Tabs - hide when viewing a relationship detail */}
      {!selectedRelationId && (
        <RoomSubTabs>
            {[
                { id: 'memory', label: 'Memory', icon: <BookHeart size={14} /> },
                { id: 'overview', label: 'Overview', icon: <Activity size={14} /> },
                { id: 'relationships', label: 'Network', icon: <Users size={14} /> },
            ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-widest flex items-center justify-center gap-2 transition-all border-2 ${
                      activeTab === tab.id 
                      ? 'bg-slate-900 text-white border-slate-900 shadow-[2px_2px_0px_rgba(0,0,0,0.2)]' 
                      : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                  }`}
                >
                    {tab.icon}
                    {tab.label}
                </button>
            ))}
        </RoomSubTabs>
      )}

      <div className="flex-1 overflow-hidden p-4 space-y-6 relative z-10 pb-20" style={{ minHeight: 0, overflowY: 'auto' }}>
        
        {/* === MEMORY TAB (front page) === */}
        {activeTab === 'memory' && (
          <div className="space-y-6 animate-fade-in">
            <MemoryScrapbookView />
          </div>
        )}

        {/* === OVERVIEW TAB === */}
        {activeTab === 'overview' && (
            <div className="space-y-6 animate-fade-in">
                
                {/* Score Cards */}
                <div className="grid grid-cols-2 gap-4">
                    <div className="bg-white p-4 border-2 border-slate-900 shadow-[4px_4px_0px_rgba(30,41,59,0.1)] relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-2 opacity-5">
                            <Heart size={64} className="text-rose-500" />
                        </div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Connection Level</p>
                        <div className="flex items-end gap-2">
                            <span className="text-3xl font-black text-rose-500 font-mono">{affectionScore}%</span>
                            <span className="text-[10px] font-bold text-green-600 mb-1 flex items-center bg-green-50 px-1 border border-green-200"><TrendingUp size={10} className="mr-0.5" /> +2.4%</span>
                        </div>
                        <div className="w-full bg-slate-100 h-2 mt-3 border border-slate-200">
                            <div className="h-full bg-rose-500" style={{ width: `${affectionScore}%` }}></div>
                        </div>
                    </div>

                    <div className="bg-white p-4 border-2 border-slate-900 shadow-[4px_4px_0px_rgba(30,41,59,0.1)] relative overflow-hidden">
                        <div className="absolute top-0 right-0 p-2 opacity-5">
                            <Activity size={64} className="text-indigo-500" />
                        </div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Comm. Score</p>
                        <div className="flex items-end gap-2">
                            <span className="text-3xl font-black text-indigo-500 font-mono">{commScore}</span>
                            <span className="text-[10px] font-bold text-slate-400 mb-1">/ 100</span>
                        </div>
                         <div className="w-full bg-slate-100 h-2 mt-3 border border-slate-200">
                            <div className="h-full bg-indigo-500" style={{ width: `${commScore}%` }}></div>
                        </div>
                    </div>
                </div>

                {/* Weekly Trend */}
                <div className="bg-white p-5 border-2 border-slate-200">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-bold text-slate-800 flex items-center gap-2 uppercase tracking-tight text-sm">
                            <BarChart3 size={16} className="text-slate-400" />
                            Connection Quality
                        </h3>
                        <div className="text-[9px] font-mono bg-slate-100 px-2 py-1 border border-slate-200 text-slate-500 uppercase">LAST 7 DAYS</div>
                    </div>
                    <div className="h-20 flex items-end">
                        <MiniTrendChart data={weeklyTrend} color="#6366f1" />
                    </div>
                    <div className="flex justify-between mt-2 text-[9px] text-slate-400 font-mono uppercase">
                        <span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span><span>Sun</span>
                    </div>
                </div>

                {/* Account Summary */}
                <div className="bg-white border-2 border-slate-200">
                    <div className="p-3 bg-slate-50 border-b-2 border-slate-200">
                        <h3 className="font-bold text-slate-800 flex items-center gap-2 text-xs uppercase tracking-widest">
                            <User size={14} /> Account Config
                        </h3>
                    </div>
                    <div className="p-4 space-y-4">
                        <div className="flex justify-between items-center">
                            <span className="text-sm text-slate-600 font-medium">Voice Print ID</span>
                            <span className="text-[10px] font-mono bg-slate-100 px-2 py-1 border border-slate-200 text-slate-500">{user.voicePrintId || 'NOT SET'}</span>
                        </div>
                         <div className="flex justify-between items-center">
                            <span className="text-sm text-slate-600 font-medium">Personality Type</span>
                            <span className="text-[10px] font-bold text-indigo-600 border border-indigo-200 bg-indigo-50 px-2 py-1">{user.personalityType || 'UNSET'}</span>
                        </div>
                    </div>
                </div>
            </div>
        )}

        {/* === RELATIONSHIPS TAB === */}
        {activeTab === 'relationships' && (
             <div className="space-y-4 animate-fade-in">
                 {selectedRelationId ? (
                   (() => {
                     const person = networkNodes.find(l => l.id === selectedRelationId);
                     return person ? <RelationshipDetail person={person} onBack={handleRelationshipBack} /> : null;
                   })()
                 ) : (
                   <>
                     <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 px-1 border-b border-slate-200 pb-1">Network Nodes</h3>

                     {networkNodes.length === 0 && (
                         <div className="text-center py-8 bg-white border-2 border-dashed border-slate-300">
                             <p className="text-xs font-mono text-slate-500 uppercase">No relationships tracked yet.</p>
                         </div>
                     )}

                     {networkNodes.map((person, idx) => {
                         const transactions = person.transactions || [];
                         const totalTx = transactions.length;
                         const rawScore = ((person.balance ?? 0) / 100) + (totalTx * 5);
                         const loveMapScore = Math.min(Math.floor(rawScore), 100);
                         const mapLevel = loveMapScore > 80 ? 'Level 5: Inner World' : loveMapScore > 50 ? 'Level 3: History' : 'Level 1: The Basics';
                         const mockTrend = [60, 65, 62, 70, 72, 68, loveMapScore || 60 + (person.name.length * 5) % 35];

                         return (
                             <button
                                 key={person.id}
                                 onClick={() => setSelectedRelationId(person.id)}
                                 className="w-full bg-white p-4 border-2 border-slate-200 hover:border-slate-900 transition-colors group text-left"
                             >
                                 <div className="flex items-center justify-between mb-3">
                                     <div className="flex items-center gap-3">
                                         <div className={`w-10 h-10 flex items-center justify-center font-bold text-white border-2 border-slate-900 shrink-0 ${idx % 2 === 0 ? 'bg-indigo-600' : 'bg-rose-500'}`}>
                                             {person.name.charAt(0)}
                                         </div>
                                         <div>
                                             <h4 className="font-bold text-slate-900 uppercase tracking-tight">{person.name}</h4>
                                             <p className="text-[10px] font-mono text-slate-500 uppercase">{person.relationship}</p>
                                         </div>
                                     </div>
                                     <div className="text-right shrink-0">
                                         <div className="text-2xl font-black text-slate-900 font-mono">{loveMapScore || 0}</div>
                                         <div className="text-[9px] font-bold text-slate-400 uppercase">Love Map %</div>
                                     </div>
                                 </div>

                                 <div className="flex flex-wrap gap-2 mb-2">
                                     <div className="px-2 py-0.5 bg-slate-100 border border-slate-200 text-[9px] font-mono font-bold text-slate-600 uppercase">
                                         {person.balance ?? 0} {person.economy?.currencySymbol ?? '🪙'}
                                     </div>
                                     <div className="px-2 py-0.5 bg-rose-50 border border-rose-200 text-[9px] font-mono font-bold text-rose-700 uppercase">
                                         {mapLevel}
                                     </div>
                                 </div>

                                 <div className="h-8 w-full mt-2 opacity-50 group-hover:opacity-100 transition-opacity">
                                    <MiniTrendChart data={mockTrend} color={idx % 2 === 0 ? '#4f46e5' : '#e11d48'} />
                                 </div>

                                 <div className="mt-3 pt-3 border-t border-slate-100 flex justify-between items-center text-xs">
                                     <span className="text-slate-400 font-mono text-[9px]">Tap to View Full Analysis</span>
                                     <span className="font-bold text-indigo-600 group-hover:text-indigo-900 uppercase text-[10px] tracking-wider flex items-center gap-1">
                                         Access Data <ChevronRight size={12} />
                                     </span>
                                 </div>
                             </button>
                         );
                     })}

                     <button className="w-full py-3 bg-slate-100 hover:bg-slate-200 text-slate-500 font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 transition-colors border-2 border-slate-200 hover:border-slate-400">
                         <Users size={14} /> Add New Node
                     </button>
                   </>
                 )}
             </div>
        )}
      </div>
    </div>
  );
};
