import React, { useState, useEffect } from 'react';
import { Mail, Lock, ArrowRight, ShieldCheck, Ruler, Fingerprint, UserPlus, LogIn } from 'lucide-react';
import { apiService } from '../services/apiService';

interface Props {
  onLogin: (email: string) => void;
  onSignup: (email: string) => void;
  inviteToken?: string | null;
  inviteEmail?: string | null;
  inviteRelationshipType?: string | null;
  inviterName?: string | null;
}

export const AuthScreen: React.FC<Props> = ({ 
  onLogin, 
  onSignup, 
  inviteToken, 
  inviteEmail,
  inviteRelationshipType,
  inviterName
}) => {
  // Check URL for token on mount (in case it wasn't passed as prop)
  const getTokenFromURL = () => {
    if (typeof window !== 'undefined') {
      const urlParams = new URLSearchParams(window.location.search);
      return urlParams.get('token');
    }
    return null;
  };

  const urlToken = getTokenFromURL();
  const effectiveToken = inviteToken || urlToken;
  
  const [isLogin, setIsLogin] = useState(!effectiveToken); // If invite token exists, start in signup mode
  const [email, setEmail] = useState(inviteEmail || '');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [localInviteEmail, setLocalInviteEmail] = useState(inviteEmail || '');
  const [localRelationshipType, setLocalRelationshipType] = useState(inviteRelationshipType || '');
  const [localInviterName, setLocalInviterName] = useState(inviterName || '');
  const [showDevCredentials, setShowDevCredentials] = useState(false);

  /** Demo family credentials (dev/QA only). See docs/FAMILY_DEMO_CREDENTIALS.md */
  const DEMO_ACCOUNTS = [
    { email: 'marcus.rivera@demo.inside.app', password: 'DemoFamily2025!', displayName: 'Marcus Rivera', label: 'Marcus' },
    { email: 'priya.rivera@demo.inside.app', password: 'DemoFamily2025!', displayName: 'Priya Rivera', label: 'Priya' },
    { email: 'sam.rivera@demo.inside.app', password: 'DemoFamily2025!', displayName: 'Sam Rivera', label: 'Sam' },
  ] as const;

  const fillDevCredentials = (account: typeof DEMO_ACCOUNTS[number]) => {
    setEmail(account.email);
    setPassword(account.password);
    setDisplayName(account.displayName);
    setConfirmPassword(account.password);
    setError(null);
  };

  // Update isLogin when inviteToken changes
  useEffect(() => {
    if (effectiveToken) {
      setIsLogin(false); // Switch to signup mode if token exists
    }
  }, [effectiveToken]);

  // Update local state when props change (from async invite validation)
  useEffect(() => {
    if (inviteEmail) {
      setLocalInviteEmail(inviteEmail);
      setEmail(inviteEmail);
    }
  }, [inviteEmail]);

  useEffect(() => {
    if (inviteRelationshipType) {
      setLocalRelationshipType(inviteRelationshipType);
    }
  }, [inviteRelationshipType]);

  useEffect(() => {
    if (inviterName) {
      setLocalInviterName(inviterName);
    }
  }, [inviterName]);

  // If we have a token but no email yet, try to fetch it
  useEffect(() => {
    if (effectiveToken && !localInviteEmail) {
      apiService.validateInviteToken(effectiveToken)
        .then((response: any) => {
          const inviteData = response.data as { 
            email?: string; 
            relationship_type?: string;
            inviter_name?: string;
          };
          if (inviteData.email) {
            setLocalInviteEmail(inviteData.email);
            setEmail(inviteData.email);
          }
          if (inviteData.relationship_type) {
            setLocalRelationshipType(inviteData.relationship_type);
          }
          if (inviteData.inviter_name) {
            setLocalInviterName(inviteData.inviter_name);
          }
        })
        .catch((error) => {
          console.error('Failed to validate invite token:', error);
        });
    }
  }, [effectiveToken, localInviteEmail]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    
    if (!isLogin && password !== confirmPassword) {
        setError("Passkeys do not match.");
        return;
    }

    setLoading(true);

    try {
      if (isLogin) {
        // Login via backend API
        await apiService.login(email, password);
        setLoading(false);
        onLogin(email);
      } else {
        // Signup via backend API - include invite token if present
        const tokenToUse = inviteToken || urlToken;
        await apiService.signup(email, password, displayName.trim() || undefined, tokenToUse || undefined);
        setLoading(false);
        onSignup(email);
      }
    } catch (err: any) {
      setLoading(false);
      setError(err.message || (isLogin ? "Invalid credentials or user not found." : "Failed to create account."));
    }
  };

  return (
    <div className="h-screen bg-slate-50 flex flex-col items-center justify-center p-6 relative overflow-hidden font-sans text-slate-900 safe-area" style={{ height: '100vh', width: '100vw' }}>
       
       {/* Blueprint Grid Background Pattern */}
       <div className="absolute inset-0 z-0 pointer-events-none opacity-20" 
            style={{ 
                backgroundImage: 'linear-gradient(#1e293b 1px, transparent 1px), linear-gradient(90deg, #1e293b 1px, transparent 1px)', 
                backgroundSize: '20px 20px' 
            }}>
       </div>

       {/* Main Container */}
       <div className="w-full max-w-sm bg-white border-2 border-slate-900 shadow-[8px_8px_0px_rgba(30,41,59,0.2)] relative z-10 animate-fade-in flex flex-col">
          
          {/* Header Strip */}
          <div className="bg-slate-900 text-white p-4 flex justify-between items-center border-b-2 border-slate-900">
             <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest">
                <Ruler size={14} className="text-indigo-400" />
                <span>Access Control</span>
             </div>
             <button
               type="button"
               onClick={() => setShowDevCredentials((v) => !v)}
               className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded hover:bg-slate-700 hover:text-slate-300 transition-colors cursor-pointer"
               aria-label="Toggle dev credentials"
             >
                SECURE
             </button>
          </div>

          {/* Dev-only: fill demo family credentials */}
          {showDevCredentials && (
            <div className="bg-slate-800/90 border-b border-slate-600 px-4 py-2 flex flex-wrap gap-2 items-center">
              <span className="text-[9px] font-mono text-slate-500 uppercase tracking-widest mr-1">Dev fill:</span>
              {DEMO_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => fillDevCredentials(account)}
                  className="text-[10px] font-mono font-bold text-slate-300 bg-slate-700 hover:bg-indigo-600 hover:text-white px-2 py-1 rounded border border-slate-600 hover:border-indigo-500 transition-colors"
                >
                  {account.label}
                </button>
              ))}
            </div>
          )}

          <div className="p-8">
            <div className="mb-8">
                <h1 className="text-3xl font-black text-slate-900 uppercase tracking-tighter mb-1 leading-none">
                    {isLogin ? 'Welcome Back' : effectiveToken ? 'Accept Invitation' : 'Join Us Inside'}
                </h1>
                <p className="text-xs font-mono text-slate-500 mt-2">
                    {isLogin ? '// PLEASE AUTHENTICATE' : effectiveToken ? '// YOU\'VE BEEN INVITED' : '// INITIALIZE ACCOUNT'}
                </p>
                {effectiveToken && !isLogin && (
                    <div className="mt-3 space-y-1">
                        {localInviterName && (
                            <p className="text-xs font-mono text-indigo-600 font-bold">
                                {localInviterName} has invited you
                            </p>
                        )}
                        {localRelationshipType && (
                            <p className="text-xs font-mono text-slate-600">
                                Relationship: <span className="font-bold uppercase">{localRelationshipType}</span>
                            </p>
                        )}
                        <p className="text-xs font-mono text-slate-500 mt-2">
                            Sign up to accept the invitation and connect.
                        </p>
                    </div>
                )}
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                        Identity (Email)
                    </label>
                    <div className="relative">
                        <input 
                            type="email" 
                            required
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            className="w-full bg-slate-50 border-2 border-slate-200 p-3 pl-10 text-sm font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none placeholder:text-slate-300"
                            placeholder="USER@DOMAIN.COM"
                            disabled={effectiveToken && !!localInviteEmail} // Disable if email is pre-filled from invite
                        />
                        <Mail className="absolute left-3 top-3 text-slate-400" size={16} />
                    </div>
                    {effectiveToken && localInviteEmail && email === localInviteEmail && (
                        <p className="text-[10px] font-mono text-slate-400 mt-1">
                            Email pre-filled from invitation
                        </p>
                    )}
                </div>

                {!isLogin && (
                    <div>
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                            Display Name
                        </label>
                        <div className="relative">
                            <input 
                                type="text" 
                                value={displayName}
                                onChange={(e) => setDisplayName(e.target.value)}
                                className="w-full bg-slate-50 border-2 border-slate-200 p-3 pl-10 text-sm font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none placeholder:text-slate-300"
                                placeholder="Your Name"
                            />
                            <UserPlus className="absolute left-3 top-3 text-slate-400" size={16} />
                        </div>
                        <p className="text-[10px] font-mono text-slate-400 mt-1">
                            How others will see you
                        </p>
                    </div>
                )}

                <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                        Passkey
                    </label>
                    <div className="relative">
                        <input 
                            type="password" 
                            required
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full bg-slate-50 border-2 border-slate-200 p-3 pl-10 text-sm font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none placeholder:text-slate-300"
                            placeholder="••••••••"
                        />
                        <Lock className="absolute left-3 top-3 text-slate-400" size={16} />
                    </div>
                </div>

                {!isLogin && (
                    <div>
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                            Confirm Passkey
                        </label>
                        <div className="relative">
                            <input 
                                type="password" 
                                required
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                className="w-full bg-slate-50 border-2 border-slate-200 p-3 pl-10 text-sm font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none placeholder:text-slate-300"
                                placeholder="••••••••"
                            />
                            <Lock className="absolute left-3 top-3 text-slate-400" size={16} />
                        </div>
                    </div>
                )}

                {error && (
                    <div className="p-3 bg-red-50 border-l-4 border-red-500 text-red-600 text-xs font-bold animate-slide-in-down">
                        ERROR: {error}
                    </div>
                )}

                <button 
                    type="submit"
                    disabled={loading}
                    className="w-full bg-slate-900 hover:bg-slate-800 disabled:opacity-70 text-white font-bold text-sm uppercase tracking-widest py-4 flex items-center justify-center gap-2 transition-all shadow-lg active:translate-y-0.5 active:shadow-none mt-6"
                >
                    {loading ? 'Processing...' : isLogin ? (
                        <>Unlock Dashboard <ArrowRight size={16} /></>
                    ) : (
                        <>Initialize Setup <Fingerprint size={16} /></>
                    )}
                </button>
            </form>

            <div className="mt-6 pt-6 border-t border-slate-100 flex justify-center">
                <button 
                    onClick={() => { setIsLogin(!isLogin); setError(null); setConfirmPassword(''); setDisplayName(''); }}
                    className="text-xs font-bold text-slate-400 hover:text-indigo-600 uppercase tracking-widest flex items-center gap-2 transition-colors"
                >
                    {isLogin ? (
                        <><UserPlus size={14} /> Request Access</>
                    ) : (
                        <><LogIn size={14} /> Already Registered?</>
                    )}
                </button>
            </div>
          </div>
       </div>

       {/* Footer Branding */}
       <div className="absolute bottom-6 flex flex-col items-center gap-1 opacity-50">
           <div className="flex items-center gap-2 text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">
               <ShieldCheck size={12} />
               <span>Inside Secure Gateway</span>
           </div>
       </div>
    </div>
  );
};
