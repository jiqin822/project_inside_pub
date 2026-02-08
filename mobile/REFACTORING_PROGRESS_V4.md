# Mobile Directory Refactoring Progress - V4 (App.tsx Updated)

## ✅ Completed: App.tsx Component Imports Updated

### Updated Imports in App.tsx
- ✅ Changed all component imports to use new feature locations
- ✅ Updated component names:
  - `Onboarding` → `OnboardingWizard`
  - `LiveCoachMode` → `LiveCoachScreen`
  - `TherapistMode` → `TherapistScreen`
  - `ActivitiesMode` → `ActivitiesScreen`
  - `LoveMapsMode` → `LoveMapsScreen`
  - `RewardsMode` → `RewardsScreen`

### Fixed Issues
- ✅ Fixed TherapistScreen: Changed `XIcon` back to `X` in import and all usages
- ✅ All components now import from new feature locations
- ✅ App.tsx successfully uses refactored components

## Current Status

**Components Moved:** ✅ 12 files
**Imports Updated:** ✅ All moved components
**App.tsx Updated:** ✅ Using new component locations
**Component Names:** ✅ All renamed consistently

## Next Steps

### 1. Extract Dashboard (High Priority)
- [x] Create `src/features/dashboard/screens/DashboardHome.tsx`
- [x] Move floor plan UI from App.tsx (extracted to `FloorPlan.tsx`)
- [x] Move relationship tray (ActiveUnitsTray exists and updated)
- [x] Move side panel (extracted to `SidePanel.tsx`)
- [x] Move profile panel logic (uses existing `PersonalProfilePanel`)
- [x] Extract reaction menu (extracted to `ReactionMenu.tsx`)
- [x] Extract add relationship modal (extracted to `AddRelationshipModal.tsx`)
- [x] Update App.tsx to use DashboardHome

### 2. Create Aggregated Query
- ✅ Created `relationships.hydrated.ts` with helper functions
- ✅ Implemented full `useRelationshipsHydratedQuery()` hook with parallel queries
- ✅ Updated App.tsx to use the hook and sync with user state
- ✅ Replaced manual relationship reloads with query invalidation
- ✅ Removed `loadRelationshipsFromBackend()` entirely; login/signup/onboarding set `lovedOnes: []` and invalidate query; sync fills from `useRelationshipsHydratedQuery`

### 3. Refactor App.tsx State Management
- [x] Replace `useState` for user with `useSessionStore`
- [x] Replace `useState` for relationships with `useRelationshipStore` (syncing via query hook)
- [x] Replace `useState` for mode with `useUiStore` (via room mapping)
- [x] Replace `useState` for showSidePanel/showPersonalProfilePanel with `useUiStore`
- [x] Replace `useState` for receivedEmojis with `useRealtimeStore`
- [x] Updated DashboardHome to read from stores instead of props
- [x] Added AppMode <-> Room mapping helpers in ui.store
- [x] Updated all setUser calls to use setMe from session store
- [x] Updated all setMode calls to use setRoomFromAppMode

### 4. Wrap Screens with RoomLayout
- [x] Wrap LiveCoachScreen with RoomLayout (kept custom dark theme header)
- [x] Wrap TherapistScreen with RoomLayout
- [x] Wrap ActivitiesScreen with RoomLayout
- [x] Wrap LoveMapsScreen with RoomLayout
- [x] Wrap RewardsScreen with RoomLayout (already using RoomLayout)

### 5. Update Components to Use Stores
- [x] Update components to read from stores instead of props
  - Updated ActivitiesScreen, TherapistScreen, LiveCoachScreen, LoveMapsScreen, RewardsScreen to use `useSessionStore` and `useRelationshipsStore` instead of receiving `user` prop
  - Updated ProfileViewScreen and EditProfileScreen to use `useSessionStore` instead of receiving `user` prop
  - Updated DashboardHome to use `useSessionStore` and `useRelationshipsStore` instead of receiving `user` prop
  - Updated SidePanel to use `useSessionStore` instead of receiving `user` prop
  - Updated PersonalProfilePanel to use `useSessionStore` instead of receiving `user` prop
  - Updated App.tsx to remove `user` prop from all screen components
  - All components now read user and relationships directly from Zustand stores, reducing prop drilling significantly
- [x] Update components to use React Query hooks (beyond relationships)
  - ActivitiesScreen: added `useActivitySuggestionsMutation()` and `qk.activitySuggestions(relationshipId)`; generate-quests uses mutation for API and Gemini fallback.
  - RewardsScreen: uses `usePendingVerificationsQuery()` and `useUserMarketQuery(user.id, viewMode === 'vault')` for vault data; uses `useApproveTaskMutation()` for approve verification; replaced `loadPendingVerifications`/`loadMyMarketItems` with query data and invalidation.
- [x] Remove remaining prop drilling where possible
  - Moved dashboard UI state into `ui.store`: `isAddingUnit`, `isAddingUnitLoading`, `newUnitEmail`, `newUnitRel`, `reactionMenuTarget`, `menuPosition`, `toast`, `showToast`. DashboardHome and App read/write from store; removed ~15 props from DashboardHome.

## Files Status

**Moved:** 12 component files ✅
**Updated:** All imports fixed ✅
**Renamed:** 6 components ✅
**App.tsx:** Updated to use new components ✅
**Bug Fixes:** TherapistScreen X icon issue fixed ✅

## Cleanup (post-refactor)

- [x] Removed deprecated `handleSendInvite` from App.tsx
- [x] Removed dead code: `getBubbleStyle`, `handleUnitPointerDown/Up/Leave`, `Door`, `Window` (only used in old dashboard)
- [x] Removed entire `_OldDashboardView` block (~548 lines) from App.tsx
- [x] Removed duplicate `useEffect` that synced `userRef`
- [x] Removed unused `reactions` array and unused lucide-react / `Reward` imports from App.tsx

## Notes

- App.tsx now successfully uses all refactored components
- Old component files in `mobile/components/` still exist; App imports from `src/features/` only
- All components are in their new feature-based locations
