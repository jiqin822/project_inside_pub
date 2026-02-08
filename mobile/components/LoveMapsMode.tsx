import React, { useState, useEffect } from 'react';
import { UserProfile, EconomyConfig, LovedOne } from '../types';
import { Heart, Trophy, Check, X, Map as MapIcon, Lock, Star, ChevronDown, PenTool, Save, Play, Compass, FileText, Search, Plus, MessageSquare, Edit3 } from 'lucide-react';

interface Props {
  user: UserProfile;
  xp: number;
  setXp: (xp: number) => void;
  economy: EconomyConfig;
  onExit: () => void;
  onUpdateLovedOne: (id: string, updates: Partial<LovedOne>) => void;
}

interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correctIndex: number;
  xp: number;
}

interface MapLevel {
  id: string;
  title: string;
  category: string;
  difficulty: 'Easy' | 'Medium' | 'Hard';
  status: 'locked' | 'current' | 'completed';
  stars: number; // 0-3
  totalQuestions: number;
}

const INITIAL_MAP_LEVELS: MapLevel[] = [
  { id: 'l1', title: 'The Basics', category: 'Fundamentals', difficulty: 'Easy', status: 'current', stars: 0, totalQuestions: 3 },
  { id: 'l2', title: 'Preferences', category: 'Lifestyle', difficulty: 'Easy', status: 'locked', stars: 0, totalQuestions: 3 },
  { id: 'l3', title: 'History', category: 'Memory', difficulty: 'Medium', status: 'locked', stars: 0, totalQuestions: 4 },
  { id: 'l4', title: 'Conflict Style', category: 'Dynamics', difficulty: 'Hard', status: 'locked', stars: 0, totalQuestions: 5 },
  { id: 'l5', title: 'Deep Dreams', category: 'Future', difficulty: 'Hard', status: 'locked', stars: 0, totalQuestions: 5 },
  { id: 'l6', title: 'Inner World', category: 'Intimacy', difficulty: 'Hard', status: 'locked', stars: 0, totalQuestions: 5 },
];

const QUIZ_DATA: QuizQuestion[] = [
  {
    id: 'q1',
    question: "What is [NAME]'s absolute dream vacation destination?",
    options: ["Kyoto, Japan", "Paris, France", "Bora Bora", "Reykjavik, Iceland"],
    correctIndex: 0,
    xp: 20
  },
  {
    id: 'q2',
    question: "Which of these stresses [NAME] out the most?",
    options: ["Running late", "Messy kitchen", "Unanswered emails", "Social events"],
    correctIndex: 2,
    xp: 20
  },
  {
    id: 'q3',
    question: "What is [NAME]'s favorite comfort food after a bad day?",
    options: ["Pizza", "Ice Cream", "Mac & Cheese", "Spicy Ramen"],
    correctIndex: 3,
    xp: 20
  }
];

interface OpenEndedQuestion {
  id: string;
  category: string;
  text: string;
}

const OPEN_ENDED_QUESTIONS: OpenEndedQuestion[] = [
  { id: 'sq1', category: 'Dreams', text: "What is your absolute dream vacation destination?" },
  { id: 'sq2', category: 'Stress', text: "What stresses you out the most in daily life?" },
  { id: 'sq3', category: 'Comfort', text: "What is your go-to comfort food after a bad day?" },
  { id: 'sq4', category: 'History', text: "What is your favorite childhood memory?" },
  { id: 'sq5', category: 'Values', text: "What is one non-negotiable value you hold?" },
  { id: 'sq6', category: 'Affection', text: "How do you prefer to receive affection (words, touch, etc.)?" },
  { id: 'sq7', category: 'Conflict', text: "When you are upset, do you prefer space or comfort?" },
  { id: 'sq8', category: 'Future', text: "Where do you see yourself in 5 years?" },
  { id: 'sq9', category: 'Hobbies', text: "What is a hobby you've always wanted to pick up?" },
  { id: 'sq10', category: 'Fears', text: "What is your biggest irrational fear?" },
];

