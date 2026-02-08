// API Service for backend integration.
// Local dev (npm run dev): use local backend/db. Production build (phone): use remote server/db from .env.production.
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? 'http://localhost:8000' : 'https://project-inside-c6bdb.ondigitalocean.app');
const API_VERSION = 'v1';
const BASE_PATH = `/${API_VERSION}`;

/** Request timeout (ms). Prevents long hangs when server is unreachable (e.g. wrong IP or iOS blocking). */
const REQUEST_TIMEOUT_MS = 20_000;
/** Scrapbook generation can be slow; allow longer timeouts. */
const SCRAPBOOK_REQUEST_TIMEOUT_MS = 60_000;
/** Screenshot analysis (vision + LLM) can take 30–90s; use longer timeout for Living Room analyze-screenshots. */
const SCREENSHOT_ANALYSIS_TIMEOUT_MS = 90_000;

interface ApiResponse<T> {
  data: T;
  status: number;
}

/** Notification list item from GET /notifications (id, type, title, message, read, timestamp). */
export interface NotificationListItem {
  id: string;
  type: string;
  title: string;
  message: string;
  read: boolean;
  timestamp: number;
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

  /** Base URL for the API server (e.g. for resolving relative storage paths). */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Base URL for relationship invite links, derived from API URL (consistent with VITE_API_BASE_URL).
   * Local: same host, port 3000. Remote: same origin as API (scheme + host + port).
   */
  getAppBaseUrlForInvite(): string {
    try {
      const apiUrl = new URL(this.baseUrl);
      const isLocal =
        apiUrl.protocol === 'http:' &&
        (apiUrl.hostname === 'localhost' ||
          apiUrl.hostname === '127.0.0.1' ||
          /^10\./.test(apiUrl.hostname) ||
          /^172\.(1[6-9]|2\d|3[01])\./.test(apiUrl.hostname) ||
          /^192\.168\./.test(apiUrl.hostname));
      if (isLocal) {
        return `${apiUrl.protocol}//${apiUrl.hostname}:3000`;
      }
      return apiUrl.origin;
    } catch {
      return this.baseUrl.replace(/\/+$/, '');
    }
  }

  /** Resolve a relative memory/storage path to a full URL for display. */
  getMemoryImageUrl(relativePath: string): string {
    const path = relativePath.startsWith('/') ? relativePath.slice(1) : relativePath;
    return `${this.baseUrl}/${path}`;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    timeoutMs: number = REQUEST_TIMEOUT_MS
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

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url, {
        method: options.method || 'GET',
        headers,
        body: options.body,
        credentials: 'include', // Include credentials for CORS
        mode: 'cors', // Explicitly set CORS mode
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

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
            
            const retryController = new AbortController();
            const retryTimeoutId = setTimeout(() => retryController.abort(), timeoutMs);
            const retryResponse = await fetch(url, {
              method: options.method || 'GET',
              headers: retryHeaders,
              body: options.body,
              credentials: 'include',
              mode: 'cors',
              signal: retryController.signal,
            });
            clearTimeout(retryTimeoutId);
            
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
      clearTimeout(timeoutId);
      if (error instanceof Error) {
        const exampleUrl = `${this.baseUrl}${BASE_PATH}/auth/login`;
        const hints =
          'Check: 1) Backend is running on your Mac 2) Same Wi‑Fi as iPhone 3) VITE_API_BASE_URL is your Mac’s IP (e.g. 192.168.x.x), not localhost. On iOS: Settings > Privacy > Local Network — allow this app. On Mac: allow incoming connections in Firewall if enabled.';
        if (error.name === 'AbortError') {
          throw new Error(`Connection timed out. API base: ${this.baseUrl}\n${hints}`);
        }
        if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError') || error.message.includes('Load failed')) {
          throw new Error(`Cannot connect to server. API base: ${this.baseUrl}\nExample: ${exampleUrl}\n${hints}`);
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
    personal_description?: string;
    hobbies?: string[];
    birthday?: string; // ISO date YYYY-MM-DD
    occupation?: string;
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
      headers: { 'X-App-Base-URL': this.getAppBaseUrlForInvite() },
      body: JSON.stringify({ email, role, message }),
    });
  }

