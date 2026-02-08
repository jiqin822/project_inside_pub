
import React, { useState, useEffect } from 'react';
import { UserProfile, LovedOne } from '../../../shared/types/domain';
import { Mic, Check, ArrowRight, Plus, Trash2, Users, Heart, Ruler, Fingerprint, ShieldCheck, Activity, BrainCircuit, Info, Image as ImageIcon, X, Loader2 } from 'lucide-react';
import { AvatarPicker } from '../components/AvatarPicker';
import { MBTISliders } from '../components/MBTISliders';
import { BiometricSync } from '../../profile/components/BiometricSync';
import { apiService } from '../../../shared/api/apiService';
import { Capacitor } from '@capacitor/core';

interface Props {
  onComplete: (profile: UserProfile) => void;
}

export const OnboardingWizard: React.FC<Props> = ({ onComplete }) => {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  
  // New Profile Fields
  const [gender, setGender] = useState('Prefer not to say');
  const [personalityMBTI, setPersonalityMBTI] = useState({
    ei: 50, // Introvert (0) vs Extrovert (100)
    sn: 50, // Sensing (0) vs Intuitive (100)
    tf: 50, // Thinking (0) vs Feeling (100)
    jp: 50, // Judging (0) vs Perceiving (100)
  });
  const [preferNotToSayMBTI, setPreferNotToSayMBTI] = useState(false);
  const [birthday, setBirthday] = useState(''); // Optional, ISO YYYY-MM-DD
  const [occupation, setOccupation] = useState('');
  const [description, setDescription] = useState('');
  const [interests, setInterests] = useState('');

  // Loved Ones State
  const [lovedOnes, setLovedOnes] = useState<LovedOne[]>([]);
  const [newEmail, setNewEmail] = useState('');
  const [newRel, setNewRel] = useState('Partner');
  const [isAddingLovedOne, setIsAddingLovedOne] = useState(false);
  const [showShareLink, setShowShareLink] = useState(false);
  const [shareLinkUrl, setShareLinkUrl] = useState<string>('');
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  // Voice Print State
  const [voiceRecorded, setVoiceRecorded] = useState(false);

  // Profile Picture State
  const [profilePicture, setProfilePicture] = useState<string | null>(null);
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);

  // Get current user ID and name on mount
  useEffect(() => {
    const fetchCurrentUser = async () => {
      try {
        const token = apiService.getAccessToken();
        if (token) {
          const response = await apiService.getCurrentUser();
          const userData = response.data as { 
            id: string; 
            display_name?: string;
            email?: string;
          };
          setCurrentUserId(userData.id);
          // Set name from backend if available, otherwise use email prefix
          if (userData.display_name) {
            setName(userData.display_name);
          } else if (userData.email) {
            setName(userData.email.split('@')[0]);
          }
        }
      } catch (error) {
        console.warn('Could not fetch current user during onboarding:', error);
      }
    };
    fetchCurrentUser();
  }, []);

  // Map relationship type to backend format
  const mapRelationshipTypeToBackend = (relType: string): string => {
    const lower = relType.toLowerCase();
    if (lower.includes('partner') || lower.includes('spouse')) return 'romantic';
    if (lower === 'date') return 'date';
    if (lower.includes('child')) return 'parent_child';
    if (lower.includes('parent')) return 'parent_child';
    if (lower.includes('sibling')) return 'sibling';
    if (lower.includes('friend')) return 'friend';
    if (lower.includes('colleague')) return 'colleague';
    return 'friend';
  };

  const addLovedOne = async () => {
    if (!newEmail.trim()) {
      return;
    }

    // Check if user is authenticated
    const token = apiService.getAccessToken();
    if (!token || !currentUserId) {
      // Fallback: add as local-only entry (will be synced later)
      const emailName = newEmail.trim().split('@')[0] || 'Pending User';
      setLovedOnes([...lovedOnes, {
        id: Date.now().toString(),
        name: emailName,
        relationship: newRel,
        isPending: true,
      }]);
      setNewEmail('');
      setNewRel('Friend');
      return;
    }

    setIsAddingLovedOne(true);

    try {
      // Lookup contact by email
      const lookupResponse = await apiService.lookupContact(newEmail.trim());
      const lookupData = lookupResponse.data as {
        status: string;
        user?: { id: string; display_name?: string; email?: string };
      };

      if (lookupData.status === 'EXISTS' && lookupData.user) {
        // User exists - check if relationship already exists first
        try {
          const existingRelationships = await apiService.getRelationships();
          const relationships = (existingRelationships.data as any[]) || [];
          
          // Check if user is already in a relationship with current user
          let existingRelationship = null;
          for (const rel of relationships) {
            try {
              const consentResponse = await apiService.getConsentInfo(rel.id);
              const consentData = consentResponse.data as {
                members?: Array<{ user_id: string }>;
              };
              const members = (consentData.members || []) as Array<{ user_id: string }>;
              const hasUser = members.some(m => m.user_id === lookupData.user!.id);
              if (hasUser) {
                existingRelationship = rel;
                break;
              }
            } catch (error) {
              // Skip if we can't check this relationship
              continue;
            }
          }
          
          if (existingRelationship) {
            // Relationship already exists - add to loved ones list using existing relationship
            const lovedOneName = lookupData.user.display_name 
              || lookupData.user.email?.split('@')[0] 
              || newEmail.trim().split('@')[0];

            const existingPerson: LovedOne = {
              id: lookupData.user.id,
              name: lovedOneName,
              relationship: newRel,
              relationshipId: existingRelationship.id,
              isPending: false,
            };

            setLovedOnes([...lovedOnes, existingPerson]);
            setNewEmail('');
            setNewRel('Friend');
            setIsAddingLovedOne(false);
            return;
          }
          
          // No existing relationship - create new one
          const relationshipType = mapRelationshipTypeToBackend(newRel);
          const createResponse = await apiService.createRelationship(
            relationshipType,
            [lookupData.user.id]
          );
          const relationshipId = (createResponse.data as { id: string }).id;

          // Use the user's display name from backend, fallback to email prefix
          const lovedOneName = lookupData.user.display_name 
            || lookupData.user.email?.split('@')[0] 
            || newEmail.trim().split('@')[0];

          // Add to loved ones list
          const newPerson: LovedOne = {
            id: lookupData.user.id,
            name: lovedOneName,
            relationship: newRel,
            relationshipId: relationshipId,
            isPending: false,
          };

          setLovedOnes([...lovedOnes, newPerson]);
          setNewEmail('');
          setNewRel('Friend');
          setIsAddingLovedOne(false);
        } catch (createError: any) {
          // If relationship creation fails, don't fall back to invite flow
          console.error('Failed to create relationship:', createError);
          setIsAddingLovedOne(false);
          // Could show error toast here
          alert(`Failed to add ${lookupData.user.display_name || newEmail.trim()}: ${createError.message || 'Relationship creation failed'}`);
        }
      } else if (lookupData.status === 'NOT_FOUND') {
        // User doesn't exist - create invite and show share interface
        try {
          // Create a draft relationship
          const relationshipType = mapRelationshipTypeToBackend(newRel);
          const createResponse = await apiService.createRelationship(
            relationshipType,
            [] // Empty array - will add creator automatically
          );
          const relationshipId = (createResponse.data as { id: string }).id;

          // Create invite and get invitation link
          const inviteResponse = await apiService.createInvite(
            relationshipId,
            newEmail.trim(),
            newRel.toLowerCase()
          );

          const inviteData = inviteResponse.data as { invite_url?: string; invite_id: string };
          const inviteUrl = inviteData.invite_url;

          if (!inviteUrl) {
            throw new Error('Invitation URL not returned from server');
          }

          // Use email prefix as name for pending entry
          const emailName = newEmail.trim().split('@')[0] || 'Pending User';

          // Add pending loved one
          const pendingPerson: LovedOne = {
            id: Date.now().toString(), // Temporary ID
            name: emailName,
            relationship: newRel,
            relationshipId: relationshipId,
            isPending: true,
            pendingEmail: newEmail.trim(),
          };

          setLovedOnes([...lovedOnes, pendingPerson]);

          // Check if we're on a native platform
          const isNative = Capacitor.isNativePlatform();

          if (isNative) {
            // Use native share interface on mobile devices
            try {
              const { Share } = await import('@capacitor/share');
              await Share.share({
                title: `Join my ${newRel} relationship on Project Inside`,
                text: `${name || 'Someone'} has invited you to connect with them as their ${newRel} on Project Inside.\n\nAccept the invitation: ${inviteUrl}`,
                url: inviteUrl,
                dialogTitle: 'Share Invitation',
              });
            } catch (shareError: any) {
              console.error('Failed to share invite:', shareError);
              // Fallback: show the link modal
              setShareLinkUrl(inviteUrl);
              setShowShareLink(true);
            }
          } else {
            // On web, show the link in a modal for copying
            setShareLinkUrl(inviteUrl);
            setShowShareLink(true);
          }

          setNewEmail('');
          setNewRel('Friend');
          setIsAddingLovedOne(false);
        } catch (inviteError: any) {
          console.error('Failed to create invite:', inviteError);
          setIsAddingLovedOne(false);
          // Still add as pending locally
          const emailName = newEmail.trim().split('@')[0] || 'Pending User';
          setLovedOnes([...lovedOnes, {
            id: Date.now().toString(),
            name: emailName,
            relationship: newRel,
            isPending: true,
          }]);
          setNewEmail('');
          setNewRel('Friend');
        }
      } else if (lookupData.status === 'BLOCKED') {
        setIsAddingLovedOne(false);
        // Could show error toast here if needed
      }
    } catch (lookupError: any) {
      console.error('Contact lookup failed:', lookupError);
      setIsAddingLovedOne(false);
      // Fallback: add as pending locally
      const emailName = newEmail.trim().split('@')[0] || 'Pending User';
      setLovedOnes([...lovedOnes, {
        id: Date.now().toString(),
        name: emailName,
        relationship: newRel,
        isPending: true,
      }]);
      setNewEmail('');
      setNewRel('Friend');
    }
  };

  const removeLovedOne = async (id: string) => {
    const lovedOneToRemove = lovedOnes.find(l => l.id === id);
    if (!lovedOneToRemove) return;
    
    // Remove from local state immediately for responsive UI
    setLovedOnes(lovedOnes.filter(l => l.id !== id));
    
    // If there's a relationshipId, delete it from backend
    if (lovedOneToRemove.relationshipId && currentUserId) {
      try {
        await apiService.deleteRelationship(lovedOneToRemove.relationshipId);
        console.log(`[DEBUG] Deleted relationship ${lovedOneToRemove.relationshipId} from backend`);
      } catch (error) {
        console.error(`[ERROR] Failed to delete relationship ${lovedOneToRemove.relationshipId}:`, error);
        // Re-add to local state if backend deletion failed
        setLovedOnes([...lovedOnes.filter(l => l.id !== id), lovedOneToRemove]);
      }
    }
  };

  const handleVoicePrintComplete = (voicePrintId: string) => {
    setVoiceRecorded(true);
    setTimeout(() => setStep(5), 500);
  };

  const handleSkipVoice = () => {
    setVoiceRecorded(false);
    setStep(5);
  };

  const handleFinish = async () => {
    // Infer/Simulate attachment stats for demo
    const anxietyScore = 35; 
    const avoidanceScore = 25;
    const inferredStyle = 'secure'; 

    // Find primary partner name if exists
    const partner = lovedOnes.find(l => l.relationship.toLowerCase().includes('partner') || l.relationship.toLowerCase().includes('spouse') || l.relationship.toLowerCase().includes('wife') || l.relationship.toLowerCase().includes('husband'));

    // Use actual backend user ID if available, otherwise fallback to UUID
    let userId = currentUserId || crypto.randomUUID();
    
    // If we don't have the backend ID yet, try to fetch it
    if (!currentUserId) {
      try {
        const token = apiService.getAccessToken();
        if (token) {
          const response = await apiService.getCurrentUser();
          const userData = response.data as { id: string };
          userId = userData.id;
        }
      } catch (error) {
        console.warn('Could not fetch current user ID during onboarding completion:', error);
      }
    }

    onComplete({
      id: userId,
      name,
      partnerName: partner?.name,
      gender,
      birthday: birthday.trim() || undefined,
      occupation: occupation.trim() || undefined,
      personalDescription: description,
      interests: interests.split(',').map(i => i.trim()).filter(Boolean),
      lovedOnes: lovedOnes,
      attachmentStyle: inferredStyle,
      attachmentStats: {
          anxiety: anxietyScore,
          avoidance: avoidanceScore
      },
      // Only set ID if they actually recorded
      voicePrintId: voiceRecorded ? 'vp_' + Date.now() : undefined,
      personalityType: preferNotToSayMBTI ? 'Prefer not to say' : (() => {
        const ei = personalityMBTI.ei >= 50 ? 'E' : 'I';
        const sn = personalityMBTI.sn >= 50 ? 'N' : 'S';
        const tf = personalityMBTI.tf >= 50 ? 'F' : 'T';
        const jp = personalityMBTI.jp >= 50 ? 'P' : 'J';
        return `${ei}${sn}${tf}${jp}`;
      })(),
      personalityMBTIValues: preferNotToSayMBTI ? undefined : personalityMBTI,
      profilePicture: profilePicture || undefined,
    });
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
       <div className="absolute inset-0 z-0 pointer-events-none opacity-10" 
            style={{ 
                backgroundImage: 'linear-gradient(#1e293b 2px, transparent 2px), linear-gradient(90deg, #1e293b 2px, transparent 2px)', 
                backgroundSize: '100px 100px' 
            }}>
       </div>

       {/* Main Container */}
       <div className="w-full max-w-md bg-white border-2 border-slate-900 shadow-[8px_8px_0px_rgba(30,41,59,0.2)] relative z-10 animate-fade-in flex flex-col max-h-[90vh]">
          
          {/* Header Strip */}
          <div className="bg-slate-900 text-white p-4 flex justify-between items-center border-b-2 border-slate-900 shrink-0">
             <div className="flex items-center gap-2 text-xs font-mono font-bold uppercase tracking-widest">
                <Ruler size={14} className="text-indigo-400" />
                <span>System Initialization</span>
             </div>
             <div className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded">
                SEQ: 0{step} / 05
             </div>
          </div>

          <div className="p-8 overflow-hidden" style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
          
          {/* STEP 1: Basic Info */}
          {step === 1 && (
            <div className="space-y-6 animate-slide-in-down">
              <div>
                  <h1 className="text-2xl font-black text-slate-900 uppercase tracking-tighter mb-1">
                    Identity Config
                  </h1>
                  <p className="text-xs font-mono text-slate-500">
                    // ENTER PRIMARY USER DETAILS
                  </p>
              </div>

              <div className="space-y-4">
                {/* Profile Picture Selection */}
                <div className="flex flex-col items-center mb-4">
                  <div className="relative">
                    <div className={`w-20 h-20 border-4 border-slate-900 flex items-center justify-center font-bold text-3xl shadow-[4px_4px_0px_rgba(30,41,59,0.2)] ${
                      profilePicture 
                        ? 'bg-white' 
                        : 'bg-indigo-100 text-indigo-700'
                    }`}>
                      {profilePicture ? (
                        <img 
                          src={profilePicture} 
                          alt="Profile" 
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        name.charAt(0).toUpperCase() || '?'
                      )}
                    </div>
                    <button
                      onClick={() => setShowAvatarPicker(true)}
                      className="absolute -bottom-1 -right-1 w-7 h-7 bg-indigo-600 hover:bg-indigo-700 text-white border-2 border-slate-900 flex items-center justify-center shadow-lg transition-colors"
                      title="Choose Avatar"
                    >
                      <ImageIcon size={12} />
                    </button>
                  </div>
                  <p className="text-[9px] font-mono text-slate-500 mt-2 uppercase">Profile Picture</p>
                </div>

                <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                        Gender
                    </label>
                    <div className="relative">
                        <select 
                            value={gender} 
                            onChange={(e) => setGender(e.target.value)}
                            className="w-full appearance-none bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none"
                        >
                            <option value="Prefer not to say">PREFER NOT TO SAY</option>
                            <option value="Male">MALE</option>
                            <option value="Female">FEMALE</option>
                            <option value="Non-binary">NON-BINARY</option>
                            <option value="Other">OTHER</option>
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
                            <ArrowRight size={14} className="rotate-90" />
                        </div>
                    </div>
                </div>

                <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                        Birthday <span className="font-normal text-slate-400">(optional)</span>
                    </label>
                    <input
                        type="date"
                        value={birthday}
                        onChange={(e) => setBirthday(e.target.value)}
                        className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none"
                    />
                </div>

                <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                        Occupation <span className="font-normal text-slate-400">(optional)</span>
                    </label>
                    <input
                        type="text"
                        value={occupation}
                        onChange={(e) => setOccupation(e.target.value)}
                        placeholder="e.g. Software Engineer, Teacher"
                        className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none placeholder:text-slate-300"
                    />
                </div>

                <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                        Personal Description
                    </label>
                    <textarea 
                        value={description} 
                        onChange={(e) => setDescription(e.target.value)}
                        className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none placeholder:text-slate-300 min-h-[80px]"
                        placeholder="Briefly describe yourself..."
                    />
                </div>

                <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                        Interests
                    </label>
                    <input 
                        type="text" 
                        value={interests} 
                        onChange={(e) => setInterests(e.target.value)}
                        className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none placeholder:text-slate-300"
                        placeholder="Cooking, Hiking, Sci-Fi (Comma separated)"
                    />
                </div>
                
                <div className="pt-4">
                    <button 
                    onClick={() => setStep(2)}
                    disabled={!name}
                    className="w-full bg-slate-900 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm uppercase tracking-widest py-4 flex items-center justify-center gap-2 transition-all shadow-lg active:translate-y-0.5 active:shadow-none"
                    >
                    Initialize Setup <ArrowRight size={16} />
                    </button>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Personality (MBTI) only */}
          {step === 2 && (
            <div className="space-y-6 animate-slide-in-down">
              <div>
                <h1 className="text-2xl font-black text-slate-900 uppercase tracking-tighter mb-1">
                  Personality (MBTI)
                </h1>
                <p className="text-xs font-mono text-slate-500 mb-4">
                  // CONFIGURE PERSONALITY DIMENSIONS
                </p>
                {preferNotToSayMBTI ? (
                  <div className="bg-slate-50 border-2 border-slate-200 p-4 text-center">
                    <p className="text-sm font-bold text-slate-600 uppercase">Prefer Not to Say</p>
                    <button
                      onClick={() => setPreferNotToSayMBTI(false)}
                      className="mt-2 text-xs font-bold text-indigo-600 hover:text-indigo-800 uppercase tracking-widest border-b border-transparent hover:border-indigo-600 transition-all"
                    >
                      Change My Mind
                    </button>
                  </div>
                ) : (
                  <>
                    <div className="bg-slate-50 border-2 border-slate-200 p-4">
                      <MBTISliders
                        values={personalityMBTI}
                        onChange={(dimension, value) => {
                          setPersonalityMBTI(prev => ({ ...prev, [dimension]: value }));
                        }}
                      />
                    </div>
                    <button
                      onClick={() => setPreferNotToSayMBTI(true)}
                      className="w-full mt-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors"
                    >
                      Prefer Not to Say
                    </button>
                  </>
                )}
              </div>
              <button
                onClick={() => setStep(3)}
                className="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm uppercase tracking-widest py-4 flex items-center justify-center gap-2 transition-all shadow-lg active:translate-y-0.5 active:shadow-none"
              >
                Proceed <ArrowRight size={16} />
              </button>
            </div>
          )}

          {/* STEP 3: Add Relationships (Team Roster) */}
          {step === 3 && (
            <div className="space-y-6 animate-slide-in-down">
              <div className="flex justify-between items-start">
                <div>
                  <h1 className="text-2xl font-black text-slate-900 uppercase tracking-tighter mb-1">
                    Team Roster
                  </h1>
                  <p className="text-xs font-mono text-slate-500">
                    // ASSIGN RELATIONSHIP NODES
                  </p>
                </div>
                <Users size={32} className="text-slate-200" />
              </div>

              {/* List */}
              <div className="space-y-2 border-2 border-slate-100 bg-slate-50 p-2 min-h-[120px] max-h-48 overflow-y-auto">
                {lovedOnes.length === 0 && (
                   <div className="h-full flex flex-col items-center justify-center text-slate-400 py-6">
                      <span className="text-[10px] font-mono uppercase">No personnel assigned</span>
                   </div>
                )}
                {lovedOnes.map(person => (
                  <div key={person.id} className={`flex items-center justify-between bg-white p-2 border shadow-sm group ${person.isPending ? 'border-dashed border-slate-300 opacity-60' : 'border-slate-200'}`}>
                    <div className="flex items-center gap-3">
                       <div className={`w-8 h-8 flex items-center justify-center text-xs font-bold border ${person.isPending ? 'bg-slate-300 text-slate-500 border-dashed border-slate-400' : 'bg-slate-900 text-white border-slate-900'}`}>
                         {person.isPending ? '⏳' : person.name.charAt(0)}
                       </div>
                       <div>
                         <p className="font-bold text-xs uppercase text-slate-900 leading-none">{person.name}</p>
                         <p className="text-[10px] font-mono text-slate-500 uppercase">{person.relationship} {person.isPending && '(Pending)'}</p>
                       </div>
                    </div>
                    <button onClick={() => removeLovedOne(person.id)} className="text-slate-300 hover:text-red-500 p-2 transition-colors">
                       <Trash2 size={14} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Input */}
              <div className="bg-slate-100 p-3 border border-slate-200 space-y-3">
                  <div className="grid grid-cols-5 gap-2">
                      <input 
                        type="email"
                        value={newEmail}
                        onChange={(e) => setNewEmail(e.target.value)}
                        placeholder="EMAIL"
                        className="col-span-3 bg-white border border-slate-300 p-2 text-xs font-bold uppercase placeholder:text-slate-300 focus:outline-none focus:border-indigo-500"
                        onKeyDown={(e) => e.key === 'Enter' && !isAddingLovedOne && addLovedOne()}
                        disabled={isAddingLovedOne}
                      />
                      <select
                        value={newRel}
                        onChange={(e) => setNewRel(e.target.value)}
                        className="col-span-2 bg-white border border-slate-300 p-2 text-[10px] font-bold uppercase focus:outline-none focus:border-indigo-500"
                        disabled={isAddingLovedOne}
                      >
                         <option value="Partner">Partner</option>
                         <option value="Date">Date</option>
                         <option value="Spouse">Spouse</option>
                         <option value="Child">Child</option>
                         <option value="Parent">Parent</option>
                         <option value="Friend">Friend</option>
                         <option value="Sibling">Sibling</option>
                         <option value="Colleague">Colleague</option>
                      </select>
                  </div>
                  <button 
                    onClick={addLovedOne}
                    disabled={!newEmail.trim() || isAddingLovedOne}
                    className="w-full bg-white border-2 border-slate-900 hover:bg-slate-50 disabled:opacity-50 text-slate-900 text-[10px] font-bold uppercase tracking-widest py-2 flex items-center justify-center gap-2 transition-colors"
                  >
                    {isAddingLovedOne ? (
                      <>
                        <Loader2 size={12} className="animate-spin" /> Checking...
                      </>
                    ) : (
                      <>
                        <Plus size={12} /> Add Entry
                      </>
                    )}
                  </button>
              </div>

              <button
                onClick={() => setStep(4)}
                className="w-full bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold text-sm uppercase tracking-widest py-4 flex items-center justify-center gap-2 transition-all shadow-lg active:translate-y-0.5 active:shadow-none"
              >
                Proceed <ArrowRight size={16} />
              </button>
            </div>
          )}

          {/* STEP 4: Voice Print */}
          {step === 4 && (
            <BiometricSync
              context="onboarding"
              onComplete={handleVoicePrintComplete}
              onSkip={handleSkipVoice}
              allowSkip={true}
            />
          )}

          {/* STEP 5: Complete */}
          {step === 5 && (
            <div className="space-y-8 animate-slide-in-down text-center py-4">
               <div className="w-24 h-24 bg-emerald-50 text-emerald-600 border-4 border-emerald-100 rounded-full mx-auto flex items-center justify-center mb-4 relative">
                 <div className="absolute inset-0 border-2 border-emerald-500 rounded-full animate-ping opacity-20"></div>
                 <Check size={48} strokeWidth={3} />
               </div>
               
               <div>
                <h1 className="text-2xl font-black text-slate-900 uppercase tracking-tighter mb-2">
                    System Ready
                </h1>
                <p className="text-xs font-mono text-slate-500 max-w-[200px] mx-auto uppercase">
                    // PROFILE CONFIGURED<br/>
                    // BIOMETRICS: {voiceRecorded ? 'SECURED' : 'BYPASSED'}<br/>
                    // DASHBOARD UNLOCKED
                </p>
               </div>

               <div className="pt-4">
                <button 
                    onClick={handleFinish}
                    className="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm uppercase tracking-widest py-4 flex items-center justify-center gap-2 transition-all shadow-lg active:translate-y-0.5 active:shadow-none"
                    >
                    Enter Dashboard <ArrowRight size={16} />
                </button>
               </div>
            </div>
          )}

          </div>
       </div>

       {/* Footer Branding */}
       <div className="absolute bottom-6 flex flex-col items-center gap-1 opacity-50">
           <div className="flex items-center gap-2 text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">
               <ShieldCheck size={12} />
               <span>Secure Relational Operating System</span>
           </div>
           <div className="text-[8px] font-mono text-slate-300">v1.0.4-beta</div>
       </div>

       {/* Avatar Picker Modal */}
       {showAvatarPicker && (
         <AvatarPicker
           currentAvatar={profilePicture || undefined}
           onSelect={(avatarPath) => {
             setProfilePicture(avatarPath);
             setShowAvatarPicker(false);
           }}
           onClose={() => setShowAvatarPicker(false)}
         />
       )}

       {/* Share Link Modal */}
       {showShareLink && (
         <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
           <div className="bg-white w-full max-w-md border-2 border-slate-900 p-6 shadow-[8px_8px_0px_rgba(15,23,42,1)] relative animate-slide-in-down">
             <button 
               onClick={() => { setShowShareLink(false); setShareLinkUrl(''); }} 
               className="absolute top-4 right-4 text-slate-400 hover:text-slate-900"
             >
               <X size={20} />
             </button>
             <div className="mb-6">
               <h3 className="font-black text-slate-900 text-lg uppercase tracking-tight mb-2">Share Invitation</h3>
               <p className="text-xs font-mono text-slate-500 mb-4">
                 {name && `${name} has invited you to connect with them on Project Inside.`}
               </p>
               <p className="text-xs font-mono text-slate-600 mb-4">
                 Copy this link and share it with the person you want to invite:
               </p>
               <div className="space-y-2">
                 <label className="block text-[10px] font-bold text-slate-700 uppercase tracking-widest">Invitation Link</label>
                 <div className="flex gap-2">
                   <input 
                     type="text" 
                     value={shareLinkUrl} 
                     readOnly
                     className="flex-1 bg-slate-50 border border-slate-300 p-2 text-xs font-mono text-slate-700 focus:outline-none focus:border-indigo-500"
                   />
                   <button 
                     onClick={async () => {
                       try {
                         await navigator.clipboard.writeText(shareLinkUrl);
                         // Could show toast here if needed
                       } catch (err) {
                         // Fallback for older browsers
                         const textArea = document.createElement('textarea');
                         textArea.value = shareLinkUrl;
                         textArea.style.position = 'fixed';
                         textArea.style.opacity = '0';
                         document.body.appendChild(textArea);
                         textArea.select();
                         try {
                           document.execCommand('copy');
                         } catch (fallbackErr) {
                           console.error('Failed to copy link');
                         }
                         document.body.removeChild(textArea);
                       }
                     }}
                     className="bg-white border-2 border-slate-900 hover:bg-slate-50 text-slate-900 text-[10px] font-bold uppercase tracking-widest px-4 py-2 transition-colors whitespace-nowrap"
                   >
                     Copy
                   </button>
                 </div>
               </div>
             </div>
             <div className="flex gap-3">
               <button 
                 onClick={() => { setShowShareLink(false); setShareLinkUrl(''); }}
                 className="flex-1 bg-white border-2 border-slate-900 hover:bg-slate-50 text-slate-900 text-xs font-bold uppercase tracking-widest py-3 transition-colors"
               >
                 Done
               </button>
             </div>
           </div>
         </div>
       )}
    </div>
  );
};
