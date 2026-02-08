import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';
import { useSessionStore } from '../../../stores/session.store';

/**
 * React Query mutations for auth
 */

// Login mutation
export const useLoginMutation = () => {
  const queryClient = useQueryClient();
  const setTokens = useSessionStore(state => state.setTokens);
  
  return useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await apiService.request<{ access_token: string; refresh_token: string }>('/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      return response.data;
    },
    onSuccess: (data) => {
      setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token });
      queryClient.invalidateQueries({ queryKey: qk.me() });
    },
  });
};

// Signup mutation
export const useSignupMutation = () => {
  const queryClient = useQueryClient();
  const setTokens = useSessionStore(state => state.setTokens);
  
  return useMutation({
    mutationFn: async ({
      email,
      password,
      displayName,
      inviteToken,
    }: {
      email: string;
      password: string;
      displayName?: string;
      inviteToken?: string;
    }) => {
      const response = await apiService.request<{ access_token: string; refresh_token: string }>('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          display_name: displayName,
          invite_token: inviteToken,
        }),
      });

      return response.data;
    },
    onSuccess: (data) => {
      setTokens({ accessToken: data.access_token, refreshToken: data.refresh_token });
      queryClient.invalidateQueries({ queryKey: qk.me() });
    },
  });
};

// Update profile mutation
export const useUpdateProfileMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: {
      display_name?: string;
      pronouns?: string;
      personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
      communication_style?: string;
      goals?: string[];
      privacy_tier?: string;
      profile_picture_url?: string;
    }) => {
      const response = await apiService.updateProfile(data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.me() });
    },
  });
};
