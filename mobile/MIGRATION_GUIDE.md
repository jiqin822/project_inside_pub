# Mobile Refactoring Migration Guide

## Quick Start: Using the New Infrastructure

### 1. Using Stores Instead of useState

**Before:**
```typescript
const [user, setUser] = useState<UserProfile | null>(null);
const [relationships, setRelationships] = useState<LovedOne[]>([]);
```

**After:**
```typescript
import { useSessionStore } from './src/features/auth/store/sessionStore';
import { useRelationshipStore } from './src/features/relationships/store/relationshipStore';

const user = useSessionStore(state => state.user);
const setUser = useSessionStore(state => state.setUser);
const relationships = useRelationshipStore(state => state.relationships);
const activeRelationship = useRelationshipStore(state => state.activeRelationship());
```

### 2. Using React Query Instead of Manual Fetching

**Before:**
```typescript
const loadRelationships = async () => {
  const response = await apiService.getRelationships();
  setRelationships(response.data);
};
```

**After:**
```typescript
import { useRelationshipsQuery } from './src/features/relationships/api/relationshipQueries';

const { data: relationships, isLoading, error } = useRelationshipsQuery();
// React Query handles loading, caching, and refetching automatically
```

### 3. Using Shared UI Components

**Before:**
```typescript
<div className="bg-white border-2 border-slate-200 p-4">
  <h3>Room Title</h3>
  <button onClick={onBack}>Back</button>
  {/* content */}
</div>
```

**After:**
```typescript
import { RoomLayout } from './src/shared/ui/RoomLayout';

<RoomLayout title="Room Title" relationship={activeRelationship} onBack={onBack}>
  {/* content */}
</RoomLayout>
```

### 4. Using Shared Hooks

**Before:**
```typescript
const [isModalOpen, setIsModalOpen] = useState(false);
const openModal = () => setIsModalOpen(true);
const closeModal = () => setIsModalOpen(false);
```

**After:**
```typescript
import { useDisclosure } from './src/shared/hooks/useDisclosure';

const { isOpen, open, close } = useDisclosure();
```

### 5. Using Domain API Clients

**Before:**
```typescript
await apiService.getRelationships();
```

**After:**
```typescript
import { relationshipClient } from './src/features/relationships/api/relationshipClient';

await relationshipClient.getRelationships();
```

## Migration Checklist

### Phase 1: Update Imports
- [ ] Replace `DEFAULT_MARKET_ITEMS` import with `src/shared/lib/constants`
- [ ] Replace `DEFAULT_ECONOMY` import with `src/shared/lib/constants`

### Phase 2: Migrate State to Stores
- [ ] Replace `user` state with `useSessionStore`
- [ ] Replace `relationships` state with `useRelationshipStore`
- [ ] Replace `receivedEmojis` state with `useRealtimeStore`

### Phase 3: Migrate Data Fetching
- [ ] Replace `loadRelationshipsFromBackend` with `useRelationshipsQuery`
- [ ] Replace manual market fetching with `useUserMarketQuery`
- [ ] Use mutations for create/update/delete operations

### Phase 4: Extract Dashboard
- [ ] Create `DashboardScreen.tsx`
- [ ] Move dashboard JSX from App.tsx
- [ ] Use `ActiveUnitsTray` component
- [ ] Create `RoomGrid` component
- [ ] Create `AddRelationshipModal` component

### Phase 5: Migrate Rooms One by One
- [ ] Start with simplest room (Activities or Therapist)
- [ ] Move to `src/features/[room]/screens/`
- [ ] Wrap with `RoomLayout`
- [ ] Use shared components (Button, Card, etc.)
- [ ] Use React Query hooks
- [ ] Test thoroughly
- [ ] Repeat for next room

### Phase 6: Integrate Routing
- [ ] Update App.tsx to use React Router
- [ ] Replace `mode` state with routes
- [ ] Update all `setMode` calls to `navigate()`

## Example: Migrating a Simple Room

Here's how to migrate `ActivitiesMode`:

1. **Create screen file:**
   ```typescript
   // src/features/activities/screens/ActivitiesScreen.tsx
   import { RoomLayout } from '../../../shared/ui/RoomLayout';
   import { useRelationshipStore } from '../../relationships/store/relationshipStore';
   
   export const ActivitiesScreen = ({ user, onExit }) => {
     const activeRelationship = useRelationshipStore(state => state.activeRelationship());
     
     return (
       <RoomLayout
         title="Activities"
         relationship={activeRelationship}
         onBack={onExit}
       >
         {/* Existing ActivitiesMode content */}
       </RoomLayout>
     );
   };
   ```

2. **Update App.tsx:**
   ```typescript
   // Replace import
   // import { ActivitiesMode } from './components/ActivitiesMode';
   import { ActivitiesScreen } from './src/features/activities/screens/ActivitiesScreen';
   
   // Replace usage
   // {mode === AppMode.ACTIVITIES && <ActivitiesMode ... />}
   {mode === AppMode.ACTIVITIES && <ActivitiesScreen ... />}
   ```

3. **Gradually use shared components:**
   - Replace buttons with `<Button>`
   - Replace modals with `<Modal>`
   - Use `useDisclosure` for modal state

## Common Patterns

### Loading States
```typescript
const { data, isLoading, error } = useQuery(...);

if (isLoading) return <LoadingSpinner />;
if (error) return <ErrorMessage error={error} />;
// Render data
```

### Mutations
```typescript
const createMutation = useCreateRelationshipMutation();

const handleCreate = async () => {
  try {
    await createMutation.mutateAsync({ type, memberIds });
    // Success - React Query automatically invalidates and refetches
  } catch (error) {
    // Handle error
  }
};
```

### Store Updates
```typescript
// Update relationship in store
const updateRelationship = useRelationshipStore(state => state.updateRelationship);
updateRelationship(relationshipId, { balance: newBalance });

// Or use React Query mutation which updates cache automatically
```

## Testing After Migration

1. **Manual Testing:**
   - Login/logout
   - Add relationship
   - Enter each room
   - Send emoji reaction
   - Complete a transaction

2. **Check Console:**
   - No errors
   - React Query cache working
   - WebSocket connecting

3. **Check Network:**
   - No duplicate requests
   - Proper caching (requests only when needed)

## Rollback Plan

If something breaks:
1. Git commit before each major change
2. Keep old code until new code is proven
3. Use feature flags if needed
4. Each phase is independently reversible

## Getting Help

- Check `REFACTORING_SUMMARY.md` for what's been completed
- Check `REFACTORING_PROGRESS.md` for current status
- Look at `LiveCoachScreen.tsx` as a complete example
- All new code is in `src/` directory
