# Speech-to-Text: Multiple Languages

The backend **can** detect speech in different languages. It uses **Google Cloud Speech-to-Text v2**, which supports 85+ languages and locales.

## How it works

- **Session creation:** When creating an STT session (`POST /v1/stt/session`), you can pass `language_code`:
  - **BCP-47 code** (e.g. `en-US`, `es-ES`, `fr-FR`) — transcription in that language.
  - **`"auto"`** — **language-agnostic**: the backend uses **Chirp 3** and the model automatically detects and transcribes the dominant language spoken. See [Chirp 3: language-agnostic transcription](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3#perform_a_language-agnostic_transcription).
- **Default:** If omitted, the backend uses `en-US` (and the setting `gcp_stt_language_code` in settings as fallback).
- **Stream:** The WebSocket stream uses the language (or auto) set for that session for the whole conversation.

**Note:** When `language_code` is `"auto"`, speaker diarization is disabled for that session (Chirp 3 diarization in the API is only available for non-streaming methods).

## Examples

| Language        | Code    |
|----------------|---------|
| English (US)   | `en-US` |
| English (UK)   | `en-GB` |
| Spanish (Spain)| `es-ES` |
| Spanish (Latin America) | `es-US` |
| French (France)| `fr-FR` |
| German         | `de-DE` |
| Italian        | `it-IT` |
| Portuguese (Brazil) | `pt-BR` |
| Dutch          | `nl-NL` |
| Japanese       | `ja-JP` |
| Korean         | `ko-KR` |
| Mandarin (China) | `cmn-Hans-CN` |

Full list: [Google Cloud Speech-to-Text v2 supported languages](https://cloud.google.com/speech-to-text/v2/docs/speech-to-text-supported-languages).

## API

**Create session request** (`POST /v1/stt/session`):

```json
{
  "candidate_user_ids": ["user-id-1", "user-id-2"],
  "language_code": "es-ES",
  "min_speaker_count": 1,
  "max_speaker_count": 2
}
```

- `language_code` is optional. Use:
  - A BCP-47 code (e.g. `en-US`, `es-ES`) for a fixed language.
  - **`"auto"`** for automatic language detection (Chirp 3; no diarization in streaming).
- Default when omitted: `en-US`.

## Mobile app

In **Profile → Settings**, the **Transcription language** dropdown sets the STT language for Live Coach:

- **Auto** — backend uses Chirp 3 and auto-detects language (no diarization in streaming).
- **English** — `en-US` (STT transcribes English with diarization).
- **中文** — `cmn-Hans-CN` (STT transcribes Mandarin Chinese with diarization).

The chosen value is passed as `languageCode` when creating the STT session. Use **中文** when you speak Chinese so STT (not only Gemini) transcribes it.
