import React from 'react';
import { TranscriptItem } from '../hooks/useTranscriptBuffer';

interface TranscriptViewProps {
  transcripts: TranscriptItem[];
  scrollRef: React.RefObject<HTMLDivElement>;
  currentUser: string;
  partnerName?: string;
}

// Color mapping for speakers
const getSpeakerColor = (
  speaker: string,
  currentUser: string,
  partnerName?: string,
  speakerColor?: string
): string => {
  if (speakerColor) {
    if (speakerColor === 'self') return 'text-blue-700 bg-blue-50';
    if (speakerColor === 'partner') return 'text-pink-700 bg-pink-50';
    if (speakerColor === 'unknown') return 'text-slate-700 bg-slate-50';
    return 'text-slate-700 bg-slate-50';
  }
  if (speaker === currentUser) return 'text-blue-700 bg-blue-50';
  if (speaker === partnerName || speaker === 'Partner') return 'text-pink-700 bg-pink-50';
  return 'text-slate-700 bg-slate-50';
};

export const TranscriptView: React.FC<TranscriptViewProps> = ({
  transcripts,
  scrollRef,
  currentUser,
  partnerName,
}) => {
  const visibleTranscripts = transcripts.filter(
    (item) => (item.text ?? '').trim().length > 0
  );
  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-4 space-y-2 bg-slate-50"
      style={{ maxHeight: '400px' }}
    >
      {visibleTranscripts.length === 0 ? (
        <div className="text-center py-8 text-slate-400">
          <p className="text-xs font-mono uppercase">No transcript yet</p>
          <p className="text-[10px] font-mono text-slate-300 mt-2">Start speaking to see transcript</p>
        </div>
      ) : (
        visibleTranscripts.map((item) => {
          const colorClass = getSpeakerColor(
            item.speaker,
            currentUser,
            partnerName,
            item.speakerColor
          );
          return (
            <div
              key={item.id}
              className={`p-3 rounded-lg border-2 ${colorClass} border-opacity-30`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold uppercase">{item.speaker}</span>
                <span className="text-[10px] text-slate-500 font-mono">
                  {new Date(item.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-sm leading-relaxed">{item.text}</p>
              {item.sentiment && item.sentiment !== 'Neutral' && (
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[10px] text-slate-500">Sentiment:</span>
                  <span className="text-xs font-bold">{item.sentiment}</span>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );
};
