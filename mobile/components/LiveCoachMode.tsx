
import React, { useEffect, useRef, useState } from 'react';
import { UserProfile } from '../types';
import { Mic, MicOff, Activity, Bluetooth, Watch, Radio, X, AlertTriangle, Shield, Frown, MessageSquare, Zap } from 'lucide-react';
import { connectLiveCoach, AnalysisData } from '../services/geminiService';
import { getMicrophoneStream } from '../src/shared/utils/mediaDevices';

interface Props {
  user: UserProfile;
  onExit: () => void;
}

interface TranscriptItem extends AnalysisData {
    id: string;
    timestamp: number;
}

export const LiveCoachMode: React.FC<Props> = ({ user, onExit }) => {
  const [isActive, setIsActive] = useState(false);
  const [status, setStatus] = useState<'disconnected' | 'connecting' | 'active'>('disconnected');
  const [nudge, setNudge] = useState<string | null>(null);
  
  // Analysis State
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const [activeHorseman, setActiveHorseman] = useState<string | null>(null);
  const [currentSentiment, setCurrentSentiment] = useState<string>('Neutral');

  // Audio Refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const outputAudioContextRef = useRef<AudioContext | null>(null);
  
  const liveSessionRef = useRef<{ sendAudio: (d: Float32Array) => void; disconnect: () => void } | null>(null);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const startSession = async () => {
    setStatus('connecting');
    try {
      // Input Audio Setup (requires HTTPS on iOS)
      const stream = await getMicrophoneStream({ audio: true });
      streamRef.current = stream;
      
      const inputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = inputCtx;
      const source = inputCtx.createMediaStreamSource(stream);
      sourceRef.current = source;
      
      const processor = inputCtx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      // Output Audio Setup
      const outputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      outputAudioContextRef.current = outputCtx;
      let nextStartTime = 0;

      // Connect to Gemini
      const session = await connectLiveCoach(user, {
        onOpen: () => {
          setStatus('active');
          setIsActive(true);
        },
        onClose: () => {
          setStatus('disconnected');
          setIsActive(false);
        },
        onError: (err) => {
          console.error(err);
          setStatus('disconnected');
        },
        onAnalysis: (data) => {
            // Logic to fallback if model returns generic names
            let displaySpeaker = data.speaker;
            if (displaySpeaker === 'Speaker 1') {
                displaySpeaker = user.name;
            } else if (displaySpeaker === 'Speaker 2') {
                displaySpeaker = user.partnerName || 'Partner';
            }

            // Add to transcript
            setTranscripts(prev => [...prev, { ...data, speaker: displaySpeaker, id: Date.now().toString(), timestamp: Date.now() }]);
            
            // Update Dashboard State
            setCurrentSentiment(data.sentiment);
            
            if (data.horseman !== 'None') {
                setActiveHorseman(data.horseman);
                // Flash alert for 5 seconds
                setNudge(`${data.horseman} Detected`);
                setTimeout(() => {
                    setActiveHorseman(null);
                    setNudge(null);
                }, 5000);
            }
        },
        onAudioData: (buffer) => {
          if (!outputAudioContextRef.current) return;
          const ctx = outputAudioContextRef.current;
          
          if (ctx.state === 'closed') return;

          const src = ctx.createBufferSource();
          src.buffer = buffer;
          src.connect(ctx.destination);
          
          const currentTime = ctx.currentTime;
          if (nextStartTime < currentTime) {
            nextStartTime = currentTime;
          }
          src.start(nextStartTime);
          nextStartTime += buffer.duration;
        }
      });
      
      liveSessionRef.current = session;

      // Send Input Audio Loop
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        session.sendAudio(inputData);
        drawVisualizer(inputData);
      };

      source.connect(processor);
      processor.connect(inputCtx.destination); 

    } catch (err) {
      console.error("Failed to start session", err);
      setStatus('disconnected');
      alert("Could not access microphone or connect to AI service.");
    }
  };

  const stopSession = () => {
    if (liveSessionRef.current) {
      liveSessionRef.current.disconnect();
      liveSessionRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    
    if (audioContextRef.current) {
      if (audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close().catch(console.error);
      }
      audioContextRef.current = null;
    }
    
    if (outputAudioContextRef.current) {
       if (outputAudioContextRef.current.state !== 'closed') {
        outputAudioContextRef.current.close().catch(console.error);
       }
       outputAudioContextRef.current = null;
    }
    
    setIsActive(false);
    setStatus('disconnected');
  };

  const handleExit = () => {
      stopSession();
      onExit();
  };

  const drawVisualizer = (data: Float32Array) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#22d3ee'; 
    ctx.beginPath();

    const sliceWidth = canvas.width / data.length;
    let x = 0;

    for (let i = 0; i < data.length; i += 10) { 
      const v = data[i] * 50; 
      const y = (canvas.height / 2) + v;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += sliceWidth * 10;
    }
    ctx.stroke();
  };
  
  useEffect(() => {
    if (scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcripts]);

  useEffect(() => {
    return () => stopSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const getHorsemanColor = (h: string) => {
      switch(h) {
          case 'Criticism': return 'text-orange-500 border-orange-500 bg-orange-500/10';
          case 'Contempt': return 'text-red-500 border-red-500 bg-red-500/10';
          case 'Defensiveness': return 'text-yellow-500 border-yellow-500 bg-yellow-500/10';
          case 'Stonewalling': return 'text-slate-400 border-slate-400 bg-slate-400/10';
          default: return 'text-slate-700 border-slate-800 bg-slate-900';
      }
  };

  const isSpeakerUser = (speaker: string) => {
      return speaker === user.name || speaker.includes('1') || speaker.toLowerCase().includes('you');
  };

  return (
    <div className="h-full flex flex-col bg-slate-950 text-white relative overflow-hidden font-mono">
      {/* Dark Grid Background */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-10" 
            style={{ 
                backgroundImage: 'linear-gradient(#22d3ee 1px, transparent 1px), linear-gradient(90deg, #22d3ee 1px, transparent 1px)', 
                backgroundSize: '40px 40px' 
            }}>
      </div>
      
      {/* Header - Z-Index 50 to ensure it is clickable above the scrolling content */}
      <div className="absolute top-0 left-0 w-full p-4 flex justify-between items-start z-50 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
        <div>
            <div className="flex items-center gap-2 text-cyan-400 mb-1">
                <Radio className={isActive ? "animate-pulse" : ""} size={16} />
                <span className="text-[10px] tracking-widest uppercase font-bold">Signal: {status === 'active' ? 'LOCKED' : 'WAITING'}</span>
            </div>
            <h1 className="text-xl font-bold uppercase tracking-wider text-slate-100">Dialogue Deck</h1>
        </div>
        <button onClick={handleExit} className="border border-slate-700 hover:border-white text-slate-400 hover:text-white px-3 py-1 text-xs uppercase tracking-widest transition-colors">
          Abort
        </button>
      </div>

      <div className="flex-1 flex flex-col relative z-10 pt-20 pb-12">
        
        {/* TOP SECTION: ANALYSIS DASHBOARD */}
        <div className="px-6 mb-4">
             <div className="grid grid-cols-4 gap-2 mb-4">
                 {[
                     { label: 'Criticism', icon: <AlertTriangle size={14} />, id: 'Criticism' },
                     { label: 'Defensive', icon: <Shield size={14} />, id: 'Defensiveness' },
                     { label: 'Contempt', icon: <Frown size={14} />, id: 'Contempt' },
                     { label: 'Stonewall', icon: <X size={14} />, id: 'Stonewalling' },
                 ].map((h) => (
                     <div 
                        key={h.id}
                        className={`flex flex-col items-center justify-center p-2 border-2 transition-all duration-300 ${
                            activeHorseman === h.id 
                            ? getHorsemanColor(h.id) + ' scale-105 shadow-[0_0_15px_currentColor]' 
                            : 'border-slate-800 text-slate-600 bg-slate-900/50 grayscale'
                        }`}
                     >
                         <div className="mb-1">{h.icon}</div>
                         <span className="text-[8px] font-bold uppercase tracking-widest">{h.label}</span>
                     </div>
                 ))}
             </div>
             
             <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-2">
                 <div className="flex items-center gap-2">
                     <Activity size={14} className="text-cyan-400" />
                     <span className="text-[10px] uppercase font-bold text-slate-400">Current Tone</span>
                 </div>
                 <span className={`text-xs font-bold uppercase ${
                     currentSentiment === 'Hostile' ? 'text-red-500' : 
                     currentSentiment === 'Negative' ? 'text-orange-400' :
                     currentSentiment === 'Positive' ? 'text-green-400' : 'text-slate-300'
                 }`}>
                     {currentSentiment}
                 </span>
             </div>
        </div>

        {/* MIDDLE SECTION: TRANSCRIPT LOG */}
        <div className="flex-1 overflow-y-auto px-6 space-y-3 relative" ref={scrollRef}>
             <div className="sticky top-0 bg-slate-950/90 py-2 z-10 text-[9px] font-bold text-slate-500 uppercase tracking-widest border-b border-slate-800 mb-2">
                 Live Transcription Log
             </div>
             
             {transcripts.length === 0 && isActive && (
                 <div className="text-center py-8 opacity-30 text-xs font-mono uppercase">Listening for speech patterns...</div>
             )}

             {transcripts.map((t) => {
                 const isUser = isSpeakerUser(t.speaker);
                 return (
                    <div key={t.id} className={`flex gap-3 text-sm animate-fade-in ${isUser ? 'justify-start' : 'justify-end'}`}>
                        <div className={`max-w-[80%] p-3 border-l-2 ${
                            isUser
                            ? 'border-cyan-500 bg-cyan-950/20' 
                            : 'border-purple-500 bg-purple-950/20'
                        }`}>
                            <div className="flex justify-between items-center mb-1">
                                <span className={`text-[9px] font-bold uppercase tracking-widest ${
                                    isUser ? 'text-cyan-400' : 'text-purple-400'
                                }`}>
                                    {isUser ? `${user.name} (You)` : t.speaker}
                                </span>
                                {t.horseman !== 'None' && (
                                    <span className="text-[8px] bg-red-900/50 text-red-400 px-1 border border-red-800 font-bold uppercase ml-2">
                                        {t.horseman}
                                    </span>
                                )}
                            </div>
                            <p className="text-slate-300 leading-snug font-medium opacity-90">{t.transcript}</p>
                        </div>
                    </div>
                 );
             })}
        </div>
        
        {/* BOTTOM SECTION: CONTROLS */}
        <div className="mt-4 flex flex-col items-center justify-center px-6">
            
            {/* Visualizer Canvas */}
            <div className="w-full h-12 bg-slate-900/50 border-t border-slate-800 mb-4 relative">
                 <canvas ref={canvasRef} width={300} height={48} className="w-full h-full opacity-60" />
            </div>

            <div className="relative z-10 w-20 h-20 bg-slate-900 rounded-full flex items-center justify-center border-2 border-cyan-900 shadow-[0_0_30px_rgba(0,0,0,0.5)]">
                 {!isActive ? (
                     <button onClick={startSession} className="flex flex-col items-center gap-1 text-slate-500 hover:text-cyan-400 transition-colors group">
                         <Mic size={24} className="group-hover:scale-110 transition-transform" />
                         <span className="text-[9px] font-bold uppercase tracking-widest">Init</span>
                     </button>
                 ) : (
                    <button onClick={stopSession} className="flex flex-col items-center gap-1 text-cyan-500 hover:text-cyan-200 transition-colors">
                        <div className="relative">
                            <MicOff size={24} />
                            <span className="absolute -top-1 -right-1 flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
                            </span>
                        </div>
                        <span className="text-[9px] font-bold uppercase tracking-widest">Cut</span>
                    </button>
                 )}
            </div>
        </div>

        {/* Nudge Overlay */}
        {nudge && (
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 animate-ping opacity-0" style={{ animationIterationCount: 1 }}>
             {/* Visual flash effect managed by state timer */}
          </div>
        )}
      </div>

      {/* Footer Status */}
      <div className="absolute bottom-0 w-full p-3 bg-slate-950 border-t border-slate-800 flex justify-between items-center text-[10px] text-slate-500 uppercase tracking-widest z-10">
          <div className="flex items-center gap-2">
              <Bluetooth size={12} className={isActive ? "text-blue-500" : ""} />
              <span>Peripheral: Apple Watch Ultra</span>
          </div>
          <span className="flex items-center gap-2"><Zap size={12} className="text-yellow-500" /> AI Coach Active</span>
      </div>
    </div>
  );
};
