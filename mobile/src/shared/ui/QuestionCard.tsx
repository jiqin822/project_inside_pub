import React from 'react';
import { Plus, MessageSquare } from 'lucide-react';

export interface QuestionCardProps {
  /** Question ID */
  id: string;
  /** Category label (e.g., "History", "Dreams") - kept for internal use */
  category: string;
  /** Level title to display in badge (e.g., "THE BASICS", "PREFERENCES") */
  levelTitle?: string;
  /** Question text */
  text: string;
  /** Current answer value (for editing) */
  value?: string;
  /** Callback when answer changes */
  onChange?: (value: string) => void;
  /** Callback when "Add to My Specs" is clicked */
  onAdd?: () => void;
  /** Whether the question has been answered */
  answered?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Disable the add button */
  disabled?: boolean;
}

export const QuestionCard: React.FC<QuestionCardProps> = ({
  id,
  category,
  levelTitle,
  text,
  value = '',
  onChange,
  onAdd,
  answered = false,
  placeholder = 'Type your answer here...',
  disabled = false,
}) => {
  const displayLabel = levelTitle || category;
  
  return (
    <div className="bg-white border-2 border-slate-200 p-5 shadow-[4px_4px_0px_rgba(30,41,59,0.05)] hover:shadow-[4px_4px_0px_rgba(30,41,59,0.1)] transition-all">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-6 h-6 bg-slate-100 text-slate-400 flex items-center justify-center font-bold text-xs rounded-full">?</span>
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{displayLabel}</span>
      </div>
      <h4 className="font-bold text-slate-900 text-base leading-snug mb-4">{text}</h4>
      
      <div className="relative">
        <textarea 
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-sm font-medium focus:outline-none focus:border-indigo-600 focus:bg-white transition-all min-h-[80px]"
        />
        <div className="absolute bottom-2 right-2">
          <MessageSquare size={14} className="text-slate-300" />
        </div>
      </div>

      {onAdd && (
        <button 
          onClick={onAdd}
          disabled={disabled || !value?.trim()}
          className="w-full mt-4 bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white py-3 font-bold uppercase tracking-widest text-xs flex items-center justify-center gap-2 transition-all shadow-sm active:translate-y-0.5"
        >
          <Plus size={14} /> Add to My Specs
        </button>
      )}
    </div>
  );
};
