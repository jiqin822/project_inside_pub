import React from 'react';
import { Capacitor } from '@capacitor/core';
import { AppMode } from '../../../shared/types/domain';
import { Armchair, Gamepad2, Radio, Lock, Gift, Map as MapIcon, FileText, MessageCircle } from 'lucide-react';

interface FloorPlanProps {
  onRoomClick: (mode: AppMode) => void;
  onRestrictedAccess: (mode: AppMode) => void;
}

// Door component for floor plan
const Door = ({ side, position = 'center', swing = 'left', isOpen = false }: { 
  side: 'top'|'right'|'bottom'|'left', 
  position?: string, 
  swing?: 'left'|'right', 
  isOpen?: boolean 
}) => {
  let style: React.CSSProperties = {};
  
  if (side === 'right') {
    style = { right: '-10px', top: position === 'top' ? '20%' : position === 'bottom' ? '80%' : '50%', transform: 'translateY(-50%)' };
  } else if (side === 'bottom') {
    style = { bottom: '-10px', left: position === 'left' ? '20%' : position === 'right' ? '80%' : '50%', transform: 'translateX(-50%)' };
  } else if (side === 'left') {
    style = { left: '-10px', top: position === 'top' ? '20%' : position === 'bottom' ? '80%' : '50%', transform: 'translateY(-50%)' };
  } else if (side === 'top') {
    style = { top: '-10px', left: position === 'left' ? '20%' : position === 'right' ? '80%' : '50%', transform: 'translateX(-50%)' };
  }

  const isHorizontal = side === 'top' || side === 'bottom';
  const gapSize = isHorizontal ? 'w-10 h-[10px]' : 'w-[10px] h-10';

  return (
    <div className="absolute z-20 pointer-events-none" style={style}>
      <div className={`${gapSize} bg-white`} /> 
    </div>
  );
};

// Window component for floor plan
const Window = ({ side, width = 'w-12' }: { side: 'top'|'right'|'bottom'|'left', width?: string }) => {
  let style: React.CSSProperties = {};
  if (side === 'top') style = { top: '-4px', left: '50%', transform: 'translateX(-50%)' };
  if (side === 'bottom') style = { bottom: '-4px', left: '50%', transform: 'translateX(-50%)' };
  if (side === 'left') style = { left: '-4px', top: '50%', transform: 'translateY(-50%)' };
  if (side === 'right') style = { right: '-4px', top: '50%', transform: 'translateY(-50%)' };
  const isHorizontal = side === 'top' || side === 'bottom';
  return (
    <div className={`absolute z-20 bg-white border-x-2 border-slate-900 ${isHorizontal ? `${width} h-2` : `w-2 h-12 border-y-2 border-x-0`}`} style={style}>
      <div className="w-full h-full bg-slate-200 opacity-50"></div>
    </div>
  );
};

