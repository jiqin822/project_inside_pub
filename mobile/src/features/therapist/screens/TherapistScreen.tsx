import React, { useState, useRef, useEffect } from 'react';
import { ChatMessage, ChatAction, AddNotificationFn } from '../../../shared/types/domain';
import { Send, User, Bot, Loader2, Info, Users, Handshake, Check, X, MessageSquareQuote, Wind, Heart, Star, ChevronRight, Mic, MicOff, Terminal, Sparkles, Zap, Lock } from 'lucide-react';
import { getTherapistResponse } from '../../../shared/services/geminiService';
import ReactMarkdown from 'react-markdown';
import { RoomHeader } from '../../../shared/ui/RoomHeader';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';

// Minimal love map question texts for therapist context (suggest Open Love Maps).
const LOVE_MAP_QUESTION_TEXTS = [
  'What is your absolute dream vacation destination?',
  'What stresses you out the most in daily life?',
  'How do you prefer to receive affection?',
  'What is one non-negotiable value you hold?',
  'When you are upset, do you prefer space or comfort?',
  'What makes you feel most loved and understood?',
];

interface Props {
  onExit: () => void;
  onAddNotification?: AddNotificationFn;
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
           <X size={24} />
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
           <X size={24} />
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

export const TherapistScreen: React.FC<Props> = ({ onExit, onAddNotification }) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();
  
  if (!user) {
    return null; // Should not happen, but guard against it
  }
  
