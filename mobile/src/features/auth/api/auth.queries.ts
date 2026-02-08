import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';

/**
 * React Query hooks for auth
 */

// Get current user (me)
export const useMeQuery = () => {
  return useQuery({
    queryKey: qk.me(),
    queryFn: async () => {
      const response = await apiService.getCurrentUser();
      return response.data;
    },
  });
};
