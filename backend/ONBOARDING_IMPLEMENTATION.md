# Onboarding Backend Implementation Summary

## Overview

Complete backend implementation for the onboarding workflow, including all API endpoints, database models, domain services, and infrastructure components.

## Database Schema Changes

### New Tables
1. **onboarding_progress** - Tracks completion status for each onboarding step
2. **voice_enrollments** - Voice enrollment sessions
3. **voice_profiles** - Completed voice profiles
4. **relationship_invites** - Invitation system for relationships

### Updated Tables
1. **users** - Added: `pronouns`, `communication_style`, `goals` (JSONB), `privacy_tier`
2. **relationships** - Added: `type` (enum), `created_by_user_id`; Updated status to enum
3. **relationship_members** - Added: `member_status` (enum), `added_at`, `responded_at`
4. **relationship_consents** - Renamed from `consents`; Added: `version`, `status` (enum); Changed `scopes` to JSONB

## API Endpoints Implemented

### Onboarding
- `GET /v1/onboarding/status` - Get onboarding status and next step
- `POST /v1/onboarding/complete` - Mark a step as complete

### Profile
- `PATCH /v1/users/me` - Update user profile (display_name, pronouns, communication_style, goals, privacy_tier)
- `GET /v1/users/me` - Get current user (now includes all profile fields)

### Voice Enrollment
- `POST /v1/voice/enrollment/start` - Start voice enrollment
- `PUT /v1/voice/enrollment/{enrollment_id}/audio` - Upload audio (binary)
- `POST /v1/voice/enrollment/{enrollment_id}/complete` - Complete enrollment

### Contacts & Invites
- `POST /v1/contacts/lookup` - Lookup contact by email (EXISTS/NOT_FOUND/BLOCKED)
- `POST /v1/relationships/{rid}/invites` - Create and send invite
- `GET /v1/relationships/{rid}/invites` - List invites for relationship

### Relationships
- `POST /v1/relationships` - Create relationship (updated to use `type` instead of `rel_type`)
- `GET /v1/relationships` - List relationships (returns `type` field)

### Consent
- `GET /v1/relationships/{rid}/consent/templates` - Get consent templates
- `PUT /v1/relationships/{rid}/consent/me` - Set my consent (with versioning)
- `GET /v1/relationships/{rid}/consent` - Get consent state for relationship

### Devices
- `POST /v1/devices/push-token` - Register push token (MVP: logs only)

## Domain Services

### OnboardingService
- `get_status()` - Computes onboarding status with next_step logic
- `complete_step()` - Marks steps as complete

### VoiceService
- `start_enrollment()` - Creates enrollment session
- `upload_audio()` - Stores audio file locally
- `complete_enrollment()` - Creates voice profile with quality score

### ConsentService
- `get_templates()` - Returns templates by relationship type
- `set_my_consent()` - Sets consent with versioning
- `get_consent_state()` - Returns full consent state
- `_try_activate_relationship()` - Activates relationship when all members have consent

### ContactService
- `lookup_contact()` - Checks if email exists, is blocked, or not found

### InviteService
- `create_invite()` - Creates invite, sends email, adds member if user exists

## Infrastructure

### Repositories
- `OnboardingRepository` - Manages onboarding progress
- `VoiceRepository` - Manages enrollments and profiles
- `InviteRepository` - Manages invites with token hashing
- Updated `UserRepository` - Added `update_profile_fields()`
- Updated `ConsentRepository` - Added versioning and status
- Updated `RelationshipRepository` - Handles member status

### Email Service
- `ConsoleEmailService` - MVP stub that logs to console with invite URL
- Token stored as hash in DB, raw token only in email

## Alembic Migration

Created `002_onboarding_schema.py` migration that:
- Adds new columns to existing tables
- Creates new tables with proper enums
- Migrates existing data
- Includes downgrade path

## Testing

Added comprehensive pytest tests in `test_onboarding.py`:
1. Signup → onboarding status returns PROFILE step
2. Update profile → complete step → advances to VOICEPRINT
3. Skip voiceprint → advances to RELATIONSHIPS
4. Create relationship → list relationships
5. Contact lookup NOT_FOUND → create invite
6. Consent templates → set consent → version increments

## Configuration

Updated `settings.py`:
- `app_public_url` - Base URL for invite links
- `email_blocked_domains` - List of blocked email domains

Updated `env.example`:
- Added `APP_PUBLIC_URL` and `EMAIL_BLOCKED_DOMAINS`

## State Machine Logic

### Onboarding Status Computation
- `has_profile`: user.display_name OR profile_completed
- `has_voiceprint`: voice_profiles exists OR voiceprint_completed
- `pending_invites`: Count of SENT/OPENED invites for user's email
- `active_relationships`: Count of ACTIVE relationships user is member of
- `next_step`: Deterministic logic through steps (PROFILE → VOICEPRINT → RELATIONSHIPS → CONSENT → DEVICE_SETUP → DONE)

### Relationship Creation
- Creator automatically added as member with ACCEPTED status
- Other members added with INVITED status
- Status: DRAFT if only creator, PENDING_ACCEPTANCE if multiple members

### Consent Activation
- Relationship activates when all members are ACCEPTED and have ACTIVE consent
- Downgrades to PENDING_ACCEPTANCE if requirements no longer met

## Running

1. **Start services**: `make docker-up` (from project root)
2. **Run migration**: `cd backend && make migrate`
3. **Start server**: `cd backend && make dev`
4. **Run tests**: `cd backend && make test`

## Notes

- All endpoints require JWT authentication (except signup/login/refresh/health)
- Voice audio stored in `storage/audio/` directory (local filesystem)
- Email service is a console stub (logs invite URLs)
- Push token registration logs only (no DB storage yet)
- Relationship `type` enum maps to `rel_type` string for backward compatibility
- Consent versioning increments on each update
- Invite tokens are hashed before storage (SHA256)
