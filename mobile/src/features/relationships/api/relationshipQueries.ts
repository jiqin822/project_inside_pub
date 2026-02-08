import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '../../../../services/apiService';
import { LovedOne } from '../../../../types';

// Query keys
export const relationshipKeys = {
  all: ['relationships'] as const,
  lists: () => [...relationshipKeys.all, 'list'] as const,
  list: (filters: string) => [...relationshipKeys.lists(), { filters }] as const,
  details: () => [...relationshipKeys.all, 'detail'] as const,
  detail: (id: string) => [...relationshipKeys.details(), id] as const,
  invites: (relationshipId: string) => [...relationshipKeys.all, 'invites', relationshipId] as const,
};

// Fetch all relationships
export const useRelationshipsQuery = () => {
  return useQuery({
    queryKey: relationshipKeys.lists(),
    queryFn: async () => {
      const response = await apiService.getRelationships();
      return response.data as any[];
    },
  });
};

// Fetch single relationship
export const useRelationshipQuery = (id: string, enabled = true) => {
  return useQuery({
    queryKey: relationshipKeys.detail(id),
    queryFn: async () => {
      const response = await apiService.getConsentInfo(id);
      return response.data;
    },
    enabled: enabled && !!id,
  });
};

// Create relationship mutation
export const useCreateRelationshipMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ type, memberIds }: { type: string; memberIds: string[] }) => {
      const response = await apiService.createRelationship(type, memberIds);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: relationshipKeys.lists() });
    },
  });
};

// Delete relationship mutation
export const useDeleteRelationshipMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (relationshipId: string) => {
      await apiService.deleteRelationship(relationshipId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: relationshipKeys.lists() });
    },
  });
};

// Send invite mutation
export const useInviteMutation = () => {
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
      queryClient.invalidateQueries({ queryKey: relationshipKeys.invites(variables.relationshipId) });
    },
  });
};

// Accept invite mutation
export const useAcceptInviteMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (token: string) => {
      // This would typically be a separate endpoint
      // For now, we'll use the signup flow with token
      const response = await apiService.validateInviteToken(token);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: relationshipKeys.lists() });
    },
  });
};

// Get invites for a relationship
export const useInvitesQuery = (relationshipId: string, enabled = true) => {
  return useQuery({
    queryKey: relationshipKeys.invites(relationshipId),
    queryFn: async () => {
      const response = await apiService.getInvites(relationshipId);
      return response.data as any[];
    },
    enabled: enabled && !!relationshipId,
  });
};

// Lookup contact by email
export const useContactLookupMutation = () => {
  return useMutation({
    mutationFn: async (email: string) => {
      const response = await apiService.lookupContact(email);
      return response.data;
    },
  });
};

// Get user by ID
export const useUserQuery = (userId: string, enabled = true) => {
  return useQuery({
    queryKey: ['users', userId],
    queryFn: async () => {
      const response = await apiService.getUserById(userId);
      return response.data;
    },
    enabled: enabled && !!userId,
  });
};
