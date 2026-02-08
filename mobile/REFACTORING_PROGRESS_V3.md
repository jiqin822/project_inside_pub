# Mobile Directory Refactoring Progress - V3 (Component Migration)

## ✅ Completed: Component Migration

### Files Moved and Imports Updated

**Auth:**
- ✅ `components/AuthScreen.tsx` → `src/features/auth/screens/AuthScreen.tsx`
- ✅ Imports updated to use `src/shared/api/apiService.ts`

**Onboarding:**
- ✅ `components/Onboarding.tsx` → `src/features/onboarding/screens/OnboardingWizard.tsx`
- ✅ `components/AvatarPicker.tsx` → `src/features/onboarding/components/AvatarPicker.tsx`
- ✅ `components/MBTISliders.tsx` → `src/features/onboarding/components/MBTISliders.tsx`
- ✅ Imports updated to use new paths
- ✅ Component renamed: `Onboarding` → `OnboardingWizard`

**Live Coach:**
- ✅ `components/LiveCoachMode.tsx` → `src/features/liveCoach/screens/LiveCoachScreen.tsx`
- ✅ Imports updated to use `src/shared/services/geminiService.ts`
- ✅ Component renamed: `LiveCoachMode` → `LiveCoachScreen`

**Therapist:**
- ✅ `components/TherapistMode.tsx` → `src/features/therapist/screens/TherapistScreen.tsx`
- ✅ Imports updated
- ✅ Component renamed: `TherapistMode` → `TherapistScreen`

**Activities:**
- ✅ `components/ActivitiesMode.tsx` → `src/features/activities/screens/ActivitiesScreen.tsx`
- ✅ Imports updated
- ✅ Component renamed: `ActivitiesMode` → `ActivitiesScreen`

**Love Maps:**
- ✅ `components/LoveMapsMode.tsx` → `src/features/loveMaps/screens/LoveMapsScreen.tsx`
- ✅ Imports updated
- ✅ Component renamed: `LoveMapsMode` → `LoveMapsScreen`

**Rewards:**
- ✅ `components/RewardsMode.tsx` → `src/features/rewards/screens/RewardsScreen.tsx`
- ✅ Imports updated
- ✅ Component renamed: `RewardsMode` → `RewardsScreen`

**Profile:**
- ✅ `components/ProfileView.tsx` → `src/features/profile/screens/ProfileViewScreen.tsx`
- ✅ `components/EditProfile.tsx` → `src/features/profile/screens/EditProfileScreen.tsx`
- ✅ `components/PersonalProfilePanel.tsx` → `src/features/profile/screens/PersonalProfilePanel.tsx`
- ✅ `components/BiometricSync.tsx` → `src/features/profile/components/BiometricSync.tsx`
- ✅ `components/VoiceAuth.tsx` → `src/features/profile/components/VoiceAuth.tsx`
- ✅ All imports updated

### Import Path Updates

All moved components now import from:
- `src/shared/types/domain.ts` (instead of `../types`)
- `src/shared/api/apiService.ts` (instead of `../services/apiService`)
- `src/shared/services/geminiService.ts` (instead of `../services/geminiService`)
- Component imports updated to use relative paths within feature folders

### Component Renames

- `Onboarding` → `OnboardingWizard`
- `LiveCoachMode` → `LiveCoachScreen`
- `TherapistMode` → `TherapistScreen`
- `ActivitiesMode` → `ActivitiesScreen`
- `LoveMapsMode` → `LoveMapsScreen`
- `RewardsMode` → `RewardsScreen`
- Profile components kept their names (ProfileView, EditProfile, PersonalProfilePanel)

## ⏭️ Next Steps

### 1. Update App.tsx Imports
- [ ] Update imports to use new component locations
- [ ] Update component names (Onboarding → OnboardingWizard, etc.)
- [ ] Test that all screens still work

### 2. Create Aggregated Query
- ✅ Created `relationships.hydrated.ts` with helper functions
- [ ] Implement full `useRelationshipsHydratedQuery()` hook
- [ ] Replace `loadRelationshipsFromBackend()` in App.tsx

### 3. Extract Dashboard
- [ ] Create `src/features/dashboard/screens/DashboardHome.tsx`
- [ ] Move floor plan UI from App.tsx
- [ ] Move relationship tray
- [ ] Move side panel
- [ ] Move profile panel logic

### 4. Refactor App.tsx
- [ ] Replace useState with stores
- [ ] Replace manual fetching with React Query
- [ ] Replace mode state with UI store
- [ ] Use Routes component

### 5. Wrap Screens with RoomLayout
- [ ] Wrap all room screens with RoomLayout component
- [ ] Update to use relationship store for active relationship
- [ ] Add consistent loading/error states

## Files Status

**Moved:** 12 component files
**Updated:** All imports fixed
**Renamed:** 6 components
**Created:** Aggregated query helper

## Notes

- Old component files still exist in `components/` for backward compatibility
- App.tsx still imports from old locations (needs update)
- All new component files are ready to use
- Import paths are consistent across all moved files
