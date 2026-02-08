import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';
import type { ActivityCard, SuggestedInvitee } from '../../../shared/types/domain';

/**
 * Map Compass recommendation item to ActivityCard (tags, explanation).
 * suggestedInvitees: derived on client from relationship members (plan: client-derived).
 * Exported for use when consuming streamed recommendations.
 */
export function mapCompassItemToCard(
  item: any,
  suggestedInvitees?: SuggestedInvitee[]
): ActivityCard {
  const desc = item.steps_markdown_template
    ? (item.steps_markdown_template as string).slice(0, 200) + (item.steps_markdown_template.length > 200 ? '…' : '')
    : item.explanation || '';
  const duration = item.constraints?.duration_min
    ? `${item.constraints.duration_min} mins`
    : (item.constraints?.duration ?? '15 mins');
  const vibe = Array.isArray(item.vibe_tags) && item.vibe_tags.length ? item.vibe_tags[0] : 'fun';
  const typeMap: Record<string, ActivityCard['type']> = {
    romantic: 'romantic',
    silly: 'fun',
    cozy: 'deep',
    adventurous: 'active',
    fun: 'fun',
    deep: 'deep',
    active: 'active',
  };
  const rationale =
    (typeof item.explanation === 'string' && item.explanation.trim()) ||
    (typeof item.rationale === 'string' && item.rationale.trim()) ||
    'Recommended for your relationship.';
  const recommendedLocation =
    typeof item.recommended_location === 'string'
      ? item.recommended_location.trim() || undefined
      : (item.constraints?.location != null ? String(item.constraints.location).trim() || undefined : undefined);
  return {
    id: item.id ?? String(Math.random()),
    title: item.title ?? 'Activity',
    description: desc,
    duration,
    type: typeMap[vibe] ?? 'fun',
    xpReward: 100,
    tags: [...(item.vibe_tags ?? []), ...(item.risk_tags ?? [])].filter(Boolean),
    suggestedInvitees: suggestedInvitees ?? item.suggested_invitees ?? [],
    explanation: rationale,
    suggestedReason: rationale,
    recommendedInvitee: item.recommended_invitee ?? undefined,
    recommendedLocation: recommendedLocation ?? undefined,
    debugPrompt: item.debug_prompt ?? undefined,
    debugResponse: item.debug_response ?? undefined,
    debugSource: item.debug_source ?? undefined,
  };
}

/**
 * Fetch activity suggestions from coach API (fallback).
 */
export const useActivitySuggestionsMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['activities', 'suggestions'],
    mutationFn: async (params: { relationshipId: string; debug?: boolean }): Promise<ActivityCard[]> => {
      const { relationshipId, debug } = typeof params === 'string' ? { relationshipId: params, debug: undefined } : params;
      const response = await apiService.getActivitySuggestions(relationshipId, { debug });
      const suggestions = (response.data as any[]) || [];
      return suggestions.map((s: any) => ({
        id: s.id ?? String(Math.random()),
        title: s.title ?? 'Activity',
        description: s.description ?? '',
        duration: '15 mins',
        type: 'fun' as const,
        xpReward: 100,
        explanation: s.explanation ?? 'Recommended for you.',
        suggestedReason: s.explanation ?? 'Recommended for you.',
        debugPrompt: s.debug_prompt ?? undefined,
        debugResponse: s.debug_response ?? undefined,
        debugSource: s.debug_source ?? undefined,
      }));
    },
    onSuccess: (_, variables) => {
      const rid = typeof variables === 'string' ? variables : variables.relationshipId;
      queryClient.invalidateQueries({
        queryKey: qk.activitySuggestions(rid),
      });
    },
  });
};

/**
 * Fetch Compass recommendations (plan: primary source). suggestedInvitees derived on client.
 */
