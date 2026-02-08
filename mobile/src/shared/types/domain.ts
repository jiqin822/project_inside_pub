
export interface UserProfile {
  id: string;
  name: string;
  profilePicture?: string | null; // Base64 data URL or image URL
  voicePrintId?: string;
  voicePrintData?: string; // Base64-encoded WAV for Live Coach identification (from backend)
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
    showDebug?: boolean; // Show speaker labels and voice matching scores in Live Coach
    liveCoachKnownSpeakersOnly?: boolean; // Limit Live Coach speakers to user + connections
    sttLanguageCode?: string; // 'auto' | 'en-US' | 'cmn-Hans-CN' — STT transcription language for Live Coach
    scrapbookStickersEnabled?: boolean; // When false, scrapbook HTML is generated without AI-generated sticker images
    sttDisableUnionJoin?: boolean; // When true, do not union-join speaker labels in Live Coach
  };
  // Mock data container for the new analytics features
  stats?: {
    overallAffection: number; // 0-100
    communicationScore: number; // 0-100
    weeklyTrends: number[]; // Array of 7 days scores
  };
  economy?: EconomyConfig; // User's own economy settings (for others to earn)
  loveMapStats?: LoveMapStats;
}

export type LoveMapLayer = 'VIBES' | 'LOGISTICS' | 'OS' | 'APPRECIATION' | 'REPAIR' | 'VULNERABILITY' | 'FUTURE';

