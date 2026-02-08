# Dialogue Deck (Live Coach) Implementation

This document describes how Dialogue Deck is implemented across the mobile app and backend, including real‑time transcription, speaker identification, and escalation prompts.

## Overview

Dialogue Deck runs a dual‑stream pipeline:

1. **Gemini Live**: real‑time coaching analysis (horsemen, sentiment, interventions).
2. **GCP Speech‑to‑Text v2**: low‑latency transcript + diarization (primary transcript source).

Speaker identity is resolved by matching diarized segments to stored **voice print embeddings**. If a segment does not match, it is labeled as `Unknown_1`, `Unknown_2`, etc.

## Mobile Architecture

### Entry point

`mobile/src/features/liveCoach/screens/LiveCoachScreen.tsx`

Key responsibilities:
- Open microphone and WebAudio graph.
- Stream PCM to **Gemini Live** and **STT** in parallel.
- Render transcript, analytics (horsemen/sentiment), and escalation prompts.

### Audio capture + fork

The `ScriptProcessorNode` in `LiveCoachScreen` drives the audio loop:

- `session.sendAudio(inputData)` → Gemini Live
- `sttSessionRef.current?.sendAudio(inputData)` → STT backend

Transcripts are rendered from STT events. Gemini is only used as a fallback if STT is unavailable.

### STT client

`mobile/src/shared/services/sttService.ts`

Responsibilities:
- `POST /v1/stt/session` to create session
- Open WS: `/v1/stt/stream/{session_id}?token=...`
- Send PCM16 audio frames as `ArrayBuffer`
- Emit events:
  - `stt.transcript` (final only)
  - `stt.escalation`
  - `stt.error`

### Gemini Live client

`mobile/src/shared/services/geminiService.ts`

Responsibilities:
- Connect to Gemini Live API.
- Convert enrolled voice print from base64 WAV → PCM16k for optional voice identification.
- Produce analysis events (`horseman`, `sentiment`) via `reportAnalysis` tool calls.

## Backend Architecture

### STT endpoints

`backend/app/api/stt/routes_stt.py`

Routes:
- `POST /v1/stt/session`
- `WS /v1/stt/stream/{session_id}`

Flow:
1. Client creates a session with candidate speaker IDs.
2. WebSocket accepts PCM16K audio and streams to GCP STT v2.
3. STT returns diarized segments with speaker tags.
4. A segment embedding is computed and matched to stored voice prints.
5. Events are pushed back to the client.

### Session registry

`backend/app/domain/stt/session_registry.py`

Stores:
- `session_id`, `user_id`
- candidate user IDs
- diarization → label mapping
- voice embeddings cache

### Speaker matching

`backend/app/domain/stt/speaker_matching.py` + `backend/app/domain/voice/embeddings.py`

Speaker matching:
- For each finalized diarized segment, compute embedding from PCM.
- Compare against stored embeddings via cosine similarity.
- If matched ≥ threshold → label with user ID.
- Otherwise assign `Unknown_N`.

### Escalation detection

`backend/app/domain/stt/escalation.py`

Rules:
- Simple keyword + profanity heuristics for sub‑second prompts.
- Emits `stt.escalation` events to the UI.
- Cooldown prevents repeated prompts.

## Voice Print Embeddings

Enrollment is handled in `backend/app/domain/voice/services.py`:

- Audio is stored as base64 WAV (`voice_sample_base64`).
- Embedding is computed and saved as JSON (`voice_embedding_json`).
- **TitaNet (NVIDIA NeMo)** is used for 192-dimensional speaker embeddings (~97% accuracy on VoxCeleb).
- Falls back to MFCC if `nemo_toolkit` is unavailable.

Database migrations:
- `backend/alembic/versions/012_add_voice_embedding_json.py`
- `backend/alembic/versions/013_clear_resemblyzer_embeddings.py` (clears old embeddings for TitaNet migration)

## UI/UX Behavior

### Transcript source priority

1. **STT transcripts** (final only, diarized)
2. **Gemini Live fallback** when STT is unavailable

### Escalation prompt

STT can emit a prompt event in <1s based on aggressive language.  
The UI displays a banner near the visualizer for ~6 seconds.

## Message Schemas

### STT → Client events

```json
{
  "type": "stt.transcript",
  "text": "I feel unheard when you interrupt me.",
  "speaker_label": "user-uuid-or-Unknown_1",
  "speaker_tag": 1,
  "is_final": true,
  "start_ms": 1020,
  "end_ms": 2480,
  "confidence": 0.91
}
```

```json
{
  "type": "stt.escalation",
  "severity": "high",
  "reason": "aggressive_language",
  "message": "Pause. This is escalating. Try a reset: slow breath, soften tone, and speak needs not blame."
}
```

```json
{
  "type": "stt.error",
  "message": "details..."
}
```

## Configuration

Backend env vars:

- `STT_RECOGNIZER` (full GCP recognizer resource name)
- `STT_SPEAKER_MATCH_THRESHOLD` (default `0.75`)
- `STT_AUDIO_BUFFER_SECONDS` (default `30`)
- `STT_ESCALATION_COOLDOWN_SECONDS` (default `5`)
- `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON)

Defaults in:
- `backend/app/settings.py`
- `backend/.env.example`
- `env.example`

## Dependencies

Backend:
- `google-cloud-speech`
- `numpy`
- `python-speech-features`
- `torch>=2.0.0`
- `torchaudio>=2.0.0`
- `nemo_toolkit[asr]>=1.20.0` (TitaNet speaker embeddings)

## Troubleshooting

- **No transcript:** verify STT WebSocket (`/v1/stt/stream/{session_id}`) is reachable and `GOOGLE_APPLICATION_CREDENTIALS` is set.
- **Unknown speakers only:** ensure voice enrollment has run after the embedding migration, and embeddings exist in `voice_profiles.voice_embedding_json`.
- **Slow prompts:** reduce `STT_ESCALATION_COOLDOWN_SECONDS` or expand escalation rules in `backend/app/domain/stt/escalation.py`.