export const useCompassRecommendationsMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['activities', 'compass-recommendations'],
    mutationFn: async (params: {
      relationshipId: string;
      otherMembers?: SuggestedInvitee[];
      options?: { limit?: number; vibeTags?: string[]; durationMaxMinutes?: number; similarToActivityId?: string; useLlm?: boolean; debug?: boolean; excludeTitles?: string[] };
    }): Promise<ActivityCard[]> => {
      const { relationshipId, otherMembers, options } = params;
      const response = await apiService.getCompassRecommendations(relationshipId, {
        limit: options?.limit ?? 15,
        vibeTags: options?.vibeTags,
        durationMaxMinutes: options?.durationMaxMinutes,
        similarToActivityId: options?.similarToActivityId,
        useLlm: options?.useLlm,
        debug: options?.debug,
        excludeTitles: options?.excludeTitles,
      });
      const items = (response.data as any[]) || [];
      return items.map((item) => mapCompassItemToCard(item, otherMembers));
    },
    onSuccess: (_, params) => {
      queryClient.invalidateQueries({
        queryKey: qk.compassRecommendations(params.relationshipId),
      });
    },
  });
};

/**
 * Fetch Compass activity recommendations (tags, suggested invitees; server logs suggestions_generated).
 */
export const useCompassActivityRecommendationsMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['activities', 'compass'],
    mutationFn: async (relationshipId: string): Promise<ActivityCard[]> => {
      const response = await apiService.getCompassActivityRecommendations(relationshipId, { limit: 15 });
      const items = (response.data as any[]) || [];
      return items.map((item) => mapCompassItemToCard(item));
    },
    onSuccess: (_, relationshipId) => {
      queryClient.invalidateQueries({
        queryKey: qk.compassRecommendations(relationshipId),
      });
    },
  });
};

/**
 * Log activity events to Compass (plan: postCompassEvent). Backend appends to dyad_activity_history on activity_completed.
 */
export const useCompassActivityLog = (relationshipId: string | undefined) => {
  const logRecommendationsShown = (activityIds: string[], limit?: number) => {
    if (!relationshipId) return Promise.resolve();
    return apiService.postCompassEvent({
      type: 'activity_recommendations_shown',
      payload: { relationship_id: relationshipId, activity_ids: activityIds, limit },
      source: 'activity',
      relationship_id: relationshipId,
    });
  };
  const logCardViewed = (activityId: string) => {
    if (!relationshipId) return Promise.resolve();
    return apiService.postCompassEvent({
      type: 'activity_card_viewed',
      payload: { activity_id: activityId },
      source: 'activity',
      relationship_id: relationshipId,
    });
  };
  const logCompleted = (activityId: string, note?: string, rating?: number) => {
    if (!relationshipId) return Promise.resolve();
    return apiService.postCompassEvent({
      type: 'activity_completed',
      payload: { activity_id: activityId, relationship_id: relationshipId, note, rating },
      source: 'activity',
      relationship_id: relationshipId,
    });
  };
  const logDismissed = (activityIds?: string[]) => {
    if (!relationshipId) return Promise.resolve();
    return apiService.postCompassEvent({
      type: 'activity_dismissed',
      payload: { activity_ids: activityIds, relationship_id: relationshipId },
      source: 'activity',
      relationship_id: relationshipId,
    });
  };
  const logSuggestionsRefreshed = (activityIds?: string[]) => {
    if (!relationshipId) return Promise.resolve();
    return apiService.postCompassEvent({
      type: 'activity_suggestions_refreshed',
      payload: { activity_ids: activityIds, relationship_id: relationshipId },
      source: 'activity',
      relationship_id: relationshipId,
    });
  };
  return {
    logRecommendationsShown,
    logCardViewed,
    logCompleted,
    logDismissed,
    logSuggestionsRefreshed,
  };
};

/**
 * Log user interaction with an activity suggestion (viewed, invite_sent, dismissed, completed).
 */
export const useLogActivityInteractionMutation = () => {
  return useMutation({
    mutationKey: ['activities', 'log-interaction'],
    mutationFn: async (params: {
      relationshipId: string;
      suggestionId: string;
      action: 'viewed' | 'invite_sent' | 'dismissed' | 'completed';
    }) => {
      await apiService.logActivitySuggestionInteraction(
        params.relationshipId,
        params.suggestionId,
        params.action
      );
    },
  });
};

/**
 * Send activity invite to a relationship member. Pass cardSnapshot (full ActivityCard) so the backend stores it for the Planned tab.
 */