export interface LoveMapStats {
  currentTier?: number;
  hintTokens: number;
  layerProgress: Record<LoveMapLayer, number>;
  completedCardIds?: string[];
  streak?: number;
  lastPlayed?: number;
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
  voiceProfileId?: string; // Voice profile ID for diarization
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

/** Lounge (group chat) room. */
export interface LoungeRoom {
  id: string;
  owner_user_id: string;
  title?: string | null;
  /** Optional goal set when creating the session (e.g. resolve a conflict, talk about feelings). */
  conversation_goal?: string | null;
  created_at: string;
  /** One-phrase summary of the session topic (from Kai context). */
  topic?: string | null;
  /** Members (included in list_rooms and get_room). */
  members?: { user_id: string; joined_at: string | null; display_name?: string | null }[];
}

/** Lounge message (public or private). */
export interface LoungeMessage {
  id: string;
  room_id: string;
  sender_user_id: string | null;
  sender_name?: string | null;
  content: string;
  visibility: 'public' | 'private_to_kai';
  sequence: number;
  created_at: string | null;
}

/** Lounge event (for replay). */
export interface LoungeEvent {
  id: string;
  room_id: string;
  sequence: number;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string | null;
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

export interface SuggestedInvitee {
  id: string;
  name: string;
}

/** Compass recommendation item (from GET /compass/recommendations). */
export interface CompassRecommendationItem {
  id: string;
  title: string;
  relationship_types?: string[];
  vibe_tags?: string[];
  risk_tags?: string[];
  constraints?: Record<string, unknown>;
  steps_markdown_template?: string;
  variants?: Record<string, unknown>;
  safety_rules?: Record<string, unknown>;
  explanation?: string;
}

export interface ActivityCard {
  id: string;
  title: string;
  description: string;
  duration: string;
  type: 'romantic' | 'fun' | 'deep' | 'active';
  xpReward: number;
  tags?: string[];
  suggestedInvitees?: SuggestedInvitee[];
  explanation?: string;
  /** Short reason for suggesting this activity (or use explanation). */
  suggestedReason?: string;
  /** LLM-recommended invitee for this activity. */
  recommendedInvitee?: SuggestedInvitee;
  /** LLM-recommended location (e.g. indoor, outdoor). */
  recommendedLocation?: string;
  /** Full LLM prompt that generated this card (debug only). */
  debugPrompt?: string;
  /** Full LLM response that generated this card (debug only). */
  debugResponse?: string;
  /** Where this activity came from when not from LLM: "seed_fallback" | "llm" (debug only). */
  debugSource?: string;
  /** Discover feed item id (for dismiss / want-to-try when card is from discover feed). */
  _discoverFeedItemId?: string;
}

/** Per-photo memory entry (url + optional caption) for completion. */
export interface MemoryEntryItem {
  url: string;
  caption?: string;
}

/** One participant's contribution to a completed activity memory (GET /activity/memories). */
export interface MemoryContribution {
  actor_user_id: string;
  actor_name?: string;
  notes_text?: string;
  memory_entries?: { url: string; caption?: string }[];
  feeling?: string;
}

/** AI-generated scrapbook layout (themeColor, headline, narrative, stickers, imageCaptions, style). API/legacy format. */
export interface ScrapbookLayout {
  themeColor: string;
  secondaryColor: string;
  narrative: string;
  headline: string;
  stickers: string[];
  imageCaptions: string[];
  style: 'polaroid' | 'classic' | 'minimal';
}

/** Single element in an element-based scrapbook layout (inside parity). */
export interface ScrapbookElement {
  type: 'text' | 'image' | 'sticker' | 'tape' | 'doodle';
  content: string;
  style: {
    top: string;
    left: string;
    width?: string;
    rotation: string;
    zIndex: number;
    fontSize?: string;
    color?: string;
    fontFamily?: string;
    background?: string;
    borderRadius?: string;
    boxShadow?: string;
    textAlign?: 'left' | 'center' | 'right';
  };
}

/** Element-based scrapbook layout (inside parity): bgStyle + elements + styleName. */
export interface ElementScrapbookLayout {
  bgStyle: { color: string; texture?: string; pattern?: string };
  elements: ScrapbookElement[];
  styleName: string;
}

/** Union: API simple layout or element-based layout for rendering. */
export type ScrapbookLayoutVariant = ScrapbookLayout | ElementScrapbookLayout;

export function isElementScrapbookLayout(l: ScrapbookLayoutVariant): l is ElementScrapbookLayout {
  return l != null && 'elements' in l && Array.isArray((l as ElementScrapbookLayout).elements);
}

/** Per-image memory (inside parity): id, url, optional caption and uploader. */
export interface MemoryImage {
  id: string;
  url: string;
  caption?: string;
  uploadedBy?: string;
}

/** Completed activity memory with combined contributions from all participants (GET /activity/memories). */
export interface ActivityMemoryItem {
  id: string;
  relationship_id: string;
  activity_template_id: string;
  activity_title: string;
  completed_at: string;
  contributions: MemoryContribution[];
  scrapbook_layout?: ScrapbookLayout | ElementScrapbookLayout | null;
}

/** History tab item: completed activity or declined invite. */
export interface ActivityHistoryAllItem {
  item_type: 'completed' | 'declined';
  id: string;
  relationship_id: string;
  activity_template_id: string;
  activity_title: string;
  date: string;
  notes_text?: string | null;
  memory_urls?: string[] | null;
  invite_id?: string | null;
}

/** Memory (inside parity): optional feeling, images, participants, partnerNotes, layout. */
export interface Memory {
  id: string;
  activityTitle: string;
  date: number;
  note: string;
  type: 'romantic' | 'fun' | 'deep' | 'active';
  feeling?: string;
  images?: MemoryImage[];
  participants?: string[];
  partnerNotes?: { authorId: string; authorName: string; text: string; timestamp: number }[];
  layout?: ScrapbookLayout | ElementScrapbookLayout;
}

/** Map API ActivityMemoryItem to Memory-like shape for shared card rendering. */
export function activityMemoryToMemory(item: ActivityMemoryItem): Memory {
  const contributions = item.contributions ?? [];
  const firstNote = contributions.map((c) => c.notes_text).filter(Boolean).join(' ') || '';
  const partnerNotes = contributions
    .filter((c) => c.actor_user_id && c.notes_text)
    .map((c) => ({
      authorId: c.actor_user_id,
      authorName: c.actor_name ?? 'Partner',
      text: c.notes_text ?? '',
      timestamp: new Date(item.completed_at).getTime(),
    }));
  const images: MemoryImage[] = contributions.flatMap((c) =>
    (c.memory_entries ?? []).map((e, i) => ({
      id: `${c.actor_user_id}-${i}`,
      url: e.url,
      caption: e.caption,
      uploadedBy: c.actor_user_id,
    }))
  );
  return {
    id: item.id,
    activityTitle: item.activity_title,
    date: new Date(item.completed_at).getTime(),
    note: firstNote,
    type: 'fun',
    feeling: contributions.find((c) => c.feeling)?.feeling,
    images: images.length ? images : undefined,
    participants: contributions.map((c) => c.actor_user_id).filter(Boolean),
    partnerNotes: partnerNotes.length ? partnerNotes : undefined,
    layout: item.scrapbook_layout ?? undefined,
  };
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

/** Action data for navigating to the event that generated the notification (e.g. open Planned tab, scroll to invite). */
export interface NotificationAction {
  inviteId?: string;
  plannedId?: string;
  roomId?: string;
}

export interface Notification {
  id: string;
  type: 'emoji' | 'transaction' | 'invite' | 'activity_invite' | 'lounge_invite' | 'nudge' | 'system' | 'message' | 'alert' | 'reward' | 'emotion' | 'love_map' | 'therapist' | 'scrapbook';
  message: string;
  timestamp: number;
  read: boolean;
  title?: string;
  actionUrl?: string;
  /** Optional action data for click-to-navigate (e.g. activity_invite → Activities, Planned tab). */
  action?: NotificationAction;
}

/** Central Notification API: addNotification(type, title, message) passed from App to feature modules. */
export type AddNotificationFn = (
  type: Notification['type'],
  title: string,
  message: string
) => void;

// Relationship context types
export interface RelationshipContext {
  activeRelationshipId: string | null;
  relationships: LovedOne[];
}
