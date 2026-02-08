import React, { useState, useRef } from 'react';
import { UserProfile, EconomyConfig } from '../types';
import { X, Settings, Mic, CheckCircle, AlertCircle, User, Info, Heart, Sparkles, Shield, TrendingUp, Users, Coins, Edit2, Save, ArrowRight, Camera } from 'lucide-react';
import { BiometricSync } from './BiometricSync';
import { MBTISliders } from './MBTISliders';
import { AvatarPicker } from './AvatarPicker';
import { apiService } from '../services/apiService';

const CURRENCY_PRESETS = [
    { name: 'Love Tokens', symbol: '🪙' },
    { name: 'Hearts', symbol: '❤️' },
    { name: 'Stars', symbol: '⭐' },
    { name: 'Flowers', symbol: '🌹' },
    { name: 'Cookies', symbol: '🍪' },
    { name: 'Gems', symbol: '💎' },
];

interface Props {
  user: UserProfile;
  onClose: () => void;
  onUpdateProfile: (profile: UserProfile) => void;
  onEditProfile?: () => void; // Optional callback to navigate to edit profile
}

export const PersonalProfilePanel: React.FC<Props> = ({ user, onClose, onUpdateProfile, onEditProfile }) => {
  const [activeTab, setActiveTab] = useState<'basic' | 'personality' | 'communication' | 'insider'>('basic');
  const [isReRecording, setIsReRecording] = useState(false);
  const [editingAttribute, setEditingAttribute] = useState<string | null>(null);
  
  // Edit state for each attribute
  const [editGender, setEditGender] = useState(user.gender || 'Prefer not to say');
  const [editPersonalityMBTI, setEditPersonalityMBTI] = useState(() => {
    // Get MBTI values from user profile if available, otherwise parse from type string or default
    if (user.personalityMBTIValues) {
      return user.personalityMBTIValues;
    }
    // Fallback: parse from type string if available
    if (user.personalityType && user.personalityType.length === 4) {
      const mbti = user.personalityType.toUpperCase();
      return {
        ei: mbti[0] === 'E' ? 75 : mbti[0] === 'I' ? 25 : 50,
        sn: mbti[1] === 'N' ? 75 : mbti[1] === 'S' ? 25 : 50,
        tf: mbti[2] === 'F' ? 75 : mbti[2] === 'T' ? 25 : 50,
        jp: mbti[3] === 'P' ? 75 : mbti[3] === 'J' ? 25 : 50,
      };
    }
    // Default to neutral values
    return { ei: 50, sn: 50, tf: 50, jp: 50 };
  });
  const [preferNotToSayMBTI, setPreferNotToSayMBTI] = useState(
    !user.personalityType || user.personalityType === 'Prefer not to say'
  );
  const [editDescription, setEditDescription] = useState(user.personalDescription || '');
  const [editInterests, setEditInterests] = useState(user.interests?.join(', ') || '');
  const [editCurrencyName, setEditCurrencyName] = useState(user.economy?.currencyName || 'Love Tokens');
  const [editCurrencySymbol, setEditCurrencySymbol] = useState(user.economy?.currencySymbol || '🪙');
  const [showCurrencyConfigModal, setShowCurrencyConfigModal] = useState(false);
  const [showAvatarPicker, setShowAvatarPicker] = useState(false);
  const [editProfilePicture, setEditProfilePicture] = useState<string | null>(user.profilePicture || null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleVoicePrintSetup = async (voicePrintId: string) => {
    try {
      // Update user profile with voice print ID
      // Note: This assumes there's an API endpoint to update voice print
      // For now, we'll update the local user state
      const updatedUser: UserProfile = {
        ...user,
        voicePrintId: voicePrintId,
      };
      onUpdateProfile(updatedUser);
      setIsReRecording(false);
    } catch (error: any) {
      console.error('Failed to save voice print:', error);
      alert(`Failed to save voice print: ${error.message}`);
    }
  };

  const handleReRecordVoicePrint = () => {
    setIsReRecording(true);
  };

  const handleSaveProfilePicture = async (pictureUrl: string | null) => {
    try {
      await apiService.updateProfile({
        profile_picture_url: pictureUrl || undefined,
      });
      // Refresh user data from backend
      const userResponse = await apiService.getCurrentUser();
      const backendUser = userResponse.data as {
        id: string;
        display_name?: string;
        pronouns?: string;
        personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
        goals?: string[];
        profile_picture_url?: string;
      };
      const updatedUser: UserProfile = {
        ...user,
        profilePicture: backendUser.profile_picture_url || pictureUrl || user.profilePicture,
      };
      onUpdateProfile(updatedUser);
      setShowAvatarPicker(false);
    } catch (error: any) {
      console.error('Failed to save profile picture:', error);
      alert(`Failed to save profile picture: ${error.message}`);
    }
  };

  const handleSaveAttribute = async (attribute: string) => {
    try {
      switch (attribute) {
        case 'gender':
          await apiService.updateProfile({
            pronouns: editGender !== 'Prefer not to say' ? editGender : undefined,
          });
          // Refresh user data from backend
          const userResponse = await apiService.getCurrentUser();
          const backendUser = userResponse.data;
          const updatedUser: UserProfile = {
            ...user,
            gender: backendUser.pronouns || editGender,
          };
          onUpdateProfile(updatedUser);
          break;
        
        case 'personality':
          const mbtiData = preferNotToSayMBTI 
            ? { type: 'Prefer not to say' }
            : {
                type: (() => {
                  const ei = editPersonalityMBTI.ei >= 50 ? 'E' : 'I';
                  const sn = editPersonalityMBTI.sn >= 50 ? 'N' : 'S';
                  const tf = editPersonalityMBTI.tf >= 50 ? 'F' : 'T';
                  const jp = editPersonalityMBTI.jp >= 50 ? 'P' : 'J';
                  return `${ei}${sn}${tf}${jp}`;
                })(),
                values: {
                  ei: editPersonalityMBTI.ei,
                  sn: editPersonalityMBTI.sn,
                  tf: editPersonalityMBTI.tf,
                  jp: editPersonalityMBTI.jp,
                }
              };
          await apiService.updateProfile({
            personality_type: mbtiData,
          });
          // Refresh user data from backend
          const userResponsePersonality = await apiService.getCurrentUser();
          const backendUserPersonality = userResponsePersonality.data;
          const personalityTypeData = backendUserPersonality.personality_type as { type: string; values?: { ei: number; sn: number; tf: number; jp: number } } | null;
          const updatedUserPersonality: UserProfile = {
            ...user,
            personalityType: personalityTypeData?.type || undefined,
            personalityMBTIValues: personalityTypeData?.values || undefined,
          };
          onUpdateProfile(updatedUserPersonality);
          break;
        
        case 'description':
          // Description might be stored in a separate field or in goals
          // For now, update locally since there's no specific API endpoint
          const updatedUserDesc: UserProfile = {
            ...user,
            personalDescription: editDescription,
          };
          onUpdateProfile(updatedUserDesc);
          break;
        
        case 'interests':
          const interestsArray = editInterests.split(',').map(s => s.trim()).filter(Boolean);
          await apiService.updateProfile({
            goals: interestsArray,
          });
          // Refresh user data from backend
          const userResponseInterests = await apiService.getCurrentUser();
          const backendUserInterests = userResponseInterests.data;
          const updatedUserInterests: UserProfile = {
            ...user,
            interests: backendUserInterests.goals || interestsArray,
          };
          onUpdateProfile(updatedUserInterests);
          break;
        
        case 'currency':
          // Currency is handled by the modal's save button
          break;
      }

      setEditingAttribute(null);
    } catch (error: any) {
      console.error(`Failed to save ${attribute}:`, error);
      alert(`Failed to save ${attribute}: ${error.message}`);
    }
  };

  const handleCancelEdit = () => {
    // Reset edit states to original values
    setEditGender(user.gender || 'Prefer not to say');
    if (user.personalityMBTIValues) {
      setEditPersonalityMBTI(user.personalityMBTIValues);
      setPreferNotToSayMBTI(false);
    } else if (user.personalityType && user.personalityType.length === 4) {
      // Fallback: parse from type string
      const mbti = user.personalityType.toUpperCase();
      setEditPersonalityMBTI({
        ei: mbti[0] === 'E' ? 75 : mbti[0] === 'I' ? 25 : 50,
        sn: mbti[1] === 'N' ? 75 : mbti[1] === 'S' ? 25 : 50,
        tf: mbti[2] === 'F' ? 75 : mbti[2] === 'T' ? 25 : 50,
        jp: mbti[3] === 'P' ? 75 : mbti[3] === 'J' ? 25 : 50,
      });
      setPreferNotToSayMBTI(false);
    } else {
      setPreferNotToSayMBTI(true);
    }
    setEditDescription(user.personalDescription || '');
    setEditInterests(user.interests?.join(', ') || '');
    setEditingAttribute(null);
  };

  return (
    <>
      {/* Slide-in Panel */}
      <div className="fixed inset-0 z-50 flex">
        {/* Backdrop */}
        <div 
          className="flex-1 bg-slate-900/60 backdrop-blur-sm transition-opacity animate-fade-in"
          onClick={onClose}
        />
        
        {/* Panel */}
        <div 
          className="w-full max-w-md bg-white shadow-2xl flex flex-col"
          style={{ 
            animation: 'slideInRight 0.3s ease-out',
            transform: 'translateX(0)'
          }}
        >
          {/* Header */}
          <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between shrink-0 border-b-4 border-slate-700">
            <div className="flex items-center gap-3">
              <Settings size={20} />
              <h2 className="text-lg font-black uppercase tracking-tight">Personal Profile</h2>
            </div>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center border border-slate-700 hover:border-white text-slate-400 hover:text-white transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Tabs */}
          <div className="bg-slate-100 border-b-2 border-slate-300 flex shrink-0">
            <button
              onClick={() => setActiveTab('basic')}
              className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-widest transition-colors ${
                activeTab === 'basic'
                  ? 'bg-white text-slate-900 border-b-2 border-slate-900'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Basic Info
            </button>
            <button
              onClick={() => setActiveTab('personality')}
              className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-widest transition-colors ${
                activeTab === 'personality'
                  ? 'bg-white text-slate-900 border-b-2 border-slate-900'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Personality
            </button>
            <button
              onClick={() => setActiveTab('communication')}
              className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-widest transition-colors ${
                activeTab === 'communication'
                  ? 'bg-white text-slate-900 border-b-2 border-slate-900'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Communication
            </button>
            <button
              onClick={() => setActiveTab('insider')}
              className={`flex-1 px-4 py-3 text-xs font-bold uppercase tracking-widest transition-colors ${
                activeTab === 'insider'
                  ? 'bg-white text-slate-900 border-b-2 border-slate-900'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              Insider
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Hidden file input for image upload */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              style={{ display: 'none' }}
              onChange={(e) => {
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
                  // Create preview and save
                  const reader = new FileReader();
                  reader.onloadend = () => {
                    const dataUrl = reader.result as string;
                    setEditProfilePicture(dataUrl);
                    // Auto-save when file is selected
                    handleSaveProfilePicture(dataUrl);
                  };
                  reader.readAsDataURL(file);
                }
              }}
            />

            {/* TAB 1: Basic Info */}
            {activeTab === 'basic' && (
              <div className="space-y-3">
                {/* Profile Image & Name */}
                <div className="flex items-center gap-4">
                  <div 
                    onClick={() => setShowAvatarPicker(true)}
                    className={`w-16 h-16 border-2 border-slate-900 flex items-center justify-center font-bold text-2xl shadow-[4px_4px_0px_rgba(30,41,59,0.2)] overflow-hidden cursor-pointer hover:opacity-80 transition-opacity relative group ${
                      user.profilePicture ? 'bg-white' : 'bg-slate-900 text-white'
                    }`}
                  >
                    {user.profilePicture ? (
                      <img 
                        src={user.profilePicture} 
                        alt={user.name} 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      user.name.charAt(0)
                    )}
                    {/* Camera icon overlay on hover */}
                    <div className="absolute inset-0 bg-slate-900/60 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                      <Camera size={20} className="text-white" />
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-900 uppercase">{user.name}</p>
                    <p className="text-xs font-mono text-slate-500">ID: {user.id?.slice(-8)}</p>
                  </div>
                </div>

                {/* Gender */}
                <div className="bg-slate-50 border border-slate-200 p-3">
                  {editingAttribute === 'gender' ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <User size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Gender</span>
                        </div>
                      </div>
                      <div className="relative">
                        <select 
                          value={editGender} 
                          onChange={(e) => setEditGender(e.target.value)}
                          className="w-full appearance-none bg-white border-2 border-slate-300 p-2 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 transition-colors rounded-none"
                        >
                          <option value="Prefer not to say">PREFER NOT TO SAY</option>
                          <option value="Male">MALE</option>
                          <option value="Female">FEMALE</option>
                          <option value="Non-binary">NON-BINARY</option>
                          <option value="Other">OTHER</option>
                        </select>
                        <ArrowRight size={12} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400 rotate-90" />
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveAttribute('gender')}
                          className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors flex items-center justify-center gap-1"
                        >
                          <Save size={12} />
                          Save
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="flex-1 bg-slate-300 hover:bg-slate-400 text-slate-900 text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <User size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Gender</span>
                        </div>
                        <button
                          onClick={() => {
                            setEditGender(user.gender || 'Prefer not to say');
                            setEditingAttribute('gender');
                          }}
                          className="p-1 hover:bg-slate-200 rounded transition-colors"
                          title="Edit Gender"
                        >
                          <Edit2 size={12} className="text-slate-600" />
                        </button>
                      </div>
                      <p className="text-sm text-slate-900 font-mono">{user.gender && user.gender !== 'Prefer not to say' ? user.gender : 'Not specified'}</p>
                    </>
                  )}
                </div>

                {/* Personal Description */}
                <div className="bg-slate-50 border border-slate-200 p-3">
                  {editingAttribute === 'description' ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Info size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Personal Description</span>
                        </div>
                      </div>
                      <textarea 
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        className="w-full bg-white border-2 border-slate-300 p-2 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 transition-colors rounded-none min-h-[80px]"
                        placeholder="Describe yourself..."
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveAttribute('description')}
                          className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors flex items-center justify-center gap-1"
                        >
                          <Save size={12} />
                          Save
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="flex-1 bg-slate-300 hover:bg-slate-400 text-slate-900 text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Info size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Personal Description</span>
                        </div>
                        <button
                          onClick={() => {
                            setEditDescription(user.personalDescription || '');
                            setEditingAttribute('description');
                          }}
                          className="p-1 hover:bg-slate-200 rounded transition-colors"
                          title="Edit Description"
                        >
                          <Edit2 size={12} className="text-slate-600" />
                        </button>
                      </div>
                      <p className="text-sm text-slate-900 leading-relaxed">{user.personalDescription || 'No description provided'}</p>
                    </>
                  )}
                </div>

                {/* Interests */}
                <div className="bg-slate-50 border border-slate-200 p-3">
                  {editingAttribute === 'interests' ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Heart size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Interests</span>
                        </div>
                      </div>
                      <input 
                        type="text"
                        value={editInterests}
                        onChange={(e) => setEditInterests(e.target.value)}
                        className="w-full bg-white border-2 border-slate-300 p-2 text-xs font-bold text-slate-900 focus:outline-none focus:border-indigo-600 transition-colors rounded-none"
                        placeholder="Cooking, Hiking, Sci-Fi (Comma separated)"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveAttribute('interests')}
                          className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors flex items-center justify-center gap-1"
                        >
                          <Save size={12} />
                          Save
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="flex-1 bg-slate-300 hover:bg-slate-400 text-slate-900 text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Heart size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Interests</span>
                        </div>
                        <button
                          onClick={() => {
                            setEditInterests(user.interests?.join(', ') || '');
                            setEditingAttribute('interests');
                          }}
                          className="p-1 hover:bg-slate-200 rounded transition-colors"
                          title="Edit Interests"
                        >
                          <Edit2 size={12} className="text-slate-600" />
                        </button>
                      </div>
                      {user.interests && user.interests.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {user.interests.map((interest, idx) => (
                            <span 
                              key={idx}
                              className="text-xs bg-white border border-slate-300 px-2 py-1 text-slate-700 font-mono"
                            >
                              {interest}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <p className="text-xs text-slate-400 italic">No interests specified</p>
                      )}
                    </>
                  )}
                </div>

                {/* Attachment Style */}
                {user.attachmentStyle && (
                  <div className="bg-slate-50 border border-slate-200 p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Shield size={14} className="text-slate-600" />
                      <span className="text-xs font-bold text-slate-700 uppercase">Attachment Style</span>
                    </div>
                    <p className="text-sm text-slate-900 font-mono capitalize mb-2">{user.attachmentStyle}</p>
                    {user.attachmentStats && (
                      <div className="space-y-2 mt-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-600">Anxiety</span>
                          <span className="text-xs text-slate-900 font-mono">{user.attachmentStats.anxiety}/100</span>
                        </div>
                        <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-indigo-600 transition-all"
                            style={{ width: `${user.attachmentStats.anxiety}%` }}
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-slate-600">Avoidance</span>
                          <span className="text-xs text-slate-900 font-mono">{user.attachmentStats.avoidance}/100</span>
                        </div>
                        <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-rose-600 transition-all"
                            style={{ width: `${user.attachmentStats.avoidance}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Stats */}
                {user.stats && (
                  <div className="bg-slate-50 border border-slate-200 p-3">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp size={14} className="text-slate-600" />
                      <span className="text-xs font-bold text-slate-700 uppercase">Analytics</span>
                    </div>
                    <div className="space-y-3">
                      {user.stats.overallAffection !== undefined && (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-slate-600">Overall Affection</span>
                            <span className="text-xs text-slate-900 font-mono">{user.stats.overallAffection}/100</span>
                          </div>
                          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-pink-600 transition-all"
                              style={{ width: `${user.stats.overallAffection}%` }}
                            />
                          </div>
                        </div>
                      )}
                      
                      {user.stats.communicationScore !== undefined && (
                        <div>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-slate-600">Communication Score</span>
                            <span className="text-xs text-slate-900 font-mono">{user.stats.communicationScore}/100</span>
                          </div>
                          <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-blue-600 transition-all"
                              style={{ width: `${user.stats.communicationScore}%` }}
                            />
                          </div>
                        </div>
                      )}
                      
                      {user.stats.weeklyTrends && user.stats.weeklyTrends.length > 0 && (
                        <div>
                          <div className="text-xs text-slate-600 mb-2">Weekly Trends</div>
                          <div className="flex items-end gap-1 h-12">
                            {user.stats.weeklyTrends.map((value, idx) => (
                              <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                                <div 
                                  className="w-full bg-indigo-600 rounded-t transition-all"
                                  style={{ height: `${value}%` }}
                                />
                                <span className="text-[8px] text-slate-500 font-mono">{['S', 'M', 'T', 'W', 'T', 'F', 'S'][idx]}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: Personality */}
            {activeTab === 'personality' && (
              <div className="space-y-3">
                <div className="bg-slate-50 border border-slate-200 p-3">
                  {editingAttribute === 'personality' ? (
                    <div className="space-y-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Sparkles size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Personality (MBTI)</span>
                        </div>
                      </div>
                      {preferNotToSayMBTI ? (
                        <div className="bg-white border-2 border-slate-300 p-4 text-center">
                          <p className="text-sm text-slate-600 mb-3">Prefer not to say</p>
                          <button
                            onClick={() => setPreferNotToSayMBTI(false)}
                            className="text-xs font-bold text-indigo-600 hover:text-indigo-700 uppercase tracking-widest"
                          >
                            Use MBTI Sliders Instead
                          </button>
                        </div>
                      ) : (
                        <>
                          <div className="bg-white border-2 border-slate-300 p-4">
                            <MBTISliders
                              values={editPersonalityMBTI}
                              onChange={(dimension, value) => {
                                setEditPersonalityMBTI(prev => ({ ...prev, [dimension]: value }));
                              }}
                            />
                          </div>
                          <button
                            onClick={() => setPreferNotToSayMBTI(true)}
                            className="w-full bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors"
                          >
                            Prefer Not to Say
                          </button>
                        </>
                      )}
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleSaveAttribute('personality')}
                          className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors flex items-center justify-center gap-1"
                        >
                          <Save size={12} />
                          Save
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="flex-1 bg-slate-300 hover:bg-slate-400 text-slate-900 text-xs font-bold uppercase tracking-widest py-2 px-3 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <Sparkles size={14} className="text-slate-600" />
                          <span className="text-xs font-bold text-slate-700 uppercase">Personality</span>
                        </div>
                        <button
                          onClick={() => {
                            // Initialize MBTI values from user profile
                            if (user.personalityMBTIValues) {
                              setEditPersonalityMBTI(user.personalityMBTIValues);
                              setPreferNotToSayMBTI(false);
                            } else if (user.personalityType && user.personalityType.length === 4) {
                              // Fallback: parse from type string
                              const mbti = user.personalityType.toUpperCase();
                              setEditPersonalityMBTI({
                                ei: mbti[0] === 'E' ? 75 : mbti[0] === 'I' ? 25 : 50,
                                sn: mbti[1] === 'N' ? 75 : mbti[1] === 'S' ? 25 : 50,
                                tf: mbti[2] === 'F' ? 75 : mbti[2] === 'T' ? 25 : 50,
                                jp: mbti[3] === 'P' ? 75 : mbti[3] === 'J' ? 25 : 50,
                              });
                              setPreferNotToSayMBTI(false);
                            } else {
                              setPreferNotToSayMBTI(true);
                            }
                            setEditingAttribute('personality');
                          }}
                          className="p-1 hover:bg-slate-200 rounded transition-colors"
                          title="Edit Personality"
                        >
                          <Edit2 size={12} className="text-slate-600" />
                        </button>
                      </div>
                      <p className="text-sm text-slate-900 font-mono">
                        {user.personalityType === 'Prefer not to say' ? 'Prefer not to say' : user.personalityType || 'Not set'}
                      </p>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* TAB 3: Communication */}
            {activeTab === 'communication' && (
              <div className="space-y-3">
                {/* Voice Print */}
                <div className="bg-slate-50 border-2 border-slate-200 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Mic size={16} className="text-slate-600" />
                      <span className="text-sm font-bold text-slate-900 uppercase">Voice Print</span>
                    </div>
                    {user.voicePrintId ? (
                      <div className="flex items-center gap-1 text-green-600">
                        <CheckCircle size={14} />
                        <span className="text-xs font-mono">Active</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-slate-400">
                        <AlertCircle size={14} />
                        <span className="text-xs font-mono">Not Set</span>
                      </div>
                    )}
                  </div>
                  
                  {user.voicePrintId && (
                    <p className="text-xs text-slate-600 font-mono">
                      Voice print ID: {user.voicePrintId.slice(-12)}
                    </p>
                  )}
                  
                  <button
                    onClick={handleReRecordVoicePrint}
                    className="w-full bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold uppercase tracking-widest py-2 px-4 transition-colors flex items-center justify-center gap-2"
                  >
                    <Mic size={14} />
                    {user.voicePrintId ? 'Re-record Voice Print' : 'Set Up Voice Print'}
                  </button>
                </div>
              </div>
            )}

            {/* TAB 4: Insider */}
            {activeTab === 'insider' && (
              <div className="space-y-3">
                {/* Love Currency */}
                <div className="bg-slate-50 border border-slate-200 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Coins size={14} className="text-slate-600" />
                      <span className="text-xs font-bold text-slate-700 uppercase">Love Currency</span>
                    </div>
                    <button
                      onClick={() => {
                        setEditCurrencyName(user.economy?.currencyName || 'Love Tokens');
                        setEditCurrencySymbol(user.economy?.currencySymbol || '🪙');
                        setShowCurrencyConfigModal(true);
                      }}
                      className="p-1 hover:bg-slate-200 rounded transition-colors"
                      title="Edit Love Currency"
                    >
                      <Edit2 size={12} className="text-slate-600" />
                    </button>
                  </div>
                  <div className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-600">Name</span>
                      <span className="text-sm text-slate-900 font-mono">{user.economy?.currencyName || 'Not set'}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-600">Symbol</span>
                      <span className="text-lg">{user.economy?.currencySymbol || '🪙'}</span>
                    </div>
                  </div>
                </div>

                {/* Love Map Configurations (Placeholder) */}
                <div className="bg-slate-50 border border-slate-200 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Heart size={14} className="text-slate-600" />
                    <span className="text-xs font-bold text-slate-700 uppercase">Love Map Configurations</span>
                  </div>
                  <p className="text-xs text-slate-400 italic">Coming soon...</p>
                </div>
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Voice Auth Modal */}
      {isReRecording && (
        <BiometricSync
          context="profile"
          onComplete={handleVoicePrintSetup}
          onCancel={() => {
            setIsReRecording(false);
          }}
          allowSkip={false}
        />
      )}

      {/* Currency Config Modal */}
      {showCurrencyConfigModal && (
        <div className="absolute inset-0 z-50 bg-slate-900/90 backdrop-blur-sm flex items-center justify-center p-6 animate-fade-in">
          <div className="bg-white w-full max-w-sm border-2 border-slate-900 p-6 shadow-2xl relative">
            <button 
              onClick={() => {
                setShowCurrencyConfigModal(false);
                // Reset to original values on cancel
                setEditCurrencyName(user.economy?.currencyName || 'Love Tokens');
                setEditCurrencySymbol(user.economy?.currencySymbol || '🪙');
              }}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-900"
            >
              <X size={20} />
            </button>

            <h3 className="font-black text-xl text-slate-900 uppercase tracking-tight mb-2 flex items-center gap-2">
              <span className="text-2xl">{editCurrencySymbol}</span> My Love Currency Settings
            </h3>
            
            <div className="mb-4 bg-slate-100 p-2 border border-slate-200">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Scope</span>
              <div className="text-xs font-bold text-slate-900 uppercase">My Personal Currency</div>
            </div>

            <p className="text-xs text-slate-500 mb-4 font-mono leading-relaxed">
              Customize the currency you offer to others. This is what your partner will see when they interact with you.
            </p>
            
            <div className="space-y-4">
              {/* Presets */}
              <div>
                <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Presets</label>
                <div className="flex flex-wrap gap-2">
                  {CURRENCY_PRESETS.map(preset => (
                    <button
                      key={preset.name}
                      onClick={() => {
                        // Just update the form fields, don't save yet
                        setEditCurrencyName(preset.name);
                        setEditCurrencySymbol(preset.symbol);
                      }}
                      className={`px-3 py-2 border-2 text-xs font-bold uppercase ${
                        (editCurrencyName === preset.name) 
                          ? 'bg-slate-900 text-white border-slate-900' 
                          : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                      }`}
                    >
                      {preset.symbol}
                    </button>
                  ))}
                </div>
              </div>
              
              <div className="pt-4 border-t border-slate-100">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Name</label>
                    <input 
                      type="text" 
                      value={editCurrencyName}
                      onChange={(e) => setEditCurrencyName(e.target.value)}
                      className="w-full border-2 border-slate-200 p-2 text-sm font-bold uppercase"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Symbol</label>
                    <input 
                      type="text" 
                      value={editCurrencySymbol}
                      onChange={(e) => setEditCurrencySymbol(e.target.value)}
                      className="w-full border-2 border-slate-200 p-2 text-sm font-bold uppercase text-center"
                    />
                  </div>
                </div>
              </div>
            </div>

            <button 
              onClick={async () => {
                try {
                  await apiService.updateEconomySettings(editCurrencyName, editCurrencySymbol);
                  // Refresh economy settings from backend
                  const economyResponse = await apiService.getEconomySettings();
                  const economyData = economyResponse.data as {
                    currency_name: string;
                    currency_symbol: string;
                  };
                  const updatedUser: UserProfile = {
                    ...user,
                    economy: {
                      currencyName: economyData.currency_name,
                      currencySymbol: economyData.currency_symbol,
                    },
                  };
                  onUpdateProfile(updatedUser);
                  setShowCurrencyConfigModal(false);
                } catch (error: any) {
                  alert(`Failed to save economy settings: ${error.message || 'Unknown error'}`);
                }
              }}
              className="w-full mt-6 bg-indigo-600 text-white py-3 font-bold uppercase tracking-widest text-xs shadow-[4px_4px_0px_#312e81] border-2 border-indigo-900 active:shadow-none active:translate-y-0.5"
            >
              Save Configuration
            </button>
          </div>
        </div>
      )}

      {/* Avatar Picker Modal */}
      {showAvatarPicker && (
        <>
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-slate-900/80 backdrop-blur-sm z-50"
            onClick={() => setShowAvatarPicker(false)}
          />
          {/* Avatar Picker */}
          <div className="absolute inset-0 z-50 flex items-center justify-center p-6">
            <div className="bg-white w-full max-w-2xl border-2 border-slate-900 shadow-2xl relative max-h-[90vh] overflow-hidden flex flex-col">
              <div className="bg-slate-900 text-white px-6 py-4 flex items-center justify-between shrink-0">
                <h3 className="text-lg font-black uppercase tracking-tight">Change Profile Picture</h3>
                <button
                  onClick={() => setShowAvatarPicker(false)}
                  className="w-8 h-8 flex items-center justify-center border border-slate-700 hover:border-white text-slate-400 hover:text-white transition-colors"
                >
                  <X size={20} />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto p-6">
                <div className="mb-4 flex gap-4">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-900 text-xs font-bold uppercase tracking-widest py-3 px-4 transition-colors flex items-center justify-center gap-2 border-2 border-slate-300"
                  >
                    <Camera size={16} />
                    Upload Image
                  </button>
                  <button
                    onClick={() => setShowAvatarPicker(false)}
                    className="flex-1 bg-slate-300 hover:bg-slate-400 text-slate-900 text-xs font-bold uppercase tracking-widest py-3 px-4 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
                <AvatarPicker
                  currentAvatar={editProfilePicture || undefined}
                  onSelect={(avatarPath) => {
                    setEditProfilePicture(avatarPath);
                    // Auto-save when avatar is selected
                    handleSaveProfilePicture(avatarPath);
                  }}
                  onClose={() => setShowAvatarPicker(false)}
                />
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
};