export const useSendActivityInviteMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['activities', 'send-invite'],
    mutationFn: async (params: {
      relationshipId: string;
      activityTemplateId: string;
      inviteeUserId: string;
      cardSnapshot?: Record<string, unknown>;
    }) => {
      const res = await apiService.sendActivityInvite(
        params.relationshipId,
        params.activityTemplateId,
        params.inviteeUserId,
        params.cardSnapshot
      );
      return (res.data as { invite_id: string }).invite_id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.pendingActivityInvites() });
      queryClient.invalidateQueries({ queryKey: qk.sentActivityInvites() });
    },
  });
};

/**
 * List sent activity invites (pending acceptance) for Planned tab.
 */
export const useSentActivityInvitesQuery = () => {
  return useQuery({
    queryKey: qk.sentActivityInvites(),
    queryFn: async () => {
      const res = await apiService.getSentActivityInvites();
      return (res.data as any[]) ?? [];
    },
  });
};

/**
 * Accept or decline an activity invite.
 */
export const useRespondToActivityInviteMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['activities', 'respond-invite'],
    mutationFn: async (params: { inviteId: string; accept: boolean }) => {
      await apiService.respondToActivityInvite(params.inviteId, params.accept);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.pendingActivityInvites() });
      queryClient.invalidateQueries({ queryKey: qk.plannedActivities() });
      queryClient.invalidateQueries({ queryKey: qk.sentActivityInvites() });
    },
  });
};

/**
 * List all activity history (completed + declined) for History tab.
 */
export const useActivityHistoryAllQuery = (relationshipId: string | undefined) => {
  return useQuery({
    queryKey: qk.activityHistoryAll(relationshipId ?? ''),
    queryFn: async () => {
      if (!relationshipId) return [];
      const res = await apiService.getActivityHistoryAll(relationshipId, 50);
      return (res.data as any[]) ?? [];
    },
    enabled: !!relationshipId,
  });
};

/**
 * List dyad activity history (completed activities) for Archived Logs.
 */
export const useActivityHistoryQuery = (relationshipId: string | undefined) => {
  return useQuery({
    queryKey: qk.activityHistory(relationshipId ?? ''),
    queryFn: async () => {
      if (!relationshipId) return [];
      const res = await apiService.getActivityHistory(relationshipId, 50);
      return (res.data as any[]) ?? [];
    },
    enabled: !!relationshipId,
  });
};

/**
 * List planned activities for the current user.
 */
export const usePlannedActivitiesQuery = (relationshipId?: string) => {
  return useQuery({
    queryKey: qk.plannedActivities(relationshipId),
    queryFn: async () => {
      const res = await apiService.getPlannedActivities(relationshipId);
      return (res.data as any[]) ?? [];
    },
  });
};

/**
 * List pending activity invites (for Accept/Decline UI).
 */
export const usePendingActivityInvitesQuery = () => {
  return useQuery({
    queryKey: qk.pendingActivityInvites(),
    queryFn: async () => {
      const res = await apiService.getPendingActivityInvites();
      return (res.data as any[]) ?? [];
    },
  });
};

/**
 * List memories (completed activities with aggregated notes/photos from all participants).
 */
export const useActivityMemoriesQuery = (relationshipId: string | undefined) => {
  return useQuery({
    queryKey: qk.activityMemories(relationshipId ?? ''),
    queryFn: async () => {
      if (!relationshipId) return [];
      const res = await apiService.getActivityMemories(relationshipId, 50);
      return (res.data as any[]) ?? [];
    },
    enabled: !!relationshipId,
  });
};

/**
 * Complete a planned activity (notes + memory URLs and/or memory_entries with captions).
 */
export const useCompletePlannedActivityMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['activities', 'complete-planned'],
    mutationFn: async (params: {
      plannedId: string;
      notes?: string;
      memory_urls?: string[];
      memory_entries?: { url: string; caption?: string }[];
      feeling?: string;
    }) => {
      await apiService.completePlannedActivity(params.plannedId, {
        notes: params.notes,
        memory_urls: params.memory_urls,
        memory_entries: params.memory_entries,
        feeling: params.feeling,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.plannedActivities() });
      queryClient.invalidateQueries({ queryKey: ['activities', 'history'] });
      queryClient.invalidateQueries({ queryKey: ['activities', 'memories'] });
    },
  });
};

