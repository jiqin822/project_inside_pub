import React from 'react';
import { X, Users, Plus, Trash2 } from 'lucide-react';
import { LovedOne } from '../../../shared/types/domain';

interface AddRelationshipModalProps {
  isOpen: boolean;
  userLovedOnes: LovedOne[];
  email: string;
  relationship: string;
  isLoading: boolean;
  onClose: () => void;
  onEmailChange: (email: string) => void;
  onRelationshipChange: (rel: string) => void;
  onAdd: () => void;
  onRemove: (id: string) => void;
}

export const AddRelationshipModal: React.FC<AddRelationshipModalProps> = ({
  isOpen,
  userLovedOnes,
  email,
  relationship,
  isLoading,
  onClose,
  onEmailChange,
  onRelationshipChange,
  onAdd,
  onRemove,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4 animate-fade-in">
      <div className="bg-white w-full max-w-sm border-2 border-slate-900 p-6 shadow-[8px_8px_0px_rgba(15,23,42,1)] relative animate-slide-in-down">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 hover:text-slate-900">
          <X size={20} />
        </button>
        
        <div className="mb-6 flex justify-between items-start">
          <div>
            <h3 className="font-black text-slate-900 text-lg uppercase tracking-tight">Team Roster</h3>
            <p className="font-mono text-slate-500 text-xs mt-1">MANAGE RELATIONSHIP NODES</p>
          </div>
          <Users size={24} className="text-slate-200" />
        </div>
        
        <div className="space-y-2 border-2 border-slate-100 bg-slate-50 p-2 min-h-[120px] max-h-48 overflow-y-auto mb-4">
          {userLovedOnes.length === 0 && (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 py-6">
              <span className="text-[10px] font-mono uppercase">No personnel assigned</span>
            </div>
          )}
          {userLovedOnes.map(person => (
            <div 
              key={person.id} 
              className={`flex items-center justify-between p-2 shadow-sm group transition-all ${
                person.isPending 
                  ? 'bg-slate-100 border-2 border-dashed border-slate-300 opacity-60' 
                  : 'bg-white border border-slate-200'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 flex items-center justify-center text-xs font-bold border ${
                  person.isPending 
                    ? 'bg-slate-300 text-slate-500 border-dashed border-slate-400' 
                    : 'bg-slate-900 text-white border-slate-900'
                }`}>
                  {person.isPending ? '⏳' : person.name.charAt(0)}
                </div>
                <div>
                  <p className={`font-bold text-xs uppercase leading-none ${
                    person.isPending ? 'text-slate-500' : 'text-slate-900'
                  }`}>
                    {person.name}
                    {person.isPending && <span className="text-[9px] font-normal text-slate-400 ml-1">(Pending)</span>}
                  </p>
                  <p className={`text-[10px] font-mono uppercase ${
                    person.isPending ? 'text-slate-400' : 'text-slate-500'
                  }`}>
                    {person.relationship}
                  </p>
                  {person.pendingEmail && (
                    <p className="text-[9px] font-mono text-slate-400 italic">{person.pendingEmail}</p>
                  )}
                </div>
              </div>
              <button 
                onClick={() => onRemove(person.id)} 
                className={`p-2 transition-colors ${
                  person.isPending 
                    ? 'text-slate-300 hover:text-slate-500' 
                    : 'text-slate-300 hover:text-red-500'
                }`}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
        
        <div className="bg-slate-100 p-3 border border-slate-200 space-y-3">
          <div className="space-y-2">
            <input 
              type="email" 
              value={email} 
              onChange={(e) => onEmailChange(e.target.value)} 
              placeholder="EMAIL *" 
              required 
              className="w-full bg-white border border-slate-300 p-2 text-xs font-bold uppercase placeholder:text-slate-300 focus:outline-none focus:border-indigo-500" 
              onKeyDown={(e) => e.key === 'Enter' && !isLoading && onAdd()}
            />
            <select 
              value={relationship} 
              onChange={(e) => onRelationshipChange(e.target.value)} 
              className="w-full bg-white border border-slate-300 p-2 text-[10px] font-bold uppercase focus:outline-none focus:border-indigo-500"
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
            onClick={onAdd} 
            disabled={!email.trim() || isLoading} 
            className="w-full bg-white border-2 border-slate-900 hover:bg-slate-50 disabled:opacity-50 text-slate-900 text-[10px] font-bold uppercase tracking-widest py-2 flex items-center justify-center gap-2 transition-colors"
          >
            {isLoading ? 'Adding...' : <><Plus size={12} /> Add Entry</>}
          </button>
          <p className="text-[9px] font-mono text-slate-500 text-center">Name will be fetched automatically if user is registered.</p>
        </div>
      </div>
    </div>
  );
};
