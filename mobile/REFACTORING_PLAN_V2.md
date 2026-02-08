# Mobile Directory Refactoring Plan - V2 (Updated)

## Overview

This is an updated refactoring plan based on a concrete file tree mapping and new Zustand store structure. The plan focuses on incremental migration with minimal breaking changes.

## Target File Structure

```
src/
  app/
    AppShell.tsx              ✅ Created
    Routes.tsx                ✅ Created
    providers/
      QueryProvider.tsx       ✅ Created
    bootstrap/
      initAuthFromStorage.ts  ✅ Created

  shared/
    api/
      apiService.ts           ✅ Moved
      queryKeys.ts            ✅ Created
    services/
      geminiService.ts        ✅ Moved
      audioUtils.ts           ✅ Moved
    ui/                       ✅ Created (RoomLayout, etc.)
    hooks/                    ✅ Created (useLongPress, etc.)
    types/
      domain.ts               ✅ Moved (from types.ts)

  stores/
    session.store.ts          ✅ Created
    relationships.store.ts     ✅ Created
    realtime.store.ts         ✅ Created
    ui.store.ts               ✅ Created

  features/
    auth/
      screens/
        AuthScreen.tsx        ⬜ To move
      api/
        auth.queries.ts       ✅ Created
        auth.mutations.ts     ✅ Created

    onboarding/
      screens/
        OnboardingWizard.tsx  ⬜ To move
      components/
        MBTISliders.tsx       ⬜ To move
        AvatarPicker.tsx      ⬜ To move

    dashboard/
      screens/
        DashboardHome.tsx     ⬜ To create
      components/
        RelationshipTray.tsx  ✅ Created (ActiveUnitsTray)

    relationships/
      api/
        relationships.queries.ts    ✅ Created
        relationships.mutations.ts  ✅ Created

    liveCoach/
      screens/
        LiveCoachScreen.tsx   ✅ Created (needs update)
      hooks/                  ✅ Created

    rewards/
      screens/
        RewardsScreen.tsx     ✅ Moved (needs RoomLayout wrapper)
      api/
        rewards.queries.ts    ✅ Created
        rewards.mutations.ts  ✅ Created

    therapist/
      screens/
        TherapistScreen.tsx   ⬜ To move

    activities/
      screens/
        ActivitiesScreen.tsx  ⬜ To move

    loveMaps/
      screens/
        LoveMapsScreen.tsx    ⬜ To move

    profile/
      screens/
        ProfileViewScreen.tsx      ⬜ To move
        EditProfileScreen.tsx      ⬜ To move
        PersonalProfilePanel.tsx    ⬜ To move
      components/
        BiometricSync.tsx     ⬜ To move
        VoiceAuth.tsx         ⬜ To move
```

## Zustand Store Structure

### session.store.ts ✅
- `accessToken`, `refreshToken`, `me`, `status`
- `setTokens()`, `clearSession()`, `hydrateFromStorage()`, `fetchMe()`

### relationships.store.ts ✅
- `relationships`, `activeRelationshipId`
- `setRelationships()`, `setActiveRelationship()`, `getActiveRelationship()`

### realtime.store.ts ✅
- `wsStatus`, `receivedEmojisByUserId`
- `setWsStatus()`, `upsertEmojiTag()`, `clearExpiredEmojiTags()`

### ui.store.ts ✅
- `room`, `showSidePanel`, `showPersonalProfilePanel`
- `setRoom()`, `toggleSidePanel()`, `toggleProfilePanel()`

## React Query Structure

### Query Keys (qk) ✅
Centralized in `src/shared/api/queryKeys.ts`:
- `qk.me()`
- `qk.relationships()`
- `qk.consentInfo(relationshipId)`
- `qk.userMarket(userId)`
- `qk.transactionsMine()`
- etc.

### Query Hooks ✅
- `src/features/auth/api/auth.queries.ts`
- `src/features/relationships/api/relationships.queries.ts`
- `src/features/rewards/api/rewards.queries.ts`

### Mutation Hooks ✅
- `src/features/auth/api/auth.mutations.ts`
- `src/features/relationships/api/relationships.mutations.ts`
- `src/features/rewards/api/rewards.mutations.ts`

## App.tsx Split Strategy

### Current State
- 1940 lines
- Handles: auth bootstrapping, invite parsing, onboarding gating, dashboard UI, per-mode rendering, real-time state, relationship loading

### Target Split

**AppShell.tsx** ✅
- Wrap providers (React Query)
- Run bootstrap (initAuthFromStorage)
- Call useMeQuery() if token exists

**Routes.tsx** ✅
- Decide which screen based on:
  - Session status (logged in)
  - Onboarding status
  - Invite route
  - Current "room" route

**DashboardHome.tsx** ⬜
- Dashboard-only UI:
  - Floor plan
  - Avatar tray / relationship selector
  - Reaction menu + long press
  - Side panel
  - Open profile panel
  - Navigation into rooms

## Migration Steps

### Step 1: Move Components ✅ (In Progress)
- [x] RewardsMode → RewardsScreen
- [ ] AuthScreen → auth/screens
- [ ] Onboarding → onboarding/screens
- [ ] Other room components

### Step 2: Update Imports ✅
- [x] Fix imports in moved files
- [x] Update shared components

### Step 3: Extract Dashboard ⬜
- [ ] Create DashboardHome.tsx
- [ ] Move floor plan UI
- [ ] Move relationship tray
- [ ] Move side panel

### Step 4: Refactor App.tsx ⬜
- [ ] Replace useState with stores
- [ ] Replace manual fetching with React Query
- [ ] Replace mode state with UI store
- [ ] Use Routes component

### Step 5: Create Aggregated Query ⬜
- [ ] `useRelationshipsHydratedQuery()` - Combines:
  - getRelationships()
  - for each: getConsentInfo(relId)
  - for each member: getUserById(memberId)
  - for each user: getUserMarket(userId)
  - also getInvites(relId)

## Key Decisions

1. **Keep AppMode enum** - Can migrate to React Router later, but keep enum for now
2. **Aggregated query** - Start with one query that does all relationship loading to reduce churn
3. **Incremental migration** - Old code continues to work alongside new code
4. **Store structure** - Matches product reality (session, relationships, realtime, UI)

## Success Criteria

- [ ] App.tsx reduced to <200 lines
- [ ] All screens use RoomLayout
- [ ] All data fetching uses React Query
- [ ] Relationship context available via store
- [ ] Consistent progress/economy visuals
- [ ] Real-time features are dismissible
- [ ] All long-press interactions have tap fallback

## Notes

- All infrastructure is ready (stores, queries, mutations)
- Components are being moved incrementally
- App.tsx will be refactored last to minimize breaking changes
- Old code continues to work (backward compatible)
