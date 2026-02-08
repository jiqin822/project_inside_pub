import React, { useState, useRef, useEffect } from 'react';
import { ActivityCard, Memory, EconomyConfig, LovedOne, AddNotificationFn, ActivityMemoryItem, ScrapbookLayout, ElementScrapbookLayout, isElementScrapbookLayout } from '../../../shared/types/domain';
import { Zap, Calendar, Sparkles, BookHeart, Loader2, Camera, Gamepad2, UserPlus, Check, History, BrainCircuit, ChevronDown, ChevronUp, Bug, X, GitMerge, Plus, Save, Image as ImageIcon, Trash2, RotateCw, CheckCircle2, Circle, Palette, Users, User, MapPin, Clock } from 'lucide-react';
import { RoomLayout } from '@/src/shared/ui/RoomLayout';
import { Modal } from '@/src/shared/ui/Modal';
import { useSessionStore } from '../../../stores/session.store';
import { useRelationshipsStore } from '../../../stores/relationships.store';
import { useUiStore } from '../../../stores/ui.store';
import {
  useActivitySuggestionsMutation,
  useCompassRecommendationsMutation,
  useCompassActivityLog,
  useLogActivityInteractionMutation,
  useSendActivityInviteMutation,
  useRespondToActivityInviteMutation,
  usePlannedActivitiesQuery,
  usePendingActivityInvitesQuery,
  useSentActivityInvitesQuery,
  useActivityHistoryQuery,
  useActivityHistoryAllQuery,
  useActivityMemoriesQuery,
  useCompletePlannedActivityMutation,
  useDiscoverFeedQuery,
  useDismissDiscoverMutation,
  useWantToTryMutation,
  useMutualMatchesQuery,
  useRespondToMutualMatchMutation,
  mapCompassItemToCard,
} from '../api/activities.mutations';
import { apiService } from '../../../shared/api/apiService';
import { useQueryClient } from '@tanstack/react-query';
import { qk } from '../../../shared/api/queryKeys';
import { processImageForUpload, pickActivityImages } from '../../../shared/utils/imageUpload';

type GameRoomTab = 'discover' | 'planned' | 'memories' | 'history';

interface Props {
  xp: number;
  setXp: (xp: number) => void;
  economy: EconomyConfig;
  onExit: () => void;
  onUpdateLovedOne: (id: string, updates: Partial<LovedOne>) => void;
  onAddNotification?: AddNotificationFn;
}

/** Normalize API activity_card (snake_case or camelCase) to ActivityCard for Planned tab. */
function normalizePlannedCardToActivityCard(
  card: Record<string, unknown>,
  fallbackId: string,
  fallbackTitle: string
): ActivityCard {
  const constraints = (card.constraints as Record<string, unknown>) ?? {};
  const durationMin = constraints.duration_min as number | undefined;
  const duration = (card.duration as string) ?? (durationMin != null ? `${durationMin} mins` : '15 mins');
  const tags = (card.tags as string[]) ?? (card.vibe_tags as string[]) ?? [];
  const recInv = card.recommendedInvitee ?? card.recommended_invitee;
  const recommendedInvitee = recInv
    ? { id: (recInv as { id?: string }).id ?? '', name: (recInv as { name?: string }).name ?? 'Someone' }
    : undefined;
  const suggestedInvitees = (card.suggestedInvitees as ActivityCard['suggestedInvitees']) ?? (card.suggested_invitees as { id: string; name: string }[]) ?? [];
  const explanation = (card.explanation as string) ?? (card.suggestedReason as string) ?? undefined;
  return {
    id: (card.id as string) ?? fallbackId,
    title: (card.title as string) ?? fallbackTitle,
    description: (card.description as string) ?? (card.steps_markdown_template as string) ?? '',
    duration,
    type: ((card.type as ActivityCard['type']) ?? 'fun') as ActivityCard['type'],
    xpReward: typeof card.xpReward === 'number' ? card.xpReward : 100,
    tags: tags.length ? tags : undefined,
    suggestedInvitees: suggestedInvitees.length ? suggestedInvitees : undefined,
    explanation,
    suggestedReason: explanation,
    recommendedInvitee,
    recommendedLocation: (card.recommendedLocation as string) ?? (card.recommended_location as string) ?? undefined,
    debugPrompt: card.debugPrompt as string | undefined,
    debugResponse: card.debugResponse as string | undefined,
    debugSource: card.debugSource as string | undefined,
  };
}

/** Map planned-invite API shape to ActivityCard for reuse in ActivityCardRow. */
function inviteToActivityCard(inv: {
  invite_id: string;
  activity_title: string;
  description?: string;
  duration_min?: number;
  vibe_tags?: string[];
  recommended_location?: string | null;
}): ActivityCard {
  const durationMin = inv.duration_min ?? 30;
  const tags = Array.isArray(inv.vibe_tags) ? inv.vibe_tags : [];
  return {
    id: inv.invite_id,
    title: inv.activity_title,
    description: inv.description ?? '',
    duration: `${durationMin}m`,
    type: 'fun',
    xpReward: 50,
    tags: tags.length ? tags : undefined,
    recommendedLocation: inv.recommended_location ?? undefined,
  };
}

