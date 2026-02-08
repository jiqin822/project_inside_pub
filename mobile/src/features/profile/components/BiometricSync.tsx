import React, { useState, useRef } from 'react';
import { Mic, Info, X, CheckCircle, AlertCircle } from 'lucide-react';
import { apiService } from '../../../shared/api/apiService';
import { getMicrophoneStream } from '../../../shared/utils/mediaDevices';

interface Props {
  onComplete: (voicePrintId: string) => void;
  onSkip?: () => void;
  onCancel?: () => void;
  allowSkip?: boolean; // Whether to show skip button
  context?: 'onboarding' | 'profile' | 'dialogue_deck'; // Context for different messaging
}

// Helper Icon component for the Quote box
const MessageCircle = ({ size, strokeWidth }: { size: number, strokeWidth: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

export const BiometricSync: React.FC<Props> = ({ 
  onComplete, 
  onSkip, 
  onCancel,
  allowSkip = true,
  context = 'onboarding'
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingProgress, setRecordingProgress] = useState(0);
  const [qualityScore, setQualityScore] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const enrollmentIdRef = useRef<string | null>(null);

  const convertToWav = async (audioBlob: Blob): Promise<Blob> => {
    // Create audio context with 16kHz sample rate
    const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 16000 });
    
    // Decode the recorded audio (webm/ogg format)
    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    
    // Resample to 16kHz if needed
    let targetSampleRate = 16000;
    let sourceSampleRate = audioBuffer.sampleRate;
    let resampledBuffer = audioBuffer;
    
    if (sourceSampleRate !== targetSampleRate) {
      // Simple resampling: create new buffer and copy samples
      const ratio = sourceSampleRate / targetSampleRate;
      const newLength = Math.floor(audioBuffer.length / ratio);
      resampledBuffer = audioContext.createBuffer(
        audioBuffer.numberOfChannels,
        newLength,
        targetSampleRate
      );
      
      for (let channel = 0; channel < audioBuffer.numberOfChannels; channel++) {
        const sourceData = audioBuffer.getChannelData(channel);
        const targetData = resampledBuffer.getChannelData(channel);
        for (let i = 0; i < newLength; i++) {
          const sourceIndex = Math.floor(i * ratio);
          targetData[i] = sourceData[sourceIndex];
        }
      }
    }
    
    // Convert to WAV format
    const numChannels = resampledBuffer.numberOfChannels;
    const numSamples = resampledBuffer.length;
    const wavBuffer = new ArrayBuffer(44 + numSamples * numChannels * 2);
    const view = new DataView(wavBuffer);
    
    // WAV header helper
    const writeString = (offset: number, string: string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };
    
    // Write WAV header
    writeString(0, 'RIFF');
    view.setUint32(4, 36 + numSamples * numChannels * 2, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, 1, true); // audio format (1 = PCM)
    view.setUint16(22, numChannels, true);
    view.setUint32(24, targetSampleRate, true);
    view.setUint32(28, targetSampleRate * numChannels * 2, true); // byte rate
    view.setUint16(32, numChannels * 2, true); // block align
    view.setUint16(34, 16, true); // bits per sample
    writeString(36, 'data');
    view.setUint32(40, numSamples * numChannels * 2, true);
    
    // Convert audio data to 16-bit PCM
    let offset = 44;
    for (let i = 0; i < numSamples; i++) {
      for (let channel = 0; channel < numChannels; channel++) {
        const sample = Math.max(-1, Math.min(1, resampledBuffer.getChannelData(channel)[i]));
        view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7FFF, true);
        offset += 2;
      }
    }
    
    return new Blob([wavBuffer], { type: 'audio/wav' });
  };

  const handleVoicePrint = async () => {
    try {
      setError(null);
      setIsRecording(true);
      audioChunksRef.current = [];

      // Request microphone access (requires HTTPS on iOS)
      const stream = await getMicrophoneStream({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      // Start enrollment session
      const enrollmentResponse = await apiService.startVoiceEnrollment();
      enrollmentIdRef.current = enrollmentResponse.data.enrollment_id;

      // Create MediaRecorder
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
      });
      mediaRecorderRef.current = mediaRecorder;

      // Collect audio chunks
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      // Handle recording stop
      mediaRecorder.onstop = async () => {
        setIsRecording(false);
        setIsProcessing(true);
        
        // Stop progress bar
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }

        try {
          // Combine audio chunks
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
          if (audioChunksRef.current.length === 0 || audioBlob.size === 0) {
            setError('No audio recorded. Please try again and speak for a few seconds.');
            setIsProcessing(false);
            if (streamRef.current) {
              streamRef.current.getTracks().forEach(track => track.stop());
              streamRef.current = null;
            }
            return;
          }

          // Convert to WAV format
          const wavBlob = await convertToWav(audioBlob);
          
          // Upload audio
          await apiService.uploadEnrollmentAudio(enrollmentIdRef.current!, wavBlob);
          
          // Complete enrollment and get quality score
          const completeResponse = await apiService.completeVoiceEnrollment(enrollmentIdRef.current!);
          const quality = completeResponse.data.quality_score;
          setQualityScore(quality);
          
          // Call onComplete with voice profile ID
          setTimeout(() => {
            onComplete(completeResponse.data.voice_profile_id);
          }, 2000);
        } catch (err: any) {
          console.error('Voice enrollment error:', err);
          setError(err.message || 'Failed to process voice recording');
          setIsProcessing(false);
        } finally {
          // Cleanup
          if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
          }
        }
      };

      // Start recording
      mediaRecorder.start();
      
      // Start progress bar
      let progress = 0;
      progressIntervalRef.current = setInterval(() => {
        progress += 1.5;
        setRecordingProgress(progress);
        if (progress >= 100) {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
          }
          mediaRecorder.stop();
        }
      }, 100); // 10 seconds total

    } catch (err: any) {
      console.error('Failed to start recording:', err);
      setError(err.message || 'Failed to access microphone');
      setIsRecording(false);
      setIsProcessing(false);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
    }
  };

  const getContextMessage = () => {
    switch (context) {
      case 'profile':
        return '// RE-RECORD VOICE PRINT';
      case 'dialogue_deck':
        return '// REQUIRED: SETUP VOICE PRINT';
      default:
        return '// OPTIONAL: REQ. FOR LIVE COACHING';
    }
  };

  const getInfoText = () => {
    switch (context) {
      case 'profile':
        return 'Voice data is used exclusively for the Real-time Conversation Coaching mode to identify you during conflict resolution.';
      case 'dialogue_deck':
        return 'Voice print is required to use Dialogue Deck. Your voice data is used exclusively for the Real-time Conversation Coaching mode to identify you during conflict resolution.';
      default:
        return 'Voice data is used exclusively for the Real-time Conversation Coaching mode to identify you during conflict resolution.';
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/90 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in safe-area">
      <div className="bg-white border-2 border-slate-900 shadow-[8px_8px_0px_rgba(30,41,59,0.3)] w-full max-w-md rounded-lg p-8 space-y-6 text-center relative">
        {/* Close button (only if onCancel provided) */}
        {onCancel && (
          <button
            onClick={onCancel}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center border border-slate-300 hover:border-slate-900 text-slate-400 hover:text-slate-900 transition-colors"
          >
            <X size={20} />
          </button>
        )}

        <div>
          <h1 className="text-2xl font-black text-slate-900 uppercase tracking-tighter mb-1">
            Biometric Sync
          </h1>
          <p className="text-xs font-mono text-slate-500">
            {getContextMessage()}
          </p>
        </div>
        
        <div className="bg-slate-50 border-2 border-dashed border-slate-300 p-6 relative overflow-hidden group">
          <div className="absolute top-2 left-2 text-[10px] font-mono text-slate-400">REF: SCRIPT-01</div>
          <p className="font-serif italic text-lg text-slate-800 leading-relaxed relative z-10">
            "Communication is the bridge between confusion and clarity."
          </p>
          <div className="absolute bottom-2 right-2 text-slate-200">
            <MessageCircle size={40} strokeWidth={1} />
          </div>
        </div>

        <div className="flex flex-col items-center justify-center gap-4">
          {isRecording || isProcessing ? (
            <div className="w-full space-y-2">
              <div className="h-12 bg-slate-900 relative overflow-hidden flex items-center justify-center border-2 border-slate-900">
                <span className="relative z-10 text-white text-xs font-mono font-bold uppercase tracking-widest animate-pulse">
                  {isProcessing ? 'Processing...' : 'Recording...'}
                </span>
                {isRecording && (
                  <div 
                    className="absolute left-0 top-0 bottom-0 bg-indigo-600 transition-all duration-75 ease-linear opacity-50"
                    style={{ width: `${recordingProgress}%` }}
                  />
                )}
              </div>
              {isRecording && (
                <p className="text-[10px] font-mono text-slate-400">DO NOT CLOSE WINDOW</p>
              )}
            </div>
          ) : qualityScore !== null ? (
            <div className="w-full space-y-4">
              <div className={`w-20 h-20 rounded-full mx-auto flex items-center justify-center ${
                qualityScore >= 0.7 ? 'bg-green-500/20 text-green-600' : 
                qualityScore >= 0.5 ? 'bg-yellow-500/20 text-yellow-600' : 
                'bg-red-500/20 text-red-600'
              }`}>
                {qualityScore >= 0.7 ? <CheckCircle size={40} /> : <AlertCircle size={40} />}
              </div>
              <div className="text-center">
                <p className="text-sm font-bold text-slate-900 mb-1">Voice Quality Score</p>
                <p className={`text-2xl font-black ${
                  qualityScore >= 0.7 ? 'text-green-600' : 
                  qualityScore >= 0.5 ? 'text-yellow-600' : 
                  'text-red-600'
                }`}>
                  {(qualityScore * 100).toFixed(0)}%
                </p>
                <p className="text-xs text-slate-500 mt-2">
                  {qualityScore >= 0.7 ? 'Excellent quality!' : 
                   qualityScore >= 0.5 ? 'Good quality' : 
                   'Low quality - try recording again in a quieter environment'}
                </p>
              </div>
            </div>
          ) : error ? (
            <div className="w-full space-y-2">
              <div className="w-20 h-20 rounded-full mx-auto bg-red-500/20 text-red-600 flex items-center justify-center">
                <AlertCircle size={40} />
              </div>
              <p className="text-sm text-red-600 text-center">{error}</p>
              <button
                onClick={handleVoicePrint}
                className="w-full bg-rose-600 hover:bg-rose-500 text-white font-bold py-2 px-4 rounded transition-colors"
              >
                Try Again
              </button>
            </div>
          ) : (
            <button 
              onClick={handleVoicePrint}
              className="w-20 h-20 rounded-full bg-rose-600 hover:bg-rose-50 border-4 border-slate-100 shadow-[0_0_0_4px_#e11d48] flex items-center justify-center text-white transition-transform hover:scale-105 active:scale-95"
            >
              <Mic size={32} />
            </button>
          )}
        </div>
        
        {!isRecording && !isProcessing && qualityScore === null && !error && (
          <>
            <p className="text-[10px] font-mono text-slate-400 uppercase tracking-widest">
              Tap to begin calibration
            </p>

            <div className="bg-indigo-50 border border-indigo-100 p-3 text-left flex items-start gap-2 mt-4">
              <Info size={14} className="text-indigo-500 shrink-0 mt-0.5" />
              <p className="text-[10px] text-indigo-900 font-medium leading-relaxed">
                <strong>NOTE:</strong> {getInfoText()}
              </p>
            </div>

            {allowSkip && onSkip && (
              <button 
                onClick={onSkip}
                className="text-xs font-bold text-slate-400 hover:text-slate-600 uppercase tracking-widest border-b border-transparent hover:border-slate-400 transition-all pb-0.5"
              >
                Skip Calibration &gt;&gt;
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
};
