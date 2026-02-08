import React from 'react';
import { X } from 'lucide-react';

export interface RoomHeaderProps {
  /** Small label above title, e.g. "MODULE: THERAPY" - slate-500, 10px, font-mono, uppercase */
  moduleTitle: string;
  /** Optional icon prefix in front of module title (e.g. <Terminal size={12} />) */
  moduleIcon?: React.ReactNode;
  /** Main title below module title, e.g. "Session Setup", "LOVE MAPS" (string or ReactNode for mixed styling) */
  title?: React.ReactNode;
  /** Optional colored subtitle, e.g. { text: "ECONOMY OF CARE", colorClass: "text-yellow-600" } */
  subtitle?: { text: string; colorClass: string };
  onClose: () => void;
  /** Optional right-side content (e.g. Global XP badge, view toggle) */
  headerRight?: React.ReactNode;
  /** Optional left icon (e.g. Bot/Handshake for therapist chat) */
  leftIcon?: React.ReactNode;
  /** Dark variant for special modes (e.g. mediation) */
  variant?: 'default' | 'dark';
  /** Optional class for main title (e.g. "text-xl font-mono leading-none") */
  titleClassName?: string;
  /** Safe area padding */
  style?: React.CSSProperties;
}

const defaultHeaderStyle: React.CSSProperties = {
  paddingTop: 'calc(var(--sat, 0px) + 1rem)',
  marginTop: 'calc(-1 * var(--sat, 0px))',
};

export const RoomHeader: React.FC<RoomHeaderProps> = ({
  moduleTitle,
  moduleIcon,
  title,
  subtitle,
  onClose,
  headerRight,
  leftIcon,
  variant = 'default',
  titleClassName,
  style,
}) => {
  const isDark = variant === 'dark';
  const titleClass = titleClassName ?? `text-2xl font-black uppercase tracking-tighter leading-none ${isDark ? 'text-white' : 'text-slate-900'}`;
  return (
    <header
      className={`relative z-10 px-6 py-4 border-b-4 flex items-center justify-between shrink-0 ${
        isDark
          ? 'bg-indigo-900 border-indigo-950 text-white'
          : 'bg-white border-slate-900 text-slate-900'
      }`}
      style={{ ...defaultHeaderStyle, ...style }}
    >
      <div className="flex items-center gap-3">
        {leftIcon && <div className="shrink-0">{leftIcon}</div>}
        <div>
          <div
            className={`flex items-center gap-2 text-[10px] font-mono font-bold uppercase tracking-widest mb-1 ${
              isDark ? 'text-indigo-300' : 'text-slate-500'
            }`}
          >
            {moduleIcon}
            <span>{moduleTitle}</span>
          </div>
          {title && (
            <h1 className={titleClass}>
              {title}
            </h1>
          )}
          {subtitle && (
            <p
              className={`text-[9px] font-mono uppercase tracking-widest font-bold mt-0.5 ${subtitle.colorClass}`}
            >
              {subtitle.text}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {headerRight}
        <button
          onClick={onClose}
          className={`w-8 h-8 flex items-center justify-center border-2 transition-colors ${
            isDark
              ? 'border-indigo-400 text-indigo-200 hover:bg-indigo-800'
              : 'border-slate-200 hover:border-slate-900 text-slate-400 hover:text-slate-900'
          }`}
          aria-label="Close"
        >
          <X size={20} />
        </button>
      </div>
    </header>
  );
};