  const [selectedSubject, setSelectedSubject] = useState<Subject | null>(null);

  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMediation, setIsMediation] = useState(false);
  const [waitingForPartner, setWaitingForPartner] = useState(false);
  const [partnerPerspective, setPartnerPerspective] = useState<string | null>(null);
  const [isBreathing, setIsBreathing] = useState(false);
  const [isAppreciation, setIsAppreciation] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const processUserMessageRef = useRef<(text: string) => void>(() => {});

  const lovedOnes: Subject[] = (relationships.length > 0 ? relationships : user.lovedOnes).map(l => ({
      id: l.id,
      name: l.name,
      relationship: l.relationship
  }));

  const selfSubject: Subject = { id: 'self', name: user?.name ?? 'Myself', relationship: 'Self' };

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

  const SpeechRecognitionAPI = typeof window !== 'undefined' && (window.SpeechRecognition || (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition);
  const isSpeechSupported = !!SpeechRecognitionAPI;

  useEffect(() => {
    if (!isSpeechSupported || !selectedSubject) return;
    const Recognition = SpeechRecognitionAPI!;
    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const result = event.results[event.results.length - 1];
      if (result.isFinal) {
        const transcript = result[0].transcript?.trim();
        if (transcript) processUserMessageRef.current(transcript);
      }
    };
    recognition.onend = () => setIsVoiceRecording(false);
    recognition.onerror = () => setIsVoiceRecording(false);
    recognitionRef.current = recognition;
    return () => {
      try { recognition.abort(); } catch { /* noop */ }
      recognitionRef.current = null;
    };
  }, [isSpeechSupported, selectedSubject?.id]);

  const toggleVoiceInput = () => {
    if (!isSpeechSupported || isLoading || waitingForPartner) return;
    const rec = recognitionRef.current;
    if (isVoiceRecording && rec) {
      try { rec.stop(); } catch { /* noop */ }
      setIsVoiceRecording(false);
      return;
    }
    if (!isVoiceRecording && rec) {
      try {
        rec.start();
        setIsVoiceRecording(true);
      } catch (e) {
        console.warn('Speech recognition start failed', e);
      }
    }
  };

  const contextData = {
    availableActivities: [] as { id: string; title: string; description: string; duration: string; type: string; xpReward: number }[],
    loveMapQuestions: LOVE_MAP_QUESTION_TEXTS.map(t => ({ text: t })),
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

      const response = await getTherapistResponse(
        history,
        text,
        user,
        selectedSubject,
        contextData,
        partnerPerspective || undefined
      );

      const botMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'model',
        text: response.text,
        timestamp: Date.now(),
        actions: response.actions,
      };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };
  processUserMessageRef.current = processUserMessage;

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

          onAddNotification?.('therapist', 'Kai', `Perspective from ${selectedSubject.name} retrieved.`);
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

        const response = await getTherapistResponse(
            history,
            "Analyze the conflict now that you have both sides.",
            user,
            selectedSubject,
            contextData,
            perspective
        );

        setMessages(prev => [...prev, {
            id: Date.now().toString(),
            role: 'model',
            text: response.text,
            timestamp: Date.now(),
            actions: response.actions,
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
      <div
        className="flex flex-col h-screen relative animate-fade-in font-sans text-[#1A1A1A] antialiased"
        style={{
          height: '100vh',
          width: '100vw',
          backgroundColor: '#f7f7f7',
          backgroundImage: 'linear-gradient(to right, rgba(15, 23, 42, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(15, 23, 42, 0.05) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      >
        <RoomHeader
          moduleTitle="MODULE: THERAPY"
          moduleIcon={<Terminal size={12} />}
          title="Session Setup"
          subtitle={{ text: 'SESSION SETUP', colorClass: 'text-indigo-600' }}
          onClose={onExit}
        />

        <div className="flex-1 p-6 overflow-hidden relative z-10" style={{ minHeight: 0, overflowY: 'auto' }}>
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-6 border-b border-slate-200 pb-2">I want to talk about relationship with</h2>
            
            <div className="grid grid-cols-1 gap-4 mb-8">
               <button
                 onClick={() => setSelectedSubject(selfSubject)}
                 className="flex items-center p-4 bg-white border-2 border-slate-900 shadow-[4px_4px_0px_rgba(30,41,59,0.2)] hover:shadow-[6px_6px_0px_rgba(30,41,59,0.2)] hover:-translate-y-0.5 transition-all text-left group active:translate-y-0 active:shadow-none"
               >
                 <div className="w-12 h-12 bg-indigo-600 text-white flex items-center justify-center font-bold text-lg mr-4 border-2 border-slate-900">
                   <User size={24} />
                 </div>
                 <div className="flex-1">
                   <h3 className="font-bold text-slate-900 uppercase tracking-tight">Myself</h3>
                   <p className="text-xs font-mono text-slate-500 uppercase">Talk about me</p>
                 </div>
                 <ChevronRight className="text-slate-300 group-hover:text-slate-900" />
               </button>
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
               )) : null}
               {lovedOnes.length === 0 && (
                 <p className="text-sm text-slate-400 italic font-mono border border-dashed border-slate-300 p-4">No other subjects. Use &quot;Myself&quot; above.</p>
               )}
            </div>
        </div>
      </div>
    );
  }

  // --- Render Chat Screen ---
  const selectedSubjectLovedOne = relationships.find(l => l.id === selectedSubject.id) || user.lovedOnes.find(l => l.id === selectedSubject.id);
  
  return (
    <>
      {isBreathing && <BreathingOverlay onClose={() => setIsBreathing(false)} />}
      {isAppreciation && (
        <AppreciationOverlay 
            partnerName={selectedSubject.name} 
            onClose={() => setIsAppreciation(false)} 
            onSubmit={handleAppreciationSubmit} 
        />
      )}
      
      <div
        className="flex flex-col h-screen relative font-sans text-[#1A1A1A] antialiased"
        style={{
          height: '100vh',
          width: '100vw',
          backgroundColor: '#f7f7f7',
          backgroundImage: 'linear-gradient(to right, rgba(15, 23, 42, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(15, 23, 42, 0.05) 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      >
      <RoomHeader
        moduleTitle="MODULE: THERAPY"
        moduleIcon={<Terminal size={12} />}
        title="Lounge"
        subtitle={{
          text: isMediation ? `LINK: ${selectedSubject.name}` : 'COACHING SESSION ACTIVE',
          colorClass: 'text-indigo-600',
        }}
        onClose={onExit}
      />

      {/* Main Content Area - dot pattern background */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden relative z-10">
          <div
            ref={scrollRef}
            className="flex-1 overflow-y-auto p-4 space-y-6 min-h-0"
            style={{
              backgroundImage: 'radial-gradient(rgba(15, 23, 42, 0.2) 1px, transparent 1px)',
              backgroundSize: '10px 10px',
            }}
          >
              {messages.map((msg) => {
                if (msg.role === 'model') {
                  return (
                    <div key={msg.id} className="flex flex-col items-start gap-3">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-8 h-8 rounded-full border-2 border-[#0D9488] flex items-center justify-center shrink-0"
                          style={{ background: 'repeating-radial-gradient(circle, transparent, transparent 4px, rgba(13, 148, 136, 0.1) 5px, rgba(13, 148, 136, 0.2) 6px)' }}
                        >
                          <Sparkles className="text-[#0D9488]" size={14} />
                        </div>
                        <span className="text-[11px] font-bold text-[#0D9488] uppercase tracking-widest">Kai • Analysis</span>
                      </div>
                      <div className="max-w-[90%] space-y-1">
                        <div className="bg-[#F0FDFA] border-2 border-[#0D9488] p-3 shadow-[4px_4px_0px_0px_rgba(13,148,136,0.2)]">
                          <div className="text-sm leading-relaxed text-slate-800 prose prose-sm max-w-none font-medium">
                            <ReactMarkdown>{msg.text}</ReactMarkdown>
                          </div>
                          {msg.actions && (
                            <div className="mt-4 flex flex-wrap gap-2">
                              {msg.actions.map(action => (
                                <button
                                  key={action.id}
                                  onClick={() => handleActionClick(action.id, msg.id)}
                                  className="shrink-0 bg-[#0D9488]/5 border border-[#0D9488]/40 px-3 py-1.5 text-[9px] font-bold uppercase text-[#0D9488] hover:bg-[#0D9488] hover:text-white transition-all flex items-center gap-1"
                                >
                                  {action.id.includes('yes') ? <Check size={12} /> : action.id === 'start_breathing' ? <Wind size={12} /> : action.id === 'start_appreciation' ? <Heart size={12} className="fill-current" /> : <X size={12} />}
                                  {action.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                }
                if (msg.role === 'user') {
                  return (
                    <div key={msg.id} className="flex gap-3 flex-row-reverse">
                      <div className="w-8 h-8 bg-[#1A1A1A] text-white flex items-center justify-center font-bold text-xs shrink-0">
                        {user?.name?.charAt(0) ?? 'A'}
                      </div>
                      <div className="space-y-1 max-w-[85%] text-right">
                        <div className="bg-white border-2 border-[#1A1A1A] p-3 shadow-[-4px_4px_0px_0px_rgba(15,23,42,1)]">
                          <div className="text-sm text-slate-800 prose prose-sm max-w-none prose-p:my-0">
                            <ReactMarkdown>{msg.text}</ReactMarkdown>
                          </div>
                        </div>
                        <span className="text-[9px] font-mono text-slate-400 uppercase block">You</span>
                      </div>
                    </div>
                  );
                }
                if (msg.role === 'system') {
                  return (
                    <div key={msg.id} className="w-full">
                      {msg.isPartnerContext ? (
                        <div className="w-full space-y-1">
                          <div className="bg-emerald-50 border-2 border-emerald-600 border-dashed p-3">
                            <div className="flex items-center gap-2 text-[11px] font-bold text-emerald-700 uppercase tracking-widest mb-1">
                              <MessageSquareQuote size={14} /> Incoming from {selectedSubject.name}
                            </div>
                            <div className="text-sm text-emerald-800 prose prose-sm max-w-none">
                              <ReactMarkdown>{msg.text}</ReactMarkdown>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="w-full bg-slate-100 text-slate-600 border border-dashed border-slate-300 text-center font-mono text-xs p-2">
                          <ReactMarkdown>{msg.text}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                  );
                }
                return null;
              })}

              {waitingForPartner && (
                <div className="flex flex-col items-center justify-center py-6 animate-pulse space-y-2">
                  <div className="w-12 h-12 bg-[#F0FDFA] border-2 border-[#0D9488] flex items-center justify-center">
                    <Loader2 className="animate-spin text-[#0D9488]" size={24} />
                  </div>
                  <p className="text-[10px] font-mono font-bold text-[#0D9488] uppercase tracking-widest">Establishing Uplink...</p>
                </div>
              )}

              {isLoading && !waitingForPartner && (
                <div className="flex justify-start items-center gap-2">
                  <div className="w-8 h-8 rounded-full border border-[#3B82F6] flex items-center justify-center shrink-0">
                    <Sparkles className="text-[#3B82F6]" size={14} />
                  </div>
                  <div className="bg-white p-3 border-2 border-[#3B82F6] shadow-[4px_4px_0px_0px_rgba(59,130,246,0.2)] flex items-center gap-2">
                    <Loader2 className="animate-spin text-[#3B82F6]" size={14} />
                    <span className="text-[10px] font-mono uppercase text-slate-500">Processing...</span>
                  </div>
                </div>
              )}
          </div>

          {/* Status bar: Tension / Empathy + LIVE FLOW */}
          <div className="px-4 py-2 border-t border-slate-200 bg-slate-50 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-4">
              <div className="flex flex-col">
                <span className="text-[8px] font-mono text-slate-500 uppercase">Tension</span>
                <div className="w-16 h-1 bg-slate-200 mt-0.5">
                  <div className="h-full bg-[#F97316]" style={{ width: '25%' }} />
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-[8px] font-mono text-slate-500 uppercase">Empathy</span>
                <div className="w-16 h-1 bg-slate-200 mt-0.5">
                  <div className="h-full bg-[#0D9488]" style={{ width: '40%' }} />
                </div>
              </div>
            </div>
            <div className="text-[10px] font-mono font-bold flex items-center gap-1 text-slate-500">
              <Zap className="text-[#0D9488]" size={12} />
              LIVE FLOW
            </div>
          </div>

          {/* Kai's Guidance chips + Mediation banner (when not in mediation) */}
          {!isMediation && (
            <div className="px-4 py-2 bg-slate-50 border-t border-slate-200 shrink-0">
              <div className="flex items-center gap-2 mb-2">
                <Zap size={12} className="text-[#0D9488]" />
                <span className="text-[10px] font-black uppercase tracking-widest text-[#1A1A1A]">Kai&apos;s Guidance</span>
              </div>
              <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
                <button
                  type="button"
                  onClick={() => processUserMessage("I'd like to validate how I'm feeling.")}
                  className="shrink-0 bg-[#0D9488]/5 border border-[#0D9488]/40 px-3 py-1.5 text-[9px] font-bold uppercase text-[#0D9488] hover:bg-[#0D9488] hover:text-white transition-all"
                >
                  Validate feelings
                </button>
                <button
                  type="button"
                  onClick={() => processUserMessage("Can you help me rephrase what I want to say?")}
                  className="shrink-0 bg-[#F97316]/5 border border-[#F97316]/40 px-3 py-1.5 text-[9px] font-bold uppercase text-[#F97316] hover:bg-[#F97316] hover:text-white transition-all"
                >
                  Rephrase that
                </button>
                <button
                  type="button"
                  onClick={() => setIsBreathing(true)}
                  className="shrink-0 bg-slate-100 border border-slate-300 px-3 py-1.5 text-[9px] font-bold uppercase text-slate-500 hover:bg-slate-500 hover:text-white transition-all"
                >
                  Breathing break
                </button>
                <button
                  type="button"
                  onClick={startMediation}
                  className="shrink-0 bg-slate-100 border border-slate-300 px-3 py-1.5 text-[9px] font-bold uppercase text-slate-500 hover:bg-slate-500 hover:text-white transition-all flex items-center gap-1"
                >
                  <Users size={10} /> Mediate
                </button>
              </div>
            </div>
          )}

          {/* Footer: Private Reflection (optional) + Public Chat input */}
          <footer className="p-4 bg-white border-t-4 border-[#1A1A1A] shrink-0">
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label className="text-[9px] font-mono font-bold text-slate-400 uppercase ml-1 flex items-center gap-1">
                  <Lock size={10} />
                  Talk to Kai in private
                </label>
                <div className="relative opacity-60 hover:opacity-100 transition-opacity">
                  <input
                    type="text"
                    placeholder="Share your thoughts (Internal)..."
                    className="w-full border border-dashed border-slate-300 bg-slate-50 px-3 py-2 font-mono text-[10px] focus:ring-0 focus:border-slate-400 uppercase placeholder:text-slate-400/80 rounded-sm"
                    readOnly
                    aria-hidden
                  />
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
                    <Lock className="text-slate-300" size={14} />
                  </div>
                </div>
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-[9px] font-mono font-bold text-[#3B82F6] uppercase ml-1 flex items-center gap-1">
                  <Send size={10} />
                  Send to chat group
                </label>
                <div className="flex gap-0 shadow-lg relative">
                  <div className="flex-1 relative">
                    <div className="absolute left-3 top-1/2 -translate-y-1/2">
                      <button
                        type="button"
                        onClick={toggleVoiceInput}
                        disabled={!isSpeechSupported || isLoading || waitingForPartner}
                        className={`p-1 transition-colors ${isVoiceRecording ? 'text-red-600 animate-pulse' : 'text-slate-400 hover:text-[#1A1A1A]'} disabled:opacity-50`}
                        aria-label={isVoiceRecording ? 'Stop recording' : 'Voice input'}
                        title={isSpeechSupported ? (isVoiceRecording ? 'Stop' : 'Speak') : 'Voice not supported'}
                      >
                        {isVoiceRecording ? <MicOff size={18} /> : <Mic size={18} />}
                      </button>
                    </div>
                    <input
                      type="text"
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                      placeholder={waitingForPartner ? 'UPLINK BUSY...' : 'Send message...'}
                      disabled={isLoading || waitingForPartner}
                      className="w-full border-2 border-[#1A1A1A] bg-white pl-10 pr-4 py-3 font-mono text-sm focus:ring-0 focus:border-[#3B82F6] uppercase placeholder:text-slate-400 font-bold h-14"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading || waitingForPartner}
                    className="w-16 h-14 bg-[#3B82F6] text-white flex items-center justify-center hover:bg-blue-600 transition-colors border-2 border-[#1A1A1A] border-l-0 disabled:opacity-50"
                  >
                    <Send size={20} />
                  </button>
                </div>
              </div>
            </div>
            <div className="mt-4 flex justify-between items-center text-[9px] font-mono font-bold text-slate-400">
              <div className="flex items-center gap-4">
                <button type="button" onClick={onExit} className="uppercase hover:text-[#1A1A1A]">Leave Session</button>
                <span className="uppercase">Transcript</span>
              </div>
              <span className="text-[#1A1A1A] uppercase">Secure • {selectedSubject.name}</span>
            </div>
          </footer>
        </div>
      </div>
    </>
  );
};