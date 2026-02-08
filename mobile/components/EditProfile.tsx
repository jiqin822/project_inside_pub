
import React, { useState, useRef } from 'react';
import { UserProfile } from '../types';
import { X, Save, ArrowRight, Fingerprint, Camera, Image as ImageIcon } from 'lucide-react';
import { apiService } from '../services/apiService';
import { AvatarPicker } from './AvatarPicker';
import { MBTISliders } from './MBTISliders';

interface Props {
  user: UserProfile;
  onBack: () => void;
  onUpdateProfile: (profile: UserProfile) => void;
}

export const EditProfile: React.FC<Props> = ({ user, onBack, onUpdateProfile }) => {
  const [name, setName] = useState(user.name);
  const [gender, setGender] = useState(user.gender || 'Prefer not to say');
  
  // Parse existing MBTI string or default to neutral values
  const parseMBTI = (mbtiString?: string, mbtiValues?: { ei: number; sn: number; tf: number; jp: number }) => {
    // Prefer stored values if available
    if (mbtiValues) {
      return mbtiValues;
    }
    // Fallback: parse from type string
    if (!mbtiString || mbtiString.length !== 4) {
      return { ei: 50, sn: 50, tf: 50, jp: 50 };
    }
    const mbti = mbtiString.toUpperCase();
    return {
      ei: mbti[0] === 'E' ? 75 : mbti[0] === 'I' ? 25 : 50,
      sn: mbti[1] === 'N' ? 75 : mbti[1] === 'S' ? 25 : 50,
      tf: mbti[2] === 'F' ? 75 : mbti[2] === 'T' ? 25 : 50,
      jp: mbti[3] === 'P' ? 75 : mbti[3] === 'J' ? 25 : 50,
    };
  };
  
  const [personalityMBTI, setPersonalityMBTI] = useState(parseMBTI(user.personalityType, user.personalityMBTIValues));
  const [description, setDescription] = useState(user.personalDescription || '');
  const [interests, setInterests] = useState(user.interests?.join(', ') || '');
  const [isDirty, setIsDirty] = useState(false);
  const [profilePicture, setProfilePicture] = useState<string | null>(user.profilePicture || null);
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleInputChange = (setter: React.Dispatch<React.SetStateAction<any>>, value: any) => {
      setter(value);
      setIsDirty(true);
  };

  const handleProfilePictureChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
          // Validate file type
          if (!file.type.startsWith('image/')) {
              alert('Please select an image file');
              return;
          }
          // Validate file size (max 5MB)
          if (file.size > 5 * 1024 * 1024) {
              alert('Image size must be less than 5MB');
              return;
          }
          // Create preview
          const reader = new FileReader();
          reader.onloadend = () => {
              setProfilePicture(reader.result as string);
              setIsDirty(true);
          };
          reader.readAsDataURL(file);
      }
  };

  const handleProfilePictureClick = () => {
      fileInputRef.current?.click();
  };

  const handleSave = async () => {
      try {
          // Convert MBTI values to JSON format
          const mbtiData = {
            type: (() => {
              const ei = personalityMBTI.ei >= 50 ? 'E' : 'I';
              const sn = personalityMBTI.sn >= 50 ? 'N' : 'S';
              const tf = personalityMBTI.tf >= 50 ? 'F' : 'T';
              const jp = personalityMBTI.jp >= 50 ? 'P' : 'J';
              return `${ei}${sn}${tf}${jp}`;
            })(),
            values: {
              ei: personalityMBTI.ei,
              sn: personalityMBTI.sn,
              tf: personalityMBTI.tf,
              jp: personalityMBTI.jp,
            }
          };

          // Update profile via backend API, including profile picture
          await apiService.updateProfile({
              display_name: name,
              pronouns: gender !== 'Prefer not to say' ? gender : undefined,
              personality_type: mbtiData,
              goals: interests.split(',').map(s => s.trim()).filter(Boolean),
              profile_picture_url: profilePicture || undefined,
          });
          
          // Refresh user data from backend
          const response = await apiService.getCurrentUser();
          const backendUser = response.data as {
            id: string;
            display_name?: string;
            pronouns?: string;
            personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
            goals?: string[];
            profile_picture_url?: string;
          };

          const updatedUser: UserProfile = {
              ...user,
              id: backendUser.id,
              name: backendUser.display_name || user.name,
              gender: backendUser.pronouns || gender,
              personalityType: backendUser.personality_type?.type || mbtiData.type,
              personalityMBTIValues: backendUser.personality_type?.values || mbtiData.values,
              interests: backendUser.goals || [],
              profilePicture: backendUser.profile_picture_url || profilePicture || user.profilePicture,
          };
          onUpdateProfile(updatedUser);
          setIsDirty(false);
          alert("Identity Configuration Updated Successfully");
      } catch (error: any) {
          alert(`Failed to update profile: ${error.message}`);
      }
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden font-sans relative animate-fade-in" style={{ height: '100vh', width: '100vw', paddingTop: 'var(--sat, 0px)' }}>
        {/* Background Grid */}
        <div className="fixed inset-0 z-0 pointer-events-none opacity-20" 
            style={{ 
                backgroundImage: 'linear-gradient(#1e293b 1px, transparent 1px), linear-gradient(90deg, #1e293b 1px, transparent 1px)', 
                backgroundSize: '20px 20px',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0
            }}>
        </div>

        {/* Header */}
        <div className="bg-white border-b-4 border-slate-900 px-4 py-4 flex items-center justify-between shrink-0 sticky top-0 z-20">
            <div className="flex items-center gap-3">
                <div>
                    <h1 className="text-sm font-black text-slate-900 uppercase tracking-widest leading-none">Config</h1>
                    <p className="text-[9px] text-slate-400 font-mono uppercase">EDIT CORE DATA</p>
                </div>
            </div>
            <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-slate-900 text-white flex items-center justify-center font-bold text-sm border-2 border-slate-900">
                    <Fingerprint size={16} />
                </div>
                <button 
                    onClick={onBack}
                    className="w-8 h-8 flex items-center justify-center border-2 border-slate-200 hover:border-slate-900 text-slate-400 hover:text-slate-900 transition-colors"
                >
                    <X size={20} />
                </button>
            </div>
        </div>

        <div className="flex-1 overflow-hidden p-4 pb-20 relative z-10" style={{ minHeight: 0, overflowY: 'auto' }}>
             <div className="bg-white border-2 border-slate-900 p-6 shadow-[4px_4px_0px_rgba(30,41,59,0.1)]">
                 <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                    <h3 className="text-xl font-black text-slate-900 uppercase tracking-tighter">Identity Config</h3>
                    <div className="text-[10px] font-mono bg-indigo-50 text-indigo-600 px-2 py-1 border border-indigo-200 uppercase">Editable</div>
                 </div>

                 <div className="space-y-4">
                    {/* Profile Picture */}
                    <div className="flex flex-col items-center mb-6">
                        <div className="relative">
                            <div className={`w-24 h-24 border-4 border-slate-900 flex items-center justify-center font-bold text-4xl shadow-[4px_4px_0px_rgba(30,41,59,0.2)] ${
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
                                    user.name.charAt(0).toUpperCase()
                                )}
                            </div>
                            <div className="absolute -bottom-2 -right-2 flex gap-1">
                                <button
                                    onClick={() => setShowAvatarPicker(true)}
                                    className="w-8 h-8 bg-indigo-600 hover:bg-indigo-700 text-white border-2 border-slate-900 flex items-center justify-center shadow-lg transition-colors"
                                    title="Choose Avatar"
                                >
                                    <ImageIcon size={14} />
                                </button>
                                <button
                                    onClick={handleProfilePictureClick}
                                    className="w-8 h-8 bg-slate-600 hover:bg-slate-700 text-white border-2 border-slate-900 flex items-center justify-center shadow-lg transition-colors"
                                    title="Upload Photo"
                                >
                                    <Camera size={14} />
                                </button>
                            </div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="image/*"
                                onChange={handleProfilePictureChange}
                                className="hidden"
                            />
                        </div>
                        <p className="text-[10px] font-mono text-slate-500 mt-2 uppercase">Profile Picture</p>
                        <div className="flex gap-2 mt-2">
                            <button
                                onClick={() => setShowAvatarPicker(true)}
                                className="text-[9px] font-bold text-indigo-600 hover:text-indigo-800 uppercase tracking-widest border-b border-transparent hover:border-indigo-600 transition-all"
                            >
                                Choose Avatar
                            </button>
                            <span className="text-[9px] text-slate-300">|</span>
                            <button
                                onClick={handleProfilePictureClick}
                                className="text-[9px] font-bold text-slate-600 hover:text-slate-800 uppercase tracking-widest border-b border-transparent hover:border-slate-600 transition-all"
                            >
                                Upload Photo
                            </button>
                        </div>
                    </div>

                    {/* Name */}
                    <div>
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                            Subject Name
                        </label>
                        <input 
                            type="text" 
                            value={name} 
                            onChange={(e) => handleInputChange(setName, e.target.value)}
                            className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-sm font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none"
                        />
                    </div>

                    {/* Gender */}
                    <div>
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                            Gender
                        </label>
                        <div className="relative">
                            <select 
                                value={gender} 
                                onChange={(e) => handleInputChange(setGender, e.target.value)}
                                className="w-full appearance-none bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none"
                            >
                                <option value="Prefer not to say">PREFER NOT TO SAY</option>
                                <option value="Male">MALE</option>
                                <option value="Female">FEMALE</option>
                                <option value="Non-binary">NON-BINARY</option>
                                <option value="Other">OTHER</option>
                            </select>
                            <ArrowRight size={14} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 rotate-90" />
                        </div>
                    </div>

                    {/* Personality (MBTI) */}
                    <div>
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-3">
                            Personality (MBTI)
                        </label>
                        <div className="bg-slate-50 border-2 border-slate-200 p-4">
                            <MBTISliders
                                values={personalityMBTI}
                                onChange={(dimension, value) => {
                                    setPersonalityMBTI(prev => ({ ...prev, [dimension]: value }));
                                    setIsDirty(true);
                                }}
                            />
                        </div>
                    </div>

                    {/* Description */}
                    <div>
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                            Personal Bio
                        </label>
                        <textarea 
                            value={description} 
                            onChange={(e) => handleInputChange(setDescription, e.target.value)}
                            className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none min-h-[100px]"
                            placeholder="Describe yourself..."
                        />
                    </div>

                     {/* Interests */}
                     <div>
                        <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">
                            Interests
                        </label>
                        <input 
                            type="text" 
                            value={interests} 
                            onChange={(e) => handleInputChange(setInterests, e.target.value)}
                            className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 focus:bg-white transition-colors rounded-none"
                            placeholder="Comma separated list"
                        />
                    </div>

                    {/* Save Button */}
                    <div className="pt-4">
                        <button 
                            onClick={handleSave}
                            disabled={!isDirty}
                            className="w-full bg-slate-900 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm uppercase tracking-widest py-4 flex items-center justify-center gap-2 transition-all shadow-lg active:translate-y-0.5 active:shadow-none"
                        >
                            <Save size={16} /> Save Configuration
                        </button>
                        {!isDirty && (
                            <p className="text-center text-[10px] font-mono text-slate-400 mt-2 uppercase">All systems nominal. No changes detected.</p>
                        )}
                    </div>
                 </div>
             </div>
        </div>

        {/* Avatar Picker Modal */}
        {showAvatarPicker && (
          <AvatarPicker
            currentAvatar={profilePicture || undefined}
            onSelect={(avatarPath) => {
              setProfilePicture(avatarPath);
              setIsDirty(true);
              setShowAvatarPicker(false);
            }}
            onClose={() => setShowAvatarPicker(false)}
          />
        )}
    </div>
  );
};
