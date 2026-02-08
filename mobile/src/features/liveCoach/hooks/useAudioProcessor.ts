import { useRef, useCallback } from 'react';

interface UseAudioProcessorOptions {
  sampleRate?: number;
  bufferSize?: number;
  onAudioData: (data: Float32Array) => void;
  onVisualize?: (data: Float32Array) => void;
}

export const useAudioProcessor = (options: UseAudioProcessorOptions) => {
  const {
    sampleRate = 16000,
    bufferSize = 4096,
    onAudioData,
    onVisualize,
  } = options;

  const audioContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  const setupProcessor = useCallback(async (stream: MediaStream) => {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate });
    audioContextRef.current = ctx;

    const source = ctx.createMediaStreamSource(stream);
    sourceRef.current = source;

    // Note: ScriptProcessorNode is deprecated but still widely supported
    // Consider migrating to AudioWorkletNode in the future
    const processor = ctx.createScriptProcessor(bufferSize, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e) => {
      const inputData = e.inputBuffer.getChannelData(0);
      onAudioData(inputData);
      onVisualize?.(inputData);
    };

    source.connect(processor);
    processor.connect(ctx.destination);

    return { audioContext: ctx, processor, source };
  }, [sampleRate, bufferSize, onAudioData, onVisualize]);

  const cleanup = useCallback(() => {
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (audioContextRef.current) {
      if (audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close().catch(console.error);
      }
      audioContextRef.current = null;
    }
  }, []);

  return {
    setupProcessor,
    cleanup,
    audioContext: audioContextRef.current,
  };
};
