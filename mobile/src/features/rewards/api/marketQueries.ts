import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '../../../../services/apiService';

// Query keys
export const marketKeys = {
  all: ['market'] as const,
  economy: () => [...marketKeys.all, 'economy'] as const,
  userMarket: (userId: string) => [...marketKeys.all, 'user', userId] as const,
  transactions: () => [...marketKeys.all, 'transactions'] as const,
  pendingVerifications: () => [...marketKeys.all, 'verifications'] as const,
};

// Get economy settings
export const useEconomySettingsQuery = () => {
  return useQuery({
    queryKey: marketKeys.economy(),
    queryFn: async () => {
      const response = await apiService.getEconomySettings();
      return response.data as {
        user_id: string;
        currency_name: string;
        currency_symbol: string;
      };
    },
  });
};

// Update economy settings mutation
export const useUpdateEconomySettingsMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ currencyName, currencySymbol }: { currencyName: string; currencySymbol: string }) => {
      const response = await apiService.updateEconomySettings(currencyName, currencySymbol);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketKeys.economy() });
    },
  });
};

// Get user market catalog
export const useUserMarketQuery = (userId: string, enabled = true) => {
  return useQuery({
    queryKey: marketKeys.userMarket(userId),
    queryFn: async () => {
      const response = await apiService.getUserMarket(userId);
      return response.data as {
        items: Array<{
          id: string;
          title: string;
          description?: string;
          cost: number;
          icon?: string;
          category: string;
          is_active: boolean;
        }>;
        balance: number;
        currency_name: string;
        currency_symbol: string;
      };
    },
    enabled: enabled && !!userId,
  });
};

// Get transaction history
export const useTransactionsQuery = () => {
  return useQuery({
    queryKey: marketKeys.transactions(),
    queryFn: async () => {
      const response = await apiService.getMyTransactions();
      return response.data as any[];
    },
  });
};

// Create market item mutation
export const useCreateMarketItemMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: {
      title: string;
      description?: string;
      cost: number;
      icon?: string;
      category: 'SPEND' | 'EARN';
      relationship_ids?: string[];
    }) => {
      const response = await apiService.createMarketItem(data);
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate all user markets since items might be visible to multiple users
      queryClient.invalidateQueries({ queryKey: marketKeys.all });
    },
  });
};

// Delete market item mutation
export const useDeleteMarketItemMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (itemId: string) => {
      await apiService.deleteMarketItem(itemId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketKeys.all });
    },
  });
};

// Purchase item mutation
export const usePurchaseItemMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ itemId, issuerId, idempotencyKey }: { itemId: string; issuerId: string; idempotencyKey?: string }) => {
      const response = await apiService.purchaseItem(itemId, issuerId, idempotencyKey);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: marketKeys.userMarket(variables.issuerId) });
      queryClient.invalidateQueries({ queryKey: marketKeys.transactions() });
    },
  });
};

// Redeem item mutation
export const useRedeemItemMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.redeemItem(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketKeys.transactions() });
    },
  });
};

// Accept task mutation
export const useAcceptTaskMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ itemId, issuerId }: { itemId: string; issuerId: string }) => {
      const response = await apiService.acceptTask(itemId, issuerId);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: marketKeys.userMarket(variables.issuerId) });
      queryClient.invalidateQueries({ queryKey: marketKeys.transactions() });
    },
  });
};

// Submit for review mutation
export const useSubmitForReviewMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.submitForReview(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketKeys.transactions() });
      queryClient.invalidateQueries({ queryKey: marketKeys.pendingVerifications() });
    },
  });
};

// Approve task mutation
export const useApproveTaskMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.approveTask(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketKeys.transactions() });
      queryClient.invalidateQueries({ queryKey: marketKeys.pendingVerifications() });
      // Invalidate all user markets since balances changed
      queryClient.invalidateQueries({ queryKey: marketKeys.all });
    },
  });
};

// Get pending verifications
export const usePendingVerificationsQuery = () => {
  return useQuery({
    queryKey: marketKeys.pendingVerifications(),
    queryFn: async () => {
      const response = await apiService.getPendingVerifications();
      return response.data as any[];
    },
  });
};

// Cancel transaction mutation
export const useCancelTransactionMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.cancelTransaction(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: marketKeys.transactions() });
      // Invalidate all user markets since balances might change
      queryClient.invalidateQueries({ queryKey: marketKeys.all });
    },
  });
};