export const FloorPlan: React.FC<FloorPlanProps> = ({ onRoomClick, onRestrictedAccess }) => {
  const isNative = Capacitor.isNativePlatform();
  const pad = isNative ? '0.5rem' : '1.0rem';
  const padRight = isNative ? '1.25rem' : pad;
  const outerStyle: React.CSSProperties = {
    width: '100%',
    minWidth: 0,
    minHeight: 0,
    flex: 1,
    paddingTop: '0.1rem',
    paddingRight: padRight,
    paddingBottom: pad,
    paddingLeft: '0.1rem',
    boxSizing: 'border-box',
  };

  return (
    <div className="relative flex flex-col items-center w-full" style={outerStyle}>
      {/* Top dimension label — in flow with gap below so it never overlaps the floor plan */}
      <div 
        className="w-full text-center text-[10px] font-mono text-slate-400 pointer-events-none shrink-0" 
        style={{ borderBottom: '1px solid #cbd5e1', paddingBottom: '2px', minHeight: '1.25rem', marginBottom: '0.5rem' }}
      >
        30' - 0"
      </div>

      {/* 2-column grid: left dimension gutter + plan column (centers correctly, no marginLeft) */}
      <div
        className="w-full flex-1 min-h-0 grid overflow-hidden"
        style={{
          gridTemplateColumns: '1.5rem 1fr',
          alignItems: 'stretch',
        }}
      >
        {/* Left dimension label column */}
        <div
          className="flex items-center justify-end pr-1 text-[10px] font-mono text-slate-400 pointer-events-none"
          style={{ borderRight: '1px solid #cbd5e1' }}
        >
          <span style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>40' - 0"</span>
        </div>

        {/* Plan column — flex column so black frame can fill and fit viewport */}
        <div className="flex flex-col items-center justify-center overflow-hidden min-h-0 min-w-0">
          <div className="flex flex-1 items-center justify-center min-h-0 w-full">
          <div
            className="bg-slate-900 p-2 shadow-2xl overflow-hidden w-full h-full"
            style={{ minHeight: 0 }}
          >
            {/* GRID SYSTEM: 6 cols x 6 rows */}
            <div className="w-full h-full grid grid-cols-6 grid-rows-6 gap-2 bg-slate-900">
          
          {/* ROOM 1: STUDY (Love Map) - Top Left (2x2) */}
          <button 
            onClick={() => onRoomClick(AppMode.LOVE_MAPS)}
            className="col-span-2 row-span-2 bg-white hover:bg-slate-50 transition-colors relative group overflow-visible flex flex-col justify-between p-3 text-left border-2 border-slate-200"
            style={{ backgroundImage: 'radial-gradient(circle, #e2e8f0 1px, transparent 1px)', backgroundSize: '10px 10px' }}
          >
            <Window side="top" /><Window side="left" />
            <Door side="bottom" position="center" swing="right" isOpen={true} />
            <div className="z-10">
              <span className="text-[8px] font-mono font-bold text-slate-400 block border-b border-slate-300 w-fit mb-1">RM-101</span>
              <h3 className="font-black text-xs text-slate-900 leading-none">STUDY</h3>
              <p className="text-[8px] font-mono text-pink-600 mt-1 font-bold uppercase">Love Map</p>
            </div>
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 opacity-10"><MapIcon size={40} strokeWidth={1} /></div>
            <div className="z-10 flex items-end justify-between mt-auto"><MapIcon size={14} className="text-slate-400" /></div>
          </button>

          {/* ROOM 2: GAME ROOM (Activities) - Top Center (2x2) */}
          <button 
            onClick={() => onRoomClick(AppMode.ACTIVITIES)}
            className="col-span-2 row-span-2 bg-white hover:bg-slate-50 transition-colors relative group overflow-visible flex flex-col justify-between p-3 text-left border-2 border-slate-200"
            style={{ backgroundImage: 'radial-gradient(circle, #e2e8f0 1px, transparent 1px)', backgroundSize: '10px 10px' }}
          >
            <Window side="top" width="w-8" />
            <Door side="bottom" position="center" swing="right" isOpen={true} /> 
            <div className="z-10">
              <span className="text-[8px] font-mono font-bold text-slate-400 block border-b border-slate-300 w-fit mb-1">RM-102</span>
              <h3 className="font-black text-xs text-slate-900 leading-none tracking-tight">GAME RM</h3>
              <p className="text-[8px] font-mono text-orange-600 mt-1 font-bold uppercase">Quests</p>
            </div>
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 opacity-10"><Gamepad2 size={40} strokeWidth={1} /></div>
          </button>

          {/* ROOM 3: VAULT (Rewards) - Top Right (2x2) */}
          <button 
            onClick={() => onRoomClick(AppMode.REWARDS)}
            className="col-span-2 row-span-2 bg-slate-100 hover:bg-slate-200 transition-colors relative group overflow-visible flex flex-col justify-between p-3 text-left border-4 border-slate-300"
          >
            <Window side="top" /><Window side="right" />
            <Door side="bottom" position="center" swing="left" />
            <div className="z-10 w-full">
              <span className="text-[8px] font-mono font-bold text-slate-400 block border-b border-slate-300 w-fit mb-1">RM-104</span>
              <h3 className="font-black text-xs text-slate-900 leading-none flex items-center gap-1"><Lock size={12} /> MARKET</h3>
              <p className="text-[8px] font-mono text-yellow-600 mt-1 font-bold uppercase">Economy of Care</p>
            </div>
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 opacity-10"><Gift size={32} strokeWidth={1} /></div>
          </button>

          {/* ROOM 4: LIVING ROOM (Conversation sessions) - Middle Strip (6x2) */}
          <button 
            onClick={() => onRoomClick(AppMode.LOUNGE)}
            className="col-span-6 row-span-2 bg-slate-50 hover:bg-slate-100 transition-colors relative group overflow-visible flex flex-col justify-between p-4 text-left border-2 border-slate-200"
            style={{ backgroundImage: 'radial-gradient(circle, #cbd5e1 1px, transparent 1px)', backgroundSize: '10px 10px' }}
          >
            <Door side="top" position="left" swing="left" />
            <Door side="top" position="center" swing="left" />
            <Door side="top" position="right" swing="right" />
            <Door side="bottom" position="left" swing="right" />
            <div className="z-10 flex justify-between w-full">
              <div>
                <span className="text-[8px] font-mono font-bold text-slate-400 block border-b border-slate-300 w-fit mb-1">RM-103</span>
                <h3 className="font-black text-lg text-slate-900 leading-none tracking-tight">LIVING ROOM</h3>
                <p className="text-[8px] font-mono text-indigo-600 mt-1 font-bold uppercase">Conversation</p>
              </div>
              <MessageCircle size={40} strokeWidth={1} className="opacity-20" />
            </div>
          </button>

          {/* ROOM 5: MASTER SUITE (Profile) - Bottom Left (4x2) */}
          <button 
            onClick={() => onRoomClick(AppMode.PROFILE)}
            className="col-span-4 row-span-2 bg-white hover:bg-slate-50 transition-colors relative group overflow-visible flex flex-col justify-between p-4 text-left border-2 border-slate-200"
            style={{ backgroundImage: 'radial-gradient(circle, #e2e8f0 1px, transparent 1px)', backgroundSize: '10px 10px' }}
          >
            <Window side="bottom" width="w-20" /><Window side="left" />
            <Door side="top" position="left" swing="left" isOpen={true} />
            <Door side="right" position="top" swing="right" />
            <div className="z-10">
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-[8px] font-mono font-bold text-slate-400 block border-b border-slate-300 w-fit mb-1">RM-200</span>
                  <h3 className="font-black text-lg text-slate-900 leading-none tracking-tight">MASTER<br/>SUITE</h3>
                  <p className="text-[8px] font-mono text-indigo-500 mt-1 font-bold uppercase">Analytics & Settings</p>
                </div>
                <div className="text-right">
                  <div className="text-xl font-black text-slate-900">85%</div>
                  <div className="text-[6px] font-bold text-slate-400 uppercase">Health</div>
                </div>
              </div>
            </div>
            <div className="absolute top-1/2 left-2/3 -translate-x-1/2 -translate-y-1/2 opacity-10"><FileText size={50} strokeWidth={1} /></div>
            <div className="z-10 flex items-center justify-between mt-auto"><span className="text-[8px] font-mono text-slate-400">20' x 14'</span></div>
          </button>

          {/* ROOM 6: DIALOGUE DECK (Live Coach) - Bottom Right (2x2) */}
          <button 
            onClick={() => onRestrictedAccess(AppMode.LIVE_COACH)}
            className="col-span-2 row-span-2 bg-slate-50 hover:bg-slate-100 transition-colors relative group overflow-hidden flex flex-col justify-between p-3 text-left border-2 border-dashed border-slate-300"
          >
            <div className="absolute inset-0 pointer-events-none opacity-5" style={{ backgroundImage: 'repeating-linear-gradient(45deg, #000 0, #000 1px, transparent 0, transparent 8px)' }}></div>
            <div className="z-10">
              <div className="flex items-center gap-1 mb-1"><span className="text-[6px] font-mono font-bold text-slate-500 bg-white px-1 border border-slate-200">EXTERIOR</span></div>
              <h3 className="font-black text-sm text-slate-900 tracking-tight leading-none">DIALOGUE<br/>DECK</h3>
              <p className="text-[8px] font-mono text-cyan-600 mt-1 font-bold uppercase">Live Coaching</p>
            </div>
            <div className="z-10 flex items-end justify-between mt-auto"><Radio size={16} className="text-slate-400" /></div>
          </button>
            </div>
          </div>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className={`w-full max-w-md mx-auto px-4 mt-2 grid grid-cols-2 gap-4 border-t border-slate-200 pt-1.5 shrink-0`}>
        <div className="flex items-center gap-2"><div className="w-4 h-4 border-2 border-slate-900 bg-white"></div><span className="text-[10px] font-mono uppercase text-slate-500">Interior</span></div>
        <div className="flex items-center gap-2"><div className="w-4 h-4 border-2 border-dashed border-slate-400 bg-slate-50"></div><span className="text-[10px] font-mono uppercase text-slate-500">Exterior</span></div>
      </div>
    </div>
  );
};
