import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';

/**
 * React Query hooks for rewards/market
 */

// Get economy settings
export const useEconomySettingsQuery = () => {
  return useQuery({
    queryKey: qk.economySettings(),
    queryFn: async () => {
      const response = await apiService.getEconomySettings();
      return response.data;
    },
  });
};

// Get user market
export const useUserMarketQuery = (userId: string, enabled = true) => {
  return useQuery({
    queryKey: qk.userMarket(userId),
    queryFn: async () => {
      const response = await apiService.getUserMarket(userId);
      return response.data;
    },
    enabled: enabled && !!userId,
  });
};

// Get my transactions
export const useTransactionsMineQuery = () => {
  return useQuery({
    queryKey: qk.transactionsMine(),
    queryFn: async () => {
      const response = await apiService.getMyTransactions();
      return response.data as any[];
    },
  });
};

// Get pending verifications
export const usePendingVerificationsQuery = () => {
  return useQuery({
    queryKey: qk.pendingVerifications(),
    queryFn: async () => {
      const response = await apiService.getPendingVerifications();
      return response.data as any[];
    },
  });
};
