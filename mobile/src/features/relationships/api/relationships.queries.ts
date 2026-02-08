import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';

/**
 * React Query hooks for relationships
 * Maps to apiService methods
 */

// Get all relationships
export const useRelationshipsQuery = () => {
  return useQuery({
    queryKey: qk.relationships(),
    queryFn: async () => {
      const response = await apiService.getRelationships();
      return response.data as any[];
    },
  });
};

// Get consent info for a relationship
export const useConsentInfoQuery = (relationshipId: string, enabled = true) => {
  return useQuery({
    queryKey: qk.consentInfo(relationshipId),
    queryFn: async () => {
      const response = await apiService.getConsentInfo(relationshipId);
      return response.data;
    },
    enabled: enabled && !!relationshipId,
  });
};

// Get invites for a relationship
export const useInvitesQuery = (relationshipId: string, enabled = true) => {
  return useQuery({
    queryKey: qk.invites(relationshipId),
    queryFn: async () => {
      const response = await apiService.getInvites(relationshipId);
      return response.data as any[];
    },
    enabled: enabled && !!relationshipId,
  });
};

// Get user by ID
export const useUserByIdQuery = (userId: string, enabled = true) => {
  return useQuery({
    queryKey: qk.userById(userId),
    queryFn: async () => {
      const response = await apiService.getUserById(userId);
      return response.data;
    },
    enabled: enabled && !!userId,
  });
};

// Lookup contact by email
export const useContactLookupQuery = (email: string, enabled = false) => {
  return useQuery({
    queryKey: qk.contactLookup(email),
    queryFn: async () => {
      const response = await apiService.lookupContact(email);
      return response.data;
    },
    enabled: enabled && !!email,
  });
};
