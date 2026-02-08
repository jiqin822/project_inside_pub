import { BaseApiClient, ApiResponse } from '../../../shared/lib/api/baseClient';

export interface EconomySettingsResponse {
  user_id: string;
  currency_name: string;
  currency_symbol: string;
}

export interface MarketItemResponse {
  id: string;
  title: string;
  description?: string;
  cost: number;
  icon?: string;
  category: 'SPEND' | 'EARN';
  is_active: boolean;
}

export interface UserMarketResponse {
  items: MarketItemResponse[];
  balance: number;
  currency_name: string;
  currency_symbol: string;
}

export interface TransactionResponse {
  id: string;
  item_id: string;
  title: string;
  amount: number;
  status: string;
  timestamp: string;
}

export class MarketClient extends BaseApiClient {
  async getEconomySettings(): Promise<ApiResponse<EconomySettingsResponse>> {
    return this.request<EconomySettingsResponse>('/market/me/economy', { method: 'GET' });
  }

  async updateEconomySettings(
    currencyName: string,
    currencySymbol: string
  ): Promise<ApiResponse<EconomySettingsResponse>> {
    return this.request<EconomySettingsResponse>('/market/me/economy', {
      method: 'PUT',
      body: JSON.stringify({ currency_name: currencyName, currency_symbol: currencySymbol }),
    });
  }

  async getUserMarket(userId: string): Promise<ApiResponse<UserMarketResponse>> {
    return this.request<UserMarketResponse>(`/market/profiles/${userId}/market`, { method: 'GET' });
  }

  async createMarketItem(data: {
    title: string;
    description?: string;
    cost: number;
    icon?: string;
    category: 'SPEND' | 'EARN';
    relationship_ids?: string[];
  }): Promise<ApiResponse<MarketItemResponse>> {
    return this.request<MarketItemResponse>('/market/items', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteMarketItem(itemId: string): Promise<ApiResponse<void>> {
    return this.request<void>(`/market/items/${itemId}`, {
      method: 'DELETE',
    });
  }

  async getMyTransactions(): Promise<ApiResponse<TransactionResponse[]>> {
    return this.request<TransactionResponse[]>('/market/wallets/transactions', { method: 'GET' });
  }

  async purchaseItem(
    itemId: string,
    issuerId: string,
    idempotencyKey?: string
  ): Promise<ApiResponse<TransactionResponse>> {
    const headers: HeadersInit = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return this.request<TransactionResponse>('/market/transactions/purchase', {
      method: 'POST',
      headers,
      body: JSON.stringify({ item_id: itemId, issuer_id: issuerId }),
    });
  }

  async redeemItem(transactionId: string): Promise<ApiResponse<TransactionResponse>> {
    return this.request<TransactionResponse>(`/market/transactions/${transactionId}/redeem`, {
      method: 'POST',
    });
  }

  async acceptTask(itemId: string, issuerId: string): Promise<ApiResponse<TransactionResponse>> {
    return this.request<TransactionResponse>('/market/transactions/accept', {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId, issuer_id: issuerId }),
    });
  }

  async submitForReview(transactionId: string): Promise<ApiResponse<TransactionResponse>> {
    return this.request<TransactionResponse>(`/market/transactions/${transactionId}/submit`, {
      method: 'POST',
    });
  }

  async approveTask(transactionId: string): Promise<ApiResponse<TransactionResponse>> {
    return this.request<TransactionResponse>(`/market/transactions/${transactionId}/approve`, {
      method: 'POST',
    });
  }

  async getPendingVerifications(): Promise<ApiResponse<TransactionResponse[]>> {
    return this.request<TransactionResponse[]>('/market/verification-requests', { method: 'GET' });
  }

  async cancelTransaction(transactionId: string): Promise<ApiResponse<TransactionResponse>> {
    return this.request<TransactionResponse>(`/market/transactions/${transactionId}/cancel`, {
      method: 'POST',
    });
  }
}

export const marketClient = new MarketClient();
