
import React, { useState } from 'react';
import { UserProfile } from '../types';
import { X, User, Heart, Shield, Users, Activity, TrendingUp, BarChart3 } from 'lucide-react';

interface Props {
  user: UserProfile;
  onBack: () => void;
}

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

export const ProfileView: React.FC<Props> = ({ user, onBack }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'relationships'>('overview');
  
  const weeklyTrend = user.stats?.weeklyTrends || [65, 70, 68, 75, 82, 80, 85];
  const commScore = user.stats?.communicationScore || 78;
  const affectionScore = user.stats?.overallAffection || 85;

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

      {/* Header */}
      <div className="bg-white border-b-4 border-slate-900 px-4 py-4 flex items-center justify-between shrink-0 sticky top-0 z-20">
        <div className="flex items-center gap-3">
            <div>
                <h1 className="text-sm font-black text-slate-900 uppercase tracking-widest leading-none">My Room</h1>
                <p className="text-[9px] text-slate-400 font-mono uppercase">ANALYTICS & DATA</p>
            </div>
        </div>
        <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-600 text-white flex items-center justify-center font-bold text-sm border-2 border-slate-900">
                {user.name.charAt(0)}
            </div>
            <button 
                onClick={onBack}
                className="w-8 h-8 flex items-center justify-center border-2 border-slate-200 hover:border-slate-900 text-slate-400 hover:text-slate-900 transition-colors"
            >
                <X size={20} />
            </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex p-2 gap-2 border-b border-slate-200 bg-white shrink-0 relative z-10">
          {[
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
      </div>

      <div className="flex-1 overflow-hidden p-4 space-y-6 relative z-10 pb-20" style={{ minHeight: 0, overflowY: 'auto' }}>
        
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

                {/* Attachment Style Deep Dive */}
                <div className="bg-slate-900 text-white p-5 border-2 border-slate-900 shadow-[6px_6px_0px_rgba(0,0,0,0.2)]">
                    <div className="flex items-center justify-between mb-4 border-b border-slate-700 pb-2">
                        <div className="flex items-center gap-2">
                            <Shield size={16} className="text-emerald-400" />
                            <h3 className="font-bold uppercase tracking-wider text-sm">Attachment Profile</h3>
                        </div>
                        <span className="text-[10px] font-mono text-slate-400 uppercase border border-slate-600 px-2 py-0.5">{user.attachmentStyle}</span>
                    </div>
                    
                    <div className="space-y-6">
                        <div className="relative pt-2">
                            <div className="flex justify-between text-[10px] font-bold text-slate-400 mb-1 uppercase tracking-widest">
                                <span>Anxiety</span>
                                <span className="text-white">{user.attachmentStats?.anxiety || 30}%</span>
                            </div>
                            <div className="w-full bg-slate-800 h-2 border border-slate-600">
                                <div className="h-full bg-gradient-to-r from-orange-500 to-rose-500" style={{ width: `${user.attachmentStats?.anxiety || 30}%` }}></div>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-1 font-mono">Tendency to worry about relationship availability.</p>
                        </div>

                        <div className="relative">
                             <div className="flex justify-between text-[10px] font-bold text-slate-400 mb-1 uppercase tracking-widest">
                                <span>Avoidance</span>
                                <span className="text-white">{user.attachmentStats?.avoidance || 20}%</span>
                            </div>
                            <div className="w-full bg-slate-800 h-2 border border-slate-600">
                                <div className="h-full bg-gradient-to-r from-blue-500 to-indigo-500" style={{ width: `${user.attachmentStats?.avoidance || 20}%` }}></div>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-1 font-mono">Tendency to value independence over intimacy.</p>
                        </div>
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
                 <h3 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2 px-1 border-b border-slate-200 pb-1">Network Nodes</h3>
                 
                 {user.lovedOnes.length === 0 && (
                     <div className="text-center py-8 bg-white border-2 border-dashed border-slate-300">
                         <p className="text-xs font-mono text-slate-500 uppercase">No relationships tracked yet.</p>
                     </div>
                 )}

                 {user.lovedOnes.map((person, idx) => {
                     const mockScore = 60 + (person.name.length * 5) % 35;
                     const mockTrend = [60, 65, 62, 70, 72, 68, mockScore];
                     
                     return (
                         <div key={person.id} className="bg-white p-4 border-2 border-slate-200 hover:border-slate-900 transition-colors group">
                             <div className="flex items-center justify-between mb-3">
                                 <div className="flex items-center gap-3">
                                     <div className={`w-10 h-10 flex items-center justify-center font-bold text-white border-2 border-slate-900 ${idx % 2 === 0 ? 'bg-indigo-600' : 'bg-rose-500'}`}>
                                         {person.name.charAt(0)}
                                     </div>
                                     <div>
                                         <h4 className="font-bold text-slate-900 uppercase tracking-tight">{person.name}</h4>
                                         <p className="text-[10px] font-mono text-slate-500 uppercase">{person.relationship}</p>
                                     </div>
                                 </div>
                                 <div className="text-right">
                                     <div className="text-2xl font-black text-slate-900 font-mono">{mockScore}</div>
                                     <div className="text-[9px] font-bold text-slate-400 uppercase">Index</div>
                                 </div>
                             </div>
                             
                             <div className="h-8 w-full mt-2 opacity-50 group-hover:opacity-100 transition-opacity">
                                <MiniTrendChart data={mockTrend} color={idx % 2 === 0 ? '#4f46e5' : '#e11d48'} />
                             </div>
                             
                             <div className="mt-3 pt-3 border-t border-slate-100 flex justify-between items-center text-xs">
                                 <span className="text-slate-400 font-mono text-[9px]">LAST PING: 2H AGO</span>
                                 <button className="font-bold text-indigo-600 hover:text-indigo-900 uppercase text-[10px] tracking-wider">Access Data</button>
                             </div>
                         </div>
                     );
                 })}

                 <button className="w-full py-3 bg-slate-100 hover:bg-slate-200 text-slate-500 font-bold text-xs uppercase tracking-widest flex items-center justify-center gap-2 transition-colors border-2 border-slate-200 hover:border-slate-400">
                     <Users size={14} /> Add New Node
                 </button>
             </div>
        )}
      </div>
    </div>
  );
};
