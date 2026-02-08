
export interface UserProfile {
  id: string;
  name: string;
  profilePicture?: string | null; // Base64 data URL or image URL
  voicePrintId?: string;
  gender?: string;
  birthday?: string; // ISO date YYYY-MM-DD
  occupation?: string;
  personalDescription?: string;
  interests?: string[];
  personalityType?: string; // e.g., MBTI or Big 5 summary (e.g., "INTJ", "ENFP", or "Prefer not to say")
  personalityMBTIValues?: { // MBTI slider values (0-100 for each dimension)
    ei: number; // 0=I (Introvert), 100=E (Extrovert)
    sn: number; // 0=S (Sensing), 100=N (Intuitive)
    tf: number; // 0=T (Thinking), 100=F (Feeling)
    jp: number; // 0=J (Judging), 100=P (Perceiving)
  };
  attachmentStyle?: 'secure' | 'anxious' | 'avoidant' | 'disorganized';
  attachmentStats?: {
    anxiety: number; // 0-100
    avoidance: number; // 0-100
  };
  partnerName?: string; // Kept for backward compatibility/easy access
  lovedOnes: LovedOne[];
  preferences?: {
    notifications: boolean;
    hapticFeedback: boolean;
    privacyMode: boolean;
    shareData: boolean;
  };
  // Mock data container for the new analytics features
  stats?: {
    overallAffection: number; // 0-100
    communicationScore: number; // 0-100
    weeklyTrends: number[]; // Array of 7 days scores
  };
  economy?: EconomyConfig; // User's own economy settings (for others to earn)
}

export interface EconomyConfig {
  currencyName: string;
  currencySymbol: string;
}

export interface MarketItem {
  id: string;
  title: string;
  cost: number; // The value of the item (cost to buy, or reward for completing)
  icon: string;
  type: 'service' | 'product' | 'quest';
  category: 'earn' | 'spend'; // 'earn' = bounty/request, 'spend' = reward/offer
  description?: string;
  visibleToRelationshipIds?: string[]; // Relationship IDs that can see this item (undefined = available to all). Issuer can always see their own items.
}

export type TransactionStatus = 
  | 'purchased'        // Shop: Bought, in vault, waiting to be used
  | 'redeemed'         // Shop: Used/Consumed (Completed)
  | 'accepted'         // Bounty: Taken, in progress
  | 'pending_approval' // Bounty: Marked done, waiting for partner
  | 'approved'         // Bounty: Partner confirmed, currency paid
  | 'canceled';        // Bounty: Abandoned

export interface Transaction {
  id: string;
  itemId: string;
  title: string;
  cost: number;
  icon: string;
  category: 'earn' | 'spend';
  status: TransactionStatus;
  timestamp: number;
}

export interface LovedOne {
  id: string; // User ID of the loved one (or local ID if not yet synced)
  name: string;
  relationship: string;
  relationshipId?: string; // Backend relationship ID (for syncing with backend)
  isPending?: boolean; // True if the user hasn't accepted the invite yet
  inviteId?: string; // Backend invite ID (for pending invites, used to fetch invite link)
  pendingEmail?: string; // Email of pending invite (if user not registered)
  profilePicture?: string | null; // Profile picture URL or base64 data URL
  economy?: EconomyConfig; // The currency used in this relationship (owned by the loved one)
  balance?: number; // The user's balance of this loved one's currency
  marketItems?: MarketItem[]; // Items available in this relationship context
  transactions?: Transaction[]; // History of interactions
  // Deprecated: inventory?: string[]; 
}

export enum AppMode {
  LOGIN = 'LOGIN',
  ONBOARDING = 'ONBOARDING',
  DASHBOARD = 'DASHBOARD',
  LIVE_COACH = 'LIVE_COACH',
  THERAPIST = 'THERAPIST',
  LOUNGE = 'LOUNGE',
  ACTIVITIES = 'ACTIVITIES',
  LOVE_MAPS = 'LOVE_MAPS',
  PROFILE = 'PROFILE',
  EDIT_PROFILE = 'EDIT_PROFILE',
  REWARDS = 'REWARDS'
}

export interface ChatAction {
  id: string;
  label: string;
  style: 'primary' | 'secondary' | 'danger';
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'model' | 'system';
  text: string;
  timestamp: number;
  actions?: ChatAction[];
  isPartnerContext?: boolean; // If true, this message represents the partner's side
}

export interface ActivityCard {
  id: string;
  title: string;
  description: string;
  duration: string;
  type: 'romantic' | 'fun' | 'deep' | 'active';
  xpReward: number;
}

export interface Memory {
  id: string;
  activityTitle: string;
  date: number;
  note: string;
  type: 'romantic' | 'fun' | 'deep' | 'active';
}

export interface Reward {
  id: string;
  title: string;
  cost: number;
  icon: string;
  redeemed: boolean;
}

export interface Nudge {
  type: 'warning' | 'encouragement' | 'insight';
  message: string;
  timestamp: number;
}

// Store-related types
export interface EmojiReaction {
  emoji: string;
  senderId: string;
  timestamp: number;
  isAnimating: boolean;
}

export interface Notification {
  id: string;
  type: 'emoji' | 'transaction' | 'invite' | 'nudge' | 'system';
  message: string;
  timestamp: number;
  read: boolean;
  actionUrl?: string;
}

// Relationship context types
export interface RelationshipContext {
  activeRelationshipId: string | null;
  relationships: LovedOne[];
}
