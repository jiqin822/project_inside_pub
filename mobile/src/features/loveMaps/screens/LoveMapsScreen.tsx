import React, { useState, useEffect } from 'react';
import {
  Heart,
  X,
  Star,
  Lock,
  Shield,
  Eye,
  Key,
  Lightbulb,
  ArrowRight,
  Layers,
  RefreshCw,
  Music,
  Package,
  Terminal,
  ChevronUp,
  ChevronDown,
} from 'lucide-react';
import {
  EconomyConfig,
  LovedOne,
  MarketItem,
  LoveMapLayer,
  AddNotificationFn,
} from '../../../shared/types/domain';
import { RoomHeader } from '../../../shared/ui/RoomHeader';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';

interface Props {
  xp: number;
  setXp: (xp: number) => void;
  economy: EconomyConfig;
  onExit: () => void;
  onUpdateLovedOne: (id: string, updates: Partial<LovedOne>) => void;
  onAddNotification?: AddNotificationFn;
}

// --- Data Models for Deck System ---

type CardType = 'QUICK_PICK' | 'GUESS' | 'SUPPORT' | 'REPAIR' | 'VULNERABILITY';

interface LoveMapCard {
  id: string;
  layer: LoveMapLayer;
  type: CardType;
  category: string;
  title: string;
  question: string;
  options?: string[];
  correctAnswer?: string;
  suggestedVoucher?: {
    title: string;
    cost: number;
    icon: string;
    type: 'earn' | 'spend';
  };
}

interface LayerDef {
  id: LoveMapLayer;
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  borderColor: string;
  milestoneTotal: number;
  vol: string;
}

// --- Static Data Configuration ---

const LAYERS: LayerDef[] = [
  { id: 'VIBES', title: 'Vibes', subtitle: 'Preferences', icon: <Music size={16} />, color: 'text-gray-900', bgColor: 'bg-white', borderColor: 'border-slate-900', milestoneTotal: 10, vol: 'Vol. 1' },
  { id: 'LOGISTICS', title: 'Logistics', subtitle: 'Routines', icon: <Package size={16} />, color: 'text-gray-900', bgColor: 'bg-white', borderColor: 'border-slate-900', milestoneTotal: 15, vol: 'Vol. 2' },
  { id: 'OS', title: 'Inner OS', subtitle: 'Processing', icon: <Terminal size={16} />, color: 'text-rose-600', bgColor: 'bg-rose-50', borderColor: 'border-rose-600', milestoneTotal: 20, vol: 'Vol. 3' },
  { id: 'APPRECIATION', title: 'Intimacy', subtitle: 'Connection', icon: <Heart size={16} />, color: 'text-pink-600', bgColor: 'bg-pink-50', borderColor: 'border-pink-600', milestoneTotal: 20, vol: 'Vol. 4' },
  { id: 'REPAIR', title: 'Repair', subtitle: 'Conflict', icon: <Shield size={16} />, color: 'text-orange-600', bgColor: 'bg-orange-50', borderColor: 'border-orange-600', milestoneTotal: 10, vol: 'Vol. 5' },
  { id: 'VULNERABILITY', title: 'Vision', subtitle: 'Meaning', icon: <Eye size={16} />, color: 'text-emerald-600', bgColor: 'bg-emerald-50', borderColor: 'border-emerald-600', milestoneTotal: 8, vol: 'Vol. 6' },
];

