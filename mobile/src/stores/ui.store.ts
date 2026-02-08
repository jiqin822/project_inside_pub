import { create } from "zustand";
import { AppMode } from "../shared/types/domain";

export type Room =
  | "dashboard"
  | "liveCoach"
  | "therapist"
  | "lounge"
  | "activities"
  | "loveMaps"
  | "rewards"
  | "profile"
  | "editProfile"
  | "onboarding"
  | "auth";

// Helper to map AppMode to Room
export const appModeToRoom = (mode: AppMode): Room => {
  switch (mode) {
    case AppMode.DASHBOARD:
      return "dashboard";
    case AppMode.LIVE_COACH:
      return "liveCoach";
    case AppMode.THERAPIST:
      return "therapist";
    case AppMode.LOUNGE:
      return "lounge";
    case AppMode.ACTIVITIES:
      return "activities";
    case AppMode.LOVE_MAPS:
      return "loveMaps";
    case AppMode.REWARDS:
      return "rewards";
    case AppMode.PROFILE:
      return "profile";
    case AppMode.EDIT_PROFILE:
      return "editProfile";
    case AppMode.ONBOARDING:
      return "onboarding";
    case AppMode.LOGIN:
    default:
      return "auth";
  }
};

// Helper to map Room to AppMode
export const roomToAppMode = (room: Room): AppMode => {
  switch (room) {
    case "dashboard":
      return AppMode.DASHBOARD;
    case "liveCoach":
      return AppMode.LIVE_COACH;
    case "therapist":
      return AppMode.THERAPIST;
    case "lounge":
      return AppMode.LOUNGE;
    case "activities":
      return AppMode.ACTIVITIES;
    case "loveMaps":
      return AppMode.LOVE_MAPS;
    case "rewards":
      return AppMode.REWARDS;
    case "profile":
      return AppMode.PROFILE;
    case "editProfile":
      return AppMode.EDIT_PROFILE;
    case "onboarding":
      return AppMode.ONBOARDING;
    case "auth":
    default:
      return AppMode.LOGIN;
  }
};

export type ReactionMenuTarget = { id: string; name: string; relationshipId?: string } | null;
export type MenuPosition = { x: number; y: number } | null;

type UiState = {
  room: Room;
  showSidePanel: boolean;
  showPersonalProfilePanel: boolean;
  // Dashboard: add relationship modal
  isAddingUnit: boolean;
  isAddingUnitLoading: boolean;
  newUnitEmail: string;
  newUnitRel: string;
  // Dashboard: reaction menu
  reactionMenuTarget: ReactionMenuTarget;
  menuPosition: MenuPosition;
  // Dashboard: toast
  toast: string | null;
  // Push tap: open notification center to this notification id (then clear)
  openToNotificationId: string | null;
  // Click notification → open Activities to this tab (e.g. 'planned'); cleared when Activities mounts
  activitiesOpenToTab: 'planned' | null;

  setRoom: (r: Room) => void;
  setRoomFromAppMode: (mode: AppMode) => void;
  toggleSidePanel: (v?: boolean) => void;
  toggleProfilePanel: (v?: boolean) => void;
  setIsAddingUnit: (v: boolean) => void;
  setIsAddingUnitLoading: (v: boolean) => void;
  setNewUnitEmail: (v: string) => void;
  setNewUnitRel: (v: string) => void;
  setReactionMenuTarget: (t: ReactionMenuTarget) => void;
  setMenuPosition: (p: MenuPosition) => void;
  setToast: (m: string | null) => void;
  showToast: (message: string) => void;
  setOpenToNotificationId: (id: string | null) => void;
  setActivitiesOpenToTab: (tab: 'planned' | null) => void;
};

const TOAST_DURATION_MS = 4000;

export const useUiStore = create<UiState>((set, get) => ({
  room: "auth",
  showSidePanel: false,
  showPersonalProfilePanel: false,
  isAddingUnit: false,
  isAddingUnitLoading: false,
  newUnitEmail: "",
  newUnitRel: "Partner",
  reactionMenuTarget: null,
  menuPosition: null,
  toast: null,
  openToNotificationId: null,
  activitiesOpenToTab: null,

  setRoom: (room) => set({ room }),
  setRoomFromAppMode: (mode) => set({ room: appModeToRoom(mode) }),
  toggleSidePanel: (v) => set((s) => ({ showSidePanel: v ?? !s.showSidePanel })),
  toggleProfilePanel: (v) =>
    set((s) => ({ showPersonalProfilePanel: v ?? !s.showPersonalProfilePanel })),
  setIsAddingUnit: (v) => set({ isAddingUnit: v }),
  setIsAddingUnitLoading: (v) => set({ isAddingUnitLoading: v }),
  setNewUnitEmail: (v) => set({ newUnitEmail: v }),
  setNewUnitRel: (v) => set({ newUnitRel: v }),
  setReactionMenuTarget: (t) => set({ reactionMenuTarget: t }),
  setMenuPosition: (p) => set({ menuPosition: p }),
  setToast: (m) => set({ toast: m }),
  showToast: (message) => {
    set({ toast: message });
    const t = setTimeout(() => get().setToast(null), TOAST_DURATION_MS);
    return () => clearTimeout(t);
  },
  setOpenToNotificationId: (id) => set({ openToNotificationId: id }),
  setActivitiesOpenToTab: (tab) => set({ activitiesOpenToTab: tab }),
}));
