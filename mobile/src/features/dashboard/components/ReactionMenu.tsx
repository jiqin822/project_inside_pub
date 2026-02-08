import React, { useState, useEffect } from 'react';

interface ReactionMenuProps {
  target: { id: string; name: string; relationshipId?: string } | null;
  position: { x: number; y: number } | null;
  onReaction: (emoji: string) => void;
  onClose: () => void;
}

/** Sentinel for "Send emotion" (notification type emotion: watch full-screen 5s / tag on icon / push). */
export const REACTION_EMOTION = '__emotion__';

const reactions = [
  { icon: '💜', label: 'Send emotion', dataReaction: REACTION_EMOTION },
  { icon: '❤️', label: 'Love', dataReaction: '❤️' },
  { icon: '😊', label: 'Happy', dataReaction: '😊' },
  { icon: '😘', label: 'Kiss', dataReaction: '😘' },
  { icon: '🤗', label: 'Hug', dataReaction: '🤗' },
  { icon: '👍', label: 'Thumbs Up', dataReaction: '👍' },
  { icon: '💪', label: 'Strong', dataReaction: '💪' },
  { icon: '🎉', label: 'Celebrate', dataReaction: '🎉' },
  { icon: '🌹', label: 'Rose', dataReaction: '🌹' },
];

export const ReactionMenu: React.FC<ReactionMenuProps> = ({ target, position, onReaction, onClose }) => {
  const [activeReaction, setActiveReaction] = useState<string | null>(null);

  useEffect(() => {
    if (!target || !position) return;

    const handleGlobalMove = (e: PointerEvent) => {
      const el = document.elementFromPoint(e.clientX, e.clientY);
      const reactionBtn = el?.closest('[data-reaction]');
      if (reactionBtn) {
        const reaction = reactionBtn.getAttribute('data-reaction');
        setActiveReaction(reaction);
      } else {
        setActiveReaction(null);
      }
    };

    const handleGlobalUp = (e: PointerEvent) => {
      const el = document.elementFromPoint(e.clientX, e.clientY);
      const reactionBtn = el?.closest('[data-reaction]');
      const reaction = reactionBtn?.getAttribute('data-reaction');
      
      if (reaction) {
        onReaction(reaction);
      } else {
        onClose();
      }
      
      setActiveReaction(null);
      document.body.style.overflow = '';
    };

    window.addEventListener('pointermove', handleGlobalMove);
    window.addEventListener('pointerup', handleGlobalUp);
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('pointermove', handleGlobalMove);
      window.removeEventListener('pointerup', handleGlobalUp);
      document.body.style.overflow = '';
    };
  }, [target, position, onReaction, onClose]);

  if (!target || !position) return null;

  const MENU_WIDTH = 290;
  const SCREEN_MARGIN = 16;
  const screenW = typeof window !== 'undefined' ? window.innerWidth : 1000;
  
  let left = position.x;
  let transform = 'translate(-50%, -100%)';

  if (left - MENU_WIDTH / 2 < SCREEN_MARGIN) {
    left = SCREEN_MARGIN;
    transform = 'translate(0, -100%)';
  } else if (left + MENU_WIDTH / 2 > screenW - SCREEN_MARGIN) {
    left = screenW - SCREEN_MARGIN;
    transform = 'translate(-100%, -100%)';
  }

  return (
    <div className="fixed inset-0 z-50 pointer-events-none">
      <div 
        className="absolute pointer-events-auto"
        style={{ 
          left: left, 
          top: position.y - 12,
          transform: transform,
          width: 'max-content'
        }}
      >
        <div className="flex items-center gap-2 p-2 bg-white rounded-full border-2 border-slate-900 shadow-xl animate-fade-in">
          {reactions.map((r, i) => (
            <div 
              key={i} 
              data-reaction={r.dataReaction}
              onClick={() => onReaction(r.dataReaction)}
              className={`
                w-12 h-12 flex flex-col items-center justify-center rounded-full transition-all duration-200 cursor-pointer
                ${activeReaction === r.dataReaction ? 'bg-indigo-100 scale-125 border-2 border-indigo-500 z-10 shadow-lg' : 'bg-transparent hover:bg-slate-50 border border-transparent'}
              `}
            >
              <span className="text-2xl">{r.icon}</span>
              {activeReaction === r.dataReaction && (
                <span className="absolute -top-8 bg-slate-900 text-white text-[10px] font-bold px-2 py-1 rounded whitespace-nowrap border border-slate-700">
                  {r.label}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
