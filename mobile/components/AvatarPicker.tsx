import React, { useState, useEffect } from 'react';
import { X, Image as ImageIcon } from 'lucide-react';

interface Props {
  currentAvatar: string | null | undefined;
  onSelect: (avatarPath: string | null) => void;
  onClose: () => void;
}

// MBTI personality types
const MBTI_TYPES = [
  'INTJ', 'INTP', 'ENTJ', 'ENTP',
  'INFJ', 'INFP', 'ENFJ', 'ENFP',
  'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
  'ISTP', 'ISFP', 'ESTP', 'ESFP',
];

// Gender codes: w = woman, m = man
const GENDERS = ['w', 'm'];

// Generate all possible avatar paths based on MBTI-gender pattern
// Note: File names are lowercase (e.g., intj-w.png, enfp-m.png)
const generateAvatarList = (): string[] => {
  const avatars: string[] = [];
  for (const mbti of MBTI_TYPES) {
    for (const gender of GENDERS) {
      avatars.push(`/avatar/${mbti.toLowerCase()}-${gender}.png`);
    }
  }
  return avatars;
};

const AVATAR_LIST = generateAvatarList();

export const AvatarPicker: React.FC<Props> = ({ currentAvatar, onSelect, onClose }) => {
  const [selectedAvatar, setSelectedAvatar] = useState<string | null>(currentAvatar || null);
  const [availableAvatars, setAvailableAvatars] = useState<string[]>([]);
  const [filterGender, setFilterGender] = useState<'all' | 'w' | 'm'>('all');

  useEffect(() => {
    // Check which avatars are actually available
    const checkAvatars = async () => {
      const checked: string[] = [];
      // Check all avatars in parallel for better performance
      const checkPromises = AVATAR_LIST.map(async (avatar) => {
        try {
          const img = new Image();
          await new Promise((resolve, reject) => {
            img.onload = resolve;
            img.onerror = reject;
            img.src = avatar;
          });
          return avatar;
        } catch {
          return null;
        }
      });
      
      const results = await Promise.all(checkPromises);
      const validAvatars = results.filter((avatar): avatar is string => avatar !== null);
      setAvailableAvatars(validAvatars);
    };
    checkAvatars();
  }, []);

  // Filter avatars by gender
  const filteredAvatars = filterGender === 'all' 
    ? availableAvatars 
    : availableAvatars.filter(avatar => avatar.includes(`-${filterGender}.png`));
  const sortedAvatars = [...filteredAvatars].sort((a, b) => a.localeCompare(b));

  const handleSelect = (avatarPath: string) => {
    setSelectedAvatar(avatarPath);
  };

  const handleConfirm = () => {
    onSelect(selectedAvatar);
    onClose();
  };

  const handleRemove = () => {
    setSelectedAvatar(null);
    onSelect(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div 
        className="bg-white border-4 border-slate-900 shadow-[8px_8px_0px_rgba(30,41,59,0.3)] max-w-md w-full max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="bg-slate-900 text-white p-4 flex justify-between items-center border-b-4 border-slate-900 shrink-0">
          <div className="flex items-center gap-2">
            <ImageIcon size={18} />
            <h2 className="text-sm font-black uppercase tracking-widest">Choose Avatar</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center border-2 border-white/20 hover:border-white text-white hover:bg-white/10 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {/* Gender Filter */}
          <div className="mb-4 flex gap-2">
            <button
              onClick={() => setFilterGender('all')}
              className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest border-2 transition-colors ${
                filterGender === 'all'
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilterGender('w')}
              className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest border-2 transition-colors ${
                filterGender === 'w'
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
              }`}
            >
              Woman
            </button>
            <button
              onClick={() => setFilterGender('m')}
              className={`px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest border-2 transition-colors ${
                filterGender === 'm'
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-slate-400'
              }`}
            >
              Man
            </button>
          </div>

          {/* Avatar Grid */}
          {sortedAvatars.length === 0 ? (
            <div className="text-center py-8 text-slate-400">
              <p className="text-xs font-mono uppercase">No avatars found</p>
              <p className="text-[10px] font-mono text-slate-300 mt-2">
                Add avatars named: [MBTI]-[gender].png
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-5 sm:grid-cols-6 gap-2">
              {sortedAvatars.map((avatar) => {
                const genderLabel = avatar.includes('-w.png') ? 'W' : 'M';
                return (
                  <button
                    key={avatar}
                    onClick={() => handleSelect(avatar)}
                    className={`aspect-square border-2 transition-all relative overflow-hidden ${
                      selectedAvatar === avatar
                        ? 'border-indigo-600 bg-white shadow-md scale-[1.03]'
                        : 'border-slate-200 hover:border-slate-400 bg-white'
                    }`}
                    title={genderLabel}
                  >
                    <img
                      src={avatar}
                      alt="Avatar"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                    <div className="absolute bottom-0 right-0 bg-slate-900/70 text-white text-[8px] font-bold px-1">
                      {genderLabel}
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {/* No Avatar Option */}
          <div className="mt-4">
            <button
              onClick={handleRemove}
              className={`w-full p-3 border-2 transition-all ${
                selectedAvatar === null
                  ? 'border-indigo-600 bg-indigo-50'
                  : 'border-slate-200 hover:border-slate-400'
              }`}
            >
              <span className="text-xs font-bold uppercase tracking-widest text-slate-700">
                Remove Avatar
              </span>
            </button>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-50 border-t-4 border-slate-900 flex gap-3 shrink-0">
          <button
            onClick={onClose}
            className="flex-1 bg-white border-2 border-slate-900 hover:bg-slate-50 text-slate-900 font-bold text-xs uppercase tracking-widest py-3 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="flex-1 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs uppercase tracking-widest py-3 transition-colors"
          >
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
};
