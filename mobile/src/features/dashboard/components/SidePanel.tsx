import React from 'react';
import { X, Sliders, Bell, Zap, Eye, LogOut } from 'lucide-react';
import { useSessionStore } from '../../../stores/session.store';

interface SidePanelProps {
  isOpen: boolean;
  onClose: () => void;
  onLogout: () => void;
  preferences: {
    notifications: boolean;
    hapticFeedback: boolean;
    privacyMode: boolean;
  };
  onTogglePreference: (key: 'notifications' | 'hapticFeedback' | 'privacyMode') => void;
}

export const SidePanel: React.FC<SidePanelProps> = ({
  isOpen,
  onClose,
  onLogout,
  preferences,
  onTogglePreference,
}) => {
  const { me: user } = useSessionStore();
  
  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-slate-900 text-white shadow-2xl transform transition-transform duration-300 ease-in-out z-50 flex flex-col">
      <div className="p-6 border-b border-slate-700 flex justify-between items-center bg-slate-950">
        <div>
          <h2 className="font-mono text-sm font-bold text-slate-400 uppercase tracking-widest mb-1">Specification</h2>
          <h3 className="text-xl font-bold">System Config</h3>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-white">
          <X size={24} />
        </button>
      </div>
      
      <div className="p-6 border-b border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-white text-slate-900 rounded-lg flex items-center justify-center font-bold text-xl border-2 border-slate-400">
            {user?.name.charAt(0)}
          </div>
          <div>
            <div className="text-xs font-mono text-slate-500 uppercase">Project Lead</div>
            <div className="font-bold">{user?.name}</div>
          </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-hidden relative" style={{ minHeight: 0, overflowY: 'auto' }}>
        <div className="p-4 bg-slate-800/50 border-b border-slate-700">
          <h3 className="font-bold text-slate-400 flex items-center gap-2 text-xs uppercase tracking-widest">
            <Sliders size={14} /> Global Preferences
          </h3>
        </div>
        <div className="divide-y divide-slate-800">
          <div className="p-4 flex items-center justify-between hover:bg-slate-800 transition-colors">
            <div className="flex items-center gap-3">
              <Bell size={18} className="text-slate-400" />
              <div>
                <p className="text-sm font-bold text-white uppercase">Smart Nudges</p>
                <p className="text-[10px] text-slate-500 font-mono">Wearable Alerts</p>
              </div>
            </div>
            <button 
              onClick={() => onTogglePreference('notifications')} 
              className={`w-10 h-5 transition-colors relative border-2 ${
                preferences.notifications ? 'bg-green-500 border-green-600' : 'bg-slate-700 border-slate-600'
              }`}
            >
              <div className={`w-3 h-3 bg-white shadow-sm absolute top-0.5 transition-all ${
                preferences.notifications ? 'left-5' : 'left-0.5'
              }`} />
            </button>
          </div>
          
          <div className="p-4 flex items-center justify-between hover:bg-slate-800 transition-colors">
            <div className="flex items-center gap-3">
              <Zap size={18} className="text-slate-400" />
              <div>
                <p className="text-sm font-bold text-white uppercase">Haptics</p>
                <p className="text-[10px] text-slate-500 font-mono">Tactile Feedback</p>
              </div>
            </div>
            <button 
              onClick={() => onTogglePreference('hapticFeedback')} 
              className={`w-10 h-5 transition-colors relative border-2 ${
                preferences.hapticFeedback ? 'bg-green-500 border-green-600' : 'bg-slate-700 border-slate-600'
              }`}
            >
              <div className={`w-3 h-3 bg-white shadow-sm absolute top-0.5 transition-all ${
                preferences.hapticFeedback ? 'left-5' : 'left-0.5'
              }`} />
            </button>
          </div>
          
          <div className="p-4 flex items-center justify-between hover:bg-slate-800 transition-colors">
            <div className="flex items-center gap-3">
              <Eye size={18} className="text-slate-400" />
              <div>
                <p className="text-sm font-bold text-white uppercase">Stealth Mode</p>
                <p className="text-[10px] text-slate-500 font-mono">Mask Dashboard</p>
              </div>
            </div>
            <button 
              onClick={() => onTogglePreference('privacyMode')} 
              className={`w-10 h-5 transition-colors relative border-2 ${
                preferences.privacyMode ? 'bg-green-500 border-green-600' : 'bg-slate-700 border-slate-600'
              }`}
            >
              <div className={`w-3 h-3 bg-white shadow-sm absolute top-0.5 transition-all ${
                preferences.privacyMode ? 'left-5' : 'left-0.5'
              }`} />
            </button>
          </div>
        </div>
        <div className="p-6 text-center mt-4">
          <p className="text-[9px] font-mono text-slate-500 mb-2 uppercase">Inside.OS v1.2.0</p>
        </div>
      </div>
      
      <div className="p-6 border-t border-slate-800 bg-slate-950 space-y-3">
        <button 
          onClick={onLogout} 
          className="w-full py-3 text-rose-500 hover:text-white hover:bg-rose-900 transition-all text-xs font-mono uppercase tracking-widest flex items-center justify-center gap-2 border border-dashed border-rose-900/30 hover:border-rose-500"
        >
          <LogOut size={14} /> System Logout
        </button>
      </div>
    </div>
  );
};
