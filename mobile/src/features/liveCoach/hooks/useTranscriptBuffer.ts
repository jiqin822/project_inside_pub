import { useState, useCallback, useRef } from 'react';

export interface TranscriptItem {
  id: string;
  speaker: string;
  text: string;
  sentiment: string;
  horseman: string;
  timestamp: number;
  speakerColor?: string;
}

interface UseTranscriptBufferOptions {
  maxItems?: number;
  autoScroll?: boolean;
}

export const useTranscriptBuffer = (options: UseTranscriptBufferOptions = {}) => {
  const { maxItems = 200, autoScroll = true } = options;
  const [transcripts, setTranscripts] = useState<TranscriptItem[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const addTranscript = useCallback((item: Omit<TranscriptItem, 'id' | 'timestamp'>) => {
    setTranscripts(prev => {
      const newItem: TranscriptItem = {
        ...item,
        id: Date.now().toString(),
        timestamp: Date.now(),
      };
      const updated = [...prev, newItem];
      // Keep only last maxItems
      return updated.slice(-maxItems);
    });

    // Auto-scroll to bottom
    if (autoScroll && scrollRef.current) {
      setTimeout(() => {
        scrollRef.current?.scrollTo({
          top: scrollRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }, 100);
    }
  }, [maxItems, autoScroll]);

  const clearTranscripts = useCallback(() => {
    setTranscripts([]);
  }, []);

  const trimTranscripts = useCallback((keepLast: number) => {
    setTranscripts(prev => prev.slice(-keepLast));
  }, []);

  return {
    transcripts,
    addTranscript,
    clearTranscripts,
    trimTranscripts,
    scrollRef,
  };
};
