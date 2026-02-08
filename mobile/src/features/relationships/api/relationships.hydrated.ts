import { useQueries, useQuery } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';
import { useRelationshipsQuery, useConsentInfoQuery, useInvitesQuery, useUserByIdQuery } from './relationships.queries';
import type { LovedOne, MarketItem } from '../../../shared/types/domain';
import { DEFAULT_MARKET_ITEMS, DEFAULT_ECONOMY } from '../../../shared/lib/constants';

/**
 * Aggregated query that loads all relationship data and transforms it into LovedOne[]
 * This replaces loadRelationshipsFromBackend() from App.tsx
 * 
 * This combines:
 * - getRelationships()
 * - for each: getConsentInfo(relId)
 * - for each member: getUserById(memberId)
 * - for each user: getUserMarket(userId)
 * - also getInvites(relId)
 */
export const useRelationshipsHydratedQuery = (currentUserId: string | null) => {
  const { data: relationships, isLoading: isLoadingRelationships, error: relationshipsError } = useRelationshipsQuery();

  // Helper: treat 404 as "relationship removed" (e.g. just deleted, stale cache)
  const isNotFound = (err: unknown) =>
    err instanceof Error && (err.message.includes('404') || err.message.includes('Not Found'));

  // Load consent info for all relationships in parallel
  const consentQueries = useQueries({
    queries: (relationships || []).map((rel: any) => ({
      queryKey: qk.consentInfo(rel.id),
      queryFn: async () => {
        try {
          const response = await apiService.getConsentInfo(rel.id);
          return { relationshipId: rel.id, data: response.data, isGone: false };
        } catch (err) {
          if (isNotFound(err)) {
            return { relationshipId: rel.id, data: null, isGone: true };
          }
          throw err;
        }
      },
      enabled: !!rel.id && !!currentUserId,
      retry: false,
    })),
  });

  // Load invites for all relationships in parallel
  const inviteQueries = useQueries({
    queries: (relationships || []).map((rel: any) => ({
      queryKey: qk.invites(rel.id),
      queryFn: async () => {
        try {
          const response = await apiService.getInvites(rel.id);
          return { relationshipId: rel.id, data: response.data as any[], isGone: false };
        } catch (err) {
          if (isNotFound(err)) {
            return { relationshipId: rel.id, data: [], isGone: true };
          }
          throw err;
        }
      },
      enabled: !!rel.id && !!currentUserId,
      retry: false,
    })),
  });

  // Collect all unique member IDs from consent info
  const allMemberIds = new Set<string>();
  const memberToRelationshipMap = new Map<string, { relationshipId: string; memberStatus: string }>();
  
  consentQueries.forEach((query) => {
    const payload = query.data as { relationshipId: string; data: unknown; isGone?: boolean } | undefined;
    if (payload && !payload.isGone && payload.data) {
      const consentData = payload.data as {
        members?: Array<{ user_id: string; member_status?: string }>;
      };
      const members = consentData.members || [];
      members.forEach((member) => {
        if (member.user_id !== currentUserId) {
          allMemberIds.add(member.user_id);
          memberToRelationshipMap.set(member.user_id, {
            relationshipId: payload.relationshipId,
            memberStatus: member.member_status || 'UNKNOWN',
          });
        }
      });
    }
  });

  // Load user details for all members in parallel
  const userQueries = useQueries({
    queries: Array.from(allMemberIds).map((userId) => ({
      queryKey: qk.userById(userId),
      queryFn: async () => {
        try {
          const response = await apiService.getUserById(userId);
          return { userId, data: response.data, error: null };
        } catch (error: any) {
          // Return error info instead of throwing
          return { userId, data: null, error };
        }
      },
      enabled: !!userId && !!currentUserId,
      retry: false, // Don't retry on 401/403 errors
    })),
  });

  // Load market data for all users in parallel
  const marketQueries = useQueries({
    queries: Array.from(allMemberIds).map((userId) => ({
      queryKey: ['userMarket', userId],
      queryFn: async () => {
        try {
          const response = await apiService.getUserMarket(userId);
          return { userId, data: response.data, error: null };
        } catch (error: any) {
          return { userId, data: null, error };
        }
      },
      enabled: !!userId && !!currentUserId,
      retry: false,
    })),
  });

  // Build a map of relationship ID to invites (skip relationships that returned 404)
  const invitesByRelationshipId = new Map<string, any[]>();
  inviteQueries.forEach((query) => {
    const payload = query.data as { relationshipId: string; data: any[]; isGone?: boolean } | undefined;
    if (payload && !payload.isGone) {
      invitesByRelationshipId.set(payload.relationshipId, payload.data ?? []);
    }
  });

  // Build maps for quick lookup
  const userDataMap = new Map<string, any>();
  userQueries.forEach((query) => {
    if (query.data && query.data.data) {
      userDataMap.set(query.data.userId, query.data.data);
    }
  });

  const marketDataMap = new Map<string, any>();
  marketQueries.forEach((query) => {
    if (query.data && query.data.data) {
      marketDataMap.set(query.data.userId, query.data.data);
    }
  });

  // Transform relationships into LovedOne[]
  const lovedOnes: LovedOne[] = [];
  const processedMemberIds = new Set<string>();

  relationships?.forEach((rel: any) => {
    const consentQuery = consentQueries.find((q) => q.data?.relationshipId === rel.id);
    if (!consentQuery?.data || (consentQuery.data as { isGone?: boolean }).isGone) return;

    const consentData = (consentQuery.data.data ?? null) as {
      members?: Array<{ user_id: string; member_status?: string }>;
    } | null;
    const members = consentData?.members || [];
    const invites = invitesByRelationshipId.get(rel.id) || [];

    // Find other members (not the current user)
    const otherMembers = members.filter((m) => m.user_id !== currentUserId);

    // Handle inviter if not already in members
    let inviterUserId: string | null = null;
    if (invites.length > 0) {
      const latestInvite = invites[invites.length - 1] as any;
      if (latestInvite.inviter_user_id && latestInvite.inviter_user_id !== currentUserId) {
        inviterUserId = latestInvite.inviter_user_id;
      }
    }

    // Add inviter if not already processed
    if (inviterUserId && !otherMembers.some((m) => m.user_id === inviterUserId)) {
      const inviterData = userDataMap.get(inviterUserId);
      if (inviterData) {
        otherMembers.push({
          user_id: inviterUserId,
          member_status: 'ACCEPTED',
        });
      }
    }

    // Process each member
    otherMembers.forEach((member) => {
      if (processedMemberIds.has(member.user_id)) return; // Skip duplicates
      processedMemberIds.add(member.user_id);

      const isPending = member.member_status === 'INVITED' || member.member_status === 'PENDING';
      const isAccepted = member.member_status === 'ACCEPTED';

      const userData = userDataMap.get(member.user_id);
      const marketData = marketDataMap.get(member.user_id);

      // Handle case where user data fetch failed (401/403)
      if (!userData) {
        const userQuery = userQueries.find((q) => q.data?.userId === member.user_id);
        const error = userQuery?.data?.error;

        if (
          (error?.message?.includes('401') ||
            error?.message?.includes('403') ||
            error?.message?.includes('Unauthorized') ||
            error?.message?.includes('Forbidden')) &&
          isAccepted
        ) {
          // User is accepted but we can't fetch details - still show them
          const relatedInvite = invites.find(
            (inv: any) =>
              inv.inviter_user_id === member.user_id ||
              (inv.status === 'ACCEPTED' && inv.inviter_user_id === currentUserId)
          );

          lovedOnes.push({
            id: member.user_id,
            name: relatedInvite?.email?.split('@')[0] || 'Partner',
            relationship: rel.type || 'Partner',
            relationshipId: rel.id,
            isPending: false,
            economy: { ...DEFAULT_ECONOMY },
            balance: 500,
            marketItems: [...DEFAULT_MARKET_ITEMS],
          });
          return;
        }

        // Check for pending invite
        const pendingInvite = invites.find(
          (inv: any) => inv.status === 'PENDING' || inv.status === 'SENT'
        );
        if (pendingInvite) {
          lovedOnes.push({
            id: `pending_${rel.id}`,
            name: pendingInvite.email.split('@')[0] || 'Pending User',
            relationship: rel.type || 'Partner',
            relationshipId: rel.id,
            isPending: true,
            inviteId: pendingInvite.invite_id,
            pendingEmail: pendingInvite.email,
            economy: { ...DEFAULT_ECONOMY },
            balance: 500,
            marketItems: [...DEFAULT_MARKET_ITEMS],
          });
          return;
        }

        // Fallback when we couldn't load user details
        lovedOnes.push({
          id: member.user_id,
          name: 'Partner',
          relationship: rel.type || 'Partner',
          relationshipId: rel.id,
          isPending: isPending,
          economy: { ...DEFAULT_ECONOMY },
          balance: 500,
          marketItems: [...DEFAULT_MARKET_ITEMS],
        });
        return;
      }

      // User data exists - build full LovedOne
      const economy = marketData
        ? {
            currencyName: marketData.currency_name || DEFAULT_ECONOMY.currencyName,
            currencySymbol: marketData.currency_symbol || DEFAULT_ECONOMY.currencySymbol,
          }
        : { ...DEFAULT_ECONOMY };

      const balance = marketData?.balance || 0;

      const marketItems: MarketItem[] = marketData?.items
        ?.filter((item: any) => item.is_active)
        .map((item: any) => ({
          id: item.id,
          title: item.title,
          description: item.description,
          cost: item.cost,
          icon: item.icon || '🎁',
          type: (item.category === 'SPEND' ? 'product' : 'quest') as 'service' | 'product' | 'quest',
          category: (item.category === 'SPEND' ? 'spend' : 'earn') as 'earn' | 'spend',
          visibleToRelationshipIds: item.visible_to_relationship_ids || [],
        })) || [...DEFAULT_MARKET_ITEMS];

      const rawDisplay = (userData.display_name && String(userData.display_name).trim()) || '';
      const isPlaceholderName = /^User\s+[a-f0-9]{8}$/i.test(rawDisplay);
      const displayName = (!isPlaceholderName && rawDisplay) || userData.email?.split('@')[0] || 'Partner';
      lovedOnes.push({
        id: userData.id,
        name: displayName,
        relationship: rel.type || 'Partner',
        relationshipId: rel.id,
        isPending: isPending,
        profilePicture: userData.profile_picture_url || undefined,
        voiceProfileId: userData.voice_profile_id || undefined,
        economy,
        balance,
        marketItems,
      });
    });
  });

  // Check loading states
  const isLoadingConsent = consentQueries.some((q) => q.isLoading);
  const isLoadingInvites = inviteQueries.some((q) => q.isLoading);
  const isLoadingUsers = userQueries.some((q) => q.isLoading);
  const isLoadingMarkets = marketQueries.some((q) => q.isLoading);

  const isLoading =
    isLoadingRelationships ||
    isLoadingConsent ||
    isLoadingInvites ||
    isLoadingUsers ||
    isLoadingMarkets;

  return {
    data: lovedOnes,
    isLoading,
    error: relationshipsError,
  };
};

