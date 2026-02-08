import { BaseApiClient, ApiResponse } from '../../../shared/lib/api/baseClient';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  display_name?: string;
  invite_token?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  display_name?: string;
  pronouns?: string;
  personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
  goals?: string[];
  birthday?: string; // ISO date YYYY-MM-DD
  occupation?: string;
  profile_picture_url?: string;
  voice_profile_id?: string;
  voice_print_data?: string; // Base64-encoded WAV for Live Coach
}

export class AuthClient extends BaseApiClient {
  async login(email: string, password: string): Promise<ApiResponse<AuthResponse>> {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await this.request<AuthResponse>('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    this.setAccessToken(response.data.access_token);
    this.setRefreshToken(response.data.refresh_token);
    return response;
  }

  async signup(
    email: string,
    password: string,
    displayName?: string,
    inviteToken?: string
  ): Promise<ApiResponse<AuthResponse>> {
    const body: SignupRequest = {
      email,
      password,
      display_name: displayName,
      invite_token: inviteToken,
    };

    const response = await this.request<AuthResponse>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    this.setAccessToken(response.data.access_token);
    this.setRefreshToken(response.data.refresh_token);
    return response;
  }

  async getCurrentUser(): Promise<ApiResponse<UserResponse>> {
    return this.request<UserResponse>('/users/me', { method: 'GET' });
  }

  async updateProfile(data: {
    display_name?: string;
    pronouns?: string;
    personality_type?: { type: string; values?: { ei: number; sn: number; tf: number; jp: number } };
    communication_style?: string;
    goals?: string[];
    birthday?: string; // ISO date YYYY-MM-DD
    occupation?: string;
    privacy_tier?: string;
    profile_picture_url?: string;
  }): Promise<ApiResponse<UserResponse>> {
    return this.request<UserResponse>('/users/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }
}

export const authClient = new AuthClient();