const MOCK_DECK: LoveMapCard[] = [
  {
    id: 'c1',
    layer: 'VIBES',
    type: 'QUICK_PICK',
    category: 'Weekend',
    title: 'Ideal Saturday',
    question: 'If we had zero responsibilities this Saturday, I would choose:',
    options: ['Brunch & Walk', 'Stay in & Game', 'See Friends', 'Total Solitude'],
    suggestedVoucher: { title: 'Planned Lazy Saturday', cost: 200, icon: '🛌', type: 'spend' },
  },
  {
    id: 'c2',
    layer: 'VIBES',
    type: 'GUESS',
    category: 'Food',
    title: 'Comfort Food',
    question: "Guess my absolute go-to comfort food when I'm sad:",
    options: ['Pizza', 'Ice Cream', 'Spicy Noodles', 'Soup'],
    correctAnswer: 'Spicy Noodles',
    suggestedVoucher: { title: 'Noodle Night Delivery', cost: 150, icon: '🍜', type: 'spend' },
  },
  {
    id: 'c3',
    layer: 'OS',
    type: 'SUPPORT',
    category: 'Stress',
    title: 'Overwhelm Protocol',
    question: 'When I am overwhelmed, the most helpful thing is:',
    options: ['Advice/Solutions', 'Silent Presence', 'Distraction/Jokes', 'Physical Help'],
    suggestedVoucher: { title: 'Silent Support Hour', cost: 100, icon: '🤫', type: 'spend' },
  },
  {
    id: 'c4',
    layer: 'REPAIR',
    type: 'REPAIR',
    category: 'Conflict',
    title: 'Shut Down Trigger',
    question: 'I tend to shut down during arguments when I feel:',
    options: ['Criticized', 'Ignored', 'Overwhelmed', 'Unsafe'],
    suggestedVoucher: { title: 'Safe Word Pause', cost: 0, icon: '🛑', type: 'earn' },
  },
];

const DEFAULT_LAYER_PROGRESS: Record<LoveMapLayer, number> = {
  VIBES: 8,
  LOGISTICS: 10,
  OS: 12,
  APPRECIATION: 4,
  REPAIR: 2,
  VULNERABILITY: 1,
  FUTURE: 0,
};

