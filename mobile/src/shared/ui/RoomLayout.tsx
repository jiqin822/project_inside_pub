import React from 'react';
import { HelpCircle } from 'lucide-react';
import { LovedOne } from '../types/domain';
import { RoomHeader } from './RoomHeader';

interface RoomLayoutProps {
  title: string;
  /** Module title line (e.g. "MODULE: THERAPY", "MODULE: EXPERIENCE"). If not set, uses "MODULE: " + headerLabel. */
  moduleTitle?: string;
  /** Optional icon prefix in front of module title (e.g. <Terminal size={12} />) */
  moduleIcon?: React.ReactNode;
  /** Small label above title when moduleTitle not set (e.g. "Room", "Training") */
  headerLabel?: string;
  /** Optional colored subtitle (e.g. { text: "ECONOMY OF CARE", colorClass: "text-yellow-600" }) */
  subtitle?: { text: string; colorClass: string };
  /** Optional right-side content in header (e.g. Global XP) */
  headerRight?: React.ReactNode;
  /** Optional class for main title (e.g. "text-xl font-mono leading-none") */
  titleClassName?: string;
  relationship?: LovedOne;
  onBack: () => void;
  helpContent?: React.ReactNode;
  children: React.ReactNode;
  isLoading?: boolean;
  error?: string | null;
  emptyMessage?: string;
  showEmptyState?: boolean;
  /** Optional full-page grid background (matches original Love Maps / room style) */
  showGridBackground?: boolean;
  /** Optional content rendered directly below header/relationship bar; does not scroll (e.g. tab strip). */
  stickyBelowHeader?: React.ReactNode;
}

export const RoomLayout: React.FC<RoomLayoutProps> = ({
  title,
  moduleTitle: moduleTitleProp,
  moduleIcon,
  headerLabel = 'Room',
  subtitle,
  headerRight,
  titleClassName,
  relationship,
  onBack,
  helpContent,
  children,
  isLoading = false,
  error = null,
  emptyMessage,
  showEmptyState = false,
  showGridBackground = false,
  stickyBelowHeader,
}) => {
  const moduleTitle = moduleTitleProp ?? `MODULE: ${headerLabel.toUpperCase()}`;
  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden font-sans relative">
      {showGridBackground && (
        <div
          className="absolute inset-0 z-0 pointer-events-none opacity-[0.12]"
          style={{
            backgroundImage: 'linear-gradient(#94a3b8 1px, transparent 1px), linear-gradient(90deg, #94a3b8 1px, transparent 1px)',
            backgroundSize: '20px 20px',
          }}
        />
      )}
      <RoomHeader
        moduleTitle={moduleTitle}
        moduleIcon={moduleIcon}
        title={title}
        subtitle={subtitle}
        titleClassName={titleClassName}
        onClose={onBack}
        headerRight={
          <>
            {headerRight}
            {helpContent && (
              <div className="relative group">
                <button
                  className="w-8 h-8 flex items-center justify-center border-2 border-slate-200 hover:border-slate-900 text-slate-400 hover:text-slate-900 transition-colors"
                  aria-label="Help"
                >
                  <HelpCircle size={18} />
                </button>
                <div className="absolute right-0 top-full mt-2 w-64 bg-white border-2 border-slate-900 p-4 shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                  {helpContent}
                </div>
              </div>
            )}
          </>
        }
      />

      {/* Relationship Context Indicator - opaque */}
      {relationship && (
        <div className="bg-slate-100 bg-opacity-100 border-b-2 border-slate-200 px-4 py-2 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-slate-900 text-white flex items-center justify-center font-bold text-xs border-2 border-slate-900">
              {relationship.name.charAt(0)}
            </div>
            <span className="text-xs font-bold text-slate-700 uppercase">{relationship.name}</span>
            <span className="text-xs text-slate-500">•</span>
            <span className="text-xs text-slate-500">{relationship.relationship}</span>
          </div>
        </div>
      )}

      {/* Sticky area below header (e.g. tab strip) – does not scroll */}
      {stickyBelowHeader && (
        <div className="shrink-0 relative z-10 bg-white border-b border-slate-200 px-4 py-2">
          {stickyBelowHeader}
        </div>
      )}

      {/* Content - flex column; overflow-y-auto so only this area scrolls */}
      <div className="flex-1 flex flex-col min-h-0 overflow-y-auto p-4 relative z-10">
        {isLoading && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto mb-4"></div>
              <p className="text-sm text-slate-500">Loading...</p>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border-2 border-red-200 p-4 mb-4">
            <p className="text-sm font-bold text-red-800">{error}</p>
          </div>
        )}

        {!isLoading && !error && showEmptyState && emptyMessage && (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-sm font-bold text-slate-400 uppercase">{emptyMessage}</p>
            </div>
          </div>
        )}

        {!isLoading && !error && !showEmptyState && children}
      </div>
    </div>
  );
};
