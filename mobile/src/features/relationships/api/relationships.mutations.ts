import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';

/**
 * React Query mutations for relationships
 */

// Create relationship
export const useCreateRelationshipMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ type, memberIds }: { type: string; memberIds: string[] }) => {
      const response = await apiService.createRelationship(type, memberIds);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
    },
  });
};

// Delete relationship
export const useDeleteRelationshipMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (relationshipId: string) => {
      await apiService.deleteRelationship(relationshipId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
    },
  });
};

// Create invite
export const useCreateInviteMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({
      relationshipId,
      email,
      role,
      message,
    }: {
      relationshipId: string;
      email: string;
      role?: string;
      message?: string;
    }) => {
      const response = await apiService.createInvite(relationshipId, email, role, message);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: qk.invites(variables.relationshipId) });
    },
  });
};

// Accept invite (via signup/login flow)
export const useAcceptInviteMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (token: string) => {
      const response = await apiService.validateInviteToken(token);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.relationships() });
    },
  });
};
