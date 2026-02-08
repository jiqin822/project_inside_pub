import React, { useState } from 'react';
import { UserProfile, ActivityCard, Memory, EconomyConfig, LovedOne } from '../types';
import { Heart, Zap, Calendar, Sparkles, BookHeart, X, Loader2, Flame, Camera, User } from 'lucide-react';
import { generateActivities } from '../services/geminiService';
import { apiService } from '../services/apiService';

interface Props {
  user: UserProfile;
  xp: number;
  setXp: (xp: number) => void;
  economy: EconomyConfig;
  onExit: () => void;
  onUpdateLovedOne: (id: string, updates: Partial<LovedOne>) => void;
}

const HARDCODED_ACTIVITIES: ActivityCard[] = [
  {
    id: 'h1',
    title: 'The Eye Contact Challenge',
    description: 'Sit opposite each other for 2 minutes maintaining eye contact without speaking. It is okay to laugh!',
    duration: '2 mins',
    type: 'deep',
    xpReward: 150
  },
  {
    id: 'h2',
    title: 'Kitchen Dance Party',
    description: 'Put on your favorite upbeat song and dance in the kitchen while making a snack together.',
    duration: '15 mins',
    type: 'fun',
    xpReward: 100
  },
  {
    id: 'h3',
    title: 'Compliment Barrage',
    description: 'Take turns giving each other 3 sincere compliments in a row.',
    duration: '5 mins',
    type: 'romantic',
    xpReward: 120
  }
];

