import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage, ChatAction, UserProfile } from '../types';
import { Send, User, Bot, Loader2, Info, Users, Handshake, Check, X as XIcon, MessageSquareQuote, Wind, Heart, Star, ChevronRight, Plus, Terminal, Mic } from 'lucide-react';
import { getTherapistResponse } from '../services/geminiService';
import ReactMarkdown from 'react-markdown';

interface Props {
  user: UserProfile;
  onExit: () => void;
}

// ... Overlays remain similar but styled ...
const BreathingOverlay = ({ onClose }: { onClose: () => void }) => {
  const [step, setStep] = useState(0); 
  const instructions = ["INHALE", "HOLD", "EXHALE", "HOLD"];
  
  useEffect(() => {
    const interval = setInterval(() => {
      setStep(s => (s + 1) % 4);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed inset-0 z-50 bg-slate-900 flex flex-col items-center justify-center text-white animate-fade-in relative overflow-hidden safe-area">
       {/* Grid Background */}
       <div className="absolute inset-0 z-0 pointer-events-none opacity-20" 
            style={{ 
                backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)', 
                backgroundSize: '40px 40px' 
            }}>
       </div>

       <button onClick={onClose} className="absolute top-6 right-6 p-4 border border-white hover:bg-white hover:text-slate-900 transition-colors z-50">
           <XIcon size={24} />
       </button>
       
       <div className="mb-12 text-center z-10">
          <div className="inline-flex items-center gap-2 border border-indigo-500 px-3 py-1 mb-4 text-indigo-400 font-mono text-xs uppercase tracking-widest">
             <Wind size={12} /> Protocol: CALM_DOWN
          </div>
          <h2 className="text-4xl font-black mb-2 uppercase tracking-tighter">
              Self-Soothing
          </h2>
          <p className="text-slate-400 font-mono text-sm">System Reset in Progress...</p>
       </div>

       <div className="relative w-80 h-80 flex items-center justify-center z-10">
          <div className="absolute inset-0 border-2 border-slate-700 rounded-full border-dashed"></div>
          
          <div 
            className={`absolute bg-indigo-600 transition-all duration-[4000ms] ease-in-out ${
                step === 0 ? 'w-full h-full opacity-50' : 
                step === 1 ? 'w-full h-full opacity-50' : 
                step === 2 ? 'w-24 h-24 opacity-80' : 
                'w-24 h-24 opacity-80'
            }`}
            style={{ borderRadius: '50%' }}
          ></div>

          <div className="z-10 text-center pointer-events-none">
             <div className="text-5xl font-black tracking-widest uppercase text-white drop-shadow-lg">
               {instructions[step]}
             </div>
             <div className="text-xs font-mono mt-4 text-indigo-400">
               CYCLE: 4-4-4-4
             </div>
          </div>
       </div>

       <button 
         onClick={onClose} 
         className="mt-16 px-10 py-4 bg-transparent border-2 border-white text-white hover:bg-white hover:text-slate-900 font-bold uppercase tracking-widest transition-colors z-10"
       >
         I Am Stabilized
       </button>
    </div>
  )
}

const AppreciationOverlay = ({ onClose, onSubmit, partnerName }: { onClose: () => void, onSubmit: (items: string[]) => void, partnerName: string }) => {
  const [items, setItems] = useState(['', '', '']);

  const handleChange = (index: number, val: string) => {
    const newItems = [...items];
    newItems[index] = val;
    setItems(newItems);
  };

  const handleSubmit = () => {
    const filled = items.filter(i => i.trim());
    if (filled.length > 0) {
      onSubmit(filled);
    } else {
      onClose();
    }
  };

    return (
    <div className="fixed inset-0 z-50 bg-slate-900/95 flex flex-col items-center justify-center text-white animate-fade-in p-6 safe-area">
       <button onClick={onClose} className="absolute top-6 right-6 p-2 text-slate-400 hover:text-white">
           <XIcon size={24} />
       </button>
       
       <div className="w-full max-w-md bg-white text-slate-900 p-8 border-2 border-slate-900 shadow-[8px_8px_0px_rgba(255,255,255,0.1)]">
           <div className="mb-8 text-center">
              <div className="w-12 h-12 bg-rose-100 text-rose-500 border-2 border-rose-500 flex items-center justify-center mx-auto mb-4">
                  <Heart size={24} className="fill-rose-500" />
              </div>
              <h2 className="text-2xl font-black uppercase tracking-tight mb-2">Operation: Fondness</h2>
              <p className="text-slate-500 text-xs font-mono">TARGET: {partnerName.toUpperCase()}</p>
           </div>

           <div className="space-y-4 mb-8">
               {items.map((item, i) => (
                   <div key={i} className="relative">
                       <span className="absolute left-3 top-3.5 text-slate-400 font-mono text-xs">0{i + 1}</span>
                       <input 
                          autoFocus={i === 0}
                          type="text"
                          value={item}
                          onChange={(e) => handleChange(i, e.target.value)}
                          placeholder={`APPRECIATION DATA...`}
                          className="w-full bg-slate-50 border-2 border-slate-200 py-3 pl-10 pr-4 focus:outline-none focus:border-rose-500 focus:bg-white transition-all font-mono text-sm uppercase placeholder:text-slate-300"
                       />
                   </div>
               ))}
           </div>

           <button 
             onClick={handleSubmit} 
             disabled={!items.some(i => i.trim())}
             className="w-full py-4 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white font-bold uppercase tracking-widest border-2 border-slate-900 shadow-[4px_4px_0px_rgba(30,41,59,1)] active:translate-y-0.5 active:shadow-none transition-all"
           >
             Submit Data
           </button>
       </div>
    </div>
  )
}

interface Subject {
  id: string;
  name: string;
  relationship: string;
}

export const TherapistMode: React.FC<Props> = ({ user, onExit }) => {
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);
  const [isAddingNew, setIsAddingNew] = useState(false);
  const [newSubjectName, setNewSubjectName] = useState('');
  const [newSubjectRel, setNewSubjectRel] = useState('');

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMediation, setIsMediation] = useState(false);
  const [waitingForPartner, setWaitingForPartner] = useState(false);
  const [partnerPerspective, setPartnerPerspective] = useState<string | null>(null);
  const [isBreathing, setIsBreathing] = useState(false);
  const [isAppreciation, setIsAppreciation] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  
  const scrollRef = useRef<HTMLDivElement>(null);

  const lovedOnes: Subject[] = user.lovedOnes.map(l => ({
      id: l.id,
      name: l.name,
      relationship: l.relationship
  }));

  useEffect(() => {
    if (selectedSubject) {
      const now = Date.now();
      setMessages([
        {
          id: '1',
          role: 'model',
          text: 'How are you feeling? Anything on your mind?',
          timestamp: now
        }
      ]);
    }
  }, [selectedSubject]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, waitingForPartner]);

  const handleAddNew = () => {
    if (newSubjectName && newSubjectRel) {
      setSelectedSubject({
        id: 'custom_' + Date.now(),
        name: newSubjectName,
        relationship: newSubjectRel
      });
    }
  };

  const processUserMessage = async (text: string) => {
    if (!selectedSubject) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      text: text,
      timestamp: Date.now()
    };

    setMessages(prev => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const history = messages
        .filter(m => m.role === 'user' || m.role === 'model')
        .map(m => ({ role: m.role as 'user' | 'model', text: m.text }));

      history.push({ role: 'user', text });

      const responseText = await getTherapistResponse(
          history.slice(0, -1),
          text, 
          user,
          selectedSubject,
          partnerPerspective || undefined
      );
      
      const actions: ChatAction[] = [];
      const lowerResp = responseText.toLowerCase();

      if (lowerResp.includes('breathing exercise')) {
        actions.push({ id: 'start_breathing', label: 'INITIATE BREATHING', style: 'primary' });
      }
      if (lowerResp.includes('appreciation exercise')) {
        actions.push({ id: 'start_appreciation', label: 'INITIATE APPRECIATION', style: 'primary' });
      }

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'model',
        text: responseText,
        timestamp: Date.now(),
        actions: actions.length > 0 ? actions : undefined
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    const text = input;
    setInput('');
    processUserMessage(text);
  };

  const startMediation = () => {
    if (!selectedSubject) return;
    setIsMediation(true);
    setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'model',
        text: `**MEDIATION PROTOCOL ACTIVE** \n\nI will act as a neutral node. Querying **${selectedSubject.name}** for asynchronous perspective data.\n\nAuthorize external contact?`,
        timestamp: Date.now(),
        actions: [
            { id: 'yes_partner', label: `AUTHORIZE CONTACT`, style: 'primary' },
            { id: 'no_partner', label: 'DENY', style: 'secondary' }
        ]
    }]);
  };

  const handleActionClick = (actionId: string, msgId: string) => {
      setMessages(prev => prev.map(m => 
        m.id === msgId ? { ...m, actions: undefined } : m
      ));

      if (actionId === 'yes_partner') {
          handleGetPartnerPerspective();
      } else if (actionId === 'no_partner') {
           setMessages(prev => [...prev, {
               id: Date.now().toString(),
               role: 'model',
               text: "External contact denied. Focusing on local user analysis.",
               timestamp: Date.now()
           }]);
      } else if (actionId === 'start_breathing') {
          setIsBreathing(true);
      } else if (actionId === 'start_appreciation') {
          setIsAppreciation(true);
      }
  };

  const handleAppreciationSubmit = (items: string[]) => {
      setIsAppreciation(false);
      const text = `I want to express appreciation for ${selectedSubject?.name} to help shift our dynamic:\n` + items.map((it, i) => `${i+1}. ${it}`).join('\n');
      processUserMessage(text);
  };

  const handleGetPartnerPerspective = () => {
      if (!selectedSubject) return;
      setWaitingForPartner(true);
      
      setTimeout(() => {
          setWaitingForPartner(false);
          const simPerspective = "I feel unheard sometimes. It seems like whenever I bring up an issue, it turns into a debate about facts instead of feelings. I just want to be listened to.";

          setPartnerPerspective(simPerspective);

          setMessages(prev => [...prev, {
              id: Date.now().toString(),
              role: 'system',
              isPartnerContext: true,
              text: `**INCOMING TRANSMISSION FROM ${selectedSubject.name.toUpperCase()}:**\n\n"${simPerspective}"`,
              timestamp: Date.now()
          }]);

          triggerAnalysisWithPerspective(simPerspective);

      }, 3500);
  };

  const triggerAnalysisWithPerspective = async (perspective: string) => {
      if (!selectedSubject) return;
      setIsLoading(true);
      try {
        const history = messages
            .filter(m => m.role === 'user' || m.role === 'model')
            .map(m => ({ role: m.role as 'user' | 'model', text: m.text }));

        const responseText = await getTherapistResponse(
            history, 
            "Analyze the conflict now that you have both sides.", 
            user,
            selectedSubject,
            perspective
        );

        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'model',
            text: responseText,
            timestamp: Date.now()
        }]);
      } catch (e) {
          console.error(e);
      } finally {
          setIsLoading(false);
      }
  };

  // --- Render Selection Screen ---
  if (!selectedSubject) {
    return (
      <div className="flex flex-col h-screen bg-slate-50 relative animate-fade-in font-sans" style={{ height: '100vh', width: '100vw' }}>
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

        <header className="relative z-10 px-6 py-4 bg-white border-b-4 border-slate-900 flex items-center justify-between" style={{ paddingTop: 'calc(var(--sat, 0px) + 1rem)', marginTop: 'calc(-1 * var(--sat, 0px))' }}>
           <div>
               <div className="flex items-center gap-2 text-slate-500 text-[10px] font-mono font-bold uppercase tracking-widest mb-1">
                   <Terminal size={12} />
                   <span>Module: Therapy</span>
               </div>
               <h1 className="text-2xl font-black text-slate-900 uppercase tracking-tighter">Session Setup</h1>
           </div>
           <button onClick={onExit} className="w-8 h-8 flex items-center justify-center border-2 border-slate-200 hover:border-slate-900 text-slate-400 hover:text-slate-900 transition-colors">
               <XIcon size={20} />
           </button>
        </header>

        <div className="flex-1 p-6 overflow-hidden relative z-10" style={{ minHeight: 0, overflowY: 'auto' }}>
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-6 border-b border-slate-200 pb-2">I want to talk about relationship with</h2>
            
            <div className="grid grid-cols-1 gap-4 mb-8">
               {lovedOnes.length > 0 ? lovedOnes.map(subject => (
                  <button 
                    key={subject.id}
                    onClick={() => setSelectedSubject(subject)}
                    className="flex items-center p-4 bg-white border-2 border-slate-900 shadow-[4px_4px_0px_rgba(30,41,59,0.2)] hover:shadow-[6px_6px_0px_rgba(30,41,59,0.2)] hover:-translate-y-0.5 transition-all text-left group active:translate-y-0 active:shadow-none"
                  >
                      <div className="w-12 h-12 bg-indigo-600 text-white flex items-center justify-center font-bold text-lg mr-4 border-2 border-slate-900">
                          {subject.name.charAt(0)}
                      </div>
                      <div className="flex-1">
                          <h3 className="font-bold text-slate-900 uppercase tracking-tight">{subject.name}</h3>
                          <p className="text-xs font-mono text-slate-500 uppercase">{subject.relationship}</p>
                      </div>
                      <ChevronRight className="text-slate-300 group-hover:text-slate-900" />
                  </button>
               )) : (
                 <p className="text-sm text-slate-400 italic font-mono border border-dashed border-slate-300 p-4">NO SUBJECTS FOUND IN DATABASE.</p>
               )}
            </div>

            <div className="pt-6">
                <button 
                  onClick={() => setIsAddingNew(!isAddingNew)}
                  className={`flex items-center gap-2 text-xs font-bold uppercase tracking-widest ${isAddingNew ? 'text-slate-900' : 'text-slate-500 hover:text-indigo-600'}`}
                >
                    <Plus size={14} />
                    {isAddingNew ? 'Cancel Entry' : 'New Entry'}
                </button>

                {isAddingNew && (
                    <div className="mt-4 bg-white p-4 border-2 border-slate-900 animate-slide-in-down shadow-[4px_4px_0px_rgba(30,41,59,0.1)]">
                        <div className="space-y-4">
                            <div>
                                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Subject Name</label>
                                <input 
                                    type="text" 
                                    value={newSubjectName}
                                    onChange={(e) => setNewSubjectName(e.target.value)}
                                    placeholder="ENTER NAME"
                                    className="w-full bg-slate-50 border-2 border-slate-200 p-2 text-sm font-mono uppercase focus:outline-none focus:border-indigo-600"
                                />
                            </div>
                            <div>
                                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Relationship</label>
                                <input 
                                    type="text" 
                                    value={newSubjectRel}
                                    onChange={(e) => setNewSubjectRel(e.target.value)}
                                    placeholder="ENTER ROLE"
                                    className="w-full bg-slate-50 border-2 border-slate-200 p-2 text-sm font-mono uppercase focus:outline-none focus:border-indigo-600"
                                />
                            </div>
                            <button 
                                onClick={handleAddNew}
                                disabled={!newSubjectName || !newSubjectRel}
                                className="w-full bg-indigo-600 text-white font-bold py-3 uppercase tracking-widest text-xs hover:bg-indigo-700 disabled:opacity-50 border-2 border-slate-900 shadow-[2px_2px_0px_rgba(0,0,0,1)] active:translate-y-0.5 active:shadow-none"
                            >
                                Initialize Session
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
      </div>
    );
  }

  // --- Render Chat Screen ---
    return (
      <div className="flex flex-col h-screen bg-slate-50 relative font-sans" style={{ height: '100vh', width: '100vw' }}>
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

      {isBreathing && <BreathingOverlay onClose={() => setIsBreathing(false)} />}
      {isAppreciation && (
        <AppreciationOverlay 
            partnerName={selectedSubject.name} 
            onClose={() => setIsAppreciation(false)} 
            onSubmit={handleAppreciationSubmit} 
        />
      )}

      {/* Header */}
      <header className={`relative z-10 px-4 py-3 border-b-4 flex justify-between items-center transition-colors ${isMediation ? 'bg-indigo-900 border-indigo-950 text-white' : 'bg-white border-slate-900 text-slate-900'}`} style={{ paddingTop: 'calc(var(--sat, 0px) + 0.75rem)', marginTop: 'calc(-1 * var(--sat, 0px))' }}>
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 flex items-center justify-center border-2 ${isMediation ? 'bg-indigo-700 border-white text-white' : 'bg-indigo-50 border-slate-900 text-indigo-600'}`}>
            {isMediation ? <Handshake size={20} /> : <Bot size={20} />}
          </div>
          <div>
            <h2 className="font-black uppercase tracking-tight leading-none text-lg">Kai</h2>
            <p className={`text-[9px] font-mono uppercase tracking-widest ${isMediation ? 'text-indigo-300' : 'text-slate-500'}`}>
                {isMediation ? `LINK: ${selectedSubject.name}` : `SUBJ: ${selectedSubject.name}`}
            </p>
          </div>
        </div>

        <button onClick={onExit} className={`w-8 h-8 flex items-center justify-center border-2 ${isMediation ? 'border-indigo-400 text-indigo-200 hover:bg-indigo-800' : 'border-slate-200 text-slate-400 hover:border-slate-900 hover:text-slate-900'} transition-colors`}>
          <X size={20} />
        </button>
      </header>

      {/* Main Content Area - CHAT ONLY */}
      <div className="flex-1 flex flex-col overflow-hidden relative z-10">
          <div 
              ref={scrollRef}
              className="flex-1 overflow-hidden p-4 space-y-6"
              style={{ minHeight: 0, overflowY: 'auto' }}
          >
              {messages.map((msg) => (
              <div 
                  key={msg.id} 
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'} gap-1`}
              >
                  {/* Role Label */}
                  <span className="text-[9px] font-mono font-bold uppercase text-slate-400 px-1">
                      {msg.role === 'user' ? 'YOU' : msg.role === 'system' ? 'SYSTEM' : 'Kai'}
                  </span>

                  <div 
                  className={`max-w-[90%] p-4 relative border-2 shadow-[4px_4px_0px_rgba(0,0,0,0.1)] ${
                      msg.role === 'user' 
                      ? 'bg-slate-900 text-white border-slate-900' 
                      : msg.role === 'system'
                        ? msg.isPartnerContext 
                            ? 'bg-emerald-50 text-emerald-900 border-emerald-600 border-dashed w-full max-w-full' 
                            : 'bg-slate-100 text-slate-600 border-slate-300 w-full max-w-full text-center font-mono text-xs border-dashed'
                      : 'bg-white text-slate-900 border-slate-900'
                  }`}
                  >
                    {msg.isPartnerContext && (
                        <div className="absolute -top-3 -left-3 bg-emerald-100 text-emerald-700 p-1 border-2 border-emerald-600">
                            <MessageSquareQuote size={16} />
                        </div>
                    )}

                    <div className={`text-sm leading-relaxed prose prose-sm max-w-none font-medium ${
                        msg.role === 'user' 
                          ? 'prose-invert text-white' 
                          : msg.isPartnerContext 
                            ? 'text-emerald-800'
                            : 'text-slate-800'
                      }`}>
                      <ReactMarkdown>
                        {msg.text}
                      </ReactMarkdown>
                    </div>

                    {/* Action Buttons */}
                    {msg.actions && (
                        <div className="mt-4 flex flex-wrap gap-2">
                            {msg.actions.map(action => (
                                <button
                                    key={action.id}
                                    onClick={() => handleActionClick(action.id, msg.id)}
                                    className={`px-4 py-2 text-xs font-bold uppercase tracking-wider border-2 transition-transform active:translate-y-0.5 active:shadow-none flex items-center gap-2 ${
                                        action.style === 'primary' 
                                        ? 'bg-indigo-600 text-white border-indigo-800 shadow-[2px_2px_0px_#1e1b4b]' 
                                        : 'bg-white text-slate-900 border-slate-900 shadow-[2px_2px_0px_#0f172a] hover:bg-slate-50'
                                    }`}
                                >
                                    {action.id.includes('yes') ? <Check size={14} /> : 
                                     action.id === 'start_breathing' ? <Wind size={14} /> :
                                     action.id === 'start_appreciation' ? <Heart size={14} className="fill-white" /> :
                                     <XIcon size={14} />
                                    }
                                    {action.label}
                                </button>
                            ))}
                        </div>
                    )}
                  </div>
              </div>
              ))}
              
              {waitingForPartner && (
                  <div className="flex flex-col items-center justify-center py-6 animate-pulse space-y-2">
                      <div className="w-12 h-12 bg-emerald-100 border-2 border-emerald-500 flex items-center justify-center">
                          <Loader2 className="animate-spin text-emerald-600" size={24} />
                      </div>
                      <p className="text-xs font-mono font-bold text-emerald-600 uppercase tracking-widest">Establishing Uplink...</p>
                  </div>
              )}

              {isLoading && !waitingForPartner && (
              <div className="flex justify-start">
                  <div className="bg-white p-3 border-2 border-slate-200 flex items-center gap-2">
                  <Loader2 className="animate-spin text-indigo-600" size={14} />
                  <span className="text-[10px] font-mono uppercase text-slate-400">Processing Input...</span>
                  </div>
              </div>
              )}
          </div>

          {/* Chat Mediation Banner */}
          {!isMediation && (
              <div className="px-4 py-3 bg-amber-50 border-y-2 border-amber-200 flex items-center justify-between gap-2 shrink-0">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-800 uppercase tracking-wide">
                      <Info size={14} className="shrink-0" />
                      <p>Conflict Detected?</p>
                  </div>
                  <button 
                      onClick={startMediation}
                      className="text-[10px] font-bold bg-amber-200 hover:bg-amber-300 text-amber-900 px-3 py-1.5 border border-amber-400 uppercase tracking-widest flex items-center gap-1 transition-colors"
                  >
                      <Users size={12} />
                      Mediate
                  </button>
              </div>
          )}

          {/* Chat Input */}
          <div className="p-4 bg-slate-50 border-t-2 border-slate-200 shrink-0">
              <div className="flex items-center gap-0 bg-white border-2 border-slate-900 shadow-[4px_4px_0px_rgba(30,41,59,0.1)] focus-within:shadow-[4px_4px_0px_rgba(99,102,241,1)] focus-within:border-indigo-600 transition-all">
              <input 
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder={waitingForPartner ? "UPLINK BUSY..." : isMediation ? "INPUT STATEMENT..." : `MESSAGE...`}
                  className="flex-1 bg-transparent border-none focus:outline-none text-slate-900 placeholder:text-slate-300 text-sm font-medium p-3 uppercase"
                  disabled={isLoading || waitingForPartner}
              />
              <button 
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading || waitingForPartner}
                  className="w-12 h-full bg-slate-900 hover:bg-indigo-600 disabled:opacity-50 disabled:hover:bg-slate-900 flex items-center justify-center text-white transition-colors border-l-2 border-slate-900"
              >
                  <Send size={16} />
              </button>
              </div>
          </div>
      </div>
    </div>
  );
};