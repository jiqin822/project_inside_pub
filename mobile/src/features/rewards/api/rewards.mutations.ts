import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiService } from '../../../shared/api/apiService';
import { qk } from '../../../shared/api/queryKeys';

/**
 * React Query mutations for rewards/market
 */

// Update economy settings
export const useUpdateEconomySettingsMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ currencyName, currencySymbol }: { currencyName: string; currencySymbol: string }) => {
      const response = await apiService.updateEconomySettings(currencyName, currencySymbol);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.economySettings() });
    },
  });
};

// Create market item
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
      queryClient.invalidateQueries({ queryKey: ['market'] });
    },
  });
};

// Delete market item
export const useDeleteMarketItemMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (itemId: string) => {
      await apiService.deleteMarketItem(itemId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['market'] });
    },
  });
};

// Purchase item
export const usePurchaseItemMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ itemId, issuerId, idempotencyKey }: { itemId: string; issuerId: string; idempotencyKey?: string }) => {
      const response = await apiService.purchaseItem(itemId, issuerId, idempotencyKey);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: qk.userMarket(variables.issuerId) });
      queryClient.invalidateQueries({ queryKey: qk.transactionsMine() });
    },
  });
};

// Accept task
export const useAcceptTaskMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ itemId, issuerId }: { itemId: string; issuerId: string }) => {
      const response = await apiService.acceptTask(itemId, issuerId);
      return response.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: qk.userMarket(variables.issuerId) });
      queryClient.invalidateQueries({ queryKey: qk.transactionsMine() });
    },
  });
};

// Submit for review
export const useSubmitForReviewMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.submitForReview(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.transactionsMine() });
      queryClient.invalidateQueries({ queryKey: qk.pendingVerifications() });
    },
  });
};

// Approve task
export const useApproveTaskMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.approveTask(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.transactionsMine() });
      queryClient.invalidateQueries({ queryKey: qk.pendingVerifications() });
      queryClient.invalidateQueries({ queryKey: ['market'] });
    },
  });
};

// Cancel transaction
export const useCancelTransactionMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.cancelTransaction(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.transactionsMine() });
      queryClient.invalidateQueries({ queryKey: ['market'] });
    },
  });
};

// Redeem item
export const useRedeemItemMutation = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (transactionId: string) => {
      const response = await apiService.redeemItem(transactionId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.transactionsMine() });
    },
  });
};
