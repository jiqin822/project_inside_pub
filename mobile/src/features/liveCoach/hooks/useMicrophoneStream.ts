import { useState, useRef, useCallback } from 'react';
import { getMicrophoneStream } from '../../shared/utils/mediaDevices';

interface UseMicrophoneStreamOptions {
  onStreamReady?: (stream: MediaStream) => void;
  onError?: (error: Error) => void;
}

export const useMicrophoneStream = (options: UseMicrophoneStreamOptions = {}) => {
  const [hasPermission, setHasPermission] = useState(false);
  const [isActive, setIsActive] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);

  const requestPermission = useCallback(async () => {
    try {
      const stream = await getMicrophoneStream({ audio: true });
      streamRef.current = stream;
      setHasPermission(true);
      options.onStreamReady?.(stream);
      return stream;
    } catch (error) {
      const err = error instanceof Error ? error : new Error('Failed to access microphone');
      setHasPermission(false);
      options.onError?.(err);
      throw err;
    }
  }, [options]);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    setIsActive(false);
    setHasPermission(false);
  }, []);

  const startStream = useCallback(async () => {
    if (!streamRef.current) {
      await requestPermission();
    }
    setIsActive(true);
  }, [requestPermission]);

  return {
    stream: streamRef.current,
    hasPermission,
    isActive,
    requestPermission,
    startStream,
    stopStream,
  };
};
