# Mobile Directory Refactoring Progress - V2 (Updated Plan)

## New Plan Implementation Status

### ✅ Phase 1: File Structure & Core Infrastructure

**File Tree Created:**
- ✅ `src/app/` - App shell, routes, providers, bootstrap
- ✅ `src/shared/` - API, services, UI, hooks, types
- ✅ `src/stores/` - Zustand stores
- ✅ `src/features/` - Feature-based organization

**Files Moved:**
- ✅ `services/apiService.ts` → `src/shared/api/apiService.ts`
- ✅ `services/geminiService.ts` → `src/shared/services/geminiService.ts`
- ✅ `services/audioUtils.ts` → `src/shared/services/audioUtils.ts`
- ✅ `types.ts` → `src/shared/types/domain.ts`
- ✅ `components/RewardsMode.tsx` → `src/features/rewards/screens/RewardsScreen.tsx`

**Imports Updated:**
- ✅ Fixed imports in moved files to use new paths
- ✅ Updated shared components to use new type paths

### ✅ Phase 2: Zustand Stores (New Structure)

**Created Stores:**
- ✅ `src/stores/session.store.ts` - Auth tokens, current user, status
- ✅ `src/stores/relationships.store.ts` - Relationships list, active relationship
- ✅ `src/stores/realtime.store.ts` - WebSocket status, emoji tags
- ✅ `src/stores/ui.store.ts` - Room navigation, panels, modals

**Store Features:**
- ✅ Session store with `hydrateFromStorage()` and `fetchMe()`
- ✅ Relationships store with `getActiveRelationship()` selector
- ✅ Realtime store with `clearExpiredEmojiTags()` for TTL cleanup
- ✅ UI store with room navigation and panel toggles

### ✅ Phase 3: React Query Setup

**Query Keys:**
- ✅ `src/shared/api/queryKeys.ts` - Centralized query key factory
- ✅ Maps to all apiService.ts methods
- ✅ Type-safe query keys

**Query Hooks Created:**
- ✅ `src/features/auth/api/auth.queries.ts` - useMeQuery
- ✅ `src/features/relationships/api/relationships.queries.ts` - All relationship queries
- ✅ `src/features/rewards/api/rewards.queries.ts` - Market and transaction queries

**Mutation Hooks Created:**
- ✅ `src/features/auth/api/auth.mutations.ts` - Login, signup, update profile
- ✅ `src/features/relationships/api/relationships.mutations.ts` - CRUD operations
- ✅ `src/features/rewards/api/rewards.mutations.ts` - Market operations

### ✅ Phase 4: App Shell & Bootstrap

**Created:**
- ✅ `src/app/bootstrap/initAuthFromStorage.ts` - Initialize auth from localStorage
- ✅ `src/app/AppShell.tsx` - Updated to use new stores and bootstrap
- ✅ `src/app/Routes.tsx` - Route definitions using new stores

**Features:**
- ✅ Auth initialization on app start
- ✅ Session status checking
- ✅ Route protection based on auth status

### ✅ Phase 5: Component Migration (COMPLETE)

**Moved:**
- ✅ RewardsMode → RewardsScreen (imports updated)
- ✅ AuthScreen → `src/features/auth/screens/AuthScreen.tsx`
- ✅ Onboarding → `src/features/onboarding/screens/OnboardingWizard.tsx`
- ✅ LiveCoachMode → `src/features/liveCoach/screens/LiveCoachScreen.tsx`
- ✅ TherapistMode → `src/features/therapist/screens/TherapistScreen.tsx`
- ✅ ActivitiesMode → `src/features/activities/screens/ActivitiesScreen.tsx`
- ✅ LoveMapsMode → `src/features/loveMaps/screens/LoveMapsScreen.tsx`
- ✅ ProfileView → `src/features/profile/screens/ProfileViewScreen.tsx`
- ✅ EditProfile → `src/features/profile/screens/EditProfileScreen.tsx`
- ✅ PersonalProfilePanel → `src/features/profile/screens/PersonalProfilePanel.tsx`
- ✅ BiometricSync → `src/features/profile/components/BiometricSync.tsx`
- ✅ VoiceAuth → `src/features/profile/components/VoiceAuth.tsx`
- ✅ AvatarPicker → `src/features/onboarding/components/AvatarPicker.tsx`
- ✅ MBTISliders → `src/features/onboarding/components/MBTISliders.tsx`

**App.tsx Updated:**
- ✅ All imports updated to use new component locations
- ✅ All component usages updated to use new names
- ✅ No linter errors

### ⬜ Phase 6: Dashboard Extraction

**To Create:**
- ⬜ `src/features/dashboard/screens/DashboardHome.tsx` - Extract from App.tsx
- ⬜ `src/features/dashboard/components/FloorPlan.tsx` - Optional
- ⬜ `src/features/dashboard/components/RelationshipTray.tsx` - Optional (ActiveUnitsTray exists)
- ⬜ `src/features/dashboard/components/ReactionMenu.tsx` - Optional
- ⬜ `src/features/dashboard/components/SidePanel.tsx` - Optional

### ⬜ Phase 7: App.tsx Refactoring

**Current State:**
- App.tsx still contains all logic (1940 lines)
- Uses old state management (useState)
- Uses old data fetching (manual apiService calls)
- Uses mode-based navigation

**Target State:**
- App.tsx becomes thin wrapper (<200 lines)
- Uses stores for state
- Uses React Query for data
- Uses UI store for navigation

## Next Steps

1. **Continue Component Migration**
   - Move remaining components to feature folders
   - Update imports
   - Wrap screens with RoomLayout

2. **Extract Dashboard**
   - Create DashboardHome.tsx
   - Move floor plan UI
   - Move relationship tray
   - Move side panel

3. **Refactor App.tsx**
   - Replace useState with stores
   - Replace manual fetching with React Query
   - Replace mode state with UI store
   - Use Routes component

4. **Create Aggregated Query**
   - `useRelationshipsHydratedQuery()` - Combines all relationship loading
   - Reduces churn from current `loadRelationshipsFromBackend()`

5. **Update RewardsScreen**
   - Wrap with RoomLayout
   - Use React Query hooks instead of manual fetching
   - Use stores for state

## Files Created/Updated

### New Files (30+)
- Stores: 4 files
- Query hooks: 6 files
- Mutation hooks: 3 files
- Bootstrap: 1 file
- Query keys: 1 file
- Routes: 1 file (updated)
- AppShell: 1 file (updated)
- Moved files: 5 files

### Updated Files
- Fixed imports in 7 shared files
- Updated AppShell.tsx
- Created Routes.tsx

## Key Improvements

1. **Centralized Query Keys**: All query keys in one place, type-safe
2. **Store Structure**: Matches product reality (session, relationships, realtime, UI)
3. **Bootstrap Pattern**: Auth initialization separated from app logic
4. **Feature Organization**: Components organized by domain
5. **Import Paths**: Consistent import structure

## Migration Strategy

The refactoring follows an incremental approach:
1. ✅ Infrastructure is ready (stores, queries, mutations)
2. ⚠️ Components are being moved one by one
3. ⬜ App.tsx will be refactored last to minimize breaking changes
4. ⬜ Old code continues to work alongside new code

## Notes

- All new code uses the new file structure
- Old components still work (backward compatible)
- Stores are ready but not yet integrated into App.tsx
- React Query hooks are ready but not yet used in components
- RewardsScreen moved but needs RoomLayout wrapper and React Query integration