/** Map discover feed API card to ActivityCard (includes _discoverFeedItemId). */
export function mapDiscoverFeedCardToActivityCard(card: Record<string, unknown>): ActivityCard {
  const id = (card.id as string) ?? (card._discover_feed_item_id as string) ?? '';
  const desc = (card.description as string) ?? '';
  const duration = card.constraints?.duration_min
    ? `${(card.constraints as { duration_min?: number }).duration_min} mins`
    : (card.constraints?.location ? '15 mins' : '15 mins');
  const tags = (card.vibe_tags as string[]) ?? [];
  const recommendedInvitee = card.recommended_invitee as { id?: string; name?: string } | undefined;
  return {
    id,
    title: (card.title as string) ?? 'Activity',
    description: desc,
    duration,
    type: 'fun',
    xpReward: 100,
    tags,
    suggestedInvitees: (card.suggested_invitees as ActivityCard['suggestedInvitees']) ?? [],
    explanation: (card.explanation as string) ?? undefined,
    suggestedReason: (card.explanation as string) ?? undefined,
    recommendedInvitee: recommendedInvitee ? { id: recommendedInvitee.id ?? '', name: recommendedInvitee.name ?? 'Someone' } : undefined,
    recommendedLocation: (card.recommended_location as string) ?? undefined,
    _discoverFeedItemId: (card._discover_feed_item_id as string) ?? undefined,
    debugSource: (card.debug_source as string) ?? undefined,
    debugPrompt: (card.debug_prompt as string) ?? undefined,
    debugResponse: (card.debug_response as string) ?? undefined,
  };
}

/**
 * Fetch Discover feed for relationship (cards where user is generator or recommended invitee).
 */
export const useDiscoverFeedQuery = (relationshipId: string | undefined) => {
  return useQuery({
    queryKey: qk.discoverFeed(relationshipId ?? ''),
    queryFn: async (): Promise<ActivityCard[]> => {
      if (!relationshipId) return [];
      const res = await apiService.getDiscoverFeed(relationshipId, 50);
      const raw = (res.data as Record<string, unknown>[]) ?? [];
      return raw.map((c) => mapDiscoverFeedCardToActivityCard(c));
    },
    enabled: !!relationshipId,
  });
};

/**
 * Dismiss a discover feed item (swipe-left).
 */
export const useDismissDiscoverMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: ['activities', 'discover', 'dismiss'],
    mutationFn: async (params: { relationshipId: string; discoverFeedItemId: string }) => {
      await apiService.dismissDiscoverItem(params.relationshipId, params.discoverFeedItemId);
    },
    onSuccess: (_, params) => {
      queryClient.invalidateQueries({ queryKey: qk.discoverFeed(params.relationshipId) });
    },
  });
};

/**
 * Record "Want to try" for a discover feed item.
 */
export const useWantToTryMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: ['activities', 'want-to-try'],
    mutationFn: async (params: { relationshipId: string; discoverFeedItemId: string }) => {
      const res = await apiService.wantToTry(params.relationshipId, params.discoverFeedItemId);
      return res.data as { ok: boolean; mutual_match_id?: string };
    },
    onSuccess: (_, params) => {
      queryClient.invalidateQueries({ queryKey: qk.discoverFeed(params.relationshipId) });
      queryClient.invalidateQueries({ queryKey: qk.mutualMatches(params.relationshipId) });
    },
  });
};

/**
 * List pending mutual matches for the current user.
 */
export const useMutualMatchesQuery = (relationshipId: string | undefined) => {
  return useQuery({
    queryKey: qk.mutualMatches(relationshipId),
    queryFn: async () => {
      const res = await apiService.listMutualMatches(relationshipId);
      return (res.data as any[]) ?? [];
    },
  });
};

/**
 * Accept or decline a mutual match.
 */
export const useRespondToMutualMatchMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: ['activities', 'mutual-match', 'respond'],
    mutationFn: async (params: { mutualMatchId: string; accept: boolean }) => {
      await apiService.respondToMutualMatch(params.mutualMatchId, params.accept);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.plannedActivities() });
      queryClient.invalidateQueries({ queryKey: qk.mutualMatches() });
    },
  });
};