/**
 * Helper function to transform backend relationship data into LovedOne format
 * This matches the current loadRelationshipsFromBackend() logic
 * @deprecated Use useRelationshipsHydratedQuery instead
 */
export const transformRelationshipToLovedOne = async (
  relationship: any,
  currentUserId: string
): Promise<LovedOne | null> => {
  try {
    // Get consent info to find members
    const consentResponse = await apiService.getConsentInfo(relationship.id);
    const consentData = consentResponse.data as {
      members?: Array<{ user_id: string; member_status?: string }>;
    };
    
    const members = consentData.members || [];
    // Find the other member (not current user)
    const otherMember = members.find((m) => m.user_id !== currentUserId);
    
    if (!otherMember) {
      return null;
    }

    // Get user data
    const userResponse = await apiService.getUserById(otherMember.user_id);
    const userData = userResponse.data as any;

    // Get market data
    let marketData = null;
    try {
      const marketResponse = await apiService.getUserMarket(otherMember.user_id);
      marketData = marketResponse.data as any;
    } catch (error) {
      console.warn(`Failed to load market for user ${otherMember.user_id}:`, error);
    }

    // Transform to LovedOne
    const lovedOne: LovedOne = {
      id: otherMember.user_id,
      name: userData.display_name || userData.email?.split('@')[0] || 'Unknown',
      relationship: relationship.type || 'Partner',
      relationshipId: relationship.id,
      isPending: otherMember.member_status !== 'ACCEPTED',
      profilePicture: userData.profile_picture_url || null,
      economy: marketData
        ? {
            currencyName: marketData.currency_name || 'Love Tokens',
            currencySymbol: marketData.currency_symbol || '🪙',
          }
        : { ...DEFAULT_ECONOMY },
      balance: marketData?.balance || 0,
      marketItems: marketData?.items?.map((item: any) => ({
        id: item.id,
        title: item.title,
        cost: item.cost,
        icon: item.icon || '🎁',
        type: item.category === 'SPEND' ? 'product' : 'quest',
        category: item.category === 'SPEND' ? 'spend' : 'earn',
        description: item.description,
        visibleToRelationshipIds: item.visible_to_relationship_ids,
      })) || [],
    };

    return lovedOne;
  } catch (error) {
    console.error(`Failed to transform relationship ${relationship.id}:`, error);
    return null;
  }
};
