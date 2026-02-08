// API Service for backend integration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_VERSION = 'v1';
const BASE_PATH = `/${API_VERSION}`;

interface ApiResponse<T> {
  data: T;
  status: number;
}

class ApiService {
  private baseUrl: string;
  private accessToken: string | null = null;
  /** Called when we clear tokens after 401 (e.g. refresh failed). App can clear session store here. */
  private onUnauthorized: (() => void) | null = null;

  constructor() {
    this.baseUrl = API_BASE_URL;
    // Load token from localStorage on init
    if (typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${BASE_PATH}${endpoint}`;
    
    // Build headers object - don't set Content-Type for FormData
    const headers: Record<string, string> = {};
    
    // Copy existing headers
    if (options.headers) {
      const existingHeaders = options.headers as Record<string, string>;
      Object.entries(existingHeaders).forEach(([key, value]) => {
        if (typeof value === 'string') {
          headers[key] = value;
        }
      });
    }

    // Only set Content-Type for JSON requests (not FormData)
    // FormData needs browser to set Content-Type with boundary automatically
    const isFormData = options.body instanceof FormData;
    if (options.body && !isFormData && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
    
    // Don't include Content-Type for FormData - browser will set it with boundary
    if (isFormData) {
      delete headers['Content-Type'];
    }

    // Add Authorization header if token exists
    // Always try to get the latest token (in case it was updated)
    const currentToken = this.accessToken || (typeof window !== 'undefined' ? localStorage.getItem('access_token') : null);
    if (currentToken) {
      headers['Authorization'] = `Bearer ${currentToken}`;
    }

    try {
      const response = await fetch(url, {
        method: options.method || 'GET',
        headers,
        body: options.body,
        credentials: 'include', // Include credentials for CORS
        mode: 'cors', // Explicitly set CORS mode
      });

      // Handle empty responses (204 No Content, etc.)
      if (response.status === 204 || response.headers.get('content-length') === '0') {
        return { data: {} as T, status: response.status };
      }

      if (!response.ok) {
        // Handle 401 Unauthorized - try to refresh token
        if (response.status === 401 && this.getRefreshToken()) {
          try {
            await this.refreshAccessToken();
            // Retry the request with new token
            const retryHeaders: HeadersInit = {
              ...options.headers,
            };
            if (options.body && !retryHeaders['Content-Type']) {
              retryHeaders['Content-Type'] = 'application/json';
            }
            if (this.accessToken) {
              retryHeaders['Authorization'] = `Bearer ${this.accessToken}`;
            }
            
            const retryResponse = await fetch(url, {
              method: options.method || 'GET',
              headers: retryHeaders,
              body: options.body,
              credentials: 'include',
              mode: 'cors',
            });
            
            if (retryResponse.ok) {
              const retryData = await retryResponse.json().catch(() => ({}));
              return { data: retryData, status: retryResponse.status };
            }
          } catch (refreshError) {
            // Refresh failed, clear tokens and notify app so UI can show login
            this.clearTokens();
            this.onUnauthorized?.();
          }
        } else if (response.status === 401) {
          // No refresh token or didn't try refresh; clear tokens so app can show login
          this.clearTokens();
          this.onUnauthorized?.();
        }
        
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch {
          // If response is not JSON, use status text
        }
        throw new Error(errorMessage);
      }

      const data = await response.json().catch(() => ({}));
      return { data, status: response.status };
    } catch (error) {
      if (error instanceof Error) {
        // Provide more helpful error messages
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
          throw new Error(`Cannot connect to server at ${this.baseUrl}. Please check:\n1. Backend server is running\n2. Correct API URL in .env.local\n3. Server is accessible from your device`);
        }
        throw error;
      }
      throw new Error('Network error: Unable to connect to server');
    }
  }

  setAccessToken(token: string | null) {
    this.accessToken = token;
    if (token) {
      localStorage.setItem('access_token', token);
    } else {
      localStorage.removeItem('access_token');
    }
  }

  setRefreshToken(token: string | null) {
    if (token) {
      localStorage.setItem('refresh_token', token);
    } else {
      localStorage.removeItem('refresh_token');
    }
  }

  getAccessToken(): string | null {
    return this.accessToken || localStorage.getItem('access_token');
  }

  /** Set callback to run when auth is invalid and we clear tokens (e.g. clear session store). */
  setOnUnauthorized(cb: () => void): void {
    this.onUnauthorized = cb;
  }

  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  clearTokens() {
    this.accessToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  // Auth endpoints
  async signup(email: string, password: string, displayName?: string, inviteToken?: string) {
    // Build request body, only including defined values
    const body: { email: string; password: string; display_name?: string; invite_token?: string } = {
      email: email.trim(),
      password: password,
    };
    
    // Only include display_name if it's a non-empty string
    if (displayName && typeof displayName === 'string' && displayName.trim() !== '') {
      body.display_name = displayName.trim();
    }
    
    // Only include invite_token if it's a non-empty string
    if (inviteToken && typeof inviteToken === 'string' && inviteToken.trim() !== '') {
      body.invite_token = inviteToken.trim();
    }
    
    const response = await this.request<{ access_token: string; refresh_token: string }>(
      '/auth/signup',
      {
        method: 'POST',
        body: JSON.stringify(body),
      }
    );
    this.setAccessToken(response.data.access_token);
    this.setRefreshToken(response.data.refresh_token);
    return response.data;
  }

  async login(email: string, password: string) {
    const response = await this.request<{ access_token: string; refresh_token: string }>(
      '/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }
    );
    this.setAccessToken(response.data.access_token);
    this.setRefreshToken(response.data.refresh_token);
    return response.data;
  }

  async refreshAccessToken() {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await this.request<{ access_token: string; refresh_token: string }>(
      '/auth/refresh',
      {
        method: 'POST',
        body: JSON.stringify({ refresh_token: refreshToken }),
      }
    );
    this.setAccessToken(response.data.access_token);
    this.setRefreshToken(response.data.refresh_token || refreshToken);
    return response.data;
  }

  // User endpoints
  async getCurrentUser() {
    return this.request('/users/me', { method: 'GET' });
  }

  async updateProfile(data: {
    display_name?: string;
    pronouns?: string;
    personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
    communication_style?: string;
    goals?: string[];
    privacy_tier?: string;
    profile_picture_url?: string;
  }) {
    return this.request('/users/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  // Relationships endpoints
  async getRelationships() {
    return this.request('/relationships', { method: 'GET' });
  }

  async createRelationship(type: string, memberIds: string[]) {
    return this.request('/relationships', {
      method: 'POST',
      body: JSON.stringify({ type, member_ids: memberIds }),
    });
  }

  async deleteRelationship(relationshipId: string) {
    return this.request(`/relationships/${relationshipId}`, {
      method: 'DELETE',
    });
  }

  // Get user by ID (for fetching member details)
  async getUserById(userId: string) {
    return this.request(`/users/${userId}`, { method: 'GET' });
  }

  // Contact lookup
  async lookupContact(email: string) {
    return this.request('/contacts/lookup', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  // Relationship invites
  async validateInviteToken(token: string) {
    return this.request(`/relationships/invites/validate?token=${encodeURIComponent(token)}`, {
      method: 'GET',
    });
  }

  async createInvite(relationshipId: string, email: string, role?: string, message?: string) {
    return this.request(`/relationships/${relationshipId}/invites`, {
      method: 'POST',
      body: JSON.stringify({ email, role, message }),
    });
  }

  async getInvites(relationshipId: string) {
    return this.request(`/relationships/${relationshipId}/invites`, {
      method: 'GET',
    });
  }

  // Get consent info (includes member information)
  async getConsentInfo(relationshipId: string) {
    return this.request(`/relationships/${relationshipId}/consent`, {
      method: 'GET',
    });
  }

  // Activities endpoints
  async getActivitySuggestions(relationshipId: string) {
    return this.request(`/coach/activities/suggestions?rid=${relationshipId}`, {
      method: 'GET',
    });
  }

  // Sessions endpoints
  async createSession(relationshipId: string, participants: string[] = []) {
    return this.request('/coach/sessions', {
      method: 'POST',
      body: JSON.stringify({ relationship_id: relationshipId, participants }),
    });
  }

  async finalizeSession(sessionId: string) {
    return this.request(`/coach/sessions/${sessionId}/finalize`, {
      method: 'POST',
    });
  }

  async getSessionReport(sessionId: string) {
    return this.request(`/coach/sessions/${sessionId}/report`, {
      method: 'GET',
    });
  }

  // History endpoints
  async getSessionHistory(limit: number = 20) {
    return this.request(`/history/sessions?limit=${limit}`, {
      method: 'GET',
    });
  }

  // Pokes endpoints
  async sendPoke(relationshipId: string, receiverId: string, type: string, emoji?: string) {
    return this.request('/interaction/pokes', {
      method: 'POST',
      body: JSON.stringify({
        relationship_id: relationshipId,
        receiver_id: receiverId,
        type,
        emoji,
      }),
    });
  }

  async getPokes(relationshipId: string) {
    return this.request(`/interaction/pokes?rid=${relationshipId}`, {
      method: 'GET',
    });
  }

  // Onboarding endpoints
  async getOnboardingStatus() {
    try {
      return await this.request('/onboarding/status', { method: 'GET' });
    } catch (error: any) {
      // Handle backend validation errors gracefully
      // Backend may return has_voiceprint as None, causing validation error
      if (error.message.includes('has_voiceprint') || error.message.includes('500')) {
        console.warn('Onboarding status error, returning default status:', error);
        // Return a default status if backend has issues
        return {
          data: {
            has_profile: true,
            has_voiceprint: false,
            pending_invites: 0,
            active_relationships: 0,
            next_step: null,
          },
          status: 200,
        };
      }
      throw error;
    }
  }

  async completeOnboardingStep(step: string) {
    return this.request('/onboarding/complete', {
      method: 'POST',
      body: JSON.stringify({ step }),
    });
  }

  // Market endpoints
  async getEconomySettings() {
    return this.request('/market/me/economy', { method: 'GET' });
  }

  async updateEconomySettings(currencyName: string, currencySymbol: string) {
    return this.request('/market/me/economy', {
      method: 'PUT',
      body: JSON.stringify({ currency_name: currencyName, currency_symbol: currencySymbol }),
    });
  }

  async getUserMarket(userId: string) {
    return this.request(`/market/profiles/${userId}/market`, { method: 'GET' });
  }

  async createMarketItem(data: {
    title: string;
    description?: string;
    cost: number;
    icon?: string;
    category: 'SPEND' | 'EARN';
    relationship_ids?: string[]; // List of relationship IDs that can see this item. If undefined, available to all. Issuer can always see their own items.
  }) {
    return this.request('/market/items', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteMarketItem(itemId: string) {
    return this.request(`/market/items/${itemId}`, {
      method: 'DELETE',
    });
  }

  async getMyTransactions() {
    return this.request('/market/wallets/transactions', { method: 'GET' });
  }

  async purchaseItem(itemId: string, issuerId: string, idempotencyKey?: string) {
    const headers: HeadersInit = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return this.request('/market/transactions/purchase', {
      method: 'POST',
      headers,
      body: JSON.stringify({ item_id: itemId, issuer_id: issuerId }),
    });
  }

  async redeemItem(transactionId: string) {
    return this.request(`/market/transactions/${transactionId}/redeem`, {
      method: 'POST',
    });
  }

  async acceptTask(itemId: string, issuerId: string) {
    return this.request('/market/transactions/accept', {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId, issuer_id: issuerId }),
    });
  }

  async submitForReview(transactionId: string) {
    return this.request(`/market/transactions/${transactionId}/submit`, {
      method: 'POST',
    });
  }

  async approveTask(transactionId: string) {
    return this.request(`/market/transactions/${transactionId}/approve`, {
      method: 'POST',
    });
  }

  async getPendingVerifications() {
    return this.request('/market/verification-requests', {
      method: 'GET',
    });
  }

  async cancelTransaction(transactionId: string) {
    return this.request(`/market/transactions/${transactionId}/cancel`, {
      method: 'POST',
    });
  }

  // WebSocket connection for real-time notifications
  connectWebSocket(token: string, onMessage: (message: any) => void, onError?: (error: Event) => void, onClose?: () => void): WebSocket | null {
    try {
      // Determine WebSocket protocol based on base URL
      let wsUrl: string;
      if (this.baseUrl.startsWith('https://')) {
        wsUrl = this.baseUrl.replace('https://', 'wss://');
      } else if (this.baseUrl.startsWith('http://')) {
        wsUrl = this.baseUrl.replace('http://', 'ws://');
      } else {
        // Assume http if no protocol
        wsUrl = `ws://${this.baseUrl}`;
      }
      
      // Construct WebSocket URL
      const fullWsUrl = `${wsUrl}/v1/interaction/notifications?token=${encodeURIComponent(token)}`;
      console.log('[DEBUG] Connecting to WebSocket:', fullWsUrl.replace(token, 'TOKEN'));
      
      const ws = new WebSocket(fullWsUrl);
      
      ws.onopen = () => {
        console.log('[DEBUG] ✅ WebSocket connected - real-time notifications enabled (polling disabled)');
      };
      
      ws.onmessage = (event) => {
        try {
          // Handle pong responses
          if (event.data === 'pong') {
            return;
          }
          const message = JSON.parse(event.data);
          onMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };
      
      ws.onerror = (error) => {
        console.error('[DEBUG] WebSocket error:', error);
        if (onError) onError(error);
      };
      
      ws.onclose = (event) => {
        console.log('[DEBUG] WebSocket connection closed', event.code, event.reason);
        if (onClose) onClose();
      };
      
      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        } else {
          clearInterval(pingInterval);
        }
      }, 30000);
      
      return ws;
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      return null;
    }
  }

  // Voice Enrollment APIs
  async startVoiceEnrollment(): Promise<ApiResponse<{ enrollment_id: string; upload_url: string | null }>> {
    return this.request<{ enrollment_id: string; upload_url: string | null }>(
      '/voice/enrollment/start',
      {
        method: 'POST',
      }
    );
  }

  async uploadEnrollmentAudio(enrollmentId: string, audioBlob: Blob): Promise<ApiResponse<{ ok: boolean }>> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');

    return this.request<{ ok: boolean }>(`/voice/enrollment/${enrollmentId}/audio`, {
      method: 'PUT',
      body: formData,
      headers: {},
    });
  }

  async completeVoiceEnrollment(enrollmentId: string): Promise<ApiResponse<{ voice_profile_id: string; quality_score: number }>> {
    return this.request<{ voice_profile_id: string; quality_score: number }>(`/voice/enrollment/${enrollmentId}/complete`, {
      method: 'POST',
    });
  }
}

export const apiService = new ApiService();
