import { BaseApiClient, ApiResponse } from '../../../shared/lib/api/baseClient';

export interface StartEnrollmentResponse {
  enrollment_id: string;
  upload_url: string | null;
}

export interface UploadAudioResponse {
  ok: boolean;
}

export interface CompleteEnrollmentResponse {
  voice_profile_id: string;
  quality_score: number;
}

export class VoiceClient extends BaseApiClient {
  async startVoiceEnrollment(): Promise<ApiResponse<StartEnrollmentResponse>> {
    return this.request<StartEnrollmentResponse>('/voice/enrollment/start', {
      method: 'POST',
    });
  }

  async uploadEnrollmentAudio(
    enrollmentId: string,
    audioBlob: Blob
  ): Promise<ApiResponse<UploadAudioResponse>> {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');

    return this.request<UploadAudioResponse>(`/voice/enrollment/${enrollmentId}/audio`, {
      method: 'PUT',
      body: formData,
      headers: {}, // Let browser set Content-Type with boundary
    });
  }

  async completeVoiceEnrollment(
    enrollmentId: string
  ): Promise<ApiResponse<CompleteEnrollmentResponse>> {
    return this.request<CompleteEnrollmentResponse>(`/voice/enrollment/${enrollmentId}/complete`, {
      method: 'POST',
    });
  }
}

export const voiceClient = new VoiceClient();
