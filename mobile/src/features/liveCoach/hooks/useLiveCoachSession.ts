import { useRef, useCallback } from 'react';
import { UserProfile } from '../../../types';
import { connectLiveCoach, AnalysisData } from '../../../../services/geminiService';

interface LiveCoachCallbacks {
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Error) => void;
  onAnalysis?: (data: AnalysisData) => void;
  onAudioData?: (buffer: AudioBuffer) => void;
}

interface LiveSession {
  sendAudio: (data: Float32Array) => void;
  disconnect: () => void;
}

export const useLiveCoachSession = (
  user: UserProfile,
  callbacks: LiveCoachCallbacks = {}
) => {
  const sessionRef = useRef<LiveSession | null>(null);
  const outputAudioContextRef = useRef<AudioContext | null>(null);
  const nextStartTimeRef = useRef(0);

  const connect = useCallback(async () => {
    try {
      // Setup output audio context for playback
      const outputCtx = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 24000,
      });
      outputAudioContextRef.current = outputCtx;
      nextStartTimeRef.current = 0;

      const session = await connectLiveCoach(user, {
        onOpen: () => {
          callbacks.onOpen?.();
        },
        onClose: () => {
          callbacks.onClose?.();
        },
        onError: (err) => {
          callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
        },
        onAnalysis: (data) => {
          callbacks.onAnalysis?.(data);
        },
        onAudioData: (buffer) => {
          if (!outputAudioContextRef.current || outputAudioContextRef.current.state === 'closed') {
            return;
          }

          const ctx = outputAudioContextRef.current;
          const src = ctx.createBufferSource();
          src.buffer = buffer;
          src.connect(ctx.destination);

          const currentTime = ctx.currentTime;
          if (nextStartTimeRef.current < currentTime) {
            nextStartTimeRef.current = currentTime;
          }
          src.start(nextStartTimeRef.current);
          nextStartTimeRef.current += buffer.duration;

          callbacks.onAudioData?.(buffer);
        },
      });

      sessionRef.current = session;
      return session;
    } catch (error) {
      const err = error instanceof Error ? error : new Error('Failed to connect to live coach');
      callbacks.onError?.(err);
      throw err;
    }
  }, [user, callbacks]);

  const disconnect = useCallback(() => {
    if (sessionRef.current) {
      sessionRef.current.disconnect();
      sessionRef.current = null;
    }
    if (outputAudioContextRef.current) {
      if (outputAudioContextRef.current.state !== 'closed') {
        outputAudioContextRef.current.close().catch(console.error);
      }
      outputAudioContextRef.current = null;
    }
    nextStartTimeRef.current = 0;
  }, []);

  const sendAudio = useCallback((data: Float32Array) => {
    if (sessionRef.current) {
      sessionRef.current.sendAudio(data);
    }
  }, []);

  return {
    connect,
    disconnect,
    sendAudio,
    isConnected: sessionRef.current !== null,
  };
};