export const LoveMapsScreen: React.FC<Props> = ({
  xp,
  setXp,
  economy,
  onExit,
  onUpdateLovedOne,
  onAddNotification,
}) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();

  const [view, setView] = useState<'DASHBOARD' | 'CARD_PLAY'>('DASHBOARD');
  const [activeLayerId, setActiveLayerId] = useState<LoveMapLayer>('OS');
  const [isFooterOpen, setIsFooterOpen] = useState(false);
  const [isInitialSelection, setIsInitialSelection] = useState(true);

  const [dailyMix, setDailyMix] = useState<LoveMapCard[]>([]);
  const [activeCard, setActiveCard] = useState<LoveMapCard | null>(null);
  const [cardStep, setCardStep] = useState<'FRONT' | 'REVEAL'>('FRONT');
  const [selectedOption, setSelectedOption] = useState<string | null>(null);

  const [hintTokens, setHintTokens] = useState(user?.loveMapStats?.hintTokens ?? 5);
  const [layerProgress, setLayerProgress] = useState<Record<LoveMapLayer, number>>(
    user?.loveMapStats?.layerProgress ?? DEFAULT_LAYER_PROGRESS
  );

  const availablePartners = relationships.length > 0 ? relationships : user?.lovedOnes ?? [];
  const activePartner = availablePartners[0] ?? null;

  useEffect(() => {
    setDailyMix(MOCK_DECK.slice(0, 3));
  }, []);

  const activeLayer = LAYERS.find((l) => l.id === activeLayerId) ?? LAYERS[0];

  const startRound = (card?: LoveMapCard) => {
    const targetCard = card ?? MOCK_DECK.find((c) => c.layer === activeLayerId) ?? MOCK_DECK[0];
    setActiveCard(targetCard);
    setCardStep('FRONT');
    setSelectedOption(null);
    setView('CARD_PLAY');
  };

  const handleAnswer = (option: string) => {
    setSelectedOption(option);
    setTimeout(() => {
      setCardStep('REVEAL');
      let xpGain = 20;
      if (activeCard?.type === 'GUESS' && option === activeCard.correctAnswer) {
        xpGain = 50;
      }
      setXp(xp + xpGain);
      if (activeCard && activeLayer) {
        setLayerProgress((prev) => ({
          ...prev,
          [activeCard.layer]: Math.min(
            (prev[activeCard.layer] ?? 0) + 1,
            activeLayer.milestoneTotal
          ),
        }));
      }
    }, 500);
  };

  const useHint = () => {
    if (hintTokens > 0 && activeCard?.correctAnswer) {
      setHintTokens((prev) => prev - 1);
      alert(`Hint: The answer starts with "${activeCard.correctAnswer!.charAt(0)}..."`);
    }
  };

  const handleInvitePartner = () => {
    if (activePartner) {
      onAddNotification?.('message', 'Invitation Sent', `Invited ${activePartner.name} to sync Love Maps.`);
      alert(`Sync request sent to ${activePartner.name}`);
    } else {
      alert('No partner connected. Please add a partner in Settings.');
    }
  };

  const handleCreateVoucher = (card: LoveMapCard) => {
    if (!card.suggestedVoucher || !activePartner) return;
    const newItem: MarketItem = {
      id: Date.now().toString(),
      title: card.suggestedVoucher.title,
      cost: card.suggestedVoucher.cost,
      icon: card.suggestedVoucher.icon,
      type: 'service',
      category: card.suggestedVoucher.type,
    };
    const currentItems = activePartner.marketItems ?? [];
    onUpdateLovedOne(activePartner.id, { marketItems: [...currentItems, newItem] });
    onAddNotification?.('reward', 'Voucher Created', `Added "${newItem.title}" to Market.`);
    setView('DASHBOARD');
  };

  const renderDashboard = () => (
    <div className="flex-grow relative z-10 flex flex-col items-center justify-start p-4 sm:p-6 w-full max-w-md mx-auto pb-[max(6rem,18vh)] sm:pb-48 min-h-0">
      <div className="w-full flex justify-center mb-4 sm:mb-6">
        <button
          onClick={handleInvitePartner}
          className="bg-white/90 backdrop-blur-md border-2 border-slate-900 px-6 py-1.5 flex items-center space-x-3 rounded-full shadow-md transform hover:-translate-y-0.5 transition-transform"
        >
          <RefreshCw size={14} className="text-rose-600" />
          <span className="font-mono text-[9px] font-bold tracking-widest text-slate-600 uppercase">
            Sync Partner
          </span>
        </button>
      </div>

      <div className="relative w-full flex flex-col items-center justify-center mb-6 sm:mb-8 flex-shrink-0">
        <div
          className="relative"
          style={{
            width: 'min(16rem, 90vw)',
            height: 'min(20rem, 55dvh)',
            minHeight: '12rem',
            fontSize: 'clamp(10px, 2.2vmin, 16px)',
          }}
        >
          <div className="absolute inset-0 bg-white border-2 border-slate-200 rounded-xl transform rotate-6 translate-x-3 translate-y-2" />
          <div className="absolute inset-0 bg-white border-2 border-slate-300 rounded-xl transform -rotate-3 -translate-x-2 translate-y-1" />
          <div
            onClick={() => startRound()}
            className="absolute inset-0 bg-white border-[3px] border-slate-900 rounded-xl shadow-[8px_8px_0px_0px_rgba(0,0,0,0.15)] z-20 flex flex-col overflow-hidden group hover:-translate-y-2 transition-transform duration-300 cursor-pointer"
          >
            <div
              className={`text-white p-[0.75em] flex justify-between items-center border-b-2 border-slate-900 shrink-0 ${activeLayer.id === 'OS' ? 'bg-rose-600' : 'bg-slate-900'}`}
            >
              <span className="font-mono text-[1em] uppercase font-bold tracking-widest">
                {activeLayer.title} Mix
              </span>
              <div className="flex gap-[0.25em]">
                <div className="w-[0.5em] h-[0.5em] bg-white rounded-full" />
                <div className="w-[0.5em] h-[0.5em] bg-white/50 rounded-full" />
                <div className="w-[0.5em] h-[0.5em] bg-white/50 rounded-full" />
              </div>
            </div>
            <div
              className={`flex-grow p-[1em] flex flex-col justify-center items-center text-center relative ${activeLayer.bgColor} bg-opacity-30`}
            >
              <div
                className="absolute inset-0 opacity-5"
                style={{
                  backgroundImage: 'radial-gradient(currentColor 1px, transparent 1px)',
                  backgroundSize: '10px 10px',
                }}
              />
              <div
                className={`w-[3.5em] h-[3.5em] bg-white rounded-full flex items-center justify-center mb-[0.75em] border-2 shadow-sm ${activeLayer.borderColor} ${activeLayer.color}`}
              >
                {activeLayer.icon}
              </div>
              <h2 className="text-[1.25em] font-black uppercase mb-[0.25em] leading-tight text-slate-900">
                Guess My
                <br />
                Answer
              </h2>
              <div className="font-mono text-[0.625em] text-slate-500 mb-[1em] px-[0.5em] relative z-10">
                Topic: <strong className={`${activeLayer.color} uppercase`}>Conflict Styles</strong>
              </div>
              <button
                type="button"
                className={`text-white font-mono font-bold text-[0.625em] py-[0.5em] px-[1.5em] rounded-full transition-colors border border-transparent flex items-center justify-center gap-[0.5em] shadow-lg ${activeLayer.id === 'OS' ? 'bg-slate-900 hover:bg-rose-600' : 'bg-rose-600 hover:bg-slate-900'}`}
              >
                <span>DRAW CARD</span>
                <ArrowRight size={12} className="w-[0.75em] h-[0.75em] shrink-0" />
              </button>
            </div>
            <div className="bg-white p-[0.5em] border-t-2 border-slate-900 flex justify-between items-center px-[0.75em] shrink-0">
              <span className="text-[0.5625em] font-mono text-slate-400 font-bold">EST. 3 MINS</span>
              <span className={`text-[0.5625em] font-mono font-bold ${activeLayer.color}`}>+50 XP</span>
            </div>
          </div>
          <div className="absolute top-[1em] -right-[1.5em] flex flex-col gap-[0.25em]">
            <div className="w-[0.375em] h-[2em] bg-slate-200 border border-slate-300 rounded-r-md" />
            <div className="w-[0.375em] h-[2em] bg-slate-200 border border-slate-300 rounded-r-md" />
            <div
              className={`w-[0.375em] h-[2em] border rounded-r-md ${activeLayer.id === 'OS' ? 'bg-rose-500 border-rose-600' : 'bg-slate-500 border-slate-600'}`}
            />
          </div>
        </div>
      </div>
    </div>
  );

  const renderCardPlay = () => {
    if (!activeCard) return null;
    const layerConfig = LAYERS.find((l) => l.id === activeCard.layer);

    return (
      <div className="flex-grow relative z-10 flex flex-col items-center p-4 sm:p-6 w-full max-w-md mx-auto min-h-0">
        <div className="w-full flex justify-between items-center mb-3 sm:mb-4">
          <h3 className="font-mono text-xs font-bold tracking-widest text-slate-500 uppercase">
            Active Session
          </h3>
          <span className="font-mono text-[10px] bg-slate-200 text-slate-600 px-2 py-0.5 rounded uppercase font-bold">
            Card {activeCard.id}
          </span>
        </div>
        <div className="w-full bg-white border-[3px] border-slate-900 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] flex-1 min-h-0 max-h-[min(550px,65dvh)] flex flex-col relative overflow-hidden transition-all duration-500 rounded-xl">
          <div
            className={`p-4 border-b-2 border-slate-900 flex justify-between items-center ${layerConfig?.bgColor}`}
          >
            <div className="flex items-center gap-2 text-slate-900">
              {layerConfig?.icon}
              <span className="font-mono text-xs font-bold uppercase">{activeCard.category}</span>
            </div>
            <button
              type="button"
              onClick={() => setView('DASHBOARD')}
              className="text-slate-900 hover:text-red-600 transition-colors"
            >
              <X size={18} />
            </button>
          </div>
          {cardStep === 'FRONT' ? (
            <div className="flex-1 p-4 sm:p-6 flex flex-col min-h-0 overflow-y-auto">
              <h3 className="text-lg sm:text-xl font-black text-slate-900 uppercase leading-tight mb-4 sm:mb-8">
                {activeCard.question}
              </h3>
              <div className="space-y-2 sm:space-y-3 mt-auto pt-2">
                {activeCard.options?.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => handleAnswer(opt)}
                    className="w-full p-4 border-2 border-slate-200 bg-white hover:border-slate-900 hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] text-left font-bold text-slate-700 uppercase text-xs transition-all flex justify-between group active:translate-y-0.5 active:shadow-none"
                  >
                    {opt}
                    <div className="w-4 h-4 rounded-full border-2 border-slate-300 group-hover:border-slate-900" />
                  </button>
                ))}
              </div>
              {activeCard.type === 'GUESS' && (
                <div className="mt-6 flex justify-center">
                  <button
                    type="button"
                    onClick={useHint}
                    disabled={hintTokens === 0}
                    className="text-[10px] font-mono font-bold text-slate-400 uppercase hover:text-rose-600 flex items-center gap-1 border border-transparent hover:border-rose-200 px-2 py-1 rounded"
                  >
                    <Key size={12} /> Use Hint ({hintTokens})
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 p-4 sm:p-6 flex flex-col min-h-0 overflow-y-auto bg-slate-900 text-white">
              <div className="flex justify-between items-start mb-4 sm:mb-6">
                <div className="text-yellow-400">
                  <Star size={24} fill="currentColor" />
                </div>
                <div className="text-[10px] font-mono uppercase border border-slate-700 px-2 py-0.5 rounded">
                  Logged
                </div>
              </div>
              <div className="text-center mt-2 sm:mt-4">
                <p className="text-[10px] font-bold uppercase text-slate-500 mb-2">You Selected</p>
                <div className="text-xl sm:text-2xl font-black mb-4 sm:mb-8">{selectedOption}</div>
                {activeCard.type === 'GUESS' && activeCard.correctAnswer && (
                  <div className="bg-slate-800 p-4 border border-slate-700 mb-6 relative overflow-hidden">
                    <div
                      className="absolute inset-0 opacity-10"
                      style={{
                        backgroundImage:
                          'repeating-linear-gradient(45deg, #fff, #fff 5px, transparent 5px, transparent 10px)',
                      }}
                    />
                    <p className="text-[10px] font-bold uppercase text-emerald-400 mb-1 relative z-10">
                      Partner's Answer
                    </p>
                    <div className="text-xl font-bold text-white relative z-10">
                      {activeCard.correctAnswer}
                    </div>
                  </div>
                )}
              </div>
              <div className="mt-auto space-y-3">
                {activeCard.suggestedVoucher && (
                  <button
                    type="button"
                    onClick={() => handleCreateVoucher(activeCard)}
                    className="w-full bg-rose-600 text-white py-3 text-[10px] font-bold uppercase tracking-widest border-2 border-rose-400 hover:bg-rose-500 transition-colors shadow-lg active:translate-y-0.5 active:shadow-none"
                  >
                    Create &quot;{activeCard.suggestedVoucher.title}&quot; Voucher
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setView('DASHBOARD')}
                  className="w-full py-3 bg-transparent border-2 border-slate-700 text-slate-400 hover:text-white hover:border-white text-xs font-bold uppercase transition-colors"
                >
                  Next Card
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  if (!user) {
    return null;
  }

  return (
    <div className="min-h-[100dvh] h-full bg-slate-50 text-slate-900 font-sans relative overflow-hidden flex flex-col">
      <div
        className="absolute inset-0 z-0 pointer-events-none opacity-40"
        style={{
          backgroundImage:
            'linear-gradient(to right, #e5e7eb 1px, transparent 1px), linear-gradient(to bottom, #e5e7eb 1px, transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />
      <RoomHeader
        moduleTitle="MODULE: UNDERSTANDING"
        title={<>Love Maps <span className="text-sm font-normal text-slate-500 normal-case">[under construction]</span></>}
        subtitle={{ text: 'Deck Hub', colorClass: 'text-rose-600' }}
        onClose={onExit}
        titleClassName="text-2xl font-black tracking-tighter uppercase leading-none text-slate-900"
      />
      {view === 'DASHBOARD' && (
        <div className="w-full bg-white/95 backdrop-blur-sm border-b-2 border-slate-900 py-2 sm:py-3 px-4 sm:px-6 flex items-center justify-between gap-2 sm:gap-4 z-30 shrink-0 flex-wrap">
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <div
              className={`w-8 h-8 flex items-center justify-center rounded-full border-2 border-slate-900 bg-slate-50 ${activeLayer.color}`}
            >
              {activeLayer.icon}
            </div>
            <div>
              <div className="text-[9px] font-mono font-bold text-slate-400 uppercase leading-none mb-0.5">
                Current Layer
              </div>
              <div className="text-xs font-black text-slate-900 uppercase leading-none">
                {activeLayer.title}
              </div>
            </div>
          </div>
          <div className="flex-1 min-w-0 max-w-[140px] flex flex-col gap-1">
            <div className="flex justify-between text-[8px] font-mono font-bold uppercase text-slate-400">
              <span>Mastery</span>
              <span>
                {Math.round((layerProgress[activeLayerId] / activeLayer.milestoneTotal) * 100)}%
              </span>
            </div>
            <div className="h-1.5 w-full border border-slate-300 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${activeLayer.id === 'OS' ? 'bg-rose-500' : 'bg-slate-900'}`}
                style={{
                  width: `${(layerProgress[activeLayerId] / activeLayer.milestoneTotal) * 100}%`,
                }}
              />
            </div>
          </div>
          <div className="flex items-center gap-1.5 bg-yellow-50 px-2 py-1 border border-yellow-200 rounded-md text-yellow-700 shadow-sm">
            <Lightbulb size={12} className="fill-yellow-500" />
            <span className="text-[10px] font-bold font-mono">{hintTokens}</span>
          </div>
        </div>
      )}
      <main className={`flex-1 min-h-0 relative z-10 overflow-y-auto overflow-x-hidden ${isInitialSelection ? 'hidden' : ''}`}>
        {view === 'DASHBOARD' && renderDashboard()}
        {view === 'CARD_PLAY' && renderCardPlay()}
      </main>
      {view === 'DASHBOARD' && (
        <div className={`${isInitialSelection ? 'relative flex-1' : 'absolute bottom-0 left-0 right-0'} z-50 flex flex-col pointer-events-none`}>
          <footer
            className={`w-full bg-white border-t-2 border-slate-900 pointer-events-auto shadow-[0_-10px_20px_rgba(0,0,0,0.05)] transition-all duration-300 ease-in-out flex flex-col pb-[env(safe-area-inset-bottom,0px)] ${
              isInitialSelection ? 'h-full pb-4' : isFooterOpen ? 'h-auto pb-4' : 'h-10'
            }`}
          >
            <div
              role="button"
              tabIndex={0}
              onClick={() => {
                if (isInitialSelection) {
                  setIsInitialSelection(false);
                  setIsFooterOpen(false);
                } else {
                  setIsFooterOpen(!isFooterOpen);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  if (isInitialSelection) {
                    setIsInitialSelection(false);
                    setIsFooterOpen(false);
                  } else {
                    setIsFooterOpen((v) => !v);
                  }
                }
              }}
              className="flex items-center justify-between px-4 sm:px-6 h-10 cursor-pointer hover:bg-slate-50 shrink-0"
            >
              <div className="flex items-center gap-2">
                <Layers size={14} className="text-slate-400" />
                <h3 className="font-mono text-xs font-bold uppercase tracking-widest text-slate-900">
                  Subdeck Selector
                </h3>
              </div>
              {isFooterOpen || isInitialSelection ? (
                <ChevronDown size={16} className="text-slate-400" />
              ) : (
                <ChevronUp size={16} className="text-slate-400" />
              )}
            </div>
            {(isFooterOpen || isInitialSelection) && (
              <div
                className={isInitialSelection
                  ? "grid gap-2 sm:gap-4 px-3 sm:px-6 pb-6 pt-4 overflow-y-auto overflow-x-hidden max-h-[60dvh] min-w-0 items-start"
                  : "flex overflow-x-auto gap-3 px-4 sm:px-6 pb-2 pt-2"}
                style={{
                  fontSize: isInitialSelection ? 'clamp(10px, 2vmin, 14px)' : 'clamp(10px, 2.5vmin, 14px)',
                  ...(isInitialSelection
                    ? {
                        gridTemplateColumns: 'repeat(auto-fill, minmax(min(5.5rem, 42vw), 1fr))',
                        gridAutoRows: 'minmax(min(6.875rem, 52.5vw), auto)',
                        alignContent: 'start',
                      }
                    : {}),
                }}
              >
                {LAYERS.map((layer, idx) => {
                  const isLocked =
                    idx > 0 && layerProgress[LAYERS[idx - 1].id] < LAYERS[idx - 1].milestoneTotal;
                  const isActive = activeLayerId === layer.id;

                  const cardClasses = isInitialSelection
                    ? "w-full max-w-full min-w-0 aspect-[4/5] min-h-0 h-auto"
                    : "w-[min(5rem,22vmin)] h-[min(6rem,28vmin)] min-w-[4rem] flex-shrink-0";

                  if (isLocked) {
                    return (
                      <button
                        key={layer.id}
                        type="button"
                        disabled
                        className={`${cardClasses} flex flex-col border-2 border-slate-300 rounded-lg overflow-hidden bg-slate-50 opacity-70 cursor-not-allowed`}
                      >
                        <div className="w-full py-[0.25em] bg-slate-200 border-b-2 border-slate-300">
                          <span className="text-[0.7em] font-mono font-bold uppercase text-slate-400">
                            {layer.vol}
                          </span>
                        </div>
                        <div className="flex-grow flex flex-col items-center justify-center p-[0.25em] relative">
                          <div
                            className="absolute inset-0 opacity-5"
                            style={{
                              backgroundImage:
                                'repeating-linear-gradient(45deg, #000, #000 1px, transparent 1px, transparent 10px)',
                            }}
                          />
                          <Lock size={14} className="text-slate-400 mb-[0.25em] w-[1em] h-[1em]" />
                          <span className="font-black text-[0.8em] uppercase tracking-tight text-slate-400 truncate w-full text-center">
                            {layer.title}
                          </span>
                        </div>
                        <div className="w-full py-[0.25em] border-t-2 border-slate-300 bg-slate-100">
                          <span className="text-[0.7em] font-mono font-bold text-slate-400 uppercase">
                            Locked
                          </span>
                        </div>
                      </button>
                    );
                  }
                  return (
                    <button
                      key={layer.id}
                      type="button"
                      onClick={() => {
                        setActiveLayerId(layer.id);
                        if (isInitialSelection) {
                          setIsInitialSelection(false);
                          setIsFooterOpen(false);
                        }
                      }}
                      className={`${cardClasses} flex flex-col border-2 rounded-lg overflow-hidden transition-all group ${
                        isActive
                          ? 'border-rose-600 bg-rose-50 shadow-[2px_2px_0px_0px_#e11d48] hover:-translate-y-1'
                          : 'border-slate-900 bg-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] hover:-translate-y-1'
                      }`}
                    >
                      <div
                        className={`w-full py-[0.25em] border-b-2 ${isActive ? 'bg-rose-600 border-rose-600 text-white' : 'bg-slate-100 border-slate-900 text-slate-500'}`}
                      >
                        <span className="text-[0.7em] font-mono font-bold uppercase">{layer.vol}</span>
                      </div>
                      <div className="flex-grow flex flex-col items-center justify-center p-[0.25em] relative">
                        <div
                          className={`mb-[0.25em] transition-transform group-hover:scale-110 ${isActive ? 'text-rose-600' : 'text-slate-900'}`}
                        >
                          {React.cloneElement(layer.icon as React.ReactElement<{ size?: number }>, {
                            size: 16,
                          })}
                        </div>
                        <span
                          className={`font-black text-[0.8em] uppercase tracking-tight truncate w-full text-center ${isActive ? 'text-rose-600' : 'text-slate-900'}`}
                        >
                          {layer.title}
                        </span>
                      </div>
                      <div
                        className={`w-full py-[0.25em] border-t-2 ${isActive ? 'border-rose-600 bg-white' : 'border-slate-900 bg-white'}`}
                      >
                        <span
                          className={`text-[0.7em] font-mono font-bold uppercase ${isActive ? 'text-rose-600' : 'text-green-600'}`}
                        >
                          {isActive ? 'Selected' : 'Active'}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </footer>
        </div>
      )}
    </div>
  );
};
