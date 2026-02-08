import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Capacitor } from '@capacitor/core';
import { useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { AppMode, UserProfile, LovedOne, EconomyConfig, MarketItem } from './types';
import type { AddNotificationFn } from './src/shared/types/domain';
import { apiService } from './services/apiService';
import { syncLovedOnes, addWatchSendHeartListener, addWatchSendEmotionListener, canSendWatchNudge, sendEmojiToWatch, sendEmotionToWatch } from './src/shared/services/watchNudge';
import { registerPushNotifications, setupPushTapHandler } from './src/shared/services/pushNotifications';
// Import from new feature locations
import { OnboardingWizard } from './src/features/onboarding/screens/OnboardingWizard';
import { LiveCoachScreen } from './src/features/liveCoach/screens/LiveCoachScreen';
import { TherapistScreen } from './src/features/therapist/screens/TherapistScreen';
import { LoungeScreen } from './src/features/lounge/screens/LoungeScreen';
import { ActivitiesScreen } from './src/features/activities/screens/ActivitiesScreen';
import { LoveMapsScreen } from './src/features/loveMaps/screens/LoveMapsScreen';
import { RewardsScreen } from './src/features/rewards/screens/RewardsScreen';
import { AuthScreen } from './src/features/auth/screens/AuthScreen';
import { BiometricSync } from './src/features/profile/components/BiometricSync';
import { ProfileView } from './src/features/profile/screens/ProfileViewScreen';
import { EditProfile } from './src/features/profile/screens/EditProfileScreen';
import { PersonalProfilePanel } from './src/features/profile/screens/PersonalProfilePanel';
import { DashboardHome } from './src/features/dashboard/screens/DashboardHome';
import { REACTION_EMOTION } from './src/features/dashboard/components/ReactionMenu';
import { useRelationshipsHydratedQuery } from './src/features/relationships/api/relationships.hydrated';
import { qk } from './src/shared/api/queryKeys';
// Import stores
import { useSessionStore } from './src/stores/session.store';
import { useRelationshipsStore } from './src/stores/relationships.store';
import { useUiStore, roomToAppMode } from './src/stores/ui.store';
import { useRealtimeStore } from './src/stores/realtime.store';
import { DEFAULT_MARKET_ITEMS, DEFAULT_ECONOMY } from './src/shared/lib/constants';

const App: React.FC = () => {
  const queryClient = useQueryClient();
  
  // Use stores
  const { me: user, setMe, setCurrentUserEmail, currentUserEmail, clearSession } = useSessionStore();
  const { relationships, setRelationships } = useRelationshipsStore();
  const { room, setRoomFromAppMode, showSidePanel, showPersonalProfilePanel, toggleSidePanel, toggleProfilePanel } = useUiStore();
  const toast = useUiStore((s) => s.toast);
  const { receivedEmojisByUserId, upsertEmojiTag, setReceivedEmotion } = useRealtimeStore();

  /** Central Notification API: addNotification(type, title, message). Passed to feature modules. */
  const addNotification: AddNotificationFn = useCallback((type, title, message) => {
    useRealtimeStore.getState().addNotificationFromEvent(type, title, message);
  }, []);
  
  // Derive mode from room
  const mode = roomToAppMode(room);
  const setMode = (newMode: AppMode) => setRoomFromAppMode(newMode);
  
  // Local state for UI-specific things
  const [showVoiceAuth, setShowVoiceAuth] = useState(false);
  const [pendingMode, setPendingMode] = useState<AppMode | null>(null);
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState<string | null>(null);
  const [inviteRelationshipType, setInviteRelationshipType] = useState<string | null>(null);
  const [inviterName, setInviterName] = useState<string | null>(null);
  
  // Use aggregated relationships query hook
  const { data: lovedOnesFromQuery, isLoading: isLoadingRelationships } = useRelationshipsHydratedQuery(user?.id || null);
  
  // Sync query data to relationships store and user state when relationships change.
  // Only update when content actually changes (query returns new array ref every render).
  useEffect(() => {
    if (!lovedOnesFromQuery || isLoadingRelationships) return;
    const queryIds = lovedOnesFromQuery.map((lo) => lo.id).sort().join(',');
    const currentStoreIds = relationships.map((lo) => lo.id).sort().join(',');
    if (currentStoreIds !== queryIds) {
      setRelationships(lovedOnesFromQuery);
    }
    if (user) {
      const currentUserIds = user.lovedOnes.map((lo) => lo.id).sort().join(',');
      if (currentUserIds !== queryIds) {
        setMe({ ...user, lovedOnes: lovedOnesFromQuery });
      }
    }
  }, [lovedOnesFromQuery, isLoadingRelationships, user, relationships, setRelationships, setMe]);

  // When API gets 401 and can't recover (no refresh or refresh failed), clear session so UI shows login
  useEffect(() => {
    apiService.setOnUnauthorized(() => useSessionStore.getState().clearSession());
  }, []);

  // Sync loved ones to watch for grid; register watch "send heart" listener.
  useEffect(() => {
    if (!user?.lovedOnes?.length || !canSendWatchNudge()) return;
    void syncLovedOnes(user.lovedOnes);
  }, [user?.lovedOnes]);

  useEffect(() => {
    if (!canSendWatchNudge()) return;
    const unsubscribe = addWatchSendHeartListener((lovedOneId) => {
      apiService.sendHeart(lovedOneId).catch((err) => console.warn('[Watch] sendHeart failed', err));
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!canSendWatchNudge()) return;
    const unsubscribe = addWatchSendEmotionListener((lovedOneId, emotionKind) => {
      apiService.sendEmotion(lovedOneId, emotionKind).catch((err) => console.warn('[Watch] sendEmotion failed', err));
    });
    return unsubscribe;
  }, []);

  // Push notifications: register and upload token when user is set (native only)
  useEffect(() => {
    if (!user?.id || !Capacitor.isNativePlatform()) return;
    let cleanup: (() => void) | null = null;
    registerPushNotifications(apiService).then((fn) => {
      cleanup = fn;
    });
    return () => {
      cleanup?.();
    };
  }, [user?.id]);

  // Push tap: open dashboard (or Activities/Lounge for invite types) and notification center to the tapped message
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    let cleanup: (() => void) | null = null;
    setupPushTapHandler((payload) => {
      if (payload.type === 'activity_invite') {
        useUiStore.getState().setRoomFromAppMode(AppMode.ACTIVITIES);
      } else if (payload.type === 'lounge_invite') {
        useUiStore.getState().setRoomFromAppMode(AppMode.LOUNGE);
      } else {
        useUiStore.getState().setRoomFromAppMode(AppMode.DASHBOARD);
      }
      useUiStore.getState().toggleSidePanel(true);
      useUiStore.getState().setOpenToNotificationId(payload.notificationId);
    }).then((fn) => {
      cleanup = fn;
    });
    return () => {
      cleanup?.();
    };
  }, []);

  // Global XP (User Level) - Distinct from currency
  const [xp, setXp] = useState(1250);

  // Dashboard UI state lives in ui store (isAddingUnit, reaction menu, toast, etc.)
  const reactionMenuTarget = useUiStore((s) => s.reactionMenuTarget);
  const setReactionMenuTarget = useUiStore((s) => s.setReactionMenuTarget);
  const setMenuPosition = useUiStore((s) => s.setMenuPosition);
  const [showShareLink, setShowShareLink] = useState(false);
  const [shareLinkUrl, setShareLinkUrl] = useState<string>('');

  // Long press visual feedback only
  const [activeReaction, setActiveReaction] = useState<string | null>(null);
  const longPressTimer = useRef<NodeJS.Timeout | null>(null);
  const isLongPress = useRef(false);
  // Ref to store current user for WebSocket handler (avoids stale closure)
  // Use store's me value
  const userRef = useRef<UserProfile | null>(null);
  const addNotificationRef = useRef(addNotification);

  // Sync refs with current values
  useEffect(() => {
    userRef.current = user;
  }, [user]);
  useEffect(() => {
    addNotificationRef.current = addNotification;
  }, [addNotification]);

  // Relationships are loaded via useRelationshipsHydratedQuery and synced to store; invalidate after mutations.

  // WebSocket and notification handling for emoji pokes
  useEffect(() => {
    if (!user?.id) return;
    
    // Check if user is authenticated - verify token exists
    const token = apiService.getAccessToken();
    if (!token) {
      console.warn('No access token available for WebSocket connection - user may need to log in');
      return;
    }

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }

    console.log('[DEBUG] Setting up WebSocket connection for real-time emoji notifications for user:', user.id);
    console.log('[DEBUG] NOTE: Polling has been removed - using WebSocket only');
    
    // Connect to WebSocket for real-time emoji notifications
    const ws = apiService.connectWebSocket(
      token,
      async (message: any) => {
        console.log('[DEBUG] Received WebSocket message:', message);
        
        // Handle emotion notification (from send-emotion; show as tag on icon, watch full-screen, or push)
        if (message.type === 'notification.new') {
          const payload = message.payload;
          if (payload?.type === 'emotion' && payload.sender_id != null && payload.sender_name != null) {
            const senderId = String(payload.sender_id);
            const senderName = String(payload.sender_name);
            const emotionKind = payload.emotion_kind != null ? String(payload.emotion_kind) : undefined;
            const ts = typeof payload.timestamp === 'number' ? payload.timestamp : Date.now();
            setReceivedEmotion(senderId, { senderName, emotionKind, timestamp: ts });
            const deliveredToWatch = await sendEmotionToWatch({ senderName, emotionKind });
            if (!deliveredToWatch && 'Notification' in window && Notification.permission === 'granted') {
              const title = emotionKind ? `${senderName} sent you ${emotionKind}` : `${senderName} sent you love`;
              new Notification(title, {
                body: `${senderName} sent you an emotion`,
                icon: '/favicon.ico',
                tag: `emotion-${payload.id ?? Date.now()}`,
              });
            }
            return;
          }
          if (payload?.type === 'activity_invite') {
            const title = payload.title != null ? String(payload.title) : 'Activity';
            const messageText = payload.message != null ? String(payload.message) : '';
            const action =
              payload.invite_id != null || payload.planned_id != null
                ? {
                    inviteId: payload.invite_id != null ? String(payload.invite_id) : undefined,
                    plannedId: payload.planned_id != null ? String(payload.planned_id) : undefined,
                  }
                : undefined;
            useRealtimeStore.getState().addNotificationFromEvent('activity_invite', title, messageText, action);
            queryClient.invalidateQueries({ queryKey: qk.pendingActivityInvites() });
            queryClient.invalidateQueries({ queryKey: qk.sentActivityInvites() });
            queryClient.invalidateQueries({ queryKey: qk.plannedActivities() });
            showToast(messageText || title);
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification(title, {
                body: messageText,
                icon: '/favicon.ico',
                tag: `activity_invite-${payload.id ?? Date.now()}`,
              });
            }
            return;
          }
          if (payload?.type === 'lounge_invite') {
            const title = payload.title != null ? String(payload.title) : 'Chat group invite';
            const messageText = payload.message != null ? String(payload.message) : '';
            const action = payload.room_id != null ? { roomId: String(payload.room_id) } : undefined;
            useRealtimeStore.getState().addNotificationFromEvent('lounge_invite', title, messageText, action);
            showToast(messageText || title);
            if ('Notification' in window && Notification.permission === 'granted') {
              new Notification(title, {
                body: messageText,
                icon: '/favicon.ico',
                tag: `lounge_invite-${payload.id ?? Date.now()}`,
              });
            }
            return;
          }
          // Generic: any other notification.new → center + OS (dual channel)
          const allowedTypes = ['emoji', 'transaction', 'invite', 'activity_invite', 'lounge_invite', 'nudge', 'system', 'message', 'alert', 'reward', 'emotion', 'love_map', 'therapist'] as const;
          const type = payload?.type && allowedTypes.includes(payload.type as typeof allowedTypes[number])
            ? (payload.type as typeof allowedTypes[number])
            : 'system';
          const genericTitle = payload?.title != null ? String(payload.title) : 'Notification';
          const genericMessage = payload?.message != null ? String(payload.message) : '';
          addNotificationRef.current?.(type, genericTitle, genericMessage);
          if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(genericTitle, {
              body: genericMessage,
              icon: '/favicon.ico',
              tag: `notif-${payload?.id ?? Date.now()}`,
            });
          }
        }

        // Handle emoji poke messages
        if (message.type === 'emoji_poke') {
          const { sender_id, emoji, created_at, relationship_id } = message;
          
          console.log(`[DEBUG] Processing emoji poke: ${emoji} from sender ${sender_id}`);
          
          // Get current user from ref (always up-to-date)
          const currentUser = userRef.current;
          if (!currentUser) {
            console.warn('[DEBUG] No current user available in WebSocket handler');
            return;
          }
          
          // Find the loved one who sent this emoji by matching sender_id
          const lovedOne = currentUser.lovedOnes?.find(lo => lo.id === sender_id && !lo.isPending);
          if (!lovedOne) {
            console.warn(`[DEBUG] Received emoji from unknown sender: ${sender_id}, current loved ones:`, currentUser.lovedOnes?.map(lo => ({ id: lo.id, name: lo.name })));
            return;
          }
          
          console.log(`[DEBUG] Processing emoji poke: ${emoji} from ${lovedOne.name} (${sender_id})`);
          
          // Use the poke's created_at timestamp to determine age
          const pokeTimestamp = new Date(created_at).getTime();
          const emojiAge = Date.now() - pokeTimestamp;
          const isRecent = emojiAge < 30000; // Less than 30 seconds old
          
          // Show emoji indicator (always, for in-app UI)
          upsertEmojiTag(lovedOne.id, {
            emoji: emoji,
            senderId: sender_id,
            timestamp: pokeTimestamp,
            isAnimating: isRecent
          });

          const senderName = lovedOne.name;
          // Send to watch for full-screen when available; else show phone notification
          const deliveredToWatch = await sendEmojiToWatch({ emoji, senderName });
          if (!deliveredToWatch && 'Notification' in window && Notification.permission === 'granted') {
            console.log(`[DEBUG] Showing notification: ${senderName} sent ${emoji}`);
            new Notification(`${senderName} sent you ${emoji}`, {
              body: `${senderName} sent you an emoji!`,
              icon: '/favicon.ico',
              tag: `emoji-${message.poke_id}`,
            });
          } else if (deliveredToWatch) {
            console.log(`[DEBUG] Emoji sent to watch: ${senderName} sent ${emoji}`);
          } else {
            console.log(`[DEBUG] Notification permission not granted:`, Notification.permission);
          }
          
          // Stop animation after 30 seconds (when emoji becomes "old")
          // Note: Animation state is handled by the component checking timestamp
          // The store will automatically clear expired tags via clearExpiredEmojiTags
        }
      },
      (error) => {
        console.error('[DEBUG] WebSocket error:', error);
      },
      () => {
        console.log('[DEBUG] WebSocket connection closed');
      }
    );
    
    return () => {
      console.log('[DEBUG] Cleaning up WebSocket connection');
      if (ws) {
        ws.close();
      }
    };
  }, [queryClient, user?.id, user?.lovedOnes]);

  // Check for voice print requirement before entering LIVE_COACH
  useEffect(() => {
      if (mode === AppMode.LIVE_COACH && user && !user.voicePrintId && !showVoiceAuth && !pendingMode) {
          setPendingMode(AppMode.LIVE_COACH);
          setShowVoiceAuth(true);
      }
  }, [mode, user?.id, user?.voicePrintId, showVoiceAuth, pendingMode]);

  // Helper function to preserve existing preferences when loading user from backend
  const preservePreferences = (existingPrefs: UserProfile['preferences']): UserProfile['preferences'] => {
    return {
      notifications: existingPrefs?.notifications ?? true,
      hapticFeedback: existingPrefs?.hapticFeedback ?? true,
      privacyMode: existingPrefs?.privacyMode ?? false,
      shareData: existingPrefs?.shareData ?? false,
      // Preserve frontend-only preferences
      showDebug: existingPrefs?.showDebug,
      liveCoachKnownSpeakersOnly: existingPrefs?.liveCoachKnownSpeakersOnly ?? false,
      scrapbookStickersEnabled: existingPrefs?.scrapbookStickersEnabled,
      sttLanguageCode: existingPrefs?.sttLanguageCode,
    };
  };

  useEffect(() => {
    // Check if we have a token and try to load user from backend
    const loadUserFromBackend = async () => {
      const token = apiService.getAccessToken();
      if (token) {
        try {
          const response = await apiService.getCurrentUser();
          // Map backend user response to UserProfile format
          const backendUser = response.data as {
            id: string;
            email: string;
            display_name?: string;
            pronouns?: string;
            personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
            goals?: string[];
            hobbies?: string[];
            personal_description?: string;
            profile_picture_url?: string;
            voice_profile_id?: string;
            voice_print_data?: string;
          };
          
          console.log(`[DEBUG] Current user ${backendUser.id} (${backendUser.email}): profile_picture_url =`, backendUser.profile_picture_url);
          
          // Load user's economy settings
          let userEconomy: EconomyConfig | undefined;
          try {
            const economyResponse = await apiService.getEconomySettings();
            const economyData = economyResponse.data as {
              user_id: string;
              currency_name: string;
              currency_symbol: string;
            };
            userEconomy = {
              currencyName: economyData.currency_name,
              currencySymbol: economyData.currency_symbol,
            };
            console.log(`[DEBUG] Loaded user economy settings on refresh:`, userEconomy);
          } catch (error) {
            console.warn('Failed to load user economy settings on refresh, using default:', error);
            // Will default to undefined, which will fall back to DEFAULT_ECONOMY in components
          }
          
          // Preserve existing preferences
          const currentUser = useSessionStore.getState().me;
          const existingPreferences = preservePreferences(currentUser?.preferences);
          
          const userProfile: UserProfile = {
            id: backendUser.id,
            name: backendUser.display_name || backendUser.email,
            profilePicture: backendUser.profile_picture_url || undefined,
            gender: backendUser.pronouns || undefined,
            personalDescription: backendUser.personal_description || undefined,
            interests: backendUser.hobbies?.length ? backendUser.hobbies : backendUser.goals || [],
            personalityType: backendUser.personality_type?.type || undefined,
            personalityMBTIValues: backendUser.personality_type?.values || undefined,
            lovedOnes: [], // Filled by useRelationshipsHydratedQuery sync
            economy: userEconomy,
            voicePrintId: backendUser.voice_profile_id || undefined,
            voicePrintData: backendUser.voice_print_data || undefined,
            preferences: existingPreferences,
          };
          setMe(userProfile);
          setCurrentUserEmail(backendUser.email);
          queryClient.invalidateQueries({ queryKey: qk.relationships() });
          setMode(AppMode.DASHBOARD);
        } catch (error) {
          apiService.clearTokens();
          setMode(AppMode.LOGIN);
        }
      }
    };
    loadUserFromBackend();
    
    // Check for invite token in URL
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
      setInviteToken(token);
      // Try to get invite info to pre-fill email and relationship
      apiService.validateInviteToken(token)
        .then((response: any) => {
          const inviteData = response.data as { 
            email?: string; 
            relationship_type?: string;
            inviter_name?: string;
          };
          if (inviteData.email) {
            setInviteEmail(inviteData.email);
          }
          if (inviteData.relationship_type) {
            setInviteRelationshipType(inviteData.relationship_type);
          }
          if (inviteData.inviter_name) {
            setInviterName(inviteData.inviter_name);
          }
        })
        .catch((error) => {
          console.error('Failed to validate invite token:', error);
          // Token might be invalid, but we'll still show the signup form
        });
    }
  }, []);

  // Global Pointer Listeners for Slide-to-Select
  useEffect(() => {
    const handleGlobalMove = (e: PointerEvent) => {
        if (reactionMenuTarget) {
            const el = document.elementFromPoint(e.clientX, e.clientY);
            const reactionBtn = el?.closest('[data-reaction]');
            if (reactionBtn) {
                const reaction = reactionBtn.getAttribute('data-reaction');
                setActiveReaction(reaction);
            } else {
                setActiveReaction(null);
            }
        }
    };

    const handleGlobalUp = (e: PointerEvent) => {
        if (reactionMenuTarget) {
            const el = document.elementFromPoint(e.clientX, e.clientY);
            const reactionBtn = el?.closest('[data-reaction]');
            const reaction = reactionBtn?.getAttribute('data-reaction');
            
            if (reaction) {
                sendReaction(reaction);
            } else {
                setReactionMenuTarget(null);
            }
            
            // Close menu and reset
            setMenuPosition(null);
            setActiveReaction(null);
            document.body.style.overflow = '';
            isLongPress.current = false;
        }
    };

    if (reactionMenuTarget) {
        window.addEventListener('pointermove', handleGlobalMove);
        window.addEventListener('pointerup', handleGlobalUp);
        document.body.style.overflow = 'hidden';
    }

    return () => {
        window.removeEventListener('pointermove', handleGlobalMove);
        window.removeEventListener('pointerup', handleGlobalUp);
        document.body.style.overflow = '';
    };
  }, [reactionMenuTarget]);

  const migrateProfile = (profile: UserProfile): UserProfile => {
      // Ensure all loved ones have economy data structure
      const updatedLovedOnes = profile.lovedOnes.map(lo => ({
          ...lo,
          economy: lo.economy || { ...DEFAULT_ECONOMY },
          balance: lo.balance ?? 500,
          marketItems: lo.marketItems || [...DEFAULT_MARKET_ITEMS]
      }));
      return { ...profile, lovedOnes: updatedLovedOnes };
  };

  const handleLoginSuccess = async (email: string) => {
    setCurrentUserEmail(email);
    try {
      // Fetch user profile from backend
      const response = await apiService.getCurrentUser();
      const backendUser = response.data as {
        id: string;
        email: string;
        display_name?: string;
        pronouns?: string;
        personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
        goals?: string[];
        hobbies?: string[];
        personal_description?: string;
        profile_picture_url?: string;
        voice_profile_id?: string;
        voice_print_data?: string;
      };
      
      // Load user's economy settings
      let userEconomy: EconomyConfig | undefined;
      try {
        const economyResponse = await apiService.getEconomySettings();
        const economyData = economyResponse.data as {
          user_id: string;
          currency_name: string;
          currency_symbol: string;
        };
        userEconomy = {
          currencyName: economyData.currency_name,
          currencySymbol: economyData.currency_symbol,
        };
      } catch (error) {
        console.warn('Failed to load user economy settings, using default:', error);
      }
      
      const userProfile: UserProfile = {
        id: backendUser.id,
        name: backendUser.display_name || backendUser.email,
        profilePicture: backendUser.profile_picture_url || undefined,
        gender: backendUser.pronouns || undefined,
        personalDescription: backendUser.personal_description || undefined,
        interests: backendUser.hobbies?.length ? backendUser.hobbies : backendUser.goals || [],
        personalityType: backendUser.personality_type?.type || undefined,
        personalityMBTIValues: backendUser.personality_type?.values || undefined,
        lovedOnes: [], // Filled by useRelationshipsHydratedQuery sync
        economy: userEconomy,
        voicePrintId: backendUser.voice_profile_id || undefined,
        voicePrintData: backendUser.voice_print_data || undefined,
        preferences: {
          notifications: true,
          hapticFeedback: true,
          privacyMode: false,
          shareData: false,
          liveCoachKnownSpeakersOnly: false,
        },
      };
      setMe(userProfile);
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
      setMode(AppMode.DASHBOARD);
    } catch (error) {
      // If user doesn't have profile yet, go to onboarding
      console.error('Failed to load user after login:', error);
      setMode(AppMode.ONBOARDING);
    }
  };

  const handleSignupSuccess = async (email: string) => {
    setCurrentUserEmail(email);
    localStorage.setItem('inside_last_user', email);
    
    try {
      const response = await apiService.getCurrentUser();
      const backendUser = response.data as {
        id: string;
        email: string;
        display_name?: string;
        pronouns?: string;
        personality_type?: { type?: string; values?: { ei: number; sn: number; tf: number; jp: number } };
        goals?: string[];
        hobbies?: string[];
        personal_description?: string;
        voice_profile_id?: string;
        voice_print_data?: string;
      };
      
      const userProfile: UserProfile = {
        id: backendUser.id,
        name: backendUser.display_name || backendUser.email,
        gender: backendUser.pronouns || undefined,
        personalDescription: backendUser.personal_description || undefined,
        interests: backendUser.hobbies?.length ? backendUser.hobbies : backendUser.goals || [],
        personalityType: backendUser.personality_type?.type || undefined,
        personalityMBTIValues: backendUser.personality_type?.values || undefined,
        lovedOnes: [], // Filled by useRelationshipsHydratedQuery sync
        voicePrintId: backendUser.voice_profile_id || undefined,
        voicePrintData: backendUser.voice_print_data || undefined,
        preferences: {
          notifications: true,
          hapticFeedback: true,
          privacyMode: false,
          shareData: false,
          liveCoachKnownSpeakersOnly: false,
        },
      };
      setMe(userProfile);
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
      
      // Route: dashboard if they have relationships (e.g. invite), else onboarding
      try {
        const relRes = await apiService.getRelationships();
        const rels = (relRes.data as any[]) || [];
        setMode(rels.length > 0 ? AppMode.DASHBOARD : AppMode.ONBOARDING);
      } catch {
        setMode(AppMode.ONBOARDING);
      }
    } catch (error) {
      console.error('Failed to load user after signup:', error);
      setMode(AppMode.ONBOARDING);
    }
  };

  const handleOnboardingComplete = async (profile: UserProfile) => {
    const migrated = migrateProfile(profile);
    
    try {
      const response = await apiService.getCurrentUser();
      const backendUser = response.data as {
        id: string;
        email: string;
        display_name?: string;
        pronouns?: string;
        personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
        goals?: string[];
        profile_picture_url?: string;
        voice_profile_id?: string;
        voice_print_data?: string;
      };
      migrated.id = backendUser.id;
      migrated.lovedOnes = []; // Filled by useRelationshipsHydratedQuery sync
      if (backendUser.display_name && !migrated.name) {
        migrated.name = backendUser.display_name;
      }
      if (backendUser.profile_picture_url && !migrated.profilePicture) {
        migrated.profilePicture = backendUser.profile_picture_url;
      }
      if (backendUser.voice_profile_id) migrated.voicePrintId = backendUser.voice_profile_id;
      if (backendUser.voice_print_data) migrated.voicePrintData = backendUser.voice_print_data;

      // Sync onboarding profile to backend (birthday, occupation, description, interests, personality, etc.)
      await apiService.updateProfile({
        display_name: migrated.name || undefined,
        pronouns: migrated.gender || undefined,
        personal_description: migrated.personalDescription || undefined,
        hobbies: migrated.interests?.length ? migrated.interests : undefined,
        birthday: migrated.birthday || undefined,
        occupation: migrated.occupation || undefined,
        personality_type: migrated.personalityType === 'Prefer not to say'
          ? { type: 'Prefer not to say' }
          : migrated.personalityMBTIValues
            ? { type: migrated.personalityType || '', values: migrated.personalityMBTIValues }
            : undefined,
        profile_picture_url: migrated.profilePicture || undefined,
      });
    } catch (error) {
      console.error('Failed to load user after onboarding:', error);
      if (migrated.id) {
        migrated.lovedOnes = [];
      }
    }
    
    setMe(migrated);
    if (currentUserEmail) {
      const users = JSON.parse(localStorage.getItem('inside_users') || '{}');
      if (users[currentUserEmail]) {
        users[currentUserEmail].profile = migrated;
        localStorage.setItem('inside_users', JSON.stringify(users));
      }
    }
    queryClient.invalidateQueries({ queryKey: qk.relationships() });
    setMode(AppMode.DASHBOARD);
  };

  const handleProfileUpdate = (updatedProfile: UserProfile) => {
    setMe(updatedProfile);
    if (currentUserEmail) {
        const users = JSON.parse(localStorage.getItem('inside_users') || '{}');
        if (users[currentUserEmail]) {
            users[currentUserEmail].profile = updatedProfile;
            localStorage.setItem('inside_users', JSON.stringify(users));
        }
    }
  };
  
  const handleUpdateLovedOne = (id: string, updates: Partial<LovedOne>) => {
      if (!user) return;
      const updatedLovedOnes = user.lovedOnes.map(lo => 
          lo.id === id ? { ...lo, ...updates } : lo
      );
      handleProfileUpdate({ ...user, lovedOnes: updatedLovedOnes });
  };

  // Refresh market data for a specific loved one (memoized to prevent recreation)
  const refreshLovedOneMarket = useCallback(async (lovedOneId: string) => {
    if (!user) return;
    
    try {
      const marketResponse = await apiService.getUserMarket(lovedOneId);
      const marketData = marketResponse.data as {
        items: Array<{
          id: string;
          title: string;
          description?: string;
          cost: number;
          icon?: string;
          category: string;
          is_active: boolean;
        }>;
        balance: number;
        currency_name: string;
        currency_symbol: string;
      };
      
      const economy = {
        currencyName: marketData.currency_name,
        currencySymbol: marketData.currency_symbol,
      };
      const balance = marketData.balance;
      const marketItems: MarketItem[] = marketData.items
        .filter(item => item.is_active)
        .map(item => ({
          id: item.id,
          title: item.title,
          description: item.description,
          cost: item.cost,
          icon: item.icon || '🎁',
          type: (item.category === 'SPEND' ? 'product' : 'quest') as 'service' | 'product' | 'quest',
          category: (item.category === 'SPEND' ? 'spend' : 'earn') as 'earn' | 'spend',
        }));
      
      handleUpdateLovedOne(lovedOneId, { economy, balance, marketItems });
      console.log(`[DEBUG] Refreshed market data for ${lovedOneId}:`, { economy, balance, itemCount: marketItems.length });
    } catch (error: any) {
      console.warn(`Failed to refresh market data for ${lovedOneId}:`, error);
    }
  }, [user, handleUpdateLovedOne]); // Memoize with dependencies

  const handleLogout = () => {
      localStorage.removeItem('inside_last_user');
      clearSession();
      setCurrentUserEmail(null);
      setMode(AppMode.LOGIN);
  };

  const handleRestrictedAccess = (targetMode: AppMode) => {
    // Check if user has voice print set up
    if (!user?.voicePrintId) {
      // Voice print not set up - show setup prompt
      setPendingMode(targetMode);
      setShowVoiceAuth(true);
    } else {
      // Voice print exists - proceed directly to the mode without verification
      setMode(targetMode);
    }
  };

  const handleAuthSuccess = () => {
    setShowVoiceAuth(false);
    if (pendingMode) {
      setMode(pendingMode);
      setPendingMode(null);
    }
  };

  const showToast = (msg: string) => useUiStore.getState().showToast(msg);

  const handleAddUnit = async (email: string, relationship: string) => {
        if (!user || !email.trim()) {
          showToast('Email is required');
          return;
        }
        const token = apiService.getAccessToken();
        if (!token) {
          showToast('Please log in to add relationships');
          useUiStore.getState().setIsAddingUnitLoading(false);
          return;
        }
        useUiStore.getState().setIsAddingUnitLoading(true);
        
        try {
          // Lookup contact by email
          const lookupResponse = await apiService.lookupContact(email.trim());
          const lookupData = lookupResponse.data as {
            status: string;
            user?: { id: string; display_name?: string; email?: string };
          };
          
          if (lookupData.status === 'EXISTS' && lookupData.user) {
            // User exists - check if relationship already exists
            const existingRelationships = await apiService.getRelationships();
            const relationships = (existingRelationships.data as any[]) || [];
            
            // Check if user is already in a relationship with current user
            let existingRelationship = null;
            for (const rel of relationships) {
              try {
                const consentResponse = await apiService.getConsentInfo(rel.id);
                const consentData = consentResponse.data as {
                  members?: Array<{ user_id: string }>;
                };
                const members = (consentData.members || []) as Array<{ user_id: string }>;
                const hasUser = members.some(m => m.user_id === lookupData.user!.id);
                if (hasUser) {
                  existingRelationship = rel;
                  break;
                }
              } catch (error) {
                // Skip if we can't check this relationship
                continue;
              }
            }
            
            if (existingRelationship) {
              showToast(`${lookupData.user.display_name || lookupData.user.email} is already in a relationship with you`);
              useUiStore.getState().setIsAddingUnitLoading(false);
              return;
            }
            
            // User exists and no existing relationship - create relationship
            const relationshipType = mapRelationshipTypeToBackend(relationship);
            const createResponse = await apiService.createRelationship(
              relationshipType,
              [lookupData.user.id]
            );
            const relationshipId = (createResponse.data as { id: string }).id;
            const lovedOneId = lookupData.user.id;
            
            // Use the user's display name from backend, fallback to email prefix
            const lovedOneName = lookupData.user.display_name 
              || lookupData.user.email?.split('@')[0] 
              || email.trim().split('@')[0];
            
            // Create lovedOne entry with proper name
            const newPerson: LovedOne = {
              id: lovedOneId,
              name: lovedOneName,
              relationship: relationship,
              relationshipId: relationshipId,
              isPending: false, // User exists, so not pending
              economy: { ...DEFAULT_ECONOMY },
              balance: 500,
              marketItems: [...DEFAULT_MARKET_ITEMS]
            };
            
            // Invalidate relationships query to trigger refetch
            console.log(`[DEBUG] Invalidating relationships query after creating relationship ${relationshipId}`);
            queryClient.invalidateQueries({ queryKey: qk.relationships() });
            // Query hook will automatically refetch and update user state via useEffect
            
            useUiStore.getState().setNewUnitEmail('');
            useUiStore.getState().setNewUnitRel('Partner');
            useUiStore.getState().setIsAddingUnit(false);
            showToast(`Added: ${lovedOneName}`);
            useUiStore.getState().setIsAddingUnitLoading(false);
          } else if (lookupData.status === 'NOT_FOUND') {
            // User doesn't exist - ask if they want to send an invite
            // Email not found - directly create invite and show share interface
            useUiStore.getState().setIsAddingUnitLoading(true);
            
            try {
              // Create a draft relationship (with just the current user)
              const relationshipType = mapRelationshipTypeToBackend(relationship);
              const createResponse = await apiService.createRelationship(
                relationshipType,
                [] // Empty array - will add creator automatically
              );
              const relationshipId = (createResponse.data as { id: string }).id;
              
              // Create invite and get invitation link
              const inviteResponse = await apiService.createInvite(
                relationshipId,
                email.trim(),
                relationship.toLowerCase()
              );
              
              const inviteData = inviteResponse.data as { invite_url?: string; invite_id: string };
              const inviteUrl = inviteData.invite_url;
              
              if (!inviteUrl) {
                throw new Error('Invitation URL not returned from server');
              }
              
              // Use email prefix as name for pending entry
              const emailName = email.trim().split('@')[0] || 'Pending User';
              
              // Invalidate relationships query to trigger refetch
              queryClient.invalidateQueries({ queryKey: qk.relationships() });
              // Query hook will automatically refetch and update user state via useEffect
              
              // Check if we're on a native platform
              const isNative = Capacitor.isNativePlatform();
              
              if (isNative) {
                // Use native share interface on mobile devices
                try {
                  const { Share } = await import('@capacitor/share');
                  const shareResult = await Share.share({
                    title: `Join my ${relationship} relationship on Project Inside`,
                    text: `${user.name} has invited you to connect with them as their ${relationship} on Project Inside.\n\nAccept the invitation: ${inviteUrl}`,
                    url: inviteUrl,
                    dialogTitle: 'Share Invitation',
                  });
                  
                  // ShareResult.activityType contains the app identifier if shared, or empty string if cancelled
                  if (shareResult.activityType) {
                    showToast(`Invitation shared successfully`);
                  } else {
                    showToast(`Invitation cancelled`);
                  }
                  
                  useUiStore.getState().setNewUnitEmail('');
                  useUiStore.getState().setNewUnitRel('Partner');
                  useUiStore.getState().setIsAddingUnit(false);
                  useUiStore.getState().setIsAddingUnitLoading(false);
                } catch (shareError: any) {
                  console.error('Failed to share invite:', shareError);
                  // Fallback: show the link modal
                  useUiStore.getState().setNewUnitEmail('');
                  useUiStore.getState().setNewUnitRel('Partner');
                  useUiStore.getState().setIsAddingUnit(false);
                  setShareLinkUrl(inviteUrl);
                  setShowShareLink(true);
                  useUiStore.getState().setIsAddingUnitLoading(false);
                }
              } else {
                // On web, show the link in a modal for copying
                useUiStore.getState().setNewUnitEmail('');
                useUiStore.getState().setNewUnitRel('Partner');
                useUiStore.getState().setIsAddingUnit(false);
                setShareLinkUrl(inviteUrl);
                setShowShareLink(true);
                useUiStore.getState().setIsAddingUnitLoading(false);
              }
            } catch (inviteError: any) {
              console.error('Failed to create invite:', inviteError);
              showToast(`Failed to create invite: ${inviteError.message}`);
              useUiStore.getState().setIsAddingUnitLoading(false);
            }
          } else if (lookupData.status === 'BLOCKED') {
            showToast('This email domain is blocked');
            useUiStore.getState().setIsAddingUnitLoading(false);
          }
        } catch (lookupError: any) {
          console.error('Contact lookup failed:', lookupError);
          showToast(`Error: ${lookupError.message || 'Failed to lookup contact'}`);
          useUiStore.getState().setIsAddingUnitLoading(false);
        }
  };

  // Map frontend relationship type to backend type
  const mapRelationshipTypeToBackend = (relType: string): string => {
    const lower = relType.toLowerCase();
    if (lower.includes('partner') || lower.includes('spouse')) return 'romantic';
    if (lower === 'date') return 'date';
    if (lower.includes('child') || lower.includes('parent') || lower.includes('sibling')) return 'family';
    if (lower.includes('friend')) return 'friendship';
    if (lower.includes('colleague')) return 'professional';
    return 'friendship'; // Default
  };

  const handleRemoveUnit = async (id: string) => {
        if (!user) return;
        
        const lovedOne = user.lovedOnes.find(l => l.id === id);
        if (!lovedOne) return;
        
        // If has relationshipId, delete from backend
        if (lovedOne.relationshipId) {
          try {
            await apiService.deleteRelationship(lovedOne.relationshipId);
            showToast(`Removed relationship with ${lovedOne.name}`);
          } catch (error: any) {
            console.error('Failed to delete relationship:', error);
            showToast(`Error: ${error.message || 'Failed to delete relationship'}`);
            // Still remove locally even if backend fails
          }
        } else {
          // Local-only lovedOne, just remove from UI
          showToast(`Removed ${lovedOne.name}`);
        }
        
        // Invalidate relationships query to trigger refetch
        queryClient.invalidateQueries({ queryKey: qk.relationships() });
        // Query hook will automatically refetch and update user state via useEffect
  };
  
  // Function to refresh relationships from backend
  const refreshRelationships = async () => {
    if (!user) return;
    
    try {
      const currentUserResponse = await apiService.getCurrentUser();
      const currentUser = currentUserResponse.data as { id: string };
      // Invalidate query to trigger refetch
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
      // Query hook will automatically refetch and update user state via useEffect
      showToast('Relationships refreshed');
    } catch (error) {
      console.error('Failed to refresh relationships:', error);
      showToast('Failed to refresh relationships');
    }
  };

  const togglePref = (key: keyof NonNullable<UserProfile['preferences']>) => {
        if (!user) return;
        const defaultPrefs = {
          notifications: true,
          hapticFeedback: true,
          privacyMode: false,
          shareData: true,
          liveCoachKnownSpeakersOnly: false,
        };
        const currentPrefs = user.preferences || defaultPrefs;
        const newPrefs = { ...currentPrefs, [key]: !currentPrefs[key] };
        const newUser = { ...user, preferences: newPrefs };
        setMe(newUser);
        if (currentUserEmail) {
            const users = JSON.parse(localStorage.getItem('inside_users') || '{}');
            if (users[currentUserEmail]) {
                users[currentUserEmail].profile = newUser;
                localStorage.setItem('inside_users', JSON.stringify(users));
            }
        }
  };

  const getPref = (key: keyof NonNullable<UserProfile['preferences']>) => {
        return user?.preferences?.[key] ?? true;
  };

  const sendReaction = async (emoji: string) => {
        if (!reactionMenuTarget || !user) {
            setReactionMenuTarget(null);
            return;
        }
        try {
            // Send emotion notification (watch full-screen 5s / tag on icon / push)
            if (emoji === REACTION_EMOTION) {
                await apiService.sendEmotion(reactionMenuTarget.id);
                showToast(`Sent emotion to ${reactionMenuTarget.name}`);
                setReactionMenuTarget(null);
                return;
            }
            const lovedOne = user.lovedOnes.find(l => l.id === reactionMenuTarget.id);
            if (lovedOne?.relationshipId) {
                console.log(`[DEBUG] Sending emoji ${emoji} to ${reactionMenuTarget.name} (${reactionMenuTarget.id}) in relationship ${lovedOne.relationshipId}`);
                const response = await apiService.sendPoke(lovedOne.relationshipId, reactionMenuTarget.id, 'emoji', emoji);
                console.log(`[DEBUG] Emoji sent successfully:`, response);
                showToast(`Sent ${emoji} to ${reactionMenuTarget.name}`);
            } else {
                console.error(`[DEBUG] Cannot send emoji: relationship not found for ${reactionMenuTarget.id}`);
                showToast(`Cannot send emoji: relationship not found`);
            }
        } catch (error: any) {
            console.error('[DEBUG] Failed to send emoji/emotion:', error);
            showToast(`Error: ${error.message || 'Failed to send'}`);
        }
        setReactionMenuTarget(null);
  };
  const toastNode = toast ? (
    <div
      className="fixed top-6 left-1/2 transform -translate-x-1/2 bg-slate-900 text-white px-6 py-3 rounded-none border border-white shadow-xl z-50 flex items-center gap-2 animate-slide-in-down font-mono text-xs"
      style={{ top: 'calc(var(--sat, 0px) + 1.5rem)' }}
    >
      <span className="text-lg">✨</span>
      <span className="font-bold uppercase">{toast}</span>
    </div>
  ) : null;
  const withToast = (node: React.ReactNode) => (
    <>
      {toastNode}
      {node}
    </>
  );

  // --- Render Switching ---

  if (showVoiceAuth && user) {
      return withToast(
        <BiometricSync
          context="dialogue_deck"
          onComplete={async (voicePrintId: string) => {
            // Refetch /users/me to get voice_print_data (base64) for Live Coach
            if (user) {
              try {
                const res = await apiService.getCurrentUser();
                const data = res.data as { voice_profile_id?: string; voice_print_data?: string };
                handleProfileUpdate({
                  ...user,
                  voicePrintId: data.voice_profile_id ?? voicePrintId,
                  voicePrintData: data.voice_print_data ?? undefined,
                });
              } catch {
                handleProfileUpdate({ ...user, voicePrintId });
              }
            }
            setShowVoiceAuth(false);
            setPendingMode(null);
            handleAuthSuccess();
          }}
          onCancel={() => {
            setShowVoiceAuth(false);
            setPendingMode(null);
          }}
          allowSkip={false}
        />
      );
  }

  if (mode === AppMode.LOGIN) {
      return withToast(
        <AuthScreen 
          onLogin={handleLoginSuccess} 
          onSignup={handleSignupSuccess} 
          inviteToken={inviteToken} 
          inviteEmail={inviteEmail}
          inviteRelationshipType={inviteRelationshipType}
          inviterName={inviterName}
        />
      );
  }

  if (mode === AppMode.ONBOARDING) {
      return withToast(<OnboardingWizard onComplete={handleOnboardingComplete} />);
  }

  // Ensure user exists for dashboard and protected modes
  if (!user) return null;

  if (mode === AppMode.LIVE_COACH) {
      // If voice print is not set up, show VoiceAuth (handled above)
      if (!user?.voicePrintId) {
          return null; // VoiceAuth will be shown by the showVoiceAuth check above
      }
      return withToast(<LiveCoachScreen onExit={() => setMode(AppMode.DASHBOARD)} />);
  }

  if (mode === AppMode.THERAPIST) {
      return withToast(<TherapistScreen onExit={() => setMode(AppMode.DASHBOARD)} onAddNotification={addNotification} />);
  }

  if (mode === AppMode.LOUNGE) {
      return withToast(<LoungeScreen onExit={() => setMode(AppMode.DASHBOARD)} />);
  }

  if (mode === AppMode.ACTIVITIES) {
      return withToast(
        <ActivitiesScreen 
          xp={xp} 
          setXp={setXp} 
          economy={user?.economy || { currencyName: 'Tokens', currencySymbol: '🪙' }}
          onExit={() => setMode(AppMode.DASHBOARD)} 
          onUpdateLovedOne={handleUpdateLovedOne}
          onAddNotification={addNotification}
        />
      );
  }

  if (mode === AppMode.LOVE_MAPS) {
      return withToast(
        <LoveMapsScreen 
          xp={xp} 
          setXp={setXp} 
          economy={user?.economy || { currencyName: 'Tokens', currencySymbol: '🪙' }}
          onExit={() => setMode(AppMode.DASHBOARD)}
          onUpdateLovedOne={handleUpdateLovedOne}
          onAddNotification={addNotification}
        />
      );
  }

  if (mode === AppMode.REWARDS) {
      return withToast(
        <RewardsScreen 
          onUpdateLovedOne={handleUpdateLovedOne}
          onUpdateProfile={handleProfileUpdate}
          onRefreshMarket={refreshLovedOneMarket}
          onExit={() => setMode(AppMode.DASHBOARD)}
          onAddNotification={addNotification}
        />
      );
  }

  if (mode === AppMode.PROFILE) {
      return withToast(<ProfileView onBack={() => setMode(AppMode.DASHBOARD)} />);
  }

  if (mode === AppMode.EDIT_PROFILE) {
      return withToast(<EditProfile onBack={() => setMode(AppMode.DASHBOARD)} onUpdateProfile={handleProfileUpdate} />);
  }

  // Default: Dashboard View
  if (!user) {
    return null; // Should not happen, but guard against it
  }
  
  return withToast(
    <>
      <DashboardHome
        onRoomClick={setMode}
        onRestrictedAccess={handleRestrictedAccess}
        onUpdateProfile={handleProfileUpdate}
        onUpdateLovedOne={(id, updates) => {
          const updatedLovedOnes = user.lovedOnes.map(lo => lo.id === id ? { ...lo, ...updates } : lo);
          handleProfileUpdate({ ...user, lovedOnes: updatedLovedOnes });
        }}
        onAddRelationship={handleAddUnit}
        onRemoveRelationship={handleRemoveUnit}
        onLogout={handleLogout}
        onEditProfile={() => setMode(AppMode.EDIT_PROFILE)}
        sendReaction={sendReaction}
        onAddNotification={addNotification}
      />
      
      {/* Share Link Modal */}
      {showShareLink && (
        <div className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-md border-2 border-slate-900 p-6 shadow-[8px_8px_0px_rgba(15,23,42,1)] relative animate-slide-in-down">
            <button 
              onClick={() => { setShowShareLink(false); setShareLinkUrl(''); }} 
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-900"
            >
              <X size={20} />
            </button>
            <div className="mb-6">
              <h3 className="font-black text-slate-900 text-lg uppercase tracking-tight mb-2">Share Invitation</h3>
              <p className="text-xs font-mono text-slate-500 mb-4">
                {user?.name && `${user.name} has invited you to connect with them on Project Inside.`}
              </p>
              <p className="text-xs font-mono text-slate-600 mb-4">
                Copy this link and share it with the person you want to invite:
              </p>
              <div className="space-y-2">
                <label className="block text-[10px] font-bold text-slate-700 uppercase tracking-widest">Invitation Link</label>
                <div className="flex gap-2">
                  <input 
                    type="text" 
                    value={shareLinkUrl} 
                    readOnly
                    className="flex-1 bg-slate-50 border border-slate-300 p-2 text-xs font-mono text-slate-700 focus:outline-none focus:border-indigo-500"
                  />
                  <button 
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(shareLinkUrl);
                        showToast('Link copied to clipboard');
                      } catch (err) {
                        // Fallback for older browsers
                        const textArea = document.createElement('textarea');
                        textArea.value = shareLinkUrl;
                        textArea.style.position = 'fixed';
                        textArea.style.opacity = '0';
                        document.body.appendChild(textArea);
                        textArea.select();
                        try {
                          document.execCommand('copy');
                          showToast('Link copied to clipboard');
                        } catch (fallbackErr) {
                          console.error('Failed to copy link');
                          showToast('Failed to copy link');
                        }
                        document.body.removeChild(textArea);
                      }
                    }}
                    className="bg-white border-2 border-slate-900 hover:bg-slate-50 text-slate-900 text-[10px] font-bold uppercase tracking-widest px-4 py-2 transition-colors whitespace-nowrap"
                  >
                    Copy
                  </button>
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <button 
                onClick={() => { setShowShareLink(false); setShareLinkUrl(''); }}
                className="flex-1 bg-white border-2 border-slate-900 hover:bg-slate-50 text-slate-900 text-xs font-bold uppercase tracking-widest py-3 transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};


export default App;