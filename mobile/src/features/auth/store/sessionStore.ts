import { create } from 'zustand';
import { UserProfile } from '../../../types';

interface SessionState {
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  currentUserEmail: string | null;
  
  // Actions
  setUser: (user: UserProfile | null) => void;
  setTokens: (accessToken: string | null, refreshToken: string | null) => void;
  logout: () => void;
  updateUser: (updates: Partial<UserProfile>) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  user: null,
  accessToken: typeof window !== 'undefined' ? localStorage.getItem('access_token') : null,
  refreshToken: typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null,
  isAuthenticated: false,
  currentUserEmail: null,

  setUser: (user) => set({ 
    user, 
    isAuthenticated: !!user,
    currentUserEmail: user?.id || null 
  }),

  setTokens: (accessToken, refreshToken) => {
    if (typeof window !== 'undefined') {
      if (accessToken) {
        localStorage.setItem('access_token', accessToken);
      } else {
        localStorage.removeItem('access_token');
      }
      if (refreshToken) {
        localStorage.setItem('refresh_token', refreshToken);
      } else {
        localStorage.removeItem('refresh_token');
      }
    }
    set({ accessToken, refreshToken });
  },

  logout: () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      currentUserEmail: null,
    });
  },

  updateUser: (updates) => set((state) => ({
    user: state.user ? { ...state.user, ...updates } : null,
  })),
}));
