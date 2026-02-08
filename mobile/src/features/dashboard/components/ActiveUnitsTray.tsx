import React from 'react';
import { Plus, Heart, CircleDashed } from 'lucide-react';
import { LovedOne } from '../../../shared/types/domain';
import { useRealtimeStore, type EmotionTag } from '../../../stores/realtime.store';
import { useLongPress } from '../../../shared/hooks/useLongPress';

interface ActiveUnitsTrayProps {
  lovedOnes: LovedOne[];
  currentUserId: string;
  onAddUnit: () => void;
  onLongPress: (person: LovedOne, position: { x: number; y: number }) => void;
  onSelect?: (person: LovedOne) => void;
  /** When an invited (pending) unit is clicked, call this to show the invite link. */
  onInviteLinkRequest?: (person: LovedOne) => void;
}

const getBubbleStyle = (rel: string, name: string, isPending?: boolean) => {
  const lowerRel = rel.toLowerCase();
  const initial = name.charAt(0).toUpperCase();
  
  if (isPending) {
    return { 
      bg: 'bg-slate-300', 
      text: 'text-slate-500', 
      border: 'border-dashed border-2 border-slate-400', 
      initial: '⏳',
      opacity: 'opacity-60'
    };
  }
  
  if (lowerRel.includes('partner') || lowerRel.includes('spouse')) {
    return { bg: 'bg-rose-500', text: 'text-white', border: 'border-rose-600', initial, opacity: '' };
  }
  if (lowerRel.includes('child') || lowerRel.includes('kid')) {
    return { bg: 'bg-blue-500', text: 'text-white', border: 'border-blue-600', initial, opacity: '' };
  }
  return { bg: 'bg-slate-600', text: 'text-white', border: 'border-slate-700', initial, opacity: '' };
};

/** Single tray unit – uses useLongPress so hooks are called once per instance (rules of hooks). */
const TrayUnit: React.FC<{
  person: LovedOne;
  receivedEmoji: { emoji: string; timestamp: number } | undefined;
  receivedEmotion: EmotionTag | undefined;
  onLongPress: (person: LovedOne, position: { x: number; y: number }) => void;
  onSelect?: (person: LovedOne) => void;
  onInviteLinkRequest?: (person: LovedOne) => void;
}> = ({ person, receivedEmoji, receivedEmotion, onLongPress, onSelect, onInviteLinkRequest }) => {
  const handleClick = () => {
    if (person.isPending && onInviteLinkRequest) {
      onInviteLinkRequest(person);
    } else {
      onSelect?.(person);
    }
  };
  const longPressHandlers = useLongPress({
    onLongPress: (e) => {
      const x = e.clientX ?? (e as React.TouchEvent).touches?.[0]?.clientX ?? 0;
      const y = e.clientY ?? (e as React.TouchEvent).touches?.[0]?.clientY ?? 0;
      onLongPress(person, { x, y });
    },
    onClick: handleClick,
    delay: 500,
  });
  const style = getBubbleStyle(person.relationship, person.name, person.isPending);
  const emojiAge = receivedEmoji ? Date.now() - receivedEmoji.timestamp : 0;
  const shouldAnimate = receivedEmoji && emojiAge < 30000;
  const emotionAge = receivedEmotion ? Date.now() - receivedEmotion.timestamp : 0;
  const showEmotion = receivedEmotion && emotionAge < 15000;

  return (
    <button
      {...longPressHandlers}
      onContextMenu={(e) => e.preventDefault()}
      className="group relative flex flex-col items-center gap-1 shrink-0 transition-transform active:scale-95 touch-none"
      title={person.isPending ? `${person.name} – Tap to get invite link` : `${person.name} (Hold to React)`}
      aria-label={`${person.name}, ${person.relationship}${person.isPending ? ' – Pending invite' : ''}`}
    >
      <div
        className={`relative w-10 h-10 ${
          person.profilePicture ? 'bg-white' : style.bg
        } ${person.profilePicture ? '' : style.text} ${style.border} ${style.opacity || ''} flex items-center justify-center font-bold text-sm shadow-[2px_2px_0px_rgba(30,41,59,0.1)] group-hover:shadow-[3px_3px_0px_rgba(30,41,59,0.2)] transition-all ${
          person.isPending ? 'border-dashed' : 'border-2'
        } overflow-hidden`}
      >
        {person.isPending ? (
          <>
            <span className="text-base leading-none">⏳</span>
            <div className="absolute -bottom-0.5 -right-0.5 w-4 h-4 bg-slate-100 border border-slate-400 rounded-full flex items-center justify-center" title="Pending – tap for invite link">
              <CircleDashed className="w-2.5 h-2.5 text-slate-600" strokeWidth={2.5} />
            </div>
          </>
        ) : person.profilePicture ? (
          <img src={person.profilePicture} alt={person.name} className="w-full h-full object-cover" />
        ) : (
          style.initial
        )}
        {receivedEmoji && (
          <div
            className={`absolute -bottom-1 -right-1 w-5 h-5 bg-white border-2 border-slate-900 rounded-full flex items-center justify-center text-xs shadow-lg z-20 ${
              shouldAnimate ? 'animate-bounce' : ''
            }`}
          >
            {receivedEmoji.emoji}
          </div>
        )}
        {showEmotion && (
          <div
            className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-rose-500 rounded-full flex items-center justify-center shadow-lg z-20"
            title={receivedEmotion.emotionKind ? `${receivedEmotion.senderName} sent ${receivedEmotion.emotionKind}` : `${receivedEmotion.senderName} sent love`}
          >
            <Heart className="w-2.5 h-2.5 text-white fill-white" />
          </div>
        )}
      </div>
    </button>
  );
};

export const ActiveUnitsTray: React.FC<ActiveUnitsTrayProps> = ({
  lovedOnes,
  currentUserId,
  onAddUnit,
  onLongPress,
  onSelect,
  onInviteLinkRequest,
}) => {
  const { receivedEmojisByUserId, receivedEmotionByUserId } = useRealtimeStore();

  const filteredLovedOnes = lovedOnes.filter(person => person.id !== currentUserId);

  return (
    <div className="w-full bg-white bg-opacity-100 border-b-2 border-slate-200 px-6 py-3 flex items-center gap-3 overflow-x-hidden no-scrollbar z-10 shadow-lg shrink-0">
      <div className="flex flex-col justify-center border-r-2 border-slate-200 pr-4 mr-1 shrink-0">
        <span className="text-[9px] font-mono font-bold text-slate-500 uppercase tracking-widest leading-none">Active</span>
        <span className="text-[9px] font-mono font-bold text-slate-300 uppercase tracking-widest leading-none">Units</span>
      </div>
      
      {filteredLovedOnes.map((person) => (
        <TrayUnit
          key={person.id}
          person={person}
          receivedEmoji={receivedEmojisByUserId[person.id]}
          receivedEmotion={receivedEmotionByUserId[person.id]}
          onLongPress={onLongPress}
          onSelect={onSelect}
          onInviteLinkRequest={onInviteLinkRequest}
        />
      ))}
      
      <button
        onClick={onAddUnit}
        className="w-10 h-10 border-2 border-dashed border-slate-300 flex items-center justify-center text-slate-300 hover:border-slate-500 hover:text-slate-500 transition-colors shrink-0 bg-white"
        title="Add Unit"
        aria-label="Add relationship"
      >
        <Plus size={16} />
      </button>
    </div>
  );
};
