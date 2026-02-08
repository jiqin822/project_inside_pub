import { BaseApiClient, ApiResponse } from '../../../shared/lib/api/baseClient';

export interface RelationshipResponse {
  id: string;
  type: string;
  created_at: string;
}

export interface ConsentInfoResponse {
  members?: Array<{ user_id: string; member_status?: string }>;
}

export interface UserResponse {
  id: string;
  display_name?: string;
  email?: string;
  profile_picture_url?: string;
}

export interface InviteResponse {
  id: string;
  email: string;
  status: string;
  inviter_user_id?: string;
}

export class RelationshipClient extends BaseApiClient {
  async getRelationships(): Promise<ApiResponse<RelationshipResponse[]>> {
    return this.request<RelationshipResponse[]>('/relationships', { method: 'GET' });
  }

  async createRelationship(type: string, memberIds: string[]): Promise<ApiResponse<RelationshipResponse>> {
    return this.request<RelationshipResponse>('/relationships', {
      method: 'POST',
      body: JSON.stringify({ type, member_ids: memberIds }),
    });
  }

  async deleteRelationship(relationshipId: string): Promise<ApiResponse<void>> {
    return this.request<void>(`/relationships/${relationshipId}`, {
      method: 'DELETE',
    });
  }

  async getUserById(userId: string): Promise<ApiResponse<UserResponse>> {
    return this.request<UserResponse>(`/users/${userId}`, { method: 'GET' });
  }

  async lookupContact(email: string): Promise<ApiResponse<UserResponse | null>> {
    return this.request<UserResponse | null>('/contacts/lookup', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async validateInviteToken(token: string): Promise<ApiResponse<{
    email?: string;
    relationship_type?: string;
    inviter_name?: string;
  }>> {
    return this.request(`/relationships/invites/validate?token=${encodeURIComponent(token)}`, {
      method: 'GET',
    });
  }

  async createInvite(
    relationshipId: string,
    email: string,
    role?: string,
    message?: string
  ): Promise<ApiResponse<InviteResponse>> {
    return this.request<InviteResponse>(`/relationships/${relationshipId}/invites`, {
      method: 'POST',
      body: JSON.stringify({ email, role, message }),
    });
  }

  async getInvites(relationshipId: string): Promise<ApiResponse<InviteResponse[]>> {
    return this.request<InviteResponse[]>(`/relationships/${relationshipId}/invites`, {
      method: 'GET',
    });
  }

  async getConsentInfo(relationshipId: string): Promise<ApiResponse<ConsentInfoResponse>> {
    return this.request<ConsentInfoResponse>(`/relationships/${relationshipId}/consent`, {
      method: 'GET',
    });
  }
}

export const relationshipClient = new RelationshipClient();