export const LoveMapsMode: React.FC<Props> = ({ user, xp, setXp, economy, onExit, onUpdateLovedOne }) => {
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>(user.lovedOnes[0]?.id || '');
  const [mapLevels, setMapLevels] = useState<MapLevel[]>(INITIAL_MAP_LEVELS);
  const [activeLevelId, setActiveLevelId] = useState<string | null>(null);
  const [quizView, setQuizView] = useState(false);
  const [activeTab, setActiveTab] = useState<'MAP' | 'SPECS' | 'DISCOVER'>('MAP');
  
  // Game State
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
  const [quizState, setQuizState] = useState<'idle' | 'correct' | 'wrong' | 'complete'>('idle');
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [quizScore, setQuizScore] = useState(0);

  // User Answers State
  const [myAnswers, setMyAnswers] = useState<Record<string, string>>({
      'sq1': 'Kyoto, Japan in the autumn.',
      'sq2': 'When the kitchen is messy and I have to cook.',
      'sq3': 'Spicy Ramen with extra egg.'
  });
  const [tempAnswers, setTempAnswers] = useState<Record<string, string>>({}); // For editing
  const [editingSpecId, setEditingSpecId] = useState<string | null>(null); // Track which spec is being edited

  useEffect(() => {
    if (!selectedSubjectId && user.lovedOnes.length > 0) {
        setSelectedSubjectId(user.lovedOnes[0].id);
    }
  }, [user.lovedOnes, selectedSubjectId]);

  const selectedSubject = user.lovedOnes.find(l => l.id === selectedSubjectId);

  const handleSubjectChange = (newId: string) => {
      setSelectedSubjectId(newId);
      setMapLevels(INITIAL_MAP_LEVELS); 
      setQuizView(false);
  };

  const startLevel = (levelId: string) => {
      setActiveLevelId(levelId);
      setCurrentQuestionIdx(0);
      setQuizState('idle');
      setSelectedOption(null);
      setQuizScore(0);
      setQuizView(true);
  };

  const handleAnswer = (idx: number) => {
    if (quizState !== 'idle') return;
    setSelectedOption(idx);
    
    const isCorrect = idx === QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].correctIndex;
    
    if (isCorrect) {
      setQuizState('correct');
      setQuizScore(prev => prev + QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].xp);
    } else {
      setQuizState('wrong');
    }
  };

  const nextQuestion = () => {
    const activeLevel = mapLevels.find(l => l.id === activeLevelId);
    if (!activeLevel) return;

    if (currentQuestionIdx < activeLevel.totalQuestions - 1) {
      setCurrentQuestionIdx(prev => prev + 1);
      setQuizState('idle');
      setSelectedOption(null);
    } else {
      completeLevel(activeLevel);
    }
  };

  const completeLevel = (level: MapLevel) => {
      setQuizState('complete');
      
      const xpEarned = quizScore + 50;
      setXp(xp + xpEarned); 

      // Update specific loved one balance
      if (selectedSubject) {
          const currentBalance = selectedSubject.balance || 0;
          onUpdateLovedOne(selectedSubject.id, { balance: currentBalance + xpEarned });
      }
      
      setMapLevels(prev => {
          const idx = prev.findIndex(l => l.id === level.id);
          const nextLevels = [...prev];
          nextLevels[idx] = { ...level, status: 'completed', stars: 3 }; 
          if (idx + 1 < nextLevels.length) {
              nextLevels[idx + 1] = { ...nextLevels[idx + 1], status: 'current' };
          }
          return nextLevels;
      });
  };

  const exitQuiz = () => {
      setQuizView(false);
      setActiveLevelId(null);
  };

  const getQuestionText = (text: string) => {
      return text.replace('[NAME]', selectedSubject?.name || 'Partner');
  };

  // --- Specs Logic ---

  const handleSaveSpec = (id: string, text: string) => {
      setMyAnswers(prev => ({ ...prev, [id]: text }));
      setEditingSpecId(null);
      setTempAnswers(prev => {
          const newState = { ...prev };
          delete newState[id];
          return newState;
      });
      alert("Spec Updated Successfully");
  };

  const handleStartEditSpec = (id: string) => {
      setEditingSpecId(id);
      setTempAnswers(prev => ({ ...prev, [id]: myAnswers[id] || '' }));
  };

  const handleCancelEditSpec = (id: string) => {
      setEditingSpecId(null);
      setTempAnswers(prev => {
          const newState = { ...prev };
          delete newState[id];
          return newState;
      });
  };

  const handleAddNewAnswer = (id: string) => {
      const text = tempAnswers[id];
      if (!text || !text.trim()) return;
      setMyAnswers(prev => ({ ...prev, [id]: text }));
      setTempAnswers(prev => {
          const newState = { ...prev };
          delete newState[id];
          return newState;
      });
      // Switch to specs tab to show it's added
      setActiveTab('SPECS');
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden font-sans relative" style={{ height: '100vh', width: '100vw' }}>
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
      <div className="bg-white border-b-4 border-slate-900 px-4 py-3 shrink-0 flex items-center justify-between relative z-10" style={{ paddingTop: 'calc(var(--sat, 0px) + 0.75rem)', marginTop: 'calc(-1 * var(--sat, 0px))' }}>
           <div className="flex items-center gap-3">
                <div className="flex flex-col">
                    <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Training</span>
                    <span className="text-xl font-black text-slate-900 font-mono leading-none">LOVE MAPS</span>
                </div>
           </div>
           <button onClick={onExit} className="w-8 h-8 flex items-center justify-center border-2 border-slate-200 hover:border-slate-900 text-slate-400 hover:text-slate-900 transition-colors">
                <X size={20} />
           </button>
           
           <div className="flex items-center gap-2">
                <div className="bg-slate-900 text-white px-3 py-1 text-xs font-bold font-mono">
                    Global XP: {xp}
                </div>
           </div>
      </div>

      {!quizView && (
          <div className="flex p-2 gap-2 border-b border-slate-200 bg-white shrink-0 relative z-10">
              <button
                onClick={() => setActiveTab('MAP')}
                className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-widest flex items-center justify-center gap-2 transition-all border-2 ${
                    activeTab === 'MAP'
                    ? 'bg-slate-900 text-white border-slate-900 shadow-[2px_2px_0px_rgba(0,0,0,0.2)]'
                    : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                }`}
              >
                  <Compass size={14} />
                  Exploration
              </button>
              <button
                onClick={() => setActiveTab('SPECS')}
                className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-widest flex items-center justify-center gap-2 transition-all border-2 ${
                    activeTab === 'SPECS'
                    ? 'bg-slate-900 text-white border-slate-900 shadow-[2px_2px_0px_rgba(0,0,0,0.2)]'
                    : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                }`}
              >
                  <FileText size={14} />
                  My Specs
              </button>
              <button
                onClick={() => setActiveTab('DISCOVER')}
                className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-widest flex items-center justify-center gap-2 transition-all border-2 ${
                    activeTab === 'DISCOVER'
                    ? 'bg-slate-900 text-white border-slate-900 shadow-[2px_2px_0px_rgba(0,0,0,0.2)]'
                    : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                }`}
              >
                  <Search size={14} />
                  Discover
              </button>
          </div>
      )}

      <div className="flex-1 overflow-hidden p-4 pb-24 relative z-10" style={{ minHeight: 0, overflowY: 'auto' }}>
            <div className="flex flex-col h-full relative">
                
                {/* === MAP VIEW === */}
                {!quizView && activeTab === 'MAP' && (
                    <div className="flex flex-col items-center pb-20 pt-2 relative animate-fade-in">
                        
                        <div className="w-full mb-8">
                            <div className="bg-white border-2 border-slate-900 p-4 shadow-[4px_4px_0px_rgba(30,41,59,0.1)]">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Target Subject</span>
                                    {selectedSubject && (
                                        <div className="text-[10px] font-mono text-indigo-600 bg-indigo-50 px-2 py-0.5 border border-indigo-200">
                                            ID: {selectedSubject.id.slice(-4)}
                                        </div>
                                    )}
                                </div>
                                
                                {user.lovedOnes.length > 0 ? (
                                    <div className="flex items-center justify-between">
                                        <div className="relative flex-1 mr-4">
                                            <select 
                                                value={selectedSubjectId} 
                                                onChange={(e) => handleSubjectChange(e.target.value)}
                                                className="w-full appearance-none bg-transparent font-black text-xl text-slate-900 uppercase focus:outline-none cursor-pointer pr-6"
                                            >
                                                {user.lovedOnes.map(l => (
                                                    <option key={l.id} value={l.id}>{l.name}</option>
                                                ))}
                                            </select>
                                            <ChevronDown size={16} className="absolute right-0 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400" />
                                        </div>
                                        <div className="w-10 h-10 bg-slate-900 text-white flex items-center justify-center font-bold text-lg border-2 border-slate-900">
                                            {selectedSubject?.name.charAt(0)}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="text-sm font-bold text-slate-500 italic">No subjects available. Add in dashboard.</div>
                                )}
                            </div>
                        </div>

                        <div className="mb-4 text-center">
                            <div className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400 mb-2">
                                START POINT
                            </div>
                            <div className="w-4 h-4 bg-slate-900 rounded-full mx-auto"></div>
                            <div className="w-0.5 h-8 bg-slate-300 mx-auto"></div>
                        </div>

                        {mapLevels.map((level, idx) => {
                            const offset = idx % 2 === 0 ? 'translate-x-0' : (idx % 4 === 1 ? 'translate-x-8' : '-translate-x-8');
                            const isLocked = level.status === 'locked';
                            const isCompleted = level.status === 'completed';
                            const isCurrent = level.status === 'current';

                            return (
                                <React.Fragment key={level.id}>
                                    <div className={`relative z-10 flex flex-col items-center group ${offset}`}>
                                        <button 
                                            onClick={() => !isLocked && startLevel(level.id)}
                                            disabled={isLocked}
                                            className={`
                                                w-20 h-20 rounded-full border-4 flex flex-col items-center justify-center relative transition-transform duration-200 active:scale-95
                                                ${isLocked ? 'bg-slate-100 border-slate-300 text-slate-300 cursor-not-allowed' : ''}
                                                ${isCompleted ? 'bg-indigo-600 border-indigo-800 text-white shadow-[0_4px_0_#312e81]' : ''}
                                                ${isCurrent ? 'bg-white border-indigo-600 text-indigo-600 shadow-[0_4px_0_#4f46e5] animate-bounce-slow' : ''}
                                            `}
                                        >
                                            {isLocked && <Lock size={24} />}
                                            {isCompleted && <Check size={32} strokeWidth={4} />}
                                            {isCurrent && <Play size={32} className="ml-1 fill-indigo-600" />}

                                            {isCompleted && (
                                                <div className="absolute -bottom-2 flex gap-0.5">
                                                    {[1,2,3].map(s => (
                                                        <Star key={s} size={10} className="fill-yellow-400 text-yellow-500" />
                                                    ))}
                                                </div>
                                            )}
                                        </button>

                                        <div className={`
                                            absolute left-1/2 -translate-x-1/2 top-24 w-32 text-center bg-white border-2 p-2 shadow-sm
                                            ${isLocked ? 'border-slate-200 opacity-50' : 'border-slate-900'}
                                        `}>
                                            <div className="text-[9px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">
                                                {level.difficulty}
                                            </div>
                                            <div className="font-bold text-slate-900 text-xs uppercase leading-tight">
                                                {level.title}
                                            </div>
                                        </div>
                                    </div>

                                    {idx < mapLevels.length - 1 && (
                                        <div className="w-0.5 h-24 bg-slate-300 my-2 relative overflow-hidden">
                                             {isCompleted && mapLevels[idx+1].status !== 'locked' && (
                                                 <div className="absolute top-0 left-0 w-full bg-indigo-500 animate-slide-down h-full"></div>
                                             )}
                                        </div>
                                    )}
                                </React.Fragment>
                            );
                        })}
                    </div>
                )}

                {/* === SPECS TAB (Answered) === */}
                {!quizView && activeTab === 'SPECS' && (
                    <div className="animate-fade-in pb-20">
                         <div className="bg-white border-2 border-slate-900 p-6 shadow-[4px_4px_0px_rgba(30,41,59,0.1)] mb-6">
                             <div className="flex items-start gap-4 mb-4">
                                <div className="w-12 h-12 bg-indigo-50 text-indigo-600 border-2 border-indigo-200 flex items-center justify-center">
                                    <PenTool size={24} />
                                </div>
                                <div>
                                    <h3 className="font-black uppercase tracking-tight text-lg">My Specifications</h3>
                                    <p className="text-xs font-mono text-slate-500 leading-relaxed mt-1">
                                        This is your "User Manual". Keep this updated so your partner can study and understand your needs.
                                    </p>
                                </div>
                             </div>
                         </div>

                         <div className="space-y-3">
                             {OPEN_ENDED_QUESTIONS.filter(q => myAnswers[q.id]).map((q, i) => {
                                 const isEditing = editingSpecId === q.id;
                                 const displayAnswer = isEditing ? (tempAnswers[q.id] || '') : myAnswers[q.id];
                                 
                                 return (
                                     <div key={q.id} className="bg-white border-2 border-slate-200 p-3 shadow-sm group hover:border-slate-400 transition-colors">
                                         <div className="flex items-start justify-between mb-1.5">
                                            <div className="flex items-center gap-2 flex-1">
                                                <span className="text-[8px] font-bold text-slate-400 uppercase tracking-widest border border-slate-200 px-1 py-0.5">{q.category}</span>
                                                <h4 className="font-bold text-slate-900 text-xs leading-tight flex-1">{q.text}</h4>
                                            </div>
                                            {!isEditing && (
                                                <button
                                                    onClick={() => handleStartEditSpec(q.id)}
                                                    className="p-1 hover:bg-slate-100 rounded transition-colors ml-2 shrink-0"
                                                    title="Edit"
                                                >
                                                    <Edit3 size={12} className="text-slate-500" />
                                                </button>
                                            )}
                                         </div>
                                         
                                         {isEditing ? (
                                             <>
                                                 <textarea 
                                                    value={displayAnswer}
                                                    onChange={(e) => setTempAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                                                    className="w-full bg-slate-50 border-2 border-indigo-300 p-2 text-xs font-medium text-slate-700 focus:outline-none focus:bg-white focus:border-indigo-500 transition-all resize-y min-h-[60px] mt-1.5"
                                                    autoFocus
                                                 />
                                                 <div className="flex gap-2 mt-2">
                                                     <button 
                                                        onClick={() => handleSaveSpec(q.id, tempAnswers[q.id] || '')}
                                                        className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-bold uppercase tracking-widest py-1.5 px-2 transition-colors flex items-center justify-center gap-1"
                                                     >
                                                        <Save size={10} />
                                                        Save
                                                     </button>
                                                     <button
                                                        onClick={() => handleCancelEditSpec(q.id)}
                                                        className="flex-1 bg-slate-300 hover:bg-slate-400 text-slate-900 text-[10px] font-bold uppercase tracking-widest py-1.5 px-2 transition-colors"
                                                     >
                                                        Cancel
                                                     </button>
                                                 </div>
                                             </>
                                         ) : (
                                             <p className="text-xs text-slate-700 font-medium leading-relaxed mt-1.5 whitespace-pre-wrap">{myAnswers[q.id]}</p>
                                         )}
                                     </div>
                                 );
                             })}
                             
                             {Object.keys(myAnswers).length === 0 && (
                                 <div className="text-center py-12 border-2 border-dashed border-slate-300">
                                     <p className="text-sm font-bold text-slate-400 uppercase">No specs defined yet.</p>
                                     <button 
                                        onClick={() => setActiveTab('DISCOVER')}
                                        className="mt-2 text-indigo-600 text-xs font-bold uppercase tracking-widest hover:underline"
                                     >
                                         Go to Discover
                                     </button>
                                 </div>
                             )}
                         </div>
                    </div>
                )}

                {/* === DISCOVER TAB (Unanswered) === */}
                {!quizView && activeTab === 'DISCOVER' && (
                    <div className="animate-fade-in pb-20">
                        <div className="mb-6 flex items-center justify-between">
                             <h3 className="font-black text-slate-900 uppercase tracking-tight text-lg flex items-center gap-2">
                                 <Search size={20} />
                                 Unknown Data
                             </h3>
                             <span className="text-[10px] font-mono text-slate-500 uppercase">
                                 {OPEN_ENDED_QUESTIONS.filter(q => !myAnswers[q.id]).length} Available
                             </span>
                        </div>

                        <div className="space-y-4">
                            {OPEN_ENDED_QUESTIONS.filter(q => !myAnswers[q.id]).map((q) => (
                                <div key={q.id} className="bg-white border-2 border-slate-200 p-5 shadow-[4px_4px_0px_rgba(30,41,59,0.05)] hover:shadow-[4px_4px_0px_rgba(30,41,59,0.1)] transition-all">
                                    <div className="flex items-center gap-2 mb-3">
                                        <span className="w-6 h-6 bg-slate-100 text-slate-400 flex items-center justify-center font-bold text-xs rounded-full">?</span>
                                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{q.category}</span>
                                    </div>
                                    <h4 className="font-bold text-slate-900 text-base leading-snug mb-4">{q.text}</h4>
                                    
                                    <div className="relative">
                                        <textarea 
                                            value={tempAnswers[q.id] || ''}
                                            onChange={(e) => setTempAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                                            placeholder="Type your answer here..."
                                            className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-sm font-medium focus:outline-none focus:border-indigo-600 focus:bg-white transition-all min-h-[80px]"
                                        />
                                        <div className="absolute bottom-2 right-2">
                                            <MessageSquare size={14} className="text-slate-300" />
                                        </div>
                                    </div>

                                    <button 
                                        onClick={() => handleAddNewAnswer(q.id)}
                                        disabled={!tempAnswers[q.id]?.trim()}
                                        className="w-full mt-4 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white py-3 font-bold uppercase tracking-widest text-xs flex items-center justify-center gap-2 transition-all shadow-sm active:translate-y-0.5"
                                    >
                                        <Plus size={14} /> Add to My Specs
                                    </button>
                                </div>
                            ))}

                            {OPEN_ENDED_QUESTIONS.filter(q => !myAnswers[q.id]).length === 0 && (
                                <div className="text-center py-12 bg-slate-100 border-2 border-slate-200">
                                    <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center mx-auto mb-4 border-2 border-slate-200">
                                        <Check size={24} className="text-green-500" />
                                    </div>
                                    <h3 className="font-bold text-slate-900 uppercase">All Specs Completed!</h3>
                                    <p className="text-xs font-mono text-slate-500 mt-1">Your user manual is fully populated.</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* === QUIZ VIEW (Unchanged Logic, mostly hardcoded for demo) === */}
                {quizView && activeLevelId && (
                     <div className="fixed inset-0 z-50 bg-slate-50 flex flex-col animate-slide-in-down">
                        <div className="bg-white border-b-4 border-slate-900 p-4 flex justify-between items-center shadow-md">
                            <button onClick={exitQuiz} className="text-slate-400 hover:text-slate-900">
                                <X size={24} />
                            </button>
                            <div className="flex-1 px-4">
                                <div className="h-4 w-full bg-slate-100 rounded-full border border-slate-200 relative overflow-hidden">
                                    <div 
                                        className="h-full bg-indigo-600 transition-all duration-300 ease-out"
                                        style={{ width: `${((currentQuestionIdx) / (mapLevels.find(l => l.id === activeLevelId)?.totalQuestions || 1)) * 100}%` }}
                                    ></div>
                                </div>
                            </div>
                            <div className="flex items-center gap-1 font-black text-rose-500">
                                <Heart size={20} className="fill-rose-500" /> 5
                            </div>
                        </div>

                        {quizState === 'complete' ? (
                             <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-50">
                                <div className="w-32 h-32 bg-yellow-400 border-4 border-slate-900 flex items-center justify-center mb-6 shadow-[8px_8px_0px_rgba(30,41,59,1)] animate-bounce">
                                     <Trophy size={64} className="text-slate-900" />
                                </div>
                                <h2 className="text-3xl font-black text-slate-900 uppercase tracking-tighter mb-2">Level Conquered!</h2>
                                <p className="text-slate-500 font-mono mb-8">Specification data updated for {selectedSubject?.name}.</p>
                                
                                <div className="flex gap-4 w-full max-w-xs mb-8">
                                    <div className="flex-1 bg-white border-2 border-slate-200 p-4">
                                        <div className="text-[10px] font-bold text-slate-400 uppercase">XP Earned</div>
                                        <div className="text-2xl font-black text-indigo-600">+{quizScore}</div>
                                    </div>
                                    <div className="flex-1 bg-white border-2 border-slate-200 p-4">
                                        <div className="text-[10px] font-bold text-slate-400 uppercase">Bonus</div>
                                        <div className="text-2xl font-black text-orange-500">+50</div>
                                    </div>
                                </div>

                                <button 
                                    onClick={exitQuiz}
                                    className="w-full max-w-xs bg-slate-900 text-white font-bold py-4 uppercase tracking-widest hover:bg-slate-800 transition-all shadow-lg active:translate-y-0.5 active:shadow-none"
                                >
                                    Return to Map
                                </button>
                             </div>
                        ) : (
                             <div className="flex-1 flex flex-col p-6 max-w-lg mx-auto w-full">
                                <div className="flex-1">
                                    <div className="mb-6">
                                        <div className="inline-block px-2 py-0.5 mb-2 border border-indigo-200 bg-indigo-50 text-[10px] font-mono font-bold text-indigo-600 uppercase tracking-wide">
                                            Subject: {selectedSubject?.name}
                                        </div>
                                        <h3 className="text-2xl font-black text-slate-900 leading-snug">
                                            {getQuestionText(QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].question)}
                                        </h3>
                                    </div>
                                    
                                    <div className="space-y-3">
                                        {QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].options.map((opt, idx) => {
                                            let style = "bg-white border-slate-200 hover:bg-slate-50 border-b-4 active:border-b-2 active:translate-y-[2px]";
                                            if (quizState !== 'idle') {
                                                if (idx === QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].correctIndex) {
                                                    style = "bg-green-100 border-green-500 text-green-800 border-b-4";
                                                } else if (idx === selectedOption) {
                                                    style = "bg-red-100 border-red-500 text-red-800 border-b-4";
                                                } else {
                                                    style = "bg-slate-50 border-slate-100 text-slate-300 border-b-4 opacity-50";
                                                }
                                            }

                                            return (
                                                <button
                                                    key={idx}
                                                    onClick={() => handleAnswer(idx)}
                                                    disabled={quizState !== 'idle'}
                                                    className={`w-full p-4 border-2 rounded-xl text-left font-bold transition-all flex items-center justify-between ${style}`}
                                                >
                                                    {opt}
                                                    {quizState !== 'idle' && idx === QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].correctIndex && <Check size={20} />}
                                                </button>
                                            )
                                        })}
                                    </div>
                                </div>

                                <div className={`border-t-2 pt-4 ${quizState === 'idle' ? 'border-transparent' : (quizState === 'correct' ? 'border-green-200' : 'border-red-200')}`}>
                                    {quizState !== 'idle' ? (
                                        <div className={`p-4 rounded-xl flex items-center justify-between ${quizState === 'correct' ? 'bg-green-50' : 'bg-red-50'}`}>
                                            <div className="flex items-center gap-3">
                                                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${quizState === 'correct' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'}`}>
                                                    {quizState === 'correct' ? <Check size={18} /> : <X size={18} />}
                                                </div>
                                                <span className={`font-black uppercase text-sm ${quizState === 'correct' ? 'text-green-800' : 'text-red-800'}`}>
                                                    {quizState === 'correct' ? 'Excellent!' : 'Correct answer: ' + QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].options[QUIZ_DATA[currentQuestionIdx % QUIZ_DATA.length].correctIndex]}
                                                </span>
                                            </div>
                                            <button 
                                                onClick={nextQuestion}
                                                className={`px-6 py-3 rounded-lg font-bold uppercase tracking-widest text-white shadow-md active:translate-y-0.5 active:shadow-none ${quizState === 'correct' ? 'bg-green-600 hover:bg-green-500' : 'bg-red-600 hover:bg-red-500'}`}
                                            >
                                                Next
                                            </button>
                                        </div>
                                    ) : (
                                        <div className="h-20 flex items-center justify-center text-slate-300 text-xs font-mono uppercase tracking-widest">
                                            Select an option to continue
                                        </div>
                                    )}
                                </div>
                             </div>
                        )}
                     </div>
                )}
            </div>
      </div>
    </div>
  );
};
