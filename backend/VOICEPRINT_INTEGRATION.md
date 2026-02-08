# Voiceprint API Integration

This document describes the integration of the voiceprint-api service for voice enrollment and identification.

## Overview

The voiceprint-api service provides:
- **Voiceprint Registration**: Register a user's voiceprint from audio
- **Voiceprint Identification**: Identify a speaker from audio among candidate speakers
- **Voiceprint Deletion**: Delete a registered voiceprint

## Services

### Docker Compose

The voiceprint-api service is included in `docker-compose.yml`:
- **MySQL**: Database for storing voiceprint features (port 3306)
- **voiceprint-api**: Voiceprint recognition service (port 8005)

### Configuration

1. **Backend Settings** (`backend/app/settings.py`):
   - `voiceprint_api_url`: URL of the voiceprint-api service (default: `http://localhost:8005`)
   - `voiceprint_api_token`: API token for authentication (read from voiceprint-api config)

2. **Voiceprint API Config** (`voiceprint-api/data/.voiceprint.yaml`):
   - The API token is auto-generated on first startup
   - To get the token, check the logs or the config file after first run

3. **Environment Variables** (`.env`):
   ```bash
   VOICEPRINT_API_URL=http://localhost:8005
   VOICEPRINT_API_TOKEN=<token-from-voiceprint-api-config>
   ```

## Usage

### Voice Enrollment Flow

1. **Start Enrollment** (`POST /v1/voice/enrollment/start`):
   - Creates an enrollment record
   - Returns `enrollment_id`

2. **Upload Audio** (`PUT /v1/voice/enrollment/{enrollment_id}/audio`):
   - Uploads WAV audio file
   - Stores audio locally

3. **Complete Enrollment** (`POST /v1/voice/enrollment/{enrollment_id}/complete`):
   - Registers voiceprint with voiceprint-api using `user_id` as `speaker_id`
   - Creates voice profile with quality score
   - Returns `voice_profile_id` and `quality_score`

### Voice Identification

The `VoiceService.identify_speaker()` method can be used to identify speakers:
```python
speaker_id, score = await voice_service.identify_speaker(
    candidate_user_ids=["user1", "user2"],
    audio_bytes=audio_data
)
```

## API Client

The `VoiceprintClient` (`backend/app/infra/vendors/voiceprint_client.py`) provides:
- `register_voiceprint(speaker_id, audio_bytes)`: Register a voiceprint
- `identify_voiceprint(speaker_ids, audio_bytes)`: Identify a speaker
- `delete_voiceprint(speaker_id)`: Delete a voiceprint

## Setup Instructions

1. **Start Services**:
   ```bash
   docker-compose up -d mysql voiceprint-api
   ```

2. **Get API Token**:
   - After first startup, check `voiceprint-api/data/.voiceprint.yaml`
   - Copy the `authorization` value
   - Add to `.env` as `VOICEPRINT_API_TOKEN`

3. **Restart Backend**:
   ```bash
   cd backend
   make dev
   ```

## Notes

- The voiceprint-api requires WAV format audio files
- Audio is automatically processed to 16kHz sample rate
- The service uses 3D-Speaker model for voiceprint recognition
- Similarity threshold is configurable (default: 0.2)