/** Single activity card row for Discover tab and Planned tab (invites). Logs activity_card_viewed on mount. When activity is already agreed/planned, shows Mark complete instead of Invite. For pending/sent invites, shows Accept/Decline or "Waiting for X". */
const ActivityCardRow: React.FC<{
  act: ActivityCard;
  rewardEconomy: { currencyName: string; currencySymbol: string };
  onLogView: (activityId: string) => void;
  onOpenInvitePicker: (act: ActivityCard) => void;
  onMarkComplete?: (plannedId: string, title: string) => void;
  onGenerateMoreLikeThis?: (act: ActivityCard) => void;
  onWantToTry?: (discoverFeedItemId: string) => void;
  onDismiss?: (discoverFeedItemId: string) => void;
  sendInvitePending: boolean;
  generateMorePending: boolean;
  wantToTryPending?: boolean;
  hasWantedToTry?: boolean;
  plannedId?: string | null;
  plannedTitle?: string | null;
  segmentLabel?: string;
  otherMembers: { id: string; name: string }[];
  showDebug?: boolean;
  /** When set, card is shown as pending or sent invite with From / Waiting for meta and Accept/Decline or waiting text. */
  inviteVariant?: 'pending' | 'sent';
  inviteId?: string;
  inviteFromName?: string;
  inviteToName?: string;
  onAcceptInvite?: (inviteId: string) => void;
  onDeclineInvite?: (inviteId: string) => void;
  respondInvitePending?: boolean;
}> = ({ act, rewardEconomy, onLogView, onOpenInvitePicker, onMarkComplete, onGenerateMoreLikeThis, onWantToTry, onDismiss, sendInvitePending, generateMorePending, wantToTryPending, hasWantedToTry, plannedId, plannedTitle, segmentLabel, otherMembers, showDebug, inviteVariant, inviteId, inviteFromName, inviteToName, onAcceptInvite, onDeclineInvite, respondInvitePending }) => {
  const [rationaleOpen, setRationaleOpen] = useState(false);
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const touchStartX = useRef<number | null>(null);
  const hasDebugData = !!(act.debugPrompt || act.debugResponse);
  React.useEffect(() => {
    onLogView(act.id);
  }, [act.id, onLogView]);
  const handleTouchStart = (e: React.TouchEvent) => {
    if (onDismiss && act._discoverFeedItemId) touchStartX.current = e.touches[0].clientX;
  };
  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX.current == null || !onDismiss || !act._discoverFeedItemId) return;
    const endX = e.changedTouches[0].clientX;
    if (touchStartX.current - endX > 60) onDismiss(act._discoverFeedItemId);
    touchStartX.current = null;
  };
  const inviteTargets = (act.suggestedInvitees && act.suggestedInvitees.length > 0) ? act.suggestedInvitees : otherMembers;
  const rationaleText = act.explanation || act.suggestedReason || 'Recommended for your relationship.';
  const durationLabel = typeof act.duration === 'string' && /m|mins?/i.test(act.duration) ? act.duration : `${act.duration}m`;
  return (
    <>
    <article
      className="bg-white border-2 border-slate-900 shadow-[4px_4px_0px_rgba(0,0,0,0.9)] overflow-hidden group rounded-none min-w-0"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
    >
      <div className="px-3 pt-3 pb-4 sm:px-4 sm:pt-4 sm:pb-5 relative min-w-0">
        {/* Dismiss – top-right of card (discover feed only) */}
        {act._discoverFeedItemId && onDismiss && (
          <button
            type="button"
            onClick={() => onDismiss(act._discoverFeedItemId!)}
            className="absolute top-2 right-2 sm:top-3 sm:right-3 inline-flex items-center justify-center w-7 h-7 sm:w-8 sm:h-8 rounded-none text-slate-500 hover:text-slate-700 transition-colors z-10"
            title="Dismiss (swipe left)"
            aria-label="Dismiss"
          >
            <X size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0" />
          </button>
        )}
        {/* Tags row – Best Fit + vibe pills + XP (Game Room Hub style); extra right padding when Dismiss is present */}
        <div className={`flex flex-wrap items-center justify-between gap-1.5 sm:gap-2 mb-1.5 sm:mb-2 ${act._discoverFeedItemId && onDismiss ? 'pr-10 sm:pr-12' : ''}`}>
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 min-w-0">
            {segmentLabel && (
              <span className="px-1.5 py-0.5 sm:px-2 sm:py-1 bg-emerald-500 text-white text-[8px] sm:text-[10px] font-black uppercase tracking-tighter">
                {segmentLabel}
              </span>
            )}
            {act.tags && act.tags.length > 0 && (
              act.tags.slice(0, 4).map(tag => (
                <span key={tag} className={`px-1.5 py-0.5 sm:px-2 sm:py-1 text-[8px] sm:text-[10px] font-bold uppercase border border-black/10 bg-white/90 text-slate-900 ${VIBE_PILL_CLASS[tag] ?? defaultVibePillClass}`}>
                  {tag}
                </span>
              ))
            )}
          </div>
          <div className="flex items-center gap-1 sm:gap-1.5 text-orange-600 font-bold text-[8px] sm:text-[10px] uppercase shrink-0">
            <Zap size={12} className="fill-orange-600 shrink-0 sm:w-3.5 sm:h-3.5 w-3 h-3" />
            <span>{act.xpReward} {rewardEconomy.currencySymbol}</span>
          </div>
        </div>
        {/* Title – featured card style, responsive */}
        <h3 className="text-lg sm:text-xl md:text-2xl font-black uppercase leading-[0.9] mb-1.5 sm:mb-2 tracking-tighter text-slate-900 min-w-0">{act.title}</h3>
        {/* Meta row – From / Waiting for / Recommended, Location, Duration; responsive gaps & text */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 sm:gap-x-6 sm:gap-y-2 mb-2 sm:mb-3 border-b border-black/5 pb-2 sm:pb-3 min-w-0">
          {(inviteFromName || inviteToName || act.recommendedInvitee || act.recommendedLocation || durationLabel) && (
            <>
              {(inviteFromName || inviteToName || act.recommendedInvitee) && (
                <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                  <User size={14} className="text-slate-500 shrink-0 w-3.5 h-3.5 sm:w-[18px] sm:h-[18px]" />
                  <div className="flex flex-col min-w-0">
                    <span className="text-[8px] sm:text-[9px] uppercase font-bold text-slate-500 tracking-widest">
                      {inviteFromName ? 'From' : inviteToName ? 'Waiting for' : 'Recommended'}
                    </span>
                    <span className="text-[10px] sm:text-xs font-black uppercase text-slate-900 truncate">
                      {inviteFromName ?? inviteToName ?? act.recommendedInvitee?.name ?? ''}
                    </span>
                  </div>
                </div>
              )}
              {act.recommendedLocation && (
                <div className={`flex items-center gap-1.5 sm:gap-2 min-w-0 ${(inviteFromName || inviteToName || act.recommendedInvitee) ? 'border-l border-black/10 pl-3 sm:pl-6' : ''}`}>
                  <MapPin size={14} className="text-slate-500 shrink-0 w-3.5 h-3.5 sm:w-[18px] sm:h-[18px]" />
                  <div className="flex flex-col min-w-0">
                    <span className="text-[8px] sm:text-[9px] uppercase font-bold text-slate-500 tracking-widest">Location</span>
                    <span className="text-[10px] sm:text-xs font-black uppercase text-slate-900 truncate">{act.recommendedLocation}</span>
                  </div>
                </div>
              )}
              <div className={`flex items-center gap-1.5 sm:gap-2 min-w-0 ${(inviteFromName || inviteToName || act.recommendedInvitee || act.recommendedLocation) ? 'border-l border-black/10 pl-3 sm:pl-6' : ''}`}>
                <Clock size={14} className="text-slate-500 shrink-0 w-3.5 h-3.5 sm:w-[18px] sm:h-[18px]" />
                <div className="flex flex-col min-w-0">
                  <span className="text-[8px] sm:text-[9px] uppercase font-bold text-slate-500 tracking-widest">Duration</span>
                  <span className="text-[10px] sm:text-xs font-black uppercase text-slate-900">{durationLabel}</span>
                </div>
              </div>
            </>
          )}
          {!inviteFromName && !inviteToName && !act.recommendedInvitee && !act.recommendedLocation && (
            <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
              <Clock size={14} className="text-slate-500 shrink-0 w-3.5 h-3.5 sm:w-[18px] sm:h-[18px]" />
              <div className="flex flex-col min-w-0">
                <span className="text-[8px] sm:text-[9px] uppercase font-bold text-slate-500 tracking-widest">Duration</span>
                <span className="text-[10px] sm:text-xs font-black uppercase text-slate-900">{durationLabel}</span>
              </div>
            </div>
          )}
        </div>
        {/* Description – responsive text */}
        <p className="text-xs sm:text-sm text-slate-900 leading-snug mb-2 sm:mb-3 font-medium min-w-0">{act.description}</p>
        {/* Kai's rationale – in flow between description and actions (hidden for invite cards) */}
        {!inviteVariant && (
        <div className="mb-2 sm:mb-3 min-w-0">
          <button
            type="button"
            onClick={() => setRationaleOpen(!rationaleOpen)}
            className="flex items-center gap-1 sm:gap-1.5 border border-teal-500 bg-white px-2 py-0.5 sm:px-3 sm:py-1 shadow-sm text-teal-600 hover:bg-teal-50 transition-colors rounded-none"
          >
            <BrainCircuit size={12} className="shrink-0 w-3 h-3 sm:w-3.5 sm:h-3.5" />
            <span className="text-[8px] sm:text-[10px] font-black uppercase tracking-widest">Kai&apos;s rationale</span>
            {rationaleOpen ? <ChevronUp size={10} className="w-2.5 h-2.5 sm:w-3 sm:h-3" /> : <ChevronDown size={10} className="w-2.5 h-2.5 sm:w-3 sm:h-3" />}
          </button>
          {rationaleOpen && (
            <div className="mt-2 bg-teal-50/80 p-2 sm:p-3 border border-teal-100 rounded-none min-w-0">
              <div className="flex gap-1.5 sm:gap-2 mb-2 sm:mb-3">
                <span className="text-teal-500 shrink-0 text-base sm:text-lg font-serif leading-none">&quot;</span>
                <p className="text-[10px] sm:text-xs text-teal-900/90 italic font-medium leading-snug min-w-0">&quot;{rationaleText}&quot;</p>
              </div>
              {onGenerateMoreLikeThis && (
                <div className="flex justify-end">
                  <button
                    onClick={() => onGenerateMoreLikeThis(act)}
                    disabled={generateMorePending}
                    className="py-2 sm:py-2.5 px-3 sm:px-4 border border-slate-900 text-slate-900 font-black uppercase text-[8px] sm:text-[10px] tracking-widest hover:bg-slate-50 transition-colors flex items-center justify-center gap-1 sm:gap-1.5 rounded-none disabled:opacity-50"
                  >
                    {generateMorePending ? <Loader2 size={12} className="animate-spin w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" /> : <Sparkles size={12} className="w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" />}
                    More Like This
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
        )}
        {/* Actions – Want to try (discover feed), Invite/Mark complete, Accept/Decline (invite), Dismiss (discover feed) */}
        <div className="flex flex-wrap gap-1.5 sm:gap-2 min-w-0 items-center">
          {act._discoverFeedItemId && onWantToTry && (
            <button
              type="button"
              onClick={() => onWantToTry(act._discoverFeedItemId!)}
              disabled={wantToTryPending}
              className={`py-2 sm:py-2.5 px-3 sm:px-4 font-black uppercase text-[8px] sm:text-[10px] tracking-widest flex items-center justify-center gap-1 sm:gap-1.5 rounded-none shrink-0 transition-colors ${
                hasWantedToTry
                  ? 'bg-yellow-600 text-white border border-yellow-600 cursor-default'
                  : 'border border-yellow-600 text-yellow-600 hover:bg-yellow-50 disabled:opacity-50'
              }`}
            >
              {wantToTryPending ? <Loader2 size={12} className="animate-spin w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" /> : hasWantedToTry ? <Check size={12} className="w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" /> : <Sparkles size={12} className="w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" />}
              {hasWantedToTry ? 'Want to try ✓' : 'Want to try'}
            </button>
          )}
          {inviteVariant === 'pending' && inviteId && onAcceptInvite && onDeclineInvite ? (
            <>
              <button
                type="button"
                onClick={() => onAcceptInvite(inviteId)}
                disabled={respondInvitePending}
                className="flex-1 py-2 sm:py-2.5 bg-green-600 text-white font-black uppercase text-[8px] sm:text-[10px] tracking-widest shadow-lg shadow-green-100 hover:bg-green-700 transition-all flex items-center justify-center gap-1 sm:gap-1.5 rounded-none disabled:opacity-50 min-w-0"
              >
                <Check size={12} className="w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" /> Accept
              </button>
              <button
                type="button"
                onClick={() => onDeclineInvite(inviteId)}
                disabled={respondInvitePending}
                className="flex-1 py-2 sm:py-2.5 bg-slate-500 text-white font-black uppercase text-[8px] sm:text-[10px] tracking-widest border-2 border-slate-700 hover:bg-slate-600 transition-all flex items-center justify-center gap-1 sm:gap-1.5 rounded-none disabled:opacity-50 min-w-0"
              >
                Decline
              </button>
            </>
          ) : inviteVariant === 'sent' && inviteToName ? (
            <p className="text-[10px] sm:text-xs text-slate-600 font-medium italic py-2 sm:py-2.5">Waiting for {inviteToName}</p>
          ) : plannedId && plannedTitle && onMarkComplete ? (
            <button
              type="button"
              onClick={() => onMarkComplete(plannedId, plannedTitle)}
              className="flex-1 py-2 sm:py-2.5 bg-indigo-600 text-white font-black uppercase text-[8px] sm:text-[10px] tracking-widest shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition-all flex items-center justify-center gap-1 sm:gap-1.5 rounded-none min-w-0"
            >
              <CheckCircle2 size={12} className="w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" /> Mark complete
            </button>
          ) : inviteTargets.length > 0 ? (
            <button
              type="button"
              onClick={() => onOpenInvitePicker(act)}
              disabled={sendInvitePending}
              className="flex-1 py-2 sm:py-2.5 bg-indigo-600 text-white font-black uppercase text-[8px] sm:text-[10px] tracking-widest shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition-all flex items-center justify-center gap-1 sm:gap-1.5 rounded-none disabled:opacity-50 min-w-0"
            >
              <UserPlus size={12} className="w-3 h-3 sm:w-3.5 sm:h-3.5 shrink-0" /> Invite
            </button>
          ) : (
            <p className="text-[8px] sm:text-[10px] text-slate-500 italic py-2 sm:py-2.5">Add a relationship to invite someone.</p>
          )}
        </div>
        {/* Debug – bottom-right of card (only when showDebug) */}
        {showDebug && (
          <button
            type="button"
            onClick={() => setDebugModalOpen(true)}
            className="absolute bottom-2 right-2 sm:bottom-3 sm:right-3 inline-flex items-center justify-center w-7 h-7 sm:w-8 sm:h-8 rounded-none border border-slate-200 bg-white/90 text-slate-500 hover:text-slate-700 hover:border-slate-300 transition-colors"
            title={hasDebugData ? 'View LLM prompt/response' : 'No LLM data'}
            aria-label="Debug"
          >
            <Bug size={14} className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
          </button>
        )}
      </div>
    </article>
    <Modal isOpen={debugModalOpen} onClose={() => setDebugModalOpen(false)} title="LLM Debug" size="xl">
        {hasDebugData ? (
          <div className="space-y-4 p-4">
            <div>
              <h4 className="text-xs font-bold uppercase text-slate-600 mb-1">Prompt</h4>
              <pre className="bg-slate-100 border border-slate-200 p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap break-words">
                {act.debugPrompt ?? '—'}
              </pre>
            </div>
            <div>
              <h4 className="text-xs font-bold uppercase text-slate-600 mb-1">Response</h4>
              <pre className="bg-slate-100 border border-slate-200 p-3 text-xs font-mono overflow-auto max-h-48 whitespace-pre-wrap break-words">
                {act.debugResponse ?? '—'}
              </pre>
            </div>
          </div>
        ) : (
          <div className="space-y-4 p-4">
            <div className="text-sm text-slate-700">
              <p className="font-semibold text-slate-800 mb-1">Where this activity comes from</p>
              <p className="text-slate-600">
                {act.debugSource === 'seed_fallback'
                  ? 'Seed fallback: curated list used when the LLM was not used or unavailable (e.g. no API key or LLM returned empty).'
                  : act.debugSource === 'llm'
                    ? 'LLM-generated (prompt/response not captured for this card).'
                    : act.debugSource === 'backend' || act._discoverFeedItemId
                      ? 'Backend recommendation (personalized).'
                      : 'Client fallback: hardcoded list or client-side Gemini fallback. No backend source (Compass/Coach) for this card.'}
              </p>
            </div>
            <p className="text-xs font-bold uppercase text-slate-500 mt-2">Card data</p>
            <pre className="bg-slate-100 border border-slate-200 p-3 text-xs font-mono overflow-auto max-h-72 whitespace-pre-wrap break-words">
              {JSON.stringify(
                {
                  id: act.id,
                  title: act.title,
                  description: act.description,
                  duration: act.duration,
                  type: act.type,
                  xpReward: act.xpReward,
                  tags: act.tags,
                  explanation: act.explanation,
                  suggestedReason: act.suggestedReason,
                  recommendedInvitee: act.recommendedInvitee,
                  recommendedLocation: act.recommendedLocation,
                  suggestedInvitees: act.suggestedInvitees,
                },
                null,
                2
              )}
            </pre>
          </div>
        )}
      </Modal>
    </>
  );
};

/** Vibe chips for Discover tab – match Game Room Activity Hub design (Any + Silly, Nostalgic, Intimate, Calm, then rest). */
const VIBE_CHIPS = [
  { label: 'Silly', value: 'silly', unselected: 'bg-white text-yellow-700 border border-yellow-200 hover:bg-yellow-50', selected: 'bg-yellow-600 text-white border-yellow-600', pill: 'bg-white/90 text-slate-900 border border-black/10' },
  { label: 'Nostalgic', value: 'nostalgic', unselected: 'bg-white text-orange-700 border border-orange-200 hover:bg-orange-50', selected: 'bg-orange-600 text-white border-orange-600', pill: 'bg-white/90 text-slate-900 border border-black/10' },
  { label: 'Intimate', value: 'intimate', unselected: 'bg-white text-rose-700 border border-rose-200 hover:bg-rose-50', selected: 'bg-rose-600 text-white border-rose-600', pill: 'bg-white/90 text-slate-900 border border-black/10' },
  { label: 'Calm', value: 'calm', unselected: 'bg-white text-blue-700 border border-blue-200 hover:bg-blue-50', selected: 'bg-blue-600 text-white border-blue-600', pill: 'bg-white/90 text-slate-900 border border-black/10' },
  { label: 'Repair', value: 'repair', unselected: 'bg-white text-emerald-700 border border-emerald-200 hover:bg-emerald-50', selected: 'bg-emerald-600 text-white border-emerald-600', pill: 'bg-emerald-100 text-emerald-800' },
  { label: 'Creative', value: 'creative', unselected: 'bg-white text-violet-700 border border-violet-200 hover:bg-violet-50', selected: 'bg-violet-600 text-white border-violet-600', pill: 'bg-violet-100 text-violet-800' },
  { label: 'Family', value: 'family', unselected: 'bg-white text-teal-700 border border-teal-200 hover:bg-teal-50', selected: 'bg-teal-600 text-white border-teal-600', pill: 'bg-teal-100 text-teal-800' },
] as const;

const VIBE_PILL_CLASS: Record<string, string> = Object.fromEntries(VIBE_CHIPS.map((c) => [c.value, c.pill]));
const defaultVibePillClass = 'bg-slate-100 text-slate-700';

/** Feeling/vibe options for scrapbook "Log Memory" form (Vibe Check); label sent to API (lowercase). */
const FEELINGS_WITH_EMOJI = [
  { label: 'Happy', icon: '😄', value: 'happy' },
  { label: 'Loved', icon: '🥰', value: 'loved' },
  { label: 'Excited', icon: '🤩', value: 'excited' },
  { label: 'Relaxed', icon: '😌', value: 'relaxed' },
  { label: 'Playful', icon: '😜', value: 'playful' },
  { label: 'Connected', icon: '🤝', value: 'connected' },
] as const;

/** Replace {{USER_IMAGE_0}}, {{USER_IMAGE_1}}, etc. in LLM HTML with actual image URLs. */
function processHtmlContent(html: string, imageUrls: string[]): string {
  if (!html) return '';
  let processed = html;
  imageUrls.forEach((url, idx) => {
    const regex = new RegExp(`\\{\\{USER_IMAGE_${idx}\\}\\}|USER_IMAGE_${idx}`, 'g');
    processed = processed.replace(regex, url);
  });
  processed = processed.replace(/\{\{USER_IMAGE_\d+\}\}|USER_IMAGE_\d+/g, 'https://via.placeholder.com/300?text=No+Image');
  return processed;
}

/** Wraps scrapbook HTML and hides broken sticker images, logging errors to console. */
function ScrapbookHtml({
  html,
  className,
  style,
}: {
  html: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !html) return;
    const stickers = el.querySelectorAll('img.sticker');
    const cleanups: (() => void)[] = [];
    stickers.forEach((img) => {
      const imgEl = img as HTMLImageElement;
      const hideAndLog = (reason: string) => {
        imgEl.style.display = 'none';
        const srcPreview = imgEl.src ? `${imgEl.src.slice(0, 60)}...` : '(no src)';
        console.error('[Scrapbook] Sticker failed to load:', reason, srcPreview);
      };
      if (!imgEl.src || imgEl.src.trim() === '') {
        hideAndLog('missing or empty src');
        return;
      }
      const onError = () => hideAndLog('image load error');
      imgEl.addEventListener('error', onError);
      cleanups.push(() => imgEl.removeEventListener('error', onError));
    });
    return () => cleanups.forEach((c) => c());
  }, [html]);
  return (
    <div
      ref={ref}
      className={className}
      style={style}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** Render element-based scrapbook layout (inside parity). imageUrls[i] = URL for image index i. */
function renderElementScrapbookLayout(
  layout: ElementScrapbookLayout,
  imageUrls: string[],
) {
  const containerStyle: React.CSSProperties = {
    backgroundColor: layout.bgStyle.color,
    backgroundImage: layout.bgStyle.texture === 'dot-grid'
      ? 'radial-gradient(#cbd5e1 1px, transparent 1px)'
      : layout.bgStyle.texture === 'paper'
        ? 'url("https://www.transparenttextures.com/patterns/cardboard-flat.png")'
        : 'none',
    backgroundSize: '20px 20px',
  };
  return (
    <div
      className="relative overflow-hidden w-full shadow-lg transition-all hover:shadow-xl border-4 border-white aspect-[3/4]"
      style={containerStyle}
    >
      {layout.elements.map((el, i) => {
        const commonStyle: React.CSSProperties = {
          position: 'absolute',
          top: el.style.top,
          left: el.style.left,
          width: el.style.width || 'auto',
          transform: `rotate(${el.style.rotation})`,
          zIndex: el.style.zIndex,
          textAlign: (el.style.textAlign as 'left' | 'center' | 'right') || 'left',
          fontFamily: el.style.fontFamily === 'handwritten' ? 'cursive' : el.style.fontFamily,
          fontSize: el.style.fontSize,
          color: el.style.color,
          backgroundColor: el.style.background,
          borderRadius: el.style.borderRadius,
          boxShadow: el.style.boxShadow || '2px 2px 5px rgba(0,0,0,0.1)',
        };
        if (el.type === 'text') {
          return (
            <div key={i} style={commonStyle} className="p-2">
              {el.content}
            </div>
          );
        }
        if (el.type === 'image') {
          const imgIndex = parseInt(el.content, 10);
          const src = imageUrls[imgIndex];
          if (!src) return null;
          return (
            <div key={i} style={commonStyle} className="bg-white p-2">
              <div className="w-full h-full overflow-hidden aspect-square">
                <img src={src} alt="Memory" className="w-full h-full object-cover" />
              </div>
            </div>
          );
        }
        if (el.type === 'sticker' || el.type === 'doodle') {
          return (
            <div key={i} style={{ ...commonStyle, boxShadow: 'none', background: 'transparent' }} className="text-4xl pointer-events-none select-none">
              {el.content}
            </div>
          );
        }
        if (el.type === 'tape') {
          return (
            <div key={i} style={{ ...commonStyle, height: '15px', opacity: 0.8 }} />
          );
        }
        return null;
      })}
    </div>
  );
}

const OUTCOME_TAG_OPTIONS = ['fun', 'reconnect', 'quick', 'romantic', 'silly'] as const;

const PHANTOM_CARD_COUNT = 6;

/** Skeleton card matching ActivityCardRow (Game Room Hub sharp style); used while recommendations load. */
const PhantomCard: React.FC = () => (
  <div className="relative bg-white border-2 border-slate-900 p-6 shadow-[4px_4px_0px_rgba(0,0,0,0.9)] animate-pulse rounded-none">
    <div className="absolute inset-0 flex items-center justify-center z-10 bg-white/70">
      <Loader2 size={24} className="animate-spin text-slate-400" />
    </div>
    <div className="flex justify-between items-start mb-4 gap-2">
      <div className="flex flex-wrap gap-2">
        <span className="h-5 w-14 bg-slate-200" />
        <span className="h-5 w-16 bg-slate-200" />
      </div>
      <span className="h-5 w-20 bg-slate-200" />
    </div>
    <div className="h-8 w-3/4 bg-slate-200 mb-4" />
    <div className="flex gap-6 mb-6 border-b border-black/5 pb-4">
      <span className="h-4 w-24 bg-slate-100" />
      <span className="h-4 w-20 bg-slate-100" />
      <span className="h-4 w-16 bg-slate-100" />
    </div>
    <div className="space-y-2 mb-8">
      <div className="h-4 w-full bg-slate-100" />
      <div className="h-4 w-4/5 bg-slate-100" />
    </div>
    <div className="flex gap-3">
      <div className="flex-1 h-12 bg-slate-200" />
      <div className="flex-1 h-12 bg-slate-200" />
    </div>
  </div>
);

export const ActivitiesScreen: React.FC<Props> = ({ xp, setXp, economy, onExit, onUpdateLovedOne, onAddNotification }) => {
  const { me: user } = useSessionStore();
  const { relationships } = useRelationshipsStore();
  /** Use relationshipId (backend relationship id); .id on LovedOne is the other member's user id and causes 403. */
  const firstRelationshipId = relationships?.[0]?.relationshipId;

  const [memories, setMemories] = useState<Memory[]>([
    { id: '1', activityTitle: 'Sunset Walk', date: Date.now() - 86400000 * 2, note: 'The sky was purple!', type: 'romantic' },
    { id: '2', activityTitle: 'Cooked Pasta', date: Date.now() - 86400000 * 5, note: 'We burned the sauce lol', type: 'fun' }
  ]);
  const [completeModal, setCompleteModal] = useState<{ plannedId: string | null; title: string } | null>(null);
  const [completeActivityTitle, setCompleteActivityTitle] = useState('');
  const [isAddingMemory, setIsAddingMemory] = useState(false);
  const [magicDesignMemId, setMagicDesignMemId] = useState<string | null>(null);
  const [generatedLayout, setGeneratedLayout] = useState<ScrapbookLayout | null>(null);
  const [generatedOptionsFromCard, setGeneratedOptionsFromCard] = useState<ElementScrapbookLayout[] | null>(null);
  const [generatedHtmlFromCard, setGeneratedHtmlFromCard] = useState<string | null>(null);
  const [scrapbookDebugPrompt, setScrapbookDebugPrompt] = useState<string | null>(null);
  const [scrapbookDebugResponse, setScrapbookDebugResponse] = useState<string | null>(null);
  const [scrapbookDebugModalOpen, setScrapbookDebugModalOpen] = useState(false);
  const [selectedOptionIndexFromCard, setSelectedOptionIndexFromCard] = useState(0);
  const [isGeneratingLayout, setIsGeneratingLayout] = useState(false);
  const [saveScrapbookPending, setSaveScrapbookPending] = useState(false);
  const [completeFeeling, setCompleteFeeling] = useState<string | null>(null);
  const [completeNotes, setCompleteNotes] = useState('');
  const [completeFiles, setCompleteFiles] = useState<File[]>([]);
  const completeFileInputRef = useRef<HTMLInputElement>(null);
  const [selectedVibe, setSelectedVibe] = useState<string | null>(null);
  const [durationMaxMinutes, setDurationMaxMinutes] = useState<number | null>(null);
  const [completeCardModal, setCompleteCardModal] = useState<ActivityCard | null>(null);
  const [completeCardNote, setCompleteCardNote] = useState('');
  const [completeCardRating, setCompleteCardRating] = useState<number | null>(null);
  const [completeCardTags, setCompleteCardTags] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<GameRoomTab>('discover');
  const [completeFileCaptions, setCompleteFileCaptions] = useState<Record<number, string>>({});
  const [completeParticipants, setCompleteParticipants] = useState<string[]>([]);
  const [generatedOptionsFromForm, setGeneratedOptionsFromForm] = useState<ElementScrapbookLayout[] | null>(null);
  const [selectedOptionIndexFromForm, setSelectedOptionIndexFromForm] = useState(0);
  const [isGeneratingLayoutFromForm, setIsGeneratingLayoutFromForm] = useState(false);
  const [invitePicker, setInvitePicker] = useState<{ act: ActivityCard; inviteTargets: { id: string; name: string }[] } | null>(null);
  const [invitePickerSelected, setInvitePickerSelected] = useState<Set<string>>(new Set());
  /** Discover feed item ids the current user has clicked "Want to try" this session (toggled on card). */
  const [wantedDiscoverFeedItemIds, setWantedDiscoverFeedItemIds] = useState<Set<string>>(new Set());
  /** Stops initial-load spinner after done or timeout so we never spin forever. */
  const [initialLoading, setInitialLoading] = useState(false);

  const activitiesOpenToTab = useUiStore((s) => s.activitiesOpenToTab);
  const setActivitiesOpenToTab = useUiStore((s) => s.setActivitiesOpenToTab);

  useEffect(() => {
    if (activitiesOpenToTab === 'planned') {
      setActiveTab('planned');
      setActivitiesOpenToTab(null);
    }
  }, [activitiesOpenToTab, setActivitiesOpenToTab]);

  const compassMutation = useCompassRecommendationsMutation();
  const coachMutation = useActivitySuggestionsMutation();
  const compassLog = useCompassActivityLog(firstRelationshipId ?? undefined);
  const logInteractionMutation = useLogActivityInteractionMutation();
  const sendInviteMutation = useSendActivityInviteMutation();
  const respondInviteMutation = useRespondToActivityInviteMutation();
  const completeMutation = useCompletePlannedActivityMutation();
  const discoverFeedQuery = useDiscoverFeedQuery(firstRelationshipId ?? undefined);
  const dismissDiscoverMutation = useDismissDiscoverMutation();
  const wantToTryMutation = useWantToTryMutation();
  const mutualMatchesQuery = useMutualMatchesQuery(firstRelationshipId ?? undefined);
  const respondMutualMatchMutation = useRespondToMutualMatchMutation();

  // Show discover feed oldest-first so refresh appends new activities at the bottom instead of replacing the visible set
  const discoverActivities = React.useMemo(() => {
    const raw = discoverFeedQuery.data ?? [];
    return raw.length > 0 ? [...raw].reverse() : raw;
  }, [discoverFeedQuery.data]);
  const loading = compassMutation.isPending || coachMutation.isPending || discoverFeedQuery.isLoading || discoverFeedQuery.isRefetching;

  /** Other members of the selected relationship (for suggestedInvitees, plan: client-derived). */
  const otherMembers = relationships?.length
    ? relationships.map((r) => ({ id: r.id, name: r.name }))
    : (user?.lovedOnes?.map((l) => ({ id: l.id, name: l.name })) ?? []);
  /** Server-sourced balance and economy for header (first relationship from market API). */
  const firstRelationship = relationships?.[0];
  const headerBalance = firstRelationship?.balance ?? 0;
  const headerEconomy = firstRelationship?.economy ?? economy;
  const queryClient = useQueryClient();
  const plannedQuery = usePlannedActivitiesQuery(firstRelationshipId ?? undefined);
  const pendingInvitesQuery = usePendingActivityInvitesQuery();
  const sentInvitesQuery = useSentActivityInvitesQuery();
  const historyQuery = useActivityHistoryQuery(firstRelationshipId ?? undefined);
  const historyAllQuery = useActivityHistoryAllQuery(firstRelationshipId ?? undefined);
  const memoriesQuery = useActivityMemoriesQuery(firstRelationshipId ?? undefined);
  const plannedActivities = (plannedQuery.data as any[]) ?? [];
  const pendingInvites = (pendingInvitesQuery.data as any[]) ?? [];
  const sentInvites = (sentInvitesQuery.data as any[]) ?? [];
  const historyAllItems = (historyAllQuery.data as any[]) ?? [];
  const memoriesItems = (memoriesQuery.data as any[]) ?? [];
  const historyItems = (historyQuery.data as any[]) ?? [];
  const displayedMemories: Memory[] = firstRelationshipId && historyItems.length > 0
    ? historyItems.map((h: any) => ({
        id: h.id,
        activityTitle: h.activity_title ?? h.activity_template_id,
        date: h.completed_at ? new Date(h.completed_at).getTime() : (h.started_at ? new Date(h.started_at).getTime() : Date.now()),
        note: h.notes_text ?? '',
        type: 'fun' as const,
      }))
    : memories;

  // Discover tab uses useDiscoverFeedQuery; Refresh calls recommendations then refetches discover feed.

  if (!user) {
    return null;
  }

  const showDebugPref = user?.preferences?.showDebug;
  const showDebug = showDebugPref !== undefined ? showDebugPref : (typeof localStorage !== 'undefined' ? localStorage.getItem('inside_show_debug') !== 'false' : true);
  /** App-wide reward currency for activities (header badge + card XP). */
  const rewardEconomy = { currencyName: 'Tickets', currencySymbol: '🎟️' } as const;

  const parseDurationMins = (d: string): number => {
    const m = d.match(/(\d+)\s*mins?/i) || d.match(/(\d+)/);
    return m ? parseInt(m[1], 10) : 30;
  };

  const filteredActivities = React.useMemo(() => {
    if (!selectedVibe) return discoverActivities;
    return discoverActivities.filter((act) => act.tags?.includes(selectedVibe));
  }, [discoverActivities, selectedVibe]);

  const activitiesWithLabels = React.useMemo(() => {
    if (filteredActivities.length === 0) return [];
    const labels: ('Best fit' | 'Easiest' | 'Most novel')[] = ['Best fit', 'Easiest', 'Most novel'];
    return filteredActivities.map((act, i) => ({
      act,
      label: i < 3 ? labels[i] : undefined as string | undefined,
    }));
  }, [filteredActivities]);

  const handleGenerateQuests = async () => {
    try {
      const excludeTitles = discoverActivities.length > 0 ? discoverActivities.map((a) => a.title).filter(Boolean) : undefined;
      if (firstRelationshipId) {
        try {
          await compassMutation.mutateAsync({
            relationshipId: firstRelationshipId,
            otherMembers,
            options: {
              limit: 15,
              vibeTags: selectedVibe ? [selectedVibe] : undefined,
              durationMaxMinutes: durationMaxMinutes ?? undefined,
              useLlm: true,
              debug: showDebug,
              ...(excludeTitles?.length ? { excludeTitles } : {}),
            },
          });
        } catch (e) {
          console.warn('Compass recommendations failed, trying coach:', e);
          await coachMutation.mutateAsync({ relationshipId: firstRelationshipId, debug: showDebug }).catch(() => {});
        }
      }
    } catch (e) {
      console.error(e);
      onAddNotification?.('system', 'Refresh failed', 'Could not refresh activities right now.');
    } finally {
      // Always refresh the activity list from the server so the UI updates
      if (firstRelationshipId) {
        queryClient.invalidateQueries({ queryKey: qk.discoverFeed(firstRelationshipId) });
        await discoverFeedQuery.refetch();
      }
    }
  };

  const handleGenerateMoreLikeThis = async (act: ActivityCard) => {
    if (!firstRelationshipId) return;
    try {
      await compassMutation.mutateAsync({
        relationshipId: firstRelationshipId,
        otherMembers,
        options: { limit: 15, similarToActivityId: act.id, vibeTags: selectedVibe ? [selectedVibe] : undefined, durationMaxMinutes: durationMaxMinutes ?? undefined, useLlm: true, debug: showDebug },
      });
      await discoverFeedQuery.refetch();
    } catch (e) {
      console.warn('Generate more like this failed:', e);
      alert('Could not generate more like this right now.');
    }
  };

  const handleDismissDiscover = (discoverFeedItemId: string) => {
    if (!firstRelationshipId) return;
    dismissDiscoverMutation.mutate(
      { relationshipId: firstRelationshipId, discoverFeedItemId },
      { onSuccess: () => onAddNotification?.('system', 'Dismissed', 'Card removed from your feed.') }
    );
  };

  const handleWantToTry = (discoverFeedItemId: string) => {
    if (!firstRelationshipId) return;
    wantToTryMutation.mutate(
      { relationshipId: firstRelationshipId, discoverFeedItemId },
      {
        onSuccess: (data) => {
          setWantedDiscoverFeedItemIds((prev) => new Set(prev).add(discoverFeedItemId));
          if (data?.mutual_match_id) {
            onAddNotification?.('activity', 'You both want to try!', 'Accept above to plan it.');
            mutualMatchesQuery.refetch();
          }
        },
      }
    );
  };

  // Log "viewed" once per card when Compass-sourced (plan: activity_card_viewed)
  const cardViewedRef = useRef<Set<string>>(new Set());
  const logCardViewedIfNeeded = (activityId: string) => {
    if (cardViewedRef.current.has(activityId)) return;
    cardViewedRef.current.add(activityId);
    compassLog.logCardViewed(activityId).catch(() => {});
  };

  const handleInvite = async (act: ActivityCard, inviteeId: string) => {
    if (!firstRelationshipId || !act.id) return;
    try {
      await sendInviteMutation.mutateAsync({
        relationshipId: firstRelationshipId,
        activityTemplateId: act.id,
        inviteeUserId: inviteeId,
        cardSnapshot: { ...act },
      });
      logInteractionMutation.mutate({
        relationshipId: firstRelationshipId,
        suggestionId: act.id,
        action: 'invite_sent',
      });
      onAddNotification?.('system', 'Invite sent', `Activity invite sent for ${act.title}.`);
    } catch (e) {
      console.error(e);
      alert('Failed to send invite.');
    }
  };

  const openInvitePicker = (act: ActivityCard) => {
    const inviteTargets = (act.suggestedInvitees && act.suggestedInvitees.length > 0) ? act.suggestedInvitees : otherMembers;
    setInvitePicker({ act, inviteTargets });
    const initialSelected = new Set<string>();
    if (act.recommendedInvitee?.id && inviteTargets.some((t) => t.id === act.recommendedInvitee!.id)) {
      initialSelected.add(act.recommendedInvitee.id);
    }
    setInvitePickerSelected(initialSelected);
  };

  const toggleInvitePickerSelection = (id: string) => {
    setInvitePickerSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const sendInvitePickerInvites = async () => {
    if (!invitePicker || invitePickerSelected.size === 0) return;
    const { act } = invitePicker;
    for (const id of invitePickerSelected) {
      await handleInvite(act, id);
    }
    setInvitePicker(null);
    setInvitePickerSelected(new Set());
  };

  const handleRespondInvite = async (inviteId: string, accept: boolean) => {
    try {
      await respondInviteMutation.mutateAsync({ inviteId, accept });
      if (accept) onAddNotification?.('system', 'You\'re in!', 'Added to Planned.');
      pendingInvitesQuery.refetch();
    } catch (e) {
      console.error(e);
      alert(accept ? 'Failed to accept.' : 'Failed to decline.');
    }
  };

  const MEMORY_MAX_BYTES = 5 * 1024 * 1024;

  const handleCompletePlanned = async () => {
    if (!completeModal) return;
    const isStandalone = completeModal.plannedId === null;
    const relationshipId = firstRelationshipId;
    if (isStandalone && !relationshipId) {
      onAddNotification?.('system', 'Missing relationship', 'Please select a relationship before logging a memory.');
      return;
    }
    const urls: string[] = [];
    const memoryEntries: { url: string; caption?: string }[] = [];
    try {
      for (let i = 0; i < completeFiles.length; i++) {
        const file = completeFiles[i];
        if (file.size > MEMORY_MAX_BYTES) {
          onAddNotification?.('system', 'File too large', `"${file.name}" is over 5MB. Please choose a smaller image.`);
          return;
        }
        let res;
        try {
          res = isStandalone && relationshipId
            ? await apiService.uploadRelationshipMemory(relationshipId, file)
            : await apiService.uploadActivityMemory(completeModal.plannedId as string, file);
        } catch (uploadErr: unknown) {
          const msg = uploadErr instanceof Error ? uploadErr.message : `"${file.name}" could not be uploaded.`;
          onAddNotification?.('system', 'Upload failed', msg);
          return;
        }
        const data = res.data as { url?: string };
        if (data?.url) {
          urls.push(data.url);
          memoryEntries.push({ url: data.url, caption: completeFileCaptions[i]?.trim() || undefined });
        }
      }
      if (isStandalone && relationshipId) {
        const activityTitle = completeActivityTitle.trim() || completeModal.title || 'Memory';
        await apiService.logMemory({
          relationship_id: relationshipId,
          activity_title: activityTitle,
          notes: completeNotes.trim() || undefined,
          memory_urls: urls.length ? urls : undefined,
          memory_entries: memoryEntries.length ? memoryEntries : undefined,
          feeling: completeFeeling ?? undefined,
        });
        onAddNotification?.('system', 'Memory saved', activityTitle);
      } else {
        await completeMutation.mutateAsync({
          plannedId: completeModal.plannedId as string,
          notes: completeNotes.trim() || undefined,
          memory_urls: urls.length ? urls : undefined,
          memory_entries: memoryEntries.length ? memoryEntries : undefined,
          feeling: completeFeeling ?? undefined,
        });
        const xpGain = 100;
        setXp(xp + xpGain);
        setMemories(prev => [{
          id: Date.now().toString(),
          activityTitle: completeModal.title,
          date: Date.now(),
          note: completeNotes.trim() || 'Completed.',
          type: 'fun',
        }, ...prev]);
        onAddNotification?.('system', 'Activity logged', `${completeModal.title} completed. +${xpGain} XP`);
      }
      setCompleteNotes('');
      setCompleteFiles([]);
      setCompleteFileCaptions({});
      setCompleteFeeling(null);
      setIsAddingMemory(false);
      await memoriesQuery.refetch();
      plannedQuery.refetch();
      sentInvitesQuery.refetch();
      historyAllQuery.refetch();
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
    } catch (e) {
      console.error(e);
      alert('Failed to complete activity.');
    }
  };

  const closeCompleteModal = () => {
    setCompleteModal(null);
    setCompleteActivityTitle('');
    setCompleteNotes('');
    setCompleteFiles([]);
    setCompleteFileCaptions({});
    setCompleteFeeling(null);
    setCompleteParticipants([]);
    setGeneratedOptionsFromForm(null);
    setIsAddingMemory(false);
    setMagicDesignMemId(null);
    setGeneratedLayout(null);
    setGeneratedOptionsFromCard(null);
    setGeneratedHtmlFromCard(null);
    setScrapbookDebugPrompt(null);
    setScrapbookDebugResponse(null);
  };

  const runMagicDesign = async (mem: ActivityMemoryItem, singleStyle?: boolean) => {
    const contributions = [...(mem.contributions ?? [])].sort((a, b) => (a.actor_user_id === user?.id ? -1 : b.actor_user_id === user?.id ? 1 : 0));
    const allEntries = contributions.flatMap((c) => (c.memory_entries ?? []).map((e) => ({ ...e, actorName: c.actor_name, actor_user_id: c.actor_user_id })));
    const note = contributions.map((c) => c.notes_text).filter(Boolean).join(' ') || 'A moment we shared.';
    const feeling = contributions.find((c) => c.feeling)?.feeling ?? undefined;
    setIsGeneratingLayout(true);
    setMagicDesignMemId(mem.id);
    setGeneratedLayout(null);
    setGeneratedOptionsFromCard(null);
    setGeneratedHtmlFromCard(null);
    setScrapbookDebugPrompt(null);
    setScrapbookDebugResponse(null);
    try {
      // Palette (single style): use LLM HTML generation (inside-app parity)
      if (singleStyle) {
        const scrapbookStickersEnabled = user?.preferences?.scrapbookStickersEnabled ?? false;
        const res = await apiService.generateScrapbookHtml({
          activity_title: mem.activity_title,
          note,
          feeling: feeling ?? undefined,
          image_count: allEntries.length,
          activity_template_id: mem.activity_template_id ?? undefined,
          include_debug: showDebug,
          disable_sticker_generation: !scrapbookStickersEnabled,
        });
        const data = res.data as { htmlContent: string; prompt?: string; response?: string };
        const html = data.htmlContent;
        if (html) {
          setGeneratedHtmlFromCard(html);
          if (showDebug && (data.prompt != null || data.response != null)) {
            setScrapbookDebugPrompt(data.prompt ?? null);
            setScrapbookDebugResponse(data.response ?? null);
          } else {
            setScrapbookDebugPrompt(null);
            setScrapbookDebugResponse(null);
          }
        } else {
          const fallback = await apiService.generateScrapbookOptions({
            activity_title: mem.activity_title,
            note,
            feeling: feeling ?? undefined,
            image_count: allEntries.length,
            limit: 1,
          });
          const options = (fallback.data as { options: ElementScrapbookLayout[] }).options ?? [];
          if (options.length > 0) {
            setGeneratedOptionsFromCard(options);
            setSelectedOptionIndexFromCard(0);
          } else {
            const layoutRes = await apiService.generateScrapbookLayout({
              activity_title: mem.activity_title,
              note,
              feeling: feeling ?? undefined,
              image_count: allEntries.length,
            });
            setGeneratedLayout(layoutRes.data as ScrapbookLayout);
          }
        }
        return;
      }
      const res = await apiService.generateScrapbookOptions({
        activity_title: mem.activity_title,
        note,
        feeling: feeling ?? undefined,
        image_count: allEntries.length,
        limit: 3,
      });
      const options = (res.data as { options: ElementScrapbookLayout[] }).options ?? [];
      if (options.length > 0) {
        setGeneratedOptionsFromCard(options);
        setSelectedOptionIndexFromCard(0);
      } else {
        const fallback = await apiService.generateScrapbookLayout({
          activity_title: mem.activity_title,
          note,
          feeling: feeling ?? undefined,
          image_count: allEntries.length,
        });
        setGeneratedLayout(fallback.data as ScrapbookLayout);
      }
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : 'Failed to generate scrapbook design.';
      onAddNotification?.('system', 'Scrapbook generation failed', msg);
      setGeneratedLayout(null);
      setGeneratedOptionsFromCard(null);
      setGeneratedHtmlFromCard(null);
      setScrapbookDebugPrompt(null);
      setScrapbookDebugResponse(null);
      setMagicDesignMemId(null);
    } finally {
      setIsGeneratingLayout(false);
    }
  };

  const runMagicDesignFromForm = async () => {
    if (!completeModal) return;
    setIsGeneratingLayoutFromForm(true);
    try {
      const res = await apiService.generateScrapbookOptions({
        activity_title: completeActivityTitle.trim() || completeModal.title,
        note: completeNotes.trim() || 'A moment we shared.',
        feeling: completeFeeling ?? undefined,
        image_count: completeFiles.length,
      });
      const options = (res.data as { options: ElementScrapbookLayout[] }).options ?? [];
      setGeneratedOptionsFromForm(options.length > 0 ? options : null);
      setSelectedOptionIndexFromForm(0);
    } catch (e) {
      console.error(e);
      setGeneratedOptionsFromForm(null);
    } finally {
      setIsGeneratingLayoutFromForm(false);
    }
  };

  const saveScrapbookFromForm = async () => {
    if (!completeModal || !generatedOptionsFromForm?.length) return;
    if (completeModal.plannedId === null) {
      onAddNotification?.('system', 'Not yet supported', 'Standalone memory logging requires backend support.');
      closeCompleteModal();
      return;
    }
    const layout = generatedOptionsFromForm[selectedOptionIndexFromForm];
    if (!layout) return;
    setSaveScrapbookPending(true);
    try {
      await handleCompletePlanned();
      await apiService.saveScrapbook(completeModal.plannedId, layout as unknown as Record<string, unknown>);
      onAddNotification?.('system', 'Scrapbook saved', 'Your shared memory has a new layout.');
      setGeneratedOptionsFromForm(null);
      closeCompleteModal();
      await memoriesQuery.refetch();
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : 'Failed to save scrapbook.';
      onAddNotification?.('system', 'Scrapbook save failed', msg);
    } finally {
      setSaveScrapbookPending(false);
    }
  };

  const saveScrapbookLayout = async () => {
    const layoutToSave = generatedHtmlFromCard
      ? { htmlContent: generatedHtmlFromCard }
      : generatedOptionsFromCard?.length
        ? generatedOptionsFromCard[selectedOptionIndexFromCard]
        : generatedLayout;
    if (!layoutToSave) return;
    const plannedId = completeModal?.plannedId ?? magicDesignMemId;
    if (!plannedId) return;
    setSaveScrapbookPending(true);
    try {
      await apiService.saveScrapbook(plannedId, layoutToSave as unknown as Record<string, unknown>);
      onAddNotification?.('system', 'Scrapbook saved', 'Your shared memory has a new layout. All participants were notified.');
      setGeneratedLayout(null);
      setGeneratedOptionsFromCard(null);
      setGeneratedHtmlFromCard(null);
      setMagicDesignMemId(null);
      await memoriesQuery.refetch();
    } catch (e) {
      console.error(e);
      const msg = e instanceof Error ? e.message : 'Failed to save scrapbook.';
      onAddNotification?.('system', 'Scrapbook save failed', msg);
      alert(msg);
    } finally {
      setSaveScrapbookPending(false);
    }
  };

  useEffect(() => {
    if (completeModal) setCompleteActivityTitle(completeModal.title);
  }, [completeModal]);

  const openCompleteCardModal = (activity: ActivityCard) => {
    setCompleteCardModal(activity);
    setCompleteCardNote('');
    setCompleteCardRating(null);
    setCompleteCardTags([]);
  };

  const submitCompleteCard = async () => {
    if (!completeCardModal) return;
    const activity = completeCardModal;
    try {
      if (firstRelationshipId) {
        await apiService.postCompassFeedback({
          relationship_id: firstRelationshipId,
          activity_template_id: activity.id,
          rating: completeCardRating ?? undefined,
          outcome_tags: completeCardTags.length ? completeCardTags : undefined,
        });
      }
      compassLog.logCompleted(activity.id, completeCardNote || undefined, completeCardRating ?? undefined).catch(() => {});
      if (firstRelationshipId) queryClient.invalidateQueries({ queryKey: qk.activityHistory(firstRelationshipId) });
      setMemories(prev => [{
        id: Date.now().toString(),
        activityTitle: activity.title,
        date: Date.now(),
        note: completeCardNote || 'Completed.',
        type: activity.type,
      }, ...prev]);
      setXp(xp + activity.xpReward);
      onAddNotification?.('system', 'Activity Logged', `+${activity.xpReward} XP — ${activity.title}.`);
      setCompleteCardModal(null);
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
    } catch (e) {
      console.warn('Feedback failed:', e);
      setCompleteCardModal(null);
    }
  };

  const toggleCompleteCardTag = (tag: string) => {
    setCompleteCardTags(prev => prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]);
  };

  return (
    <React.Fragment>
    <RoomLayout
      title="GAME ROOM"
      moduleTitle="MODULE: SHARED EXPERIENCE"
      moduleIcon={<Gamepad2 size={12} />}
      subtitle={{ text: 'QUESTS', colorClass: 'text-orange-600' }}
      headerRight={
        <div className="flex items-center gap-1.5">
          <span className="text-xl font-black text-slate-900 font-mono leading-none">{headerBalance}</span>
          <span className="text-2xl leading-none" title={rewardEconomy.currencyName} aria-label={rewardEconomy.currencyName}>
            {rewardEconomy.currencySymbol}
          </span>
        </div>
      }
      onBack={onExit}
      isLoading={false}
      showGridBackground
      stickyBelowHeader={
        /* Tab strip – fixed below header, does not scroll */
        <div className="flex p-1 bg-gray-100/80 rounded-none border border-black/5 gap-0">
          {(['discover', 'planned', 'history'] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2.5 px-2 text-[10px] font-black uppercase tracking-widest transition-colors flex items-center justify-center gap-1.5 ${
                activeTab === tab
                  ? 'bg-white text-slate-900 shadow-sm border border-black/5'
                  : 'text-slate-500 hover:text-slate-900 border border-transparent'
              }`}
            >
              {tab === 'discover' && <><Sparkles size={12} /> Discover</>}
              {tab === 'planned' && <><Calendar size={12} /> Planned</>}
              {tab === 'history' && <><History size={12} /> History</>}
            </button>
          ))}
        </div>
      }
    >
      <div className="space-y-6">
        {/* Pending mutual matches – top bar for both users; deduplicated by match id */}
        {(() => {
          const raw = (mutualMatchesQuery.data as any[]) ?? [];
          const seen = new Set<string>();
          const uniqueMatches = raw.filter((m: any) => {
            if (!m?.id || seen.has(m.id)) return false;
            seen.add(m.id);
            return true;
          });
          return uniqueMatches.length > 0 ? (
            <div className="space-y-2 mb-2">
              {uniqueMatches.map((m: any) => (
                <div
                  key={m.id}
                  className="flex flex-wrap items-center justify-between gap-2 p-3 bg-emerald-50 border border-emerald-200 rounded-none"
                >
                  <p className="text-sm font-medium text-slate-900">
                    {m.activity_title ? `"${m.activity_title}"` : 'This activity'} — accept to plan it?
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        respondMutualMatchMutation.mutate(
                          { mutualMatchId: m.id, accept: true },
                          { onSuccess: () => { plannedQuery.refetch(); mutualMatchesQuery.refetch(); onAddNotification?.('system', 'Planned!', 'Activity added to Planned.'); } }
                        )
                      }
                      disabled={respondMutualMatchMutation.isPending}
                      className="py-2 px-4 bg-emerald-600 text-white text-[10px] font-black uppercase tracking-widest hover:bg-emerald-700 disabled:opacity-50 rounded-none"
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        respondMutualMatchMutation.mutate(
                          { mutualMatchId: m.id, accept: false },
                          { onSuccess: () => mutualMatchesQuery.refetch() }
                        )
                      }
                      disabled={respondMutualMatchMutation.isPending}
                      className="py-2 px-4 border border-slate-300 text-slate-600 text-[10px] font-bold uppercase tracking-widest hover:bg-slate-100 disabled:opacity-50 rounded-none"
                    >
                      Decline
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : null;
        })()}
        {/* Discover tab – Game Room Activity Hub layout */}
        {activeTab === 'discover' && (
          <>
            {/* Section title + Refresh – above Vibe row */}
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-black uppercase tracking-tight text-slate-900">Personalized Activities</h2>
              <button
                onClick={handleGenerateQuests}
                disabled={loading}
                className="flex items-center gap-1.5 px-4 py-2 border border-indigo-600 text-indigo-600 text-[10px] font-black uppercase tracking-widest hover:bg-indigo-50 transition-colors disabled:opacity-50 rounded-none"
              >
                {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                Refresh
              </button>
            </div>
            {/* Vibe row – horizontal scroll, sharp chips */}
            <div className="py-3 bg-white/30 border-b border-black/5 -mx-4 px-4">
              <div className="flex overflow-x-auto gap-2.5 no-scrollbar">
                <div className="flex items-center pr-2 shrink-0">
                  <span className="text-[10px] font-bold uppercase text-slate-500 tracking-[0.15em]">Vibe:</span>
                </div>
                <button
                  onClick={() => { setSelectedVibe(null); handleGenerateQuests(); }}
                  className={`flex-none px-5 py-2 text-[10px] font-bold uppercase tracking-widest transition-colors ${
                    selectedVibe === null ? 'bg-slate-900 text-white border border-slate-900 rounded-none' : 'bg-white text-slate-600 border border-slate-200 rounded-none hover:bg-slate-50'
                  }`}
                >
                  Any
                </button>
                {VIBE_CHIPS.map(({ label, value, unselected, selected }) => (
                  <button
                    key={value}
                    onClick={() => setSelectedVibe(value)}
                    className={`flex-none px-5 py-2 text-[10px] font-bold uppercase tracking-widest rounded-none transition-colors ${selectedVibe === value ? selected : unselected}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-10">
              {activitiesWithLabels.length === 0 && !loading && discoverActivities.length === 0 && (
                <p className="text-sm text-slate-500 italic">No activities yet. Tap Refresh to get personalized activities.</p>
              )}
              {activitiesWithLabels.length === 0 && !loading && discoverActivities.length > 0 && selectedVibe && (
                <p className="text-sm text-slate-500 italic">No activities with this vibe. Try another chip or tap Refresh.</p>
              )}
              {activitiesWithLabels.map(({ act, label }) => {
                const agreedPlanned = plannedActivities.find((p: any) => p.status === 'planned' && p.activity_template_id === act.id);
                return (
                  <ActivityCardRow
                    key={act.id}
                    act={act}
                    rewardEconomy={rewardEconomy}
                    onLogView={logCardViewedIfNeeded}
                    onOpenInvitePicker={openInvitePicker}
                    onMarkComplete={agreedPlanned ? () => { setCompleteModal({ plannedId: agreedPlanned.id, title: agreedPlanned.activity_title }); setIsAddingMemory(false); memoriesQuery.refetch(); } : undefined}
                    onWantToTry={act._discoverFeedItemId ? handleWantToTry : undefined}
                    onDismiss={act._discoverFeedItemId ? handleDismissDiscover : undefined}
                    plannedId={agreedPlanned?.id ?? null}
                    plannedTitle={agreedPlanned?.activity_title ?? null}
                    onGenerateMoreLikeThis={handleGenerateMoreLikeThis}
                    sendInvitePending={sendInviteMutation.isPending}
                    generateMorePending={compassMutation.isPending}
                    wantToTryPending={wantToTryMutation.isPending}
                    hasWantedToTry={act._discoverFeedItemId ? wantedDiscoverFeedItemIds.has(act._discoverFeedItemId) : false}
                    segmentLabel={label}
                    otherMembers={otherMembers}
                    showDebug={showDebug}
                  />
                );
              })}
              {loading && Array.from({ length: Math.max(0, PHANTOM_CARD_COUNT - discoverActivities.length) }, (_, i) => (
                <PhantomCard key={`phantom-${i}`} />
              ))}
            </div>
          </>
        )}

        {/* Planned tab */}
        {activeTab === 'planned' && (
          <div className="space-y-4">
            {pendingInvites.length > 0 && (
              <div className="space-y-10">
                <h3 className="font-black text-slate-900 uppercase tracking-tighter text-sm">Pending invites (to you)</h3>
                {pendingInvites.map((inv: any) => (
                  <ActivityCardRow
                    key={inv.invite_id}
                    act={inviteToActivityCard(inv)}
                    rewardEconomy={rewardEconomy}
                    onLogView={() => {}}
                    onOpenInvitePicker={() => {}}
                    sendInvitePending={false}
                    generateMorePending={false}
                    otherMembers={otherMembers}
                    inviteVariant="pending"
                    inviteId={inv.invite_id}
                    inviteFromName={inv.from_user_name}
                    onAcceptInvite={(id) => handleRespondInvite(id, true)}
                    onDeclineInvite={(id) => handleRespondInvite(id, false)}
                    respondInvitePending={respondInviteMutation.isPending}
                  />
                ))}
              </div>
            )}
            {sentInvites.length > 0 && (
              <div className="space-y-10">
                <h3 className="font-black text-slate-900 uppercase tracking-tighter text-sm">Waiting for acceptance</h3>
                {sentInvites.map((inv: any) => (
                  <ActivityCardRow
                    key={inv.invite_id}
                    act={inviteToActivityCard(inv)}
                    rewardEconomy={rewardEconomy}
                    onLogView={() => {}}
                    onOpenInvitePicker={() => {}}
                    sendInvitePending={false}
                    generateMorePending={false}
                    otherMembers={otherMembers}
                    inviteVariant="sent"
                    inviteId={inv.invite_id}
                    inviteToName={inv.to_user_name}
                  />
                ))}
              </div>
            )}
            {plannedActivities.filter((p: any) => p.status === 'planned').length > 0 && (
              <div className="space-y-4">
                <h3 className="font-black text-slate-900 uppercase tracking-tighter text-sm">Agreed planned</h3>
                {plannedActivities.filter((p: any) => p.status === 'planned').map((p: any) => {
                  const card = p.activity_card as Record<string, unknown> | undefined;
                  const match = !card && activitiesWithLabels.find(({ act }) => act.id === p.activity_template_id);
                  const act: ActivityCard = card
                    ? normalizePlannedCardToActivityCard(card, p.activity_template_id, p.activity_title)
                    : match
                      ? match.act
                      : {
                          id: p.activity_template_id || p.id,
                          title: p.activity_title,
                          description: p.agreed_at ? `Agreed ${new Date(p.agreed_at).toLocaleDateString()}` : 'Planned activity.',
                          duration: '—',
                          type: 'fun',
                          xpReward: 0,
                        };
                  return (
                    <ActivityCardRow
                      key={p.id}
                      act={act}
                      rewardEconomy={rewardEconomy}
                      onLogView={() => {}}
                      onOpenInvitePicker={() => {}}
                      onMarkComplete={() => { setCompleteModal({ plannedId: p.id, title: p.activity_title }); setIsAddingMemory(false); memoriesQuery.refetch(); }}
                      plannedId={p.id}
                      plannedTitle={p.activity_title}
                      sendInvitePending={false}
                      generateMorePending={false}
                      otherMembers={otherMembers}
                      showDebug={showDebug}
                    />
                  );
                })}
              </div>
            )}
            {pendingInvites.length === 0 && sentInvites.length === 0 && plannedActivities.filter((p: any) => p.status === 'planned').length === 0 && (
              <p className="text-center text-slate-400 py-6 text-xs font-mono uppercase border-2 border-dashed border-slate-300 bg-slate-50/50">No planned activities. Send an invite from Discover.</p>
            )}
          </div>
        )}

        {/* History tab */}
        {activeTab === 'history' && (
          <div className="space-y-4">
            <h3 className="font-black text-slate-900 uppercase tracking-tighter text-sm">All activity history</h3>
            {historyAllItems.length === 0 && (
              <p className="text-center text-slate-400 py-6 text-xs font-mono uppercase border-2 border-dashed border-slate-300 bg-slate-50/50">No history yet.</p>
            )}
            {historyAllItems.map((item: any) => (
              <div
                key={item.id}
                className={`p-3 border-2 flex items-center justify-between gap-2 ${
                  item.item_type === 'declined' ? 'bg-slate-50 border-slate-200' : 'bg-white border-slate-200'
                }`}
              >
                <div>
                  {item.item_type === 'completed' && (
                    <>
                      <h4 className="font-bold text-slate-900 text-sm">{item.activity_title}</h4>
                      {item.notes_text && <p className="text-[10px] text-slate-600 truncate">{item.notes_text}</p>}
                    </>
                  )}
                  {item.item_type === 'declined' && (
                    <span className="text-sm text-slate-600">You declined: {item.activity_title}</span>
                  )}
                </div>
                <span className="text-[9px] font-mono text-slate-400">{new Date(item.date).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Complete planned activity modal: scrapbook view or New Entry form */}
      {completeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className={`bg-white border-2 border-slate-900 p-5 max-w-md w-full max-h-[90vh] flex flex-col ${(isAddingMemory || completeModal.plannedId === null) ? 'shadow-[8px_8px_0px_rgba(30,41,59,0.2)]' : 'shadow-xl'}`}>
            {(isAddingMemory || completeModal.plannedId === null) ? (
              /* New Entry form – match Inside MemoryScrapbook look */
              <div className="overflow-y-auto flex-1 min-h-0">
                <div className="flex justify-between items-center mb-6 border-b border-slate-100 pb-4">
                  <h3 className="text-xl font-black text-slate-900 uppercase tracking-tighter">New Entry</h3>
                  <button type="button" onClick={() => completeModal.plannedId === null ? closeCompleteModal() : setIsAddingMemory(false)} className="text-slate-400 hover:text-slate-900" aria-label={completeModal.plannedId === null ? 'Close' : 'Back to scrapbook'}>
                    <X size={20} />
                  </button>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Activity Context</label>
                    <input
                      type="text"
                      value={completeActivityTitle}
                      onChange={e => setCompleteActivityTitle(e.target.value)}
                      placeholder="What did you do?"
                      className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-sm font-bold text-slate-900 focus:outline-none focus:border-indigo-600"
                    />
                    {completeModal?.plannedId === null && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {filteredActivities.slice(0, 6).map((a) => (
                          <button
                            key={a.id}
                            type="button"
                            onClick={() => setCompleteActivityTitle(a.title)}
                            className="text-[9px] bg-slate-100 hover:bg-slate-200 text-slate-500 border border-slate-200 px-2 py-1 rounded-sm uppercase font-mono transition-colors"
                          >
                            {a.title}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div>
                    <label className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
                      <Users size={12} /> Who was there?
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {otherMembers.map((m) => {
                        const selected = completeParticipants.includes(m.id);
                        return (
                          <button
                            key={m.id}
                            type="button"
                            onClick={() => setCompleteParticipants(prev => selected ? prev.filter(id => id !== m.id) : [...prev, m.id])}
                            className={`inline-flex items-center gap-1.5 px-3 py-2 border-2 text-xs font-bold uppercase transition-all ${selected ? 'bg-indigo-600 text-white border-indigo-700' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'}`}
                          >
                            {selected ? <CheckCircle2 size={14} /> : <Circle size={14} />}
                            {m.name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Vibe Check</label>
                    <div className="flex flex-wrap gap-2">
                      {FEELINGS_WITH_EMOJI.map((f) => (
                        <button
                          key={f.value}
                          type="button"
                          onClick={() => setCompleteFeeling(prev => prev === f.value ? null : f.value)}
                          className={`px-3 py-2 border-2 text-xs font-bold uppercase flex items-center gap-1.5 transition-all ${completeFeeling === f.value ? 'bg-slate-900 text-white border-slate-900' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'}`}
                        >
                          <span>{f.icon}</span> {f.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">Visuals</label>
                    <div className="grid grid-cols-3 gap-2">
                      {completeFiles.map((_, i) => (
                        <div key={i} className="aspect-square bg-slate-100 border border-slate-200 relative group overflow-hidden rounded">
                          <img src={URL.createObjectURL(completeFiles[i])} alt="" className="w-full h-full object-cover" />
                          <button
                            type="button"
                            onClick={() => { setCompleteFiles(prev => prev.filter((_, j) => j !== i)); setCompleteFileCaptions(prev => { const next = { ...prev }; delete next[i]; return next; }); }}
                            className="absolute top-1 right-1 bg-red-500 text-white p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                            aria-label="Remove photo"
                          >
                            <Trash2 size={10} />
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={async () => {
                          const picked = await pickActivityImages();
                          if (picked !== null) {
                            if (picked.length > 0) setCompleteFiles((prev) => [...prev, ...picked]);
                            return;
                          }
                          completeFileInputRef.current?.click();
                        }}
                        className="aspect-square border-2 border-dashed border-slate-300 flex flex-col items-center justify-center text-slate-400 hover:text-indigo-600 hover:border-indigo-400 hover:bg-indigo-50 transition-colors rounded"
                      >
                        <ImageIcon size={20} />
                        <span className="text-[8px] font-bold uppercase mt-1">Add Photo</span>
                      </button>
                    </div>
                    <input
                      ref={completeFileInputRef}
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={async e => {
                        const files = Array.from(e.target.files || []);
                        e.target.value = '';
                        if (files.length === 0) return;
                        const withSize = files.filter((f) => {
                          if (f.size === 0) {
                            onAddNotification?.('system', 'Image skipped', 'One or more photos are unavailable (e.g. stored in iCloud). Download them to your device or choose another.');
                            return false;
                          }
                          return true;
                        });
                        if (withSize.length === 0) return;
                        try {
                          const processed = await Promise.all(
                            withSize.map(async (f) => {
                              try {
                                return await processImageForUpload(f);
                              } catch (err) {
                                onAddNotification?.('system', 'Image skipped', err instanceof Error ? err.message : `Could not process "${f.name}".`);
                                return null;
                              }
                            })
                          );
                          const valid = processed.filter((f): f is File => f != null);
                          if (valid.length > 0) setCompleteFiles((prev) => [...prev, ...valid]);
                        } catch (err) {
                          onAddNotification?.('system', 'Error', err instanceof Error ? err.message : 'Could not process images.');
                        }
                      }}
                    />
                    {completeFiles.length > 0 && (
                      <>
                        <p className="mt-1.5 text-[10px] text-slate-500">Tap <strong>Save Raw</strong> below to upload these photos with your memory.</p>
                        <div className="mt-2 space-y-1">
                          {completeFiles.map((_, i) => (
                            <input
                              key={i}
                              type="text"
                              placeholder={`Caption for photo ${i + 1}`}
                              value={completeFileCaptions[i] ?? ''}
                              onChange={e => setCompleteFileCaptions(prev => ({ ...prev, [i]: e.target.value }))}
                              className="w-full border border-slate-200 p-1.5 text-xs bg-slate-50 rounded"
                            />
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Journal Entry</label>
                    <textarea
                      placeholder="Capture the details..."
                      value={completeNotes}
                      onChange={e => setCompleteNotes(e.target.value)}
                      className="w-full bg-slate-50 border-2 border-slate-200 p-3 text-xs font-medium focus:outline-none focus:border-indigo-600 min-h-[100px]"
                    />
                  </div>
                  {generatedOptionsFromForm && generatedOptionsFromForm.length > 0 ? (
                    <>
                      <div className="flex items-center justify-between bg-indigo-50 p-2 border border-indigo-100 rounded">
                        <span className="text-indigo-700 font-bold text-xs uppercase flex items-center gap-2"><Sparkles size={14} /> AI Layout Preview</span>
                        <button type="button" onClick={() => setGeneratedOptionsFromForm(null)} className="text-[10px] text-slate-500 hover:text-indigo-600 underline font-mono">Discard & Edit</button>
                      </div>
                      <div className="flex gap-2 mb-4 overflow-x-auto no-scrollbar pb-1">
                        {generatedOptionsFromForm.map((opt, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => setSelectedOptionIndexFromForm(idx)}
                            className={`flex-1 min-w-[80px] py-2 px-1 text-[9px] font-bold uppercase border-2 transition-all ${
                              selectedOptionIndexFromForm === idx
                                ? 'bg-indigo-600 text-white border-indigo-800 shadow-md'
                                : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                            }`}
                          >
                            {opt.styleName}
                          </button>
                        ))}
                      </div>
                      <div className="w-full max-w-sm mx-auto mb-4">
                        {(() => {
                          const layout = generatedOptionsFromForm[selectedOptionIndexFromForm];
                          const imageUrls = completeFiles.length > 0
                            ? completeFiles.map((f) => URL.createObjectURL(f))
                            : ['']; // placeholder so layout still renders
                          return layout ? renderElementScrapbookLayout(layout, imageUrls) : null;
                        })()}
                      </div>
                      <div className="flex gap-2">
                        <button type="button" onClick={runMagicDesignFromForm} disabled={isGeneratingLayoutFromForm} className="flex-1 bg-white hover:bg-slate-50 text-slate-900 border-2 border-slate-200 font-bold uppercase tracking-widest py-2.5 flex items-center justify-center gap-2">
                          {isGeneratingLayoutFromForm ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />} Regenerate
                        </button>
                        <button type="button" onClick={saveScrapbookFromForm} disabled={saveScrapbookPending} className="flex-[2] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold uppercase tracking-widest py-2.5 shadow-lg active:translate-y-0.5 active:shadow-none transition-all flex items-center justify-center gap-2 border-2 border-indigo-800">
                          {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save Scrapbook
                        </button>
                      </div>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={handleCompletePlanned}
                      disabled={completeMutation.isPending}
                      className="w-full bg-slate-900 hover:bg-slate-800 disabled:opacity-50 text-white font-bold uppercase tracking-widest py-3 shadow-lg active:translate-y-0.5 active:shadow-none transition-all flex items-center justify-center gap-2"
                    >
                      <Save size={16} /> {completeMutation.isPending ? 'Saving…' : 'Save Raw'}
                    </button>
                  )}
                </div>
              </div>
            ) : (
              /* Scrapbook view – match Inside MemoryScrapbook look */
              <>
                <div className="flex justify-between items-center mb-3 shrink-0">
                  <h3 className="font-black text-slate-900 uppercase tracking-tighter text-lg flex items-center gap-2">
                    <BookHeart size={20} className="text-slate-900" /> Scrapbook
                  </h3>
                  <button type="button" onClick={closeCompleteModal} className="text-slate-400 hover:text-slate-900" aria-label="Close">
                    <X size={20} />
                  </button>
                </div>
                <div className="overflow-y-auto flex-1 min-h-0 space-y-3">
                  {(() => {
                    const mem = (memoriesItems as ActivityMemoryItem[]).find((m) => m.id === completeModal.plannedId);
                    if (!mem) {
                      return (
                        <div className="text-center py-12 border-2 border-dashed border-slate-300 bg-slate-50">
                          <Camera size={32} className="mx-auto text-slate-300 mb-2" />
                          <p className="text-xs font-mono text-slate-500 uppercase">No memories archived.</p>
                          <button type="button" onClick={() => setIsAddingMemory(true)} className="mt-3 bg-slate-900 text-white px-4 py-2 text-[10px] font-bold uppercase shadow-lg active:translate-y-0.5">
                            Log Memory
                          </button>
                        </div>
                      );
                    }
                    const contributions = [...(mem.contributions ?? [])].sort((a, b) => (a.actor_user_id === user?.id ? -1 : b.actor_user_id === user?.id ? 1 : 0));
                    const allEntries = contributions.flatMap((c) => (c.memory_entries ?? []).map((e) => ({ ...e, actorName: c.actor_name, actor_user_id: c.actor_user_id })));
                    const isShared = contributions.length > 1;
                    return (
                      <>
                      <div className="bg-white border-2 border-slate-200 shadow-[4px_4px_0px_rgba(30,41,59,0.05)]">
                        {isShared && (
                          <div className="bg-slate-50 border-b border-slate-200 px-4 py-2 flex justify-between items-center">
                            <div className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-widest text-indigo-600">
                              <GitMerge size={12} /> Shared Memory
                            </div>
                            <div className="flex -space-x-2">
                              {user?.id && (
                                <div className="w-6 h-6 rounded-full bg-slate-900 text-white border-2 border-white flex items-center justify-center text-[9px] font-bold shadow-sm">
                                  {user.name?.charAt(0) ?? '?'}
                                </div>
                              )}
                              {contributions.filter((c) => c.actor_user_id !== user?.id).map((c) => (
                                <div key={c.actor_user_id} className="w-6 h-6 rounded-full bg-indigo-500 text-white border-2 border-white flex items-center justify-center text-[9px] font-bold shadow-sm">
                                  {c.actor_name?.charAt(0) ?? '?'}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="p-4">
                          <div className="flex justify-between items-start mb-3 border-b border-slate-100 pb-2">
                            <div>
                              <h4 className="font-bold text-slate-900 text-sm uppercase">{mem.activity_title}</h4>
                              <span className="text-[9px] font-mono text-slate-400">{mem.completed_at ? new Date(mem.completed_at).toLocaleDateString() : ''}</span>
                            </div>
                            <div className="flex flex-wrap gap-1 justify-end">
                              {(mem.contributions ?? []).filter((c) => c.feeling).map((c, i) => (
                                <span key={`${c.actor_user_id}-${i}`} className="bg-indigo-50 text-indigo-700 px-2 py-1 text-[9px] font-bold uppercase border border-indigo-200">{c.feeling}</span>
                              ))}
                            </div>
                          </div>
                          {allEntries.length > 0 && (
                            <div className="mb-4 overflow-x-auto overflow-y-hidden flex gap-0 snap-x snap-mandatory scroll-smooth -mx-1 px-1" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                              {allEntries.map((e, i) => (
                                <div key={i} className="flex-shrink-0 w-[85%] max-w-[280px] snap-start snap-always aspect-[4/3] bg-slate-100 border border-slate-200 overflow-hidden relative rounded">
                                  <img src={apiService.getMemoryImageUrl(e.url)} alt={e.caption ?? 'Memory'} className="w-full h-full object-cover" />
                                  {e.caption ? (
                                    <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-2">
                                      {e.caption}
                                    </div>
                                  ) : null}
                                  <div className={`absolute bottom-0 right-0 px-2 py-0.5 text-[8px] font-bold uppercase backdrop-blur-sm ${e.actor_user_id === user?.id ? 'bg-slate-900/90 text-white' : 'bg-indigo-600/90 text-white'}`}>
                                    {e.actor_user_id === user?.id ? 'You' : (e.actorName ?? 'Partner')}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                          {contributions.map((c) => {
                            if (!c.notes_text) return null;
                            const isUser = c.actor_user_id === user?.id;
                            return isUser ? (
                              <div key={c.actor_user_id} className="flex gap-3 mb-2">
                                <div className="w-6 h-6 bg-slate-900 text-white rounded-full flex items-center justify-center text-[9px] shrink-0 font-bold border-2 border-white shadow-sm mt-0.5">
                                  {user?.name?.charAt(0) ?? '?'}
                                </div>
                                <div className="bg-slate-50 p-2 rounded-r-lg rounded-bl-lg text-slate-700 text-xs italic font-serif leading-relaxed border border-slate-100 flex-1">
                                  &quot;{c.notes_text}&quot;
                                </div>
                              </div>
                            ) : (
                              <div key={c.actor_user_id} className="flex gap-3 mt-2 justify-end">
                                <div className="bg-indigo-50 p-2 rounded-l-lg rounded-br-lg text-indigo-900 text-xs italic font-serif leading-relaxed border border-indigo-100 flex-1 text-right">
                                  &quot;{c.notes_text}&quot;
                                </div>
                                <div className="w-6 h-6 bg-indigo-500 text-white rounded-full flex items-center justify-center text-[9px] shrink-0 font-bold border-2 border-white shadow-sm mt-0.5">
                                  {c.actor_name?.charAt(0) ?? '?'}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                      {(generatedLayout || generatedHtmlFromCard || (generatedOptionsFromCard && generatedOptionsFromCard.length > 0)) && magicDesignMemId === completeModal.plannedId && (() => {
                        const mem = (memoriesItems as ActivityMemoryItem[]).find((m) => m.id === completeModal.plannedId);
                        if (!mem) return null;
                        const contributionsForPreview = [...(mem.contributions ?? [])];
                        const allEntriesForPreview = contributionsForPreview.flatMap((c) => (c.memory_entries ?? []).map((e) => ({ ...e, actorName: c.actor_name })));
                        const imageUrlsForPreview = allEntriesForPreview.map((e) => apiService.getMemoryImageUrl(e.url));
                        const discardModal = () => { setGeneratedLayout(null); setGeneratedOptionsFromCard(null); setGeneratedHtmlFromCard(null); setScrapbookDebugPrompt(null); setScrapbookDebugResponse(null); setMagicDesignMemId(null); };
                        if (generatedHtmlFromCard) {
                          return (
                            <div className="mt-4 space-y-3">
                              <div className="flex items-center justify-between bg-indigo-50 p-2 border border-indigo-100 rounded">
                                <span className="text-indigo-700 font-bold text-xs uppercase flex items-center gap-2"><Sparkles size={14} /> Magic Design (HTML)</span>
                                <div className="flex items-center gap-2">
                                  {showDebug && (scrapbookDebugPrompt != null || scrapbookDebugResponse != null) && (
                                    <button type="button" onClick={() => setScrapbookDebugModalOpen(true)} className="flex items-center gap-1 text-[10px] font-bold text-slate-500 uppercase tracking-widest hover:text-slate-700" title="View prompt and response">
                                      <Bug size={12} /> Debug
                                    </button>
                                  )}
                                  <button type="button" onClick={discardModal} className="text-[10px] text-slate-500 hover:text-indigo-600 underline font-mono">Discard</button>
                                </div>
                              </div>
                              <div className="max-w-[280px] mx-auto mb-3 overflow-hidden border border-slate-200 rounded">
                                <ScrapbookHtml
                                  html={processHtmlContent(generatedHtmlFromCard, imageUrlsForPreview)}
                                  className="scrapbook-content w-full min-h-[200px]"
                                  style={{ isolation: 'isolate' }}
                                />
                              </div>
                              <div className="flex gap-2">
                                <button type="button" onClick={() => runMagicDesign(mem)} className="flex-1 bg-white hover:bg-slate-50 text-slate-900 border-2 border-slate-200 font-bold uppercase tracking-widest py-2.5 flex items-center justify-center gap-2">
                                  <RotateCw size={14} /> Regenerate
                                </button>
                                <button type="button" onClick={saveScrapbookLayout} disabled={saveScrapbookPending} className="flex-[2] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold uppercase tracking-widest py-2.5 shadow-lg active:translate-y-0.5 active:shadow-none transition-all flex items-center justify-center gap-2 border-2 border-indigo-800">
                                  {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save Scrapbook
                                </button>
                              </div>
                            </div>
                          );
                        }
                        if (generatedOptionsFromCard && generatedOptionsFromCard.length > 0) {
                          const layout = generatedOptionsFromCard[selectedOptionIndexFromCard];
                          return (
                            <div className="mt-4 space-y-3">
                              <div className="flex items-center justify-between bg-indigo-50 p-2 border border-indigo-100 rounded">
                                <span className="text-indigo-700 font-bold text-xs uppercase flex items-center gap-2"><Sparkles size={14} /> SCRAPBOOKING...</span>
                                <button type="button" onClick={discardModal} className="text-[10px] text-slate-500 hover:text-indigo-600 underline font-mono">Discard</button>
                              </div>
                              <div className="flex gap-2 mb-3 overflow-x-auto no-scrollbar pb-1">
                                {generatedOptionsFromCard.map((opt, idx) => (
                                  <button
                                    key={idx}
                                    type="button"
                                    onClick={() => setSelectedOptionIndexFromCard(idx)}
                                    className={`flex-1 min-w-[80px] py-2 px-1 text-[9px] font-bold uppercase border-2 transition-all ${
                                      selectedOptionIndexFromCard === idx ? 'bg-indigo-600 text-white border-indigo-800 shadow-md' : 'bg-white text-slate-500 border-slate-200 hover:border-slate-400'
                                    }`}
                                  >
                                    {opt.styleName}
                                  </button>
                                ))}
                              </div>
                              <div className="max-w-[280px] mx-auto mb-3">
                                {layout && renderElementScrapbookLayout(layout, imageUrlsForPreview)}
                              </div>
                              <div className="flex gap-2">
                                <button type="button" onClick={() => runMagicDesign(mem)} className="flex-1 bg-white hover:bg-slate-50 text-slate-900 border-2 border-slate-200 font-bold uppercase tracking-widest py-2.5 flex items-center justify-center gap-2">
                                  <RotateCw size={14} /> Regenerate
                                </button>
                                <button type="button" onClick={saveScrapbookLayout} disabled={saveScrapbookPending} className="flex-[2] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold uppercase tracking-widest py-2.5 shadow-lg active:translate-y-0.5 active:shadow-none transition-all flex items-center justify-center gap-2 border-2 border-indigo-800">
                                  {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save Scrapbook
                                </button>
                              </div>
                            </div>
                          );
                        }
                        const layout = generatedLayout!;
                        return (
                          <div className="mt-4 space-y-3">
                            <div className="flex items-center justify-between bg-indigo-50 p-2 border border-indigo-100 rounded">
                              <span className="text-indigo-700 font-bold text-xs uppercase flex items-center gap-2"><Sparkles size={14} /> AI Layout Preview</span>
                              <button type="button" onClick={discardModal} className="text-[10px] text-slate-500 hover:text-indigo-600 underline font-mono">Discard</button>
                            </div>
                            <div className="relative overflow-hidden p-4 shadow-xl border-4 border-white rounded transition-all" style={{ backgroundColor: layout.themeColor }}>
                              <div className="absolute top-4 left-4 -rotate-12 bg-white px-2 py-1 shadow-md border border-slate-200 z-10">
                                <p className="text-[8px] font-bold font-mono text-slate-400 uppercase tracking-widest">{mem?.completed_at ? new Date(mem.completed_at).toLocaleDateString() : ''}</p>
                              </div>
                              <div className="absolute top-2 right-2 text-2xl z-10">{layout.stickers[0]}</div>
                              {layout.stickers[1] != null && <div className="absolute bottom-2 left-2 text-2xl z-10">{layout.stickers[1]}</div>}
                              <div className="text-center mb-4">
                                <h3 className="font-black text-xl uppercase tracking-tighter" style={{ color: layout.secondaryColor }}>{layout.headline}</h3>
                                <div className="w-12 h-0.5 mx-auto mt-1 opacity-50" style={{ backgroundColor: layout.secondaryColor }} />
                              </div>
                              <div className={`grid gap-2 mb-4 ${allEntriesForPreview.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
                                {allEntriesForPreview.slice(0, layout.imageCaptions.length).map((e, idx) => (
                                  <div key={idx} className={`bg-white p-1.5 shadow-sm rounded transition-transform hover:rotate-0 hover:scale-105 ${idx % 2 === 0 ? '-rotate-2' : 'rotate-2'}`}>
                                    <div className="aspect-square bg-slate-100 overflow-hidden mb-1 rounded">
                                      <img src={apiService.getMemoryImageUrl(e.url)} alt="" className="w-full h-full object-cover" />
                                    </div>
                                    <p className="font-serif italic text-xs text-center text-slate-600">{layout.imageCaptions[idx] ?? 'Lovely moment'}</p>
                                  </div>
                                ))}
                              </div>
                              <div className="bg-white/80 backdrop-blur-sm p-3 rounded border border-white/50">
                                <p className="font-serif text-slate-800 leading-relaxed italic text-center text-sm">&quot;{layout.narrative}&quot;</p>
                              </div>
                              <div className="flex justify-center mt-3 -space-x-2">
                                {user?.id && (
                                  <div className="w-7 h-7 rounded-full bg-white border-2 border-slate-200 flex items-center justify-center text-[10px] font-bold text-slate-900 shadow-sm">
                                    {user.name?.charAt(0) ?? '?'}
                                  </div>
                                )}
                                {contributionsForPreview.filter((c) => c.actor_user_id !== user?.id).map((c) => (
                                  <div key={c.actor_user_id} className="w-7 h-7 rounded-full bg-indigo-500 border-2 border-white flex items-center justify-center text-[10px] font-bold text-white shadow-sm">
                                    {c.actor_name?.charAt(0) ?? '?'}
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <button type="button" onClick={() => runMagicDesign(mem)} className="flex-1 bg-white hover:bg-slate-50 text-slate-900 border-2 border-slate-200 font-bold uppercase tracking-widest py-2.5 flex items-center justify-center gap-2">
                                <RotateCw size={14} /> Regenerate
                              </button>
                              <button type="button" onClick={saveScrapbookLayout} disabled={saveScrapbookPending} className="flex-[2] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold uppercase tracking-widest py-2.5 shadow-lg active:translate-y-0.5 active:shadow-none transition-all flex items-center justify-center gap-2 border-2 border-indigo-800">
                                {saveScrapbookPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Save Scrapbook
                              </button>
                            </div>
                          </div>
                        );
                      })()}
                      </>
                    );
                  })()}
                </div>
                <div className="flex justify-end pt-2 border-t border-slate-200 shrink-0">
                  <button type="button" onClick={closeCompleteModal} className="border-2 border-slate-400 px-4 py-2 text-xs font-bold uppercase">Close</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Invite picker modal: select invitee(s) and send */}
      {invitePicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white border-2 border-slate-900 p-5 max-w-md w-full shadow-xl max-h-[85vh] flex flex-col">
            <h3 className="font-black text-slate-900 uppercase mb-2">Invite to: {invitePicker.act.title}</h3>
            <p className="text-[10px] text-slate-500 uppercase font-bold mb-3">Select who to invite</p>
            <div className="overflow-y-auto flex-1 min-h-0 space-y-1 mb-4">
              {invitePicker.inviteTargets.map((inv) => (
                <label
                  key={inv.id}
                  className="flex items-center gap-3 p-3 border-2 border-slate-200 rounded cursor-pointer hover:bg-slate-50 has-[:checked]:border-indigo-500 has-[:checked]:bg-indigo-50"
                >
                  <input
                    type="checkbox"
                    checked={invitePickerSelected.has(inv.id)}
                    onChange={() => toggleInvitePickerSelection(inv.id)}
                    className="w-4 h-4 rounded border-slate-300 text-indigo-600"
                  />
                  <span className="text-sm font-bold text-slate-900">{inv.name}</span>
                </label>
              ))}
            </div>
            <div className="flex gap-2 justify-end border-t border-slate-200 pt-3">
              <button
                type="button"
                onClick={() => { setInvitePicker(null); setInvitePickerSelected(new Set()); }}
                className="border-2 border-slate-400 px-4 py-2 text-xs font-bold uppercase"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={sendInvitePickerInvites}
                disabled={sendInviteMutation.isPending || invitePickerSelected.size === 0}
                className="bg-indigo-600 text-white px-4 py-2 text-xs font-bold uppercase disabled:opacity-50 flex items-center gap-1"
              >
                {sendInviteMutation.isPending ? <Loader2 size={12} className="animate-spin" /> : <UserPlus size={12} />}
                Send invite{invitePickerSelected.size !== 1 ? 's' : ''}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Ad-hoc complete (suggestion card): note + rating + outcome tags */}
      {completeCardModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white border-2 border-slate-900 p-5 max-w-md w-full shadow-xl max-h-[90vh] overflow-y-auto">
            <h3 className="font-black text-slate-900 uppercase mb-3">Log: {completeCardModal.title}</h3>
            <textarea
              placeholder="How did it go? (optional)"
              value={completeCardNote}
              onChange={e => setCompleteCardNote(e.target.value)}
              className="w-full border-2 border-slate-200 p-2 text-sm mb-3 min-h-[80px]"
              rows={3}
            />
            <div className="mb-3">
              <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Rating (optional)</span>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setCompleteCardRating(prev => prev === n ? null : n)}
                    className={`w-9 h-9 rounded border-2 text-sm font-bold ${completeCardRating === n ? 'bg-amber-500 text-white border-amber-600' : 'bg-white border-slate-200 text-slate-500 hover:border-slate-400'}`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
            <div className="mb-4">
              <span className="text-[10px] font-bold uppercase text-slate-500 block mb-1">Outcome tags (optional)</span>
              <div className="flex flex-wrap gap-1">
                {OUTCOME_TAG_OPTIONS.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => toggleCompleteCardTag(tag)}
                    className={`px-2 py-1 text-[10px] font-bold uppercase border-2 rounded ${completeCardTags.includes(tag) ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white border-slate-200 text-slate-600'}`}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setCompleteCardModal(null); setCompleteCardNote(''); setCompleteCardRating(null); setCompleteCardTags([]); }}
                className="border-2 border-slate-400 px-4 py-2 text-xs font-bold uppercase"
              >
                Cancel
              </button>
              <button
                onClick={submitCompleteCard}
                className="bg-indigo-600 text-white px-4 py-2 text-xs font-bold uppercase"
              >
                Log & +{completeCardModal.xpReward} XP
              </button>
            </div>
          </div>
        </div>
      )}
    </RoomLayout>
    <Modal isOpen={scrapbookDebugModalOpen} onClose={() => setScrapbookDebugModalOpen(false)} title="Scrapbook LLM Debug" size="xl">
      <div className="space-y-4 p-4">
        <div>
          <h4 className="text-xs font-bold uppercase text-slate-600 mb-1">Prompt</h4>
          <pre className="bg-slate-100 border border-slate-200 p-3 text-xs font-mono overflow-auto max-h-64 whitespace-pre-wrap break-words">
            {scrapbookDebugPrompt ?? '—'}
          </pre>
        </div>
        <div>
          <h4 className="text-xs font-bold uppercase text-slate-600 mb-1">Response</h4>
          <pre className="bg-slate-100 border border-slate-200 p-3 text-xs font-mono overflow-auto max-h-64 whitespace-pre-wrap break-words">
            {scrapbookDebugResponse ?? '—'}
          </pre>
        </div>
      </div>
    </Modal>
    </React.Fragment>
  );
};
