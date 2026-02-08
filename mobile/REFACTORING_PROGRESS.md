# Mobile Directory Refactoring Progress

## Completed Phases

### Phase 1: Foundation ✅
- ✅ Installed dependencies: `@tanstack/react-query`, `zustand`, `zod`, `react-router-dom`
- ✅ Created base folder structure (`src/app`, `src/shared`, `src/features`)
- ✅ Created constants file (`src/shared/lib/constants.ts`)
- ✅ Created error types (`src/shared/lib/errors.ts`)
- ✅ Added store-related types to `types.ts`

### Phase 2: State Management ✅
- ✅ Created Session Store (`src/features/auth/store/sessionStore.ts`)
- ✅ Created Relationship Store (`src/features/relationships/store/relationshipStore.ts`)
- ✅ Created Realtime Store (`src/shared/store/realtimeStore.ts`)
- ✅ Created Store Provider (`src/app/providers/StoreProvider.tsx`)

### Phase 3: Data Fetching ✅
- ✅ Created React Query Provider (`src/app/providers/QueryProvider.tsx`)
- ✅ Created Relationship Queries (`src/features/relationships/api/relationshipQueries.ts`)
- ✅ Created Market Queries (`src/features/rewards/api/marketQueries.ts`)
- ✅ Created Love Maps Queries structure (`src/features/loveMaps/api/loveMapQueries.ts`)

### Phase 4: API Service Refactoring ✅
- ✅ Created Base API Client (`src/shared/lib/api/baseClient.ts`)
- ✅ Created Auth Client (`src/features/auth/api/authClient.ts`)
- ✅ Created Relationship Client (`src/features/relationships/api/relationshipClient.ts`)
- ✅ Created Market Client (`src/features/rewards/api/marketClient.ts`)
- ✅ Created Voice Client (`src/features/voice/api/voiceClient.ts`)
- ✅ Created Zod Schemas (`src/shared/lib/api/schemas.ts`)

### Phase 5: Shared UI Components ✅
- ✅ Created RoomLayout component (`src/shared/ui/RoomLayout.tsx`)
- ✅ Created XpBar component (`src/shared/ui/XpBar.tsx`)
- ✅ Created TierProgress component (`src/shared/ui/TierProgress.tsx`)
- ✅ Created CurrencyDisplay component (`src/shared/ui/CurrencyDisplay.tsx`)
- ✅ Created TransactionStatusBadge component (`src/shared/ui/TransactionStatusBadge.tsx`)
- ✅ Created Button component (`src/shared/ui/Button.tsx`)
- ✅ Created Modal component (`src/shared/ui/Modal.tsx`)
- ✅ Created Toast component (`src/shared/ui/Toast.tsx`)
- ✅ Created Card component (`src/shared/ui/Card.tsx`)

### Phase 5: Shared Hooks ✅
- ✅ Created useLongPress hook (`src/shared/hooks/useLongPress.ts`)
- ✅ Created useDisclosure hook (`src/shared/hooks/useDisclosure.ts`)
- ✅ Created useInterval hook (`src/shared/hooks/useInterval.ts`)
- ✅ Created useDebounce hook (`src/shared/hooks/useDebounce.ts`)
- ✅ Created useNavigation hook (`src/shared/hooks/useNavigation.ts`)
- ✅ Created useWebSocket hook (`src/shared/hooks/useWebSocket.ts`)

### Phase 10: Real-time Improvements ✅
- ✅ Created SessionIndicator component (`src/shared/ui/SessionIndicator.tsx`)
- ✅ Created RateLimitedNudge component (`src/shared/ui/RateLimitedNudge.tsx`)
- ✅ Created NotificationList component (`src/shared/ui/NotificationList.tsx`)

### Infrastructure Updates ✅
- ✅ Updated `index.tsx` to wrap App with QueryProvider and StoreProvider
- ✅ Created ActiveUnitsTray component example (`src/features/dashboard/components/ActiveUnitsTray.tsx`)

### Phase 7: Feature Extraction - Rooms (Partial) ✅
- ✅ Created Live Coach hooks:
  - ✅ useMicrophoneStream (`src/features/liveCoach/hooks/useMicrophoneStream.ts`)
  - ✅ useAudioProcessor (`src/features/liveCoach/hooks/useAudioProcessor.ts`)
  - ✅ useLiveCoachSession (`src/features/liveCoach/hooks/useLiveCoachSession.ts`)
  - ✅ useTranscriptBuffer (`src/features/liveCoach/hooks/useTranscriptBuffer.ts`)
