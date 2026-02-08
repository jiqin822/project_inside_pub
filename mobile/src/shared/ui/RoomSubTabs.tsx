import React from 'react';

export const RoomSubTabs: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="flex p-2 gap-2 border-b border-slate-200 bg-white shrink-0 relative z-10">
      {children}
    </div>
  );
};

export interface RoomSubTabButtonProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  icon?: React.ReactNode;
}

export const RoomSubTabButton: React.FC<RoomSubTabButtonProps> = ({
  active,
  onClick,
  children,
  icon,
}) => (
  <button
    onClick={onClick}
    className={`flex-1 py-2 text-[10px] font-bold uppercase tracking-widest flex items-center justify-center gap-2 transition-all border-2 ${
      active
        ? 'bg-slate-900 text-white border-slate-900 shadow-[2px_2px_0px_rgba(0,0,0,0.2)]'
        : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
    }`}
  >
    {icon}
    {children}
  </button>
);
