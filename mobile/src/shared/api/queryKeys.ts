/**
 * Centralized React Query key factory
 * Maps to methods in apiService.ts
 */
export const qk = {
  // User / Session
  me: () => ["me"] as const,
  
  // Onboarding
  onboardingStatus: () => ["onboarding", "status"] as const,
  
  // Relationships
  relationships: () => ["relationships"] as const,
  consentInfo: (relationshipId: string) =>
    ["relationships", relationshipId, "consent"] as const,
  invites: (relationshipId: string) =>
    ["relationships", relationshipId, "invites"] as const,
  
  // Users & Contacts
  userById: (userId: string) => ["users", userId] as const,
  contactLookup: (email: string) => ["contacts", "lookup", email] as const,
  
  // Economy / Market
  economySettings: () => ["economy", "settings"] as const,
  userMarket: (userId: string) => ["market", "user", userId] as const,
  
  // Transactions
  transactionsMine: () => ["transactions", "mine"] as const,
  pendingVerifications: () => ["transactions", "pendingVerifications"] as const,
  
  // Live Coach Sessions
  sessionHistory: (limit: number) => ["sessions", "history", { limit }] as const,
  sessionReport: (sessionId: string) => ["sessions", sessionId, "report"] as const,
  
  // Interactions
  pokes: (relationshipId: string) => ["pokes", relationshipId] as const,

  // Activities
  activitySuggestions: (relationshipId: string) =>
    ["activities", "suggestions", relationshipId] as const,
  compassRecommendations: (relationshipId: string) =>
    ["activities", "compass", relationshipId] as const,
  activityHistory: (relationshipId: string) =>
    ["activities", "history", relationshipId] as const,
  plannedActivities: (relationshipId?: string) =>
    relationshipId
      ? (["activities", "planned", relationshipId] as const)
      : (["activities", "planned"] as const),
  pendingActivityInvites: () => ["activities", "invites", "pending"] as const,
  sentActivityInvites: () => ["activities", "invites", "sent"] as const,
  activityHistoryAll: (relationshipId: string) =>
    ["activities", "history", "all", relationshipId] as const,
  activityMemories: (relationshipId: string) =>
    ["activities", "memories", relationshipId] as const,
  discoverFeed: (relationshipId: string) =>
    ["activities", "discover", "feed", relationshipId] as const,
  mutualMatches: (relationshipId?: string) =>
    relationshipId
      ? (["activities", "mutual-matches", relationshipId] as const)
      : (["activities", "mutual-matches"] as const),
} as const;
