import { create } from "zustand";
import { apiService } from "../shared/api/apiService";
import type { UserProfile } from "../shared/types/domain";

type SessionState = {
  accessToken: string | null;
  refreshToken: string | null;
  me: UserProfile | null;
  status: "anonymous" | "loading" | "authenticated";
  currentUserEmail: string | null;

  setTokens: (t: { accessToken: string; refreshToken: string }) => void;
  clearSession: () => void;
  setMe: (user: UserProfile | null) => void;
  setCurrentUserEmail: (email: string | null) => void;

  hydrateFromStorage: () => void;
  fetchMe: () => Promise<void>;
};

export const useSessionStore = create<SessionState>((set, get) => ({
  accessToken: null,
  refreshToken: null,
  me: null,
  status: "anonymous",
  currentUserEmail: null,

  setTokens: ({ accessToken, refreshToken }) => {
    apiService.setAccessToken(accessToken);
    apiService.setRefreshToken(refreshToken);
    set({ accessToken, refreshToken, status: "authenticated" });
  },

  clearSession: () => {
    apiService.clearTokens();
    set({ accessToken: null, refreshToken: null, me: null, status: "anonymous", currentUserEmail: null });
  },

  setMe: (user) => set({ me: user }),
  setCurrentUserEmail: (email) => set({ currentUserEmail: email }),

  hydrateFromStorage: () => {
    const accessToken = apiService.getAccessToken();
    const refreshToken = apiService.getRefreshToken();
    if (accessToken) {
      set({ accessToken, refreshToken, status: "loading" });
    }
  },

  fetchMe: async () => {
    set({ status: "loading" });
    try {
      const res = await apiService.getCurrentUser();
      const raw = res.data as Record<string, unknown>;
      const normalizedUser: UserProfile = {
        ...(raw as UserProfile),
        name: (raw.name as string) || (raw.display_name as string) || (raw.full_name as string) || "",
        profilePicture: (raw.profilePicture as string) || (raw.profile_picture_url as string) || null,
        personalDescription: (raw.personal_description as string) || (raw.personalDescription as string) || undefined,
        interests: (raw.hobbies as string[])?.length ? (raw.hobbies as string[]) : (raw.goals as string[]) || (raw.interests as string[]) || [],
        birthday: (raw.birthday as string) || undefined,
        occupation: (raw.occupation as string) || undefined,
        voicePrintId: (raw.voicePrintId as string) || (raw.voice_profile_id as string) || undefined,
        voicePrintData: (raw.voicePrintData as string) || (raw.voice_print_data as string) || undefined,
      };
      set({ me: normalizedUser, status: "authenticated" });
    } catch (error) {
      console.error("Failed to fetch current user:", error);
      set({ status: "anonymous" });
      throw error;
    }
  },
}));