export const ActivitiesMode: React.FC<Props> = ({ user, xp, setXp, economy, onExit, onUpdateLovedOne }) => {
  const [activities, setActivities] = useState<ActivityCard[]>(HARDCODED_ACTIVITIES);
  const [loading, setLoading] = useState(false);
  const [streak, setStreak] = useState(3);
  const [selectedPartnerId, setSelectedPartnerId] = useState<string>(user.lovedOnes[0]?.id || '');
  
  const [memories, setMemories] = useState<Memory[]>([
    { id: '1', activityTitle: 'Sunset Walk', date: Date.now() - 86400000 * 2, note: 'The sky was purple!', type: 'romantic' },
    { id: '2', activityTitle: 'Cooked Pasta', date: Date.now() - 86400000 * 5, note: 'We burned the sauce lol', type: 'fun' }
  ]);

  const selectedPartner = user.lovedOnes.find(l => l.id === selectedPartnerId);

  const handleGenerateQuests = async () => {
    setLoading(true);
    try {
      // Try backend API first, fallback to Gemini if no relationship
      if (selectedPartnerId) {
        try {
          const response = await apiService.getActivitySuggestions(selectedPartnerId);
          const suggestions = response.data;
          // Map backend response to ActivityCard format
          const mappedActivities: ActivityCard[] = suggestions.map((s: any) => ({
            id: s.id,
            title: s.title,
            description: s.description,
            duration: '15 mins', // Default
            type: 'fun' as const, // Default
            xpReward: 100, // Default
          }));
          if (mappedActivities.length > 0) {
            setActivities(mappedActivities);
            return;
          }
        } catch (apiError) {
          console.warn('Backend API failed, falling back to Gemini:', apiError);
        }
      }
      // Fallback to Gemini service
      const newActivities = await generateActivities('dating', 'connected');
      if (newActivities.length > 0) {
        setActivities(newActivities);
      }
    } catch (e) {
      console.error(e);
      alert("Could not generate new quests right now.");
    } finally {
      setLoading(false);
    }
  };

  const completeActivity = (activity: ActivityCard) => {
    const note = prompt("How did it go? Write a short memory:");
    if (note) {
        setMemories(prev => [{
            id: Date.now().toString(),
            activityTitle: activity.title,
            date: Date.now(),
            note,
            type: activity.type
        }, ...prev]);
        
        // Award Global XP
        setXp(xp + activity.xpReward);

        // Award Partner Currency if selected
        if (selectedPartner) {
            const currentBalance = selectedPartner.balance || 0;
            const currencyName = selectedPartner.economy?.currencyName || 'Tokens';
            onUpdateLovedOne(selectedPartner.id, { balance: currentBalance + activity.xpReward });
            alert(`Activity Completed! +${activity.xpReward} ${economy.currencyName} (Global) & +${activity.xpReward} ${currencyName}`);
        } else {
             alert(`Activity Completed! +${activity.xpReward} ${economy.currencyName}`);
        }
    }
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden font-sans relative" style={{ height: '100vh', width: '100vw' }}>
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

      {/* Gamification Header - Compact */}
      <div className="bg-white border-b-4 border-slate-900 px-4 py-3 shrink-0 flex items-center justify-between relative z-10" style={{ paddingTop: 'calc(var(--sat, 0px) + 0.75rem)', marginTop: 'calc(-1 * var(--sat, 0px))' }}>
           <div className="flex items-center gap-3">
                <div className="flex flex-col">
                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Experience</span>
                    <span className="text-xl font-black text-slate-900 font-mono leading-none">{xp} <span className="text-xs text-slate-400">{economy.currencyName}</span></span>
                </div>
           </div>
           <button onClick={onExit} className="w-8 h-8 flex items-center justify-center border-2 border-slate-200 hover:border-slate-900 text-slate-400 hover:text-slate-900 transition-colors">
                <X size={20} />
           </button>
           
           {/* Partner Selector for Context */}
           {user.lovedOnes.length > 0 && (
                <div className="flex items-center gap-2 bg-slate-100 border border-slate-200 px-2 py-1 rounded">
                    <User size={12} className="text-slate-400" />
                    <select 
                        value={selectedPartnerId} 
                        onChange={(e) => setSelectedPartnerId(e.target.value)}
                        className="bg-transparent text-xs font-bold uppercase text-slate-700 focus:outline-none"
                    >
                        {user.lovedOnes.map(lo => <option key={lo.id} value={lo.id}>{lo.name}</option>)}
                    </select>
                </div>
           )}
      </div>

      <div className="flex-1 overflow-hidden p-4 pb-24 relative z-10" style={{ minHeight: 0, overflowY: 'auto' }}>
            <div className="space-y-6">
               <div className="space-y-4">
                   <div className="flex items-center justify-between">
                        <h3 className="font-black text-slate-900 uppercase tracking-tighter text-lg">Active Assignments</h3>
                        <button 
                            onClick={handleGenerateQuests}
                            disabled={loading}
                            className="bg-white border-2 border-indigo-600 text-indigo-700 text-[10px] font-bold uppercase tracking-widest px-3 py-1 flex items-center gap-2 transition-colors disabled:opacity-50 hover:bg-indigo-50"
                        >
                            {loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />}
                            Refresh Specs
                        </button>
                    </div>
                   {loading ? (
                        <div className="space-y-4">
                            {[1,2,3].map(i => <div key={i} className="h-32 bg-white border-2 border-slate-200 animate-pulse" />)}
                        </div>
                    ) : (
                        activities.map((act) => (
                            <div key={act.id} className="bg-white border-2 border-slate-900 p-5 shadow-[6px_6px_0px_rgba(30,41,59,0.1)] hover:shadow-[8px_8px_0px_rgba(30,41,59,0.2)] hover:-translate-y-0.5 transition-all group">
                                <div className="flex justify-between items-start mb-3">
                                    <div className="px-2 py-0.5 border border-slate-300 bg-slate-50 text-[10px] font-mono font-bold text-slate-500 uppercase tracking-wider">
                                        Type: {act.type}
                                    </div>
                                    <div className="flex items-center gap-1 text-orange-600 font-bold text-xs font-mono bg-orange-50 px-2 py-0.5 border border-orange-200">
                                        <Zap size={12} className="fill-orange-600" />
                                        REWARD: {act.xpReward} {economy.currencySymbol}
                                    </div>
                                </div>
                                <h4 className="font-black text-xl text-slate-900 mb-2 uppercase tracking-tight">{act.title}</h4>
                                <p className="text-slate-600 text-sm leading-relaxed mb-4 border-l-2 border-slate-200 pl-3">{act.description}</p>
                                <div className="flex items-center justify-between border-t border-slate-100 pt-3 mt-auto">
                                    <div className="flex items-center gap-3 text-xs text-slate-400 font-mono uppercase">
                                        <div className="flex items-center gap-1"><Calendar size={12} /> EST: {act.duration}</div>
                                    </div>
                                    <button 
                                        onClick={() => completeActivity(act)}
                                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 text-xs font-bold uppercase tracking-widest border-2 border-transparent hover:border-indigo-900 transition-all shadow-[2px_2px_0px_#312e81] active:translate-y-0.5 active:shadow-none"
                                    >
                                        Mark Complete
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
               </div>

               {/* PAST MEMORIES */}
               <div className="space-y-4 pt-4">
                    <h3 className="font-black text-slate-900 uppercase tracking-tighter text-lg border-t-2 border-slate-200 pt-6 flex items-center gap-2">
                        <BookHeart size={20} className="text-slate-900" />
                        Archived Logs
                    </h3>
                    {memories.length === 0 && <p className="text-center text-slate-400 py-6 text-xs font-mono uppercase border-2 border-dashed border-slate-300 bg-slate-50/50">NO DATA FOUND.</p>}
                    {memories.map((mem) => (
                        <div key={mem.id} className="bg-white border-2 border-slate-200 hover:border-slate-400 transition-colors p-0 flex">
                            <div className="w-16 bg-slate-100 flex flex-col items-center justify-center text-slate-300 border-r-2 border-slate-200">
                                 <Camera size={20} />
                            </div>
                            <div className="p-3 flex-1">
                                <div className="flex justify-between items-start mb-1">
                                    <h4 className="font-bold text-slate-900 text-sm uppercase">{mem.activityTitle}</h4>
                                    <span className="text-[9px] font-mono text-slate-400">{new Date(mem.date).toLocaleDateString()}</span>
                                </div>
                                <p className="text-slate-600 text-xs italic font-serif">"{mem.note}"</p>
                            </div>
                        </div>
                    ))}
               </div>
            </div>
      </div>
    </div>
  );
};