  async getInvites(relationshipId: string) {
    return this.request(`/relationships/${relationshipId}/invites`, {
      method: 'GET',
    });
  }

  /** Get a fresh invite link for a pending invite (regenerates token). */
  async getInviteLink(relationshipId: string, inviteId: string) {
    return this.request<{ invite_url: string }>(
      `/relationships/${relationshipId}/invites/${inviteId}/link`,
      { method: 'GET' }
    );
  }

  // Get consent info (includes member information)
  async getConsentInfo(relationshipId: string) {
    return this.request(`/relationships/${relationshipId}/consent`, {
      method: 'GET',
    });
  }

  // Activities endpoints
  async getActivitySuggestions(relationshipId: string, options?: { debug?: boolean }) {
    const params = new URLSearchParams({ rid: relationshipId });
    if (options?.debug === true) params.set('debug', 'true');
    return this.request(`/coach/activities/suggestions?${params.toString()}`, {
      method: 'GET',
    });
  }

  /**
   * Live Coach: analyze a single turn (transcript) for sentiment, horseman, level, nudge, rephrasing.
   * POST /v1/coach/analyze-turn. Call asynchronously on STT final; merge result into row by segment_id.
   */
  async analyzeTurn(payload: {
    transcript: string;
    segment_id?: string | number;
    include_history?: boolean;
    history?: { speaker: string; transcript: string }[];
    /** Current turn speaker: display name or anonymous label (e.g. Unknown_1) from STT. */
    speaker?: string | null;
    debug?: boolean;
  }) {
    const body: Record<string, unknown> = {
      transcript: payload.transcript,
      include_history: payload.include_history ?? false,
    };
    if (payload.segment_id != null) body.segment_id = String(payload.segment_id);
    if (payload.include_history && payload.history?.length)
      body.history = payload.history;
    if (payload.speaker != null && payload.speaker !== '') body.speaker = payload.speaker;
    if (payload.debug === true) body.debug = true;
    return this.request<{
      sentiment: string;
      horseman: string;
      level: number;
      nudgeText?: string;
      suggestedRephrasing?: string;
      latency_ms: number;
      debug_prompt?: string;
    }>('/coach/analyze-turn', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /** Activity recommendations (GET /v1/activity/recommendations). */
  async getCompassRecommendations(
    relationshipId: string,
    options?: {
      limit?: number;
      vibeTags?: string[];
      durationMaxMinutes?: number;
      similarToActivityId?: string;
      useLlm?: boolean;
      debug?: boolean;
      excludeTitles?: string[];
    }
  ) {
    const params = new URLSearchParams({
      mode: 'activities',
      relationship_id: relationshipId,
      limit: String(options?.limit ?? 10),
    });
    if (options?.vibeTags?.length) params.set('vibe_tags', options.vibeTags.join(','));
    if (options?.durationMaxMinutes != null) params.set('duration_max_minutes', String(options.durationMaxMinutes));
    if (options?.similarToActivityId) params.set('similar_to_activity_id', options.similarToActivityId);
    if (options?.useLlm === true) params.set('use_llm', 'true');
    if (options?.debug === true) params.set('debug', 'true');
    if (options?.excludeTitles?.length) params.set('exclude_titles', options.excludeTitles.join(','));
    return this.request(`/activity/recommendations?${params.toString()}`, { method: 'GET' });
  }

  /**
   * Stream activity recommendations as NDJSON (one JSON object per line).
   * Calls onItem for each activity as it arrives. Use with use_llm=true and stream=true.
   */
  async getCompassRecommendationsStream(
    relationshipId: string,
    options: {
      limit?: number;
      vibeTags?: string[];
      durationMaxMinutes?: number;
      similarToActivityId?: string;
      debug?: boolean;
      excludeTitles?: string[];
    },
    onItem: (item: Record<string, unknown>) => void
  ): Promise<void> {
    const params = new URLSearchParams({
      mode: 'activities',
      relationship_id: relationshipId,
      limit: String(options?.limit ?? 10),
      use_llm: 'true',
      stream: 'true',
    });
    if (options?.vibeTags?.length) params.set('vibe_tags', options.vibeTags.join(','));
    if (options?.durationMaxMinutes != null) params.set('duration_max_minutes', String(options.durationMaxMinutes));
    if (options?.similarToActivityId) params.set('similar_to_activity_id', options.similarToActivityId);
    if (options?.debug === true) params.set('debug', 'true');
    if (options?.excludeTitles?.length) params.set('exclude_titles', options.excludeTitles.join(','));
    const url = `${this.baseUrl}/${API_VERSION}/activity/recommendations?${params.toString()}`;
    const token = this.accessToken || (typeof window !== 'undefined' ? localStorage.getItem('access_token') : null);
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const response = await fetch(url, { method: 'GET', headers, credentials: 'include', mode: 'cors' });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error((err as { detail?: string }).detail || `HTTP ${response.status}`);
    }
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }
    const decoder = new TextDecoder();
    let buffer = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          try {
            const item = JSON.parse(trimmed) as Record<string, unknown>;
            onItem(item);
          } catch {
            // skip malformed line
          }
        }
      }
      if (buffer.trim()) {
        try {
          const item = JSON.parse(buffer.trim()) as Record<string, unknown>;
          onItem(item);
        } catch {
          // skip
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /** Activity recommendations (tags, suggested invitees). */
  async getCompassActivityRecommendations(
    relationshipId: string,
    options?: { limit?: number; vibe_tags?: string; similarToActivityId?: string }
  ) {
    const params = new URLSearchParams({
      mode: 'activities',
      relationship_id: relationshipId,
      limit: String(options?.limit ?? 10),
    });
    if (options?.vibe_tags) params.set('vibe_tags', options.vibe_tags);
    if (options?.similarToActivityId) params.set('similar_to_activity_id', options.similarToActivityId);
    return this.request(`/activity/recommendations?${params.toString()}`, { method: 'GET' });
  }

  /** Post activity feedback (rating + tags) for recommendation engine. */
  async postCompassFeedback(payload: {
    relationship_id: string;
    activity_template_id: string;
    rating?: number;
    outcome_tags?: string[];
  }) {
    return this.request('/activity/recommendations/feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  /** Post event to Compass (activity_recommendations_shown, activity_card_viewed, activity_completed, etc.). */
  async postCompassEvent(payload: {
    type: string;
    payload: Record<string, unknown>;
    source: string;
    relationship_id?: string;
  }) {
    return this.request('/compass/events', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  /** Log user interaction with an activity suggestion (viewed, invite_sent, dismissed, completed). */
  async logActivitySuggestionInteraction(
    relationshipId: string,
    suggestionId: string,
    action: 'viewed' | 'invite_sent' | 'dismissed' | 'completed'
  ) {
    return this.request('/activity/log-interaction', {
      method: 'POST',
      body: JSON.stringify({
        relationship_id: relationshipId,
        suggestion_id: suggestionId,
        action,
      }),
    });
  }

  /** Get Discover feed for relationship (cards where user is generator or recommended invitee). */
  async getDiscoverFeed(relationshipId: string, limit = 50) {
    return this.request<unknown[]>(
      `/activity/discover/feed?relationship_id=${encodeURIComponent(relationshipId)}&limit=${limit}`,
      { method: 'GET' }
    );
  }

  /** Dismiss a discover feed item (swipe-left); it will no longer appear in this user's feed. */
  async dismissDiscoverItem(relationshipId: string, discoverFeedItemId: string) {
    return this.request('/activity/discover/dismiss', {
      method: 'POST',
      body: JSON.stringify({ relationship_id: relationshipId, discover_feed_item_id: discoverFeedItemId }),
    });
  }

  /** Record "Want to try" for a discover feed item; may create mutual match and notify both. */
  async wantToTry(relationshipId: string, discoverFeedItemId: string) {
    return this.request<{ ok: boolean; mutual_match_id?: string }>('/activity/want-to-try', {
      method: 'POST',
      body: JSON.stringify({ relationship_id: relationshipId, discover_feed_item_id: discoverFeedItemId }),
    });
  }

  /** List pending mutual matches for the current user. */
  async listMutualMatches(relationshipId?: string) {
    const q = relationshipId ? `?relationship_id=${relationshipId}` : '';
    return this.request<{ id: string; relationship_id: string; discover_feed_item_id: string; activity_title?: string; card_snapshot?: unknown; other_user_id: string; created_at: string }[]>(
      `/activity/want-to-try/mutual-matches${q}`,
      { method: 'GET' }
    );
  }

  /** Accept or decline a mutual match. When both accept, activity is planned. */
  async respondToMutualMatch(mutualMatchId: string, accept: boolean) {
    return this.request(`/activity/want-to-try/mutual-match/${mutualMatchId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ accept }),
    });
  }

  /** Send activity invite to a relationship member. Optionally send full ActivityCard JSON so it can be shown in Planned tab. */
  async sendActivityInvite(
    relationshipId: string,
    activityTemplateId: string,
    inviteeUserId: string,
    cardSnapshot?: Record<string, unknown>
  ) {
    return this.request('/activity/invite', {
      method: 'POST',
      body: JSON.stringify({
        relationship_id: relationshipId,
        activity_template_id: activityTemplateId,
        invitee_user_id: inviteeUserId,
        ...(cardSnapshot != null && { card_snapshot: cardSnapshot }),
      }),
    });
  }

  /** Accept or decline an activity invite. */
  async respondToActivityInvite(inviteId: string, accept: boolean) {
    return this.request(`/activity/invite/${inviteId}/respond`, {
      method: 'POST',
      body: JSON.stringify({ accept }),
    });
  }

  /** List dyad activity history (completed activities). */
  async getActivityHistory(relationshipId: string, limit = 50) {
    return this.request(
      `/activity/history?relationship_id=${encodeURIComponent(relationshipId)}&limit=${limit}`,
      { method: 'GET' }
    );
  }

  /** List all activity history (completed + declined invites) for History tab. */
  async getActivityHistoryAll(relationshipId: string, limit = 50) {
    return this.request(
      `/activity/history/all?relationship_id=${encodeURIComponent(relationshipId)}&limit=${limit}`,
      { method: 'GET' }
    );
  }

  /** List planned activities for the current user. */
  async getPlannedActivities(relationshipId?: string) {
    const q = relationshipId ? `?relationship_id=${relationshipId}` : '';
    return this.request(`/activity/planned${q}`, { method: 'GET' });
  }

  /** Mark a planned activity as completed (notes + memory URLs and/or memory_entries with captions, optional feeling). */
  async completePlannedActivity(
    plannedId: string,
    payload: { notes?: string; memory_urls?: string[]; memory_entries?: { url: string; caption?: string }[]; feeling?: string }
  ) {
    return this.request(`/activity/planned/${plannedId}/complete`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  /** List pending activity invites for Accept/Decline UI. */
  async getPendingActivityInvites() {
    return this.request('/activity/invites/pending', { method: 'GET' });
  }

  /** List sent activity invites (pending acceptance) for Planned tab. */
  async getSentActivityInvites() {
    return this.request('/activity/invites/sent', { method: 'GET' });
  }

  /** List memories (completed activities with aggregated notes/photos from all participants). */
  async getActivityMemories(relationshipId: string, limit = 50) {
    return this.request(
      `/activity/memories?relationship_id=${encodeURIComponent(relationshipId)}&limit=${limit}`,
      { method: 'GET' }
    );
  }

  /** Upload a memory image for a planned activity. Returns { url }. */
  async uploadActivityMemory(plannedId: string, file: File) {
    const form = new FormData();
    form.append('file', file);
    return this.request(`/activity/memory-upload?planned_id=${plannedId}`, {
      method: 'POST',
      body: form,
    });
  }

  /** Upload a memory image for a standalone memory log. Returns { url }. */
  async uploadRelationshipMemory(relationshipId: string, file: File) {
    const form = new FormData();
    form.append('file', file);
    return this.request(`/activity/memory-upload?relationship_id=${encodeURIComponent(relationshipId)}`, {
      method: 'POST',
      body: form,
    });
  }

  /** Log a standalone memory (not tied to a planned activity). */
  async logMemory(payload: {
    relationship_id: string;
    activity_title: string;
    notes?: string;
    memory_urls?: string[];
    memory_entries?: { url: string; caption?: string }[];
    feeling?: string;
  }) {
    return this.request('/activity/memory/log', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // ---- Lounge (group chat with Kai) ----
  async createLoungeRoom(title?: string | null, conversationGoal?: string | null) {
    return this.request<{ id: string; owner_user_id: string; title?: string | null; conversation_goal?: string | null; created_at: string }>(
      '/lounge/rooms',
      { method: 'POST', body: JSON.stringify({ title: title ?? undefined, conversation_goal: conversationGoal ?? undefined }) }
    );
  }

  async listLoungeRooms() {
    return this.request<{ id: string; owner_user_id: string; title?: string | null; created_at: string }[]>(
      '/lounge/rooms',
      { method: 'GET' }
    );
  }

  async getLoungeRoom(roomId: string) {
    // Cache-bust so polling and visibility refetch always get fresh messages (avoids stale GET cache)
    const url = `/lounge/rooms/${roomId}?_=${Date.now()}`;
    return this.request<{
      id: string;
      owner_user_id: string;
      title?: string | null;
      created_at: string | null;
      members: { user_id: string; joined_at: string | null }[];
      messages: import('../types/domain').LoungeMessage[];
    }>(url, { method: 'GET' });
  }

  async deleteLoungeRoom(roomId: string) {
    return this.request<{ status: string }>(`/lounge/rooms/${roomId}`, { method: 'DELETE' });
  }

  async inviteToLoungeRoom(roomId: string, userId: string) {
    return this.request<{ status: string }>(`/lounge/rooms/${roomId}/invite`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId }),
    });
  }

  async listLoungeMessages(roomId: string, limit = 100, beforeSequence?: number) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (beforeSequence != null) params.set('before_sequence', String(beforeSequence));
    return this.request<{ messages: import('../types/domain').LoungeMessage[] }>(
      `/lounge/rooms/${roomId}/messages?${params}`,
      { method: 'GET' }
    );
  }

  async vetLoungeMessage(roomId: string, draft: string) {
    return this.request<{ vet_ok: boolean; suggestion?: string | null; revised_text?: string | null; horseman?: string | null }>(`/lounge/rooms/${roomId}/messages/vet`, {
      method: 'POST',
      body: JSON.stringify({ draft }),
    });
  }

  async sendLoungeMessage(roomId: string, content: string, forceSend = false, debug = false) {
    return this.request<{
      vet_ok: boolean;
      suggestion?: string | null;
      revised_text?: string | null;
      horseman?: string | null;
      message?: import('../types/domain').LoungeMessage;
      guidance?: { guidance_type: string; text?: string | null } | null;
      kai_reply?: {
        content: string;
        message?: import('../types/domain').LoungeMessage;
        prompt?: string | null;
        response?: string | null;
      } | null;
      invite_suggestion?: { user_id: string; display_name: string } | null;
      intention_detected?: { suggest_activities: boolean; activity_query: string | null; suggest_vouchers: boolean };
      activity_suggestions?: Array<{ title: string; description?: string; recommendation_rationale?: string; estimated_minutes?: number; recommended_location?: string; recommended_invitee_name?: string; vibe_tags?: string[] }> | null;
      activity_suggestions_rationale?: string | null;
      voucher_suggestions?: Array<{ title: string; description: string }> | null;
    }>(`/lounge/rooms/${roomId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, force_send: forceSend, debug }),
    });
  }

  /** Analyze screenshots of a chat and get guidance posted as a Kai message in the thread. */
  async analyzeLoungeScreenshots(roomId: string, files: File[]) {
    const form = new FormData();
    files.forEach((file) => form.append('files', file));
    return this.request<{
      message: import('../types/domain').LoungeMessage;
      extracted_thread: Array<{ sender_label: string; content: string }>;
      message_analysis: Array<{
        message_index: number;
        sender_label: string;
        content: string;
        suggested_revision?: string | null;
        guidance_type?: string | null;
        guidance_text?: string | null;
        suggested_phrase?: string | null;
      }>;
    }>(`/lounge/rooms/${roomId}/analyze-screenshots`, { method: 'POST', body: form }, SCREENSHOT_ANALYSIS_TIMEOUT_MS);
  }

  async sendLoungePrivateMessage(roomId: string, content: string) {
    return this.request<{
      user_message: import('../types/domain').LoungeMessage;
      kai_reply: { content: string } | null;
    }>(`/lounge/rooms/${roomId}/private`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
  }

  async listLoungePrivateMessages(roomId: string, limit = 50) {
    return this.request<{ messages: import('../types/domain').LoungeMessage[] }>(
      `/lounge/rooms/${roomId}/private?limit=${limit}`,
      { method: 'GET' }
    );
  }

  async getLoungeContext(roomId: string) {
    return this.request<{ summary_text: string | null; extracted_facts: Record<string, unknown>; updated_at: string | null }>(
      `/lounge/rooms/${roomId}/context`,
      { method: 'GET' }
    );
  }

  async listLoungeEvents(roomId: string, limit = 200, fromSequence?: number) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (fromSequence != null) params.set('from_sequence', String(fromSequence));
    return this.request<{ events: import('../types/domain').LoungeEvent[] }>(
      `/lounge/rooms/${roomId}/events?${params}`,
      { method: 'GET' }
    );
  }

  /** Generate scrapbook layout via backend (matches inside ScrapbookLayout shape). Returns ScrapbookLayout. */
  async generateScrapbookLayout(body: {
    activity_title: string;
    note: string;
    feeling?: string | null;
    image_count: number;
  }) {
    return this.request<{
      themeColor: string;
      secondaryColor: string;
      narrative: string;
      headline: string;
      stickers: string[];
      imageCaptions: string[];
      style: string;
    }>('/activity/scrapbook/generate', {
      method: 'POST',
      body: JSON.stringify(body),
    }, SCRAPBOOK_REQUEST_TIMEOUT_MS);
  }

  /** Generate 3 scrapbook layout options (element-based: bgStyle, elements, styleName). Inside parity. */
  async generateScrapbookOptions(body: {
    activity_title: string;
    note: string;
    feeling?: string | null;
    image_count: number;
    limit?: number; // 1 = single style (Palette), 3 = multiple options
  }) {
    type ElementScrapbookLayout = import('../types/domain').ElementScrapbookLayout;
    return this.request<{ options: ElementScrapbookLayout[] }>(
      '/activity/scrapbook/generate-options',
      { method: 'POST', body: JSON.stringify(body) },
      SCRAPBOOK_REQUEST_TIMEOUT_MS
    );
  }

  /** Generate a single scrapbook layout as raw HTML (Palette / inside-app parity). Pass activity_template_id to use activity card context. Pass include_debug: true when showDebug is on to get prompt and response for the debug modal. Pass disable_sticker_generation: true when user has disabled scrapbook stickers in settings. */
  async generateScrapbookHtml(body: {
    activity_title: string;
    note: string;
    feeling?: string | null;
    image_count: number;
    activity_template_id?: string | null;
    include_debug?: boolean;
    disable_sticker_generation?: boolean;
  }) {
    return this.request<{ htmlContent: string; prompt?: string; response?: string }>(
      '/activity/scrapbook/generate-html',
      { method: 'POST', body: JSON.stringify(body) },
      SCRAPBOOK_REQUEST_TIMEOUT_MS
    );
  }

  /** Save scrapbook layout for a planned activity; notifies all participants. */
  async saveScrapbook(plannedId: string, layout: Record<string, unknown>) {
    return this.request(`/activity/planned/${plannedId}/scrapbook`, {
      method: 'POST',
      body: JSON.stringify({ layout }),
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

  // STT endpoints
  async createSttSession(payload: {
    candidate_user_ids?: string[];
    language_code?: string;
    min_speaker_count?: number;
    max_speaker_count?: number;
    debug?: boolean;
    skip_diarization?: boolean;
    disable_speaker_union_join?: boolean;
  }) {
    return this.request('/stt/session', {
      method: 'POST',
      body: JSON.stringify(payload),
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

  /** Send a heart notification to a loved one (from watch or UI). Target must be in a relationship with current user. */
  async sendHeart(targetUserId: string) {
    return this.request<{ ok: boolean }>('/notifications/send-heart', {
      method: 'POST',
      body: JSON.stringify({ target_user_id: targetUserId }),
    });
  }

  /** Send an emotion notification to a loved one (from phone icon tap or watch). Shown on watch full-screen 5s or as tag on icon / push. */
  async sendEmotion(targetUserId: string, emotionKind?: string) {
    return this.request<{ ok: boolean }>('/notifications/send-emotion', {
      method: 'POST',
      body: JSON.stringify({
        target_user_id: targetUserId,
        ...(emotionKind != null && { emotion_kind: emotionKind }),
      }),
    });
  }

  /** Register push token with backend for FCM/APNs. */
  async registerPushToken(token: string, platform: string): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>('/devices/push-token', {
      method: 'POST',
      body: JSON.stringify({ token, platform }),
    });
  }

  /** List notifications for the current user (for notification center and tap-to-message). */
  async listNotifications(limit: number = 50, type?: string): Promise<NotificationListItem[]> {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (type) params.set('type', type);
    const res = await this.request<NotificationListItem[]>(`/notifications?${params.toString()}`, { method: 'GET' });
    return res.data ?? [];
  }

  /** Mark all notifications as read for the current user. */
  async markAllNotificationsRead(): Promise<{ ok: boolean; updated?: number }> {
    const res = await this.request<{ ok: boolean; updated?: number }>('/notifications/read-all', {
      method: 'POST',
    });
    return res.data ?? { ok: false };
  }

  /** Mark a single notification as read. */
  async markNotificationRead(notificationId: string): Promise<{ ok: boolean }> {
    const res = await this.request<{ ok: boolean }>(`/notifications/${encodeURIComponent(notificationId)}/read`, {
      method: 'PATCH',
    });
    return res.data ?? { ok: false };
  }

  /** Delete a notification for the current user (swipe-to-dismiss). Persists so it stays removed after refresh. */
  async deleteNotification(notificationId: string): Promise<{ ok: boolean }> {
    const res = await this.request<{ ok: boolean }>(`/notifications/${encodeURIComponent(notificationId)}`, {
      method: 'DELETE',
    });
    return res.data ?? { ok: false };
  }

  /** Get unread notification count for the current user. */
  async getUnreadNotificationCount(): Promise<number> {
    const res = await this.request<{ unread: number }>('/notifications/unread-count', { method: 'GET' });
    return res.data?.unread ?? 0;
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

  /** WebSocket for a lounge chat group. Receives lounge_room_update when messages or members change. */
  connectLoungeRoomWebSocket(
    roomId: string,
    token: string,
    onMessage: (data: Record<string, unknown>) => void,
    onClose?: () => void,
    onError?: (e: Event) => void
  ): WebSocket | null {
    try {
      let wsUrl: string;
      if (this.baseUrl.startsWith('https://')) {
        wsUrl = this.baseUrl.replace('https://', 'wss://');
      } else if (this.baseUrl.startsWith('http://')) {
        wsUrl = this.baseUrl.replace('http://', 'ws://');
      } else {
        wsUrl = `ws://${this.baseUrl}`;
      }
      const fullWsUrl = `${wsUrl}/v1/lounge/rooms/${roomId}/ws?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(fullWsUrl);
      ws.onopen = () => {};
      ws.onmessage = (event) => {
        if (event.data === 'pong') return;
        try {
          const message = JSON.parse(event.data as string) as Record<string, unknown>;
          onMessage(message);
        } catch (error) {
          console.error('Lounge WebSocket parse error:', error);
        }
      };
      ws.onerror = (error) => {
        if (onError) onError(error);
      };
      ws.onclose = () => {
        if (onClose) onClose();
      };
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        else clearInterval(pingInterval);
      }, 30000);
      return ws;
    } catch (error) {
      console.error('Lounge WebSocket connect failed:', error);
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

  /** Delete the current user's voice profile (voice print). */
  async deleteVoiceProfile(): Promise<ApiResponse<{ ok: boolean }>> {
    return this.request<{ ok: boolean }>('/voice/profile', { method: 'DELETE' });
  }

  /** Identify speaker from WAV audio; returns user_id and similarity_score. Used for voice matching on Gemini-sourced transcripts. */
  async identifySpeaker(
    candidateUserIds: string[],
    audioBlob: Blob
  ): Promise<ApiResponse<{ user_id: string | null; similarity_score: number }>> {
    const formData = new FormData();
    formData.append('candidate_user_ids', candidateUserIds.join(','));
    formData.append('audio', audioBlob, 'segment.wav');
    return this.request<{ user_id: string | null; similarity_score: number }>('/voice/identify', {
      method: 'POST',
      body: formData,
      headers: {},
    });
  }

  /**
   * Submit speaker feedback for a segment ("that was me" or "that wasn't me").
   * When isMe is true, audioSegmentBase64 (WAV) is required for profile update.
   * Returns success and on error returns code (e.g. VOICE_ENROLLMENT_REQUIRED, AUDIO_TOO_SHORT) for user-facing messages.
   */
  async submitVoiceFeedback(
    segmentId: number,
    isMe: boolean,
    audioSegmentBase64?: string | null
  ): Promise<{ success: true } | { success: false; code?: string; message: string }> {
    const url = `${this.baseUrl}${BASE_PATH}/voice/feedback`;
    const token = this.accessToken ?? (typeof window !== 'undefined' ? localStorage.getItem('access_token') : null);
    const body: { segment_id: number; is_me: boolean; audio_segment_base64?: string } = {
      segment_id: segmentId,
      is_me: isMe,
    };
    if (isMe && audioSegmentBase64) {
      body.audio_segment_base64 = audioSegmentBase64;
    }
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        credentials: 'include',
        mode: 'cors',
      });
      if (response.ok) {
        return { success: true };
      }
      let code: string | undefined;
      let message = `Request failed (${response.status})`;
      try {
        const errBody = await response.json();
        const detail = errBody.detail;
        if (detail && typeof detail === 'object' && 'code' in detail && 'detail' in detail) {
          code = String(detail.code);
          message = String(detail.detail);
        } else if (typeof detail === 'string') {
          message = detail;
        }
      } catch {
        // ignore
      }
      return { success: false, code, message };
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Network error';
      return { success: false, message };
    }
  }
}

export const apiService = new ApiService();