- ✅ Created Live Coach components:
  - ✅ TranscriptView (`src/features/liveCoach/components/TranscriptView.tsx`)
  - ✅ SentimentIndicator (`src/features/liveCoach/components/SentimentIndicator.tsx`)
- ✅ Created LiveCoachScreen (`src/features/liveCoach/screens/LiveCoachScreen.tsx`) - Example refactored room

### Phase 8: Routing & Navigation (Partial) ✅
- ✅ Created routes.tsx (`src/app/routes.tsx`) - Route definitions structure
- ✅ Created AppShell (`src/app/AppShell.tsx`) - Provider wrapper
- ✅ Created useNavigation hook (`src/shared/hooks/useNavigation.ts`) - Placeholder for routing

## Next Steps (Remaining Phases)

### Phase 6: Feature Extraction - Dashboard
- [ ] Extract DashboardScreen from App.tsx
- [ ] Create RoomGrid component
- [ ] Create AddRelationshipModal component
- [ ] Create EmojiReactionMenu component
- [ ] Create RelationshipSwitcher component
- ✅ Created ActiveUnitsTray component (example)

### Phase 7: Feature Extraction - Rooms (Continue)
- ✅ Live Coach - COMPLETE (hooks + components + screen)
- [ ] Extract RewardsMode to feature folder and use RoomLayout
- [ ] Extract LoveMapsMode to feature folder and use RoomLayout
- [ ] Extract TherapistMode to feature folder and use RoomLayout
- [ ] Extract ActivitiesMode to feature folder and use RoomLayout
- [ ] Extract Profile components to feature folder

### Phase 8: Routing & Navigation
- [ ] Create routes.tsx with route definitions
- [ ] Update useNavigation hook to use React Router
- [ ] Create AppShell component
- [ ] Update App.tsx to use routing instead of mode state

### Phase 9: Invite Flow Refactoring
- [ ] Create InviteScreen component
- [ ] Create invite state machine
- [ ] Remove invite logic from App.tsx and AuthScreen

### Phase 11: Virtualization & Performance
- [ ] Create VirtualizedTranscript component
- [ ] Update NotificationList to cap items

### Phase 12: Accessibility & Polish
- [ ] Add ARIA labels to all components
- [ ] Add keyboard navigation fallbacks
- [ ] Improve color contrast
- [ ] Add consistent loading states

## Migration Guide

### How to Use the New Infrastructure

#### Using Stores
```typescript
import { useSessionStore } from './src/features/auth/store/sessionStore';
import { useRelationshipStore } from './src/features/relationships/store/relationshipStore';
import { useRealtimeStore } from './src/shared/store/realtimeStore';

// In your component
const user = useSessionStore(state => state.user);
const relationships = useRelationshipStore(state => state.relationships);
const activeRelationship = useRelationshipStore(state => state.activeRelationship());
```

#### Using React Query
```typescript
import { useRelationshipsQuery } from './src/features/relationships/api/relationshipQueries';
import { useUserMarketQuery } from './src/features/rewards/api/marketQueries';

// In your component
const { data: relationships, isLoading, error } = useRelationshipsQuery();
const { data: market } = useUserMarketQuery(userId);
```

#### Using Shared UI Components
```typescript
import { RoomLayout } from './src/shared/ui/RoomLayout';
import { XpBar } from './src/shared/ui/XpBar';
import { CurrencyDisplay } from './src/shared/ui/CurrencyDisplay';
import { Button } from './src/shared/ui/Button';

// Wrap room screens with RoomLayout
<RoomLayout title="Dialogue Deck" relationship={activeRelationship} onBack={() => navigate('dashboard')}>
  {/* Room content */}
</RoomLayout>
```

#### Using Shared Hooks
```typescript
import { useLongPress } from './src/shared/hooks/useLongPress';
import { useDisclosure } from './src/shared/hooks/useDisclosure';
import { useWebSocket } from './src/shared/hooks/useWebSocket';

const longPressHandlers = useLongPress({
  onLongPress: (e) => handleLongPress(e),
  onClick: () => handleClick(),
});
```

## Notes

- The refactoring is incremental - old code still works alongside new infrastructure
- Components can be migrated one at a time
- Stores and React Query are ready to use but not yet integrated into App.tsx
- Domain clients are created but apiService.ts still exists for backward compatibility
- All new code follows the target architecture structure

## Testing Checklist

After each phase migration:
- [ ] Login flow works
- [ ] Dashboard displays correctly
- [ ] Can add relationships
- [ ] Can enter rooms
- [ ] Can send emoji reactions
- [ ] WebSocket connections work
- [ ] Data fetching works correctly
