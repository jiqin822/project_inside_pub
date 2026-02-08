import React, { useState, useEffect } from 'react';
import { Mic, Lock, CheckCircle, AlertCircle, ShieldCheck } from 'lucide-react';
import { verifyVoicePrint } from '../../../shared/services/geminiService';

interface Props {
  onAuthenticated: () => void;
  onCancel: () => void;
  isSetup?: boolean; // If true, this is for setting up voice print, not verification
  onSetupComplete?: (voicePrintId: string) => void; // Callback when setup is complete
}

export const VoiceAuth: React.FC<Props> = ({ onAuthenticated, onCancel, isSetup = false, onSetupComplete }) => {
  const [state, setState] = useState<'idle' | 'recording' | 'verifying' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const startRecording = () => {
    setState('recording');
    // Simulate recording duration
    setTimeout(() => {
      setState('verifying');
      if (isSetup) {
        handleSetup();
      } else {
        handleVerify();
      }
    }, 3000);
  };

  const handleSetup = async () => {
    try {
      // Simulate voice print setup
      // In a real implementation, this would call the voice enrollment API
      const voicePrintId = 'vp_' + Date.now();
      
      // Simulate successful setup
      setState('success');
      setTimeout(() => {
        if (onSetupComplete) {
          onSetupComplete(voicePrintId);
        }
        onAuthenticated();
      }, 1500);
    } catch (e) {
      setState('error');
      setErrorMsg("Voice print setup failed. Please try again.");
    }
  };

  const handleVerify = async () => {
    try {
      // Pass dummy data for simulation
      const success = await verifyVoicePrint('dummy_base64_audio');
      if (success) {
        setState('success');
        setTimeout(onAuthenticated, 1500);
      } else {
        throw new Error("Voice mismatch");
      }
    } catch (e) {
      setState('error');
      setErrorMsg("Voice verification failed. Please try again.");
    }
  };

  return (
    <div className="fixed inset-0 bg-slate-900/95 backdrop-blur-sm z-50 flex items-center justify-center p-6 animate-fade-in safe-area">
      <div className="bg-slate-800 border border-slate-700 w-full max-w-sm rounded-3xl p-8 flex flex-col items-center text-center shadow-2xl relative">
        <button 
          onClick={onCancel}
          className="absolute top-4 right-4 text-slate-500 hover:text-white"
        >
          ✕
        </button>

        <div className="mb-6 relative">
          <div className={`w-20 h-20 rounded-full flex items-center justify-center transition-colors duration-500 ${
            state === 'success' ? 'bg-green-500/20 text-green-400' :
            state === 'error' ? 'bg-red-500/20 text-red-400' :
            state === 'verifying' ? 'bg-indigo-500/20 text-indigo-400' :
            state === 'recording' ? 'bg-rose-500/20 text-rose-400' :
            'bg-slate-700 text-slate-400'
          }`}>
             {state === 'success' ? <CheckCircle size={40} /> :
              state === 'error' ? <AlertCircle size={40} /> :
              state === 'verifying' ? <ShieldCheck size={40} className="animate-pulse" /> :
              state === 'recording' ? <Mic size={40} className="animate-pulse" /> :
              <Lock size={32} />
             }
          </div>
          {state === 'recording' && (
             <div className="absolute inset-0 rounded-full border-2 border-rose-500 animate-ping" />
          )}
        </div>

        <h2 className="text-xl font-bold text-white mb-2">
          {isSetup 
            ? (state === 'success' ? 'Biometric Sync Complete' : 'Biometric Sync')
            : (state === 'success' ? 'Identity Verified' : 'Security Check')
          }
        </h2>
        
        <p className="text-slate-400 text-sm mb-8 h-10">
          {isSetup ? (
            <>
              {state === 'idle' && "Dialogue Deck requires voice print setup. Please record your voice to continue."}
              {state === 'recording' && "Listening... Please say: 'My voice is my password'"}
              {state === 'verifying' && "Registering your voice print..."}
              {state === 'success' && "Voice print registered successfully. You can now access Dialogue Deck."}
              {state === 'error' && errorMsg}
            </>
          ) : (
            <>
              {state === 'idle' && "This feature contains sensitive data. Please verify your voiceprint to continue."}
              {state === 'recording' && "Listening... Please say: 'My voice is my password'"}
              {state === 'verifying' && "Analyzing voice biometrics..."}
              {state === 'success' && "Voiceprint match confirmed. Access granted."}
              {state === 'error' && errorMsg}
            </>
          )}
        </p>

        {state === 'idle' || state === 'error' ? (
          <button 
            onClick={startRecording}
            className="w-full bg-rose-600 hover:bg-rose-500 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 transition-colors"
          >
            <Mic size={18} />
            {isSetup ? 'Start Setup' : 'Start Verification'}
          </button>
        ) : (
          <div className="w-full h-12 flex items-center justify-center text-slate-500 text-sm font-mono">
             {state === 'recording' ? '••• ••• •••' : 'Processing...'}
          </div>
        )}
        
        <div className="mt-6 flex items-center gap-2 text-[10px] text-slate-500">
           <ShieldCheck size={12} />
           <span>Secure Biometric Encryption</span>
        </div>
      </div>
    </div>
  );
};
