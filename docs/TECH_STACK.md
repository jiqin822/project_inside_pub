# Tech Stack

This document describes the current technology stack for Project Inside in three levels of detail: a short overview, a detailed stack by layer, and a deep dive with versions and file references.

---

## Overview

Project Inside is a communication and relationship coaching product. The system consists of:

- **Backend**: A Python service built with FastAPI, using PostgreSQL and Redis, with clean layering (api → domain → infra) and dependency injection. It provides REST and WebSocket APIs, integrates with Google Cloud Speech-to-Text and Gemini, optional NeMo-based diarization, SpeechBrain for speaker embeddings, SendGrid for email, and Firebase Cloud Messaging for push notifications.

- **Frontend**: A single codebase in `mobile/` that targets **web**, **iOS**, and **Android** via React, Vite, and Capacitor. It uses TypeScript, React Query and Zustand for data/state, and calls the backend API; it can be deployed as a static site (web) or built as native apps.

- **Infrastructure**: Local development uses Docker Compose (PostgreSQL and Redis). Production deployment is on **DigitalOcean App Platform** with two components: a static site (from `mobile/`) and a Python service (from `backend/`). No GitHub Actions or other CI/CD pipelines are present; builds and deploys are driven by the App Platform and the app spec in `.do/app.yaml`.

**Note:** The root `README.md` still describes the frontend as Flutter (Dio, Riverpod, `client/`). The **current** frontend is the React/Vite/Capacitor app in `mobile/`. This document reflects the actual codebase.

---

## Detailed Stack

### Backend

| Area | Technologies |
|------|--------------|
| **Runtime** | Python 3.12 (production; see `.do/app.yaml`, `backend/pyproject.toml`) |
| **Framework** | FastAPI, Uvicorn (ASGI) |
| **Validation & config** | Pydantic v2, Pydantic Settings; optional YAML/JSON config file (see `docs/SETTINGS_AND_ENVIRONMENT.md`) |
| **Database** | PostgreSQL 15+, SQLAlchemy 2.0, AsyncPG, Alembic (migrations) |
| **Cache / messaging** | Redis 7+ (main + queue DBs); Redis Pub/Sub for WebSocket broadcasting |
| **Auth** | JWT (python-jose), password hashing (passlib/bcrypt) |
| **HTTP client** | httpx |
| **WebSockets** | websockets library |
| **Email** | SendGrid |
| **LLM / AI** | Google Gemini (text, Love Map, activity recommendations), OpenAI (image generation, e.g. gpt-image-1) |
| **Speech & voice** | Google Cloud Speech-to-Text v2, SpeechBrain (ECAPA-TDNN embeddings), optional NeMo Sortformer diarization |
| **Push** | Firebase Cloud Messaging (FCM) |

### Mobile / Web (single codebase in `mobile/`)

| Area | Technologies |
|------|--------------|
| **UI** | React 19, TypeScript 5.8 |
| **Build** | Vite 6, @vitejs/plugin-react |
| **Native** | Capacitor 8 (iOS, Android); same codebase for web and native |
| **Data / state** | TanStack React Query, Zustand |
| **Routing** | react-router-dom 7 |
| **Validation** | Zod |
| **AI** | @google/genai (Gemini) |
| **UI** | lucide-react, react-markdown, Tailwind CSS (via CDN in index.html) |
| **Other** | heic2any (image conversion), Capacitor plugins: push-notifications, share, status-bar |

### Data stores

| Store | Role | Where |
|-------|------|--------|
| **PostgreSQL** | Primary app database | `docker-compose.yml` (postgres:15-alpine), DigitalOcean managed DB in prod |
| **Redis** | Cache, queue, WebSocket pub/sub | `docker-compose.yml` (redis:7-alpine), DO Redis in prod |

### Infrastructure and deployment

| Area | Details |
|------|--------|
| **Local** | Docker Compose: postgres (5433), redis (6379). See `docker-compose.yml`. |
| **Production** | DigitalOcean App Platform; one app, two components (static site `web` from `mobile/`, service `api` from `backend/`). See `.do/app.yaml`, `docs/DEPLOY_DIGITALOCEAN.md`. |
| **Backend build (DO)** | Python buildpack; custom build installs CPU-only PyTorch, then `requirements-full.txt`, then `requirements-nemo.txt`; run: `uvicorn app.main:app --host 0.0.0.0 --port 8080`. |
| **Frontend build (DO)** | Node.js; `npm run build` in `mobile/`, output `dist`. Node >= 22.0.0 (see `mobile/package.json` engines). |
| **CI/CD** | None in repo (no `.github/workflows`). Deploys via DO App Platform. |

### External services

| Service | Purpose |
|---------|--------|
| **Google Cloud** | Speech-to-Text v2 (STT), Gemini (text/image), FCM (push). Credentials via env (e.g. `GOOGLE_APPLICATION_CREDENTIALS_JSON`, `GEMINI_API_KEY`). |
| **OpenAI** | Image generation (e.g. gpt-image-1 for scrapbook stickers). |
| **SendGrid** | Transactional email. |

### Tooling

| Tool | Use |
|------|-----|
| **Makefile** | `make dev`, `make install`, `make test`, `make lint`, `make format`, `make docker-up`, `make docker-down`, `make migrate`, `make clean`. |
| **Poetry** | Backend dependency management (local dev). Production build uses pip + `requirements-full.txt` and `requirements-nemo.txt`. |
| **Alembic** | DB migrations (`backend/alembic.ini`, `backend/alembic/`). |
| **Ruff / Black** | Linting and formatting (backend). |
| **pytest / pytest-asyncio** | Backend tests. |
| **Scripts** | `backend/scripts/`: setup_env.sh, check_readiness.py, check_nemo.py, grant_schema_public.*, seed_remote_demo_family.sh, seed_demo_family.py, seed_love_map_prompts.py, etc. |

---

## Deep Dive

### Backend: sources and versions

- **Primary dependency list**: `backend/requirements-full.txt`. Optional NeMo stack: `backend/requirements-nemo.txt`.
- **Config and env**: `backend/app/settings.py` (Settings class); `backend/.env.example` for env template; optional `backend/config.yaml` or path via `CONFIG_FILE`. Precedence: push overrides > config file > env > defaults (see `docs/SETTINGS_AND_ENVIRONMENT.md`).
- **Setup parameters (defaults from `backend/app/settings.py`)**:

  | Area | Parameter | Default | Notes |
  |------|-----------|---------|--------|
  | **App** | `app_name` | Project Inside API | |
  | | `debug` | false | |
  | | `api_v1_prefix` | /v1 | |
  | **Database** | `database_url` | postgresql+asyncpg://postgres:postgres@localhost:5432/project_inside | Use 5433 for Docker Compose. |
  | | `database_echo` | false | SQL echo. |
  | **Redis** | `redis_url` | redis://localhost:6379/0 | |
  | | `redis_queue_url` | redis://localhost:6379/1 | |
  | **Security** | `secret_key` | change-me-in-production-use-env-var | **Must** override in production. |
  | | `access_token_expire_minutes` | 15 | |
  | | `refresh_token_expire_days` | 30 | |
  | **WebSocket** | `websocket_heartbeat_interval` | 30 | |
  | | `websocket_timeout` | 60 | |
  | **Rate limiting** | `nudge_rate_limit_seconds` | 10 | |
  | **Realtime** | `sr_threshold` | 2.0 | Speaking rate (SR_THRESHOLD). |
  | | `or_threshold` | 0.25 | Overlap ratio (OR_THRESHOLD). |
  | | `store_frames` | false | STORE_FRAMES. |
  | **Email** | `app_public_url` | from APP_PUBLIC_URL / VITE_API_BASE_URL / VITE_API_URL | Invite links. |
  | | `sendgrid_api_key` | "" | Optional; console fallback. |
  | | `email_from_address`, `email_from_name` | noreply@…, Project Inside | |
  | **Compass** | `compass_consolidation_threshold` | 5 | Unprocessed events before consolidation. |
  | **Gemini** | `gemini_api_key` | "" | Love Maps, analyze-turn, etc. |
  | | `llm_default_text_model` | gemini-2.0-flash | |
  | | `llm_backup_text_model` | gemini-2.5-flash | |
  | **OpenAI** | `openai_api_key` | "" | Scrapbook / gpt-image-1. |
  | | `llm_default_image_model` | gpt-image-1 | |
  | **Push (FCM)** | `push_enabled` | false | Set when GCP creds present. |
  | | `google_application_credentials` | "" | Path to service account JSON. |
  | | `google_application_credentials_json` | "" | Inline/base64 JSON (PaaS). |
  | **GCP STT** | `stt_recognizer` | projects/your-project/…/recognizers/default | Full recognizer resource name. |
  | | `stt_audio_buffer_seconds` | 30 | Ring buffer length. |
  | | `stt_escalation_cooldown_seconds` | 5 | |
  | | `stt_speaker_match_threshold` | 0.3 | ECAPA cosine similarity to attribute speaker. |
  | | `stt_speaker_match_margin` | 0.03 | Min gap best vs second. |
  | | `stt_prefer_known_over_unknown_gap` | 0.03 | Prefer known over unknown when gap &lt; this. |
  | | `stt_diarization_reliable_lag_ms` | 1200 | Only resolve segments ending before now − lag. |
  | **GCP STT (realtime)** | `gcp_project_id`, `gcp_stt_location`, `gcp_stt_recognizer` | "", global, "" | |
  | | `gcp_stt_language_code` | en-US | |
  | | `stt_min_speakers`, `stt_max_speakers` | 1, 2 | |
  | **STT NeMo diarization** | `stt_enable_nemo_diarization_fallback` | true | Use NeMo when Google diarization unavailable. |
  | | `stt_nemo_diarization_window_s` | 1.6 | Window size (seconds) per diarization run. |
  | | `stt_nemo_diarization_hop_s` | 0.4 | Hop (seconds) between runs. |
  | | `stt_nemo_diarization_timeout_s` | 3.0 | Max wait for NeMo response. |
  | | `stt_nemo_diarization_max_speakers` | 4 | Max speakers to detect. |
  | **STT voice centroids** | `stt_update_voice_centroid_after_session` | true | Update user voice profile at session end. |
  | | `stt_voice_centroid_min_segments` | 2 | Min segments per user to update. |
  | | `stt_voice_centroid_blend_alpha` | 0.3 | EMA: new = (1−α)·old + α·centroid. |
  | | `stt_voice_centroid_max_segments_per_user` | 50 | Cap segment list per user. |

- **Key versions (from requirements-full.txt)**:
  - anyio >=4.8.0,<5
  - fastapi >=0.115.0,<0.129.0
  - uvicorn[standard] >=0.24.0
  - pydantic >=2.5.0,<3.0.0, pydantic-settings >=2.1.0
  - sqlalchemy==2.0.23, alembic==1.12.1, asyncpg==0.29.0
  - redis[hiredis]==5.0.1
  - python-jose[cryptography]==3.3.0, passlib[bcrypt]==1.7.4
  - websockets>=13.0, httpx>=0.28.1,<1.0.0
  - sendgrid==6.11.0
  - google-cloud-speech, google-genai>=1.0.0
  - huggingface-hub==0.23.4 (pinned for SpeechBrain compatibility), speechbrain>=1.0.0, soundfile>=0.12.0
  - numpy, scipy
- **NeMo (optional)**: `requirements-nemo.txt`: PyYAML>=6.0, nemo_toolkit[asr]. Used for diarization fallback when Google streaming diarization is not used (e.g. language_code=auto). Build on DO installs CPU-only PyTorch first, then Cython/packaging, then full and nemo requirements (see `.do/app.yaml` build_command).
- **Entry and process**: `backend/app/main.py` (FastAPI app); `backend/Procfile`: uvicorn. DB layer: `backend/app/infra/db/base.py` (async engine with asyncpg). Realtime: `backend/app/infra/realtime/websocket.py`, `backend/app/infra/messaging/redis_bus.py`.

### Frontend: sources and versions

- **Dependencies**: `mobile/package.json`. Engines: Node >=22.0.0.
- **Notable versions**: react ^19.2.3, react-dom ^19.2.3, react-router-dom ^7.1.3, @tanstack/react-query ^5.62.11, zustand ^5.0.2, zod ^3.24.1, @google/genai ^1.38.0, @capacitor/core/cli/ios/android ^8.0.2, vite ^6.2.0, typescript ~5.8.2.
- **Structure**: Feature-based under `mobile/src/features/` (auth, dashboard, liveCoach, lounge, loveMaps, onboarding, profile, relationships, rewards, therapist, voice, activities). Shared: `mobile/src/shared/` (api, hooks, services, store, types, ui, utils). App shell and routes: `mobile/src/app/`.
- **Build**: `mobile/vite.config.ts`, `mobile/tsconfig.json`, `mobile/capacitor.config.ts`. Tailwind: included via CDN in `mobile/index.html`.
- **Native**: `mobile/ios/`, `mobile/android/` (Capacitor projects). See `mobile/INSTALL_ON_PHONE.md`, `mobile/CAPACITOR_SETUP.md`.

### Deployment topology

- **App spec**: `.do/app.yaml` defines `static_sites.web` (source_dir: mobile, build: npm run build, output_dir: dist) and `services.api` (source_dir: backend, custom build then uvicorn on port 8080). Routes: `/` → web, `/v1` → api (preserve path prefix).
- **Env**: Web component needs `VITE_API_BASE_URL` (build-time). Api component needs `DATABASE_URL` (postgresql+asyncpg://...), `REDIS_URL`, `SECRET_KEY` (or JWT equiv), and optionally GCP/FCM, Gemini, OpenAI, SendGrid, etc. See `docs/DEPLOY_DIGITALOCEAN.md` and `backend/.env.example`.
- **Database**: DO managed PostgreSQL; run migrations with `alembic upgrade head` against the same `DATABASE_URL`. Schema permissions: see “Permission denied for schema public” in `docs/DEPLOY_DIGITALOCEAN.md` and `backend/scripts/grant_schema_public.sh`.

### Data flow (high level)

- **Client**: Browser or Capacitor app loads the SPA from the static site, calls API at `VITE_API_BASE_URL/v1/...`, and can open a WebSocket for realtime (e.g. nudges, pokes).
- **API**: FastAPI serves `/v1/*` and WebSocket endpoints; uses PostgreSQL (SQLAlchemy + AsyncPG) and Redis (sessions, pub/sub). STT uses Google Cloud Speech-to-Text v2; speaker attribution uses ECAPA-TDNN (SpeechBrain) and optionally NeMo Sortformer diarization. LLM/image: Gemini and OpenAI as per settings.
- **Config**: Backend reads settings from defaults, env, optional config file, and optional push overrides; see `backend/app/config_store.py` and `docs/SETTINGS_AND_ENVIRONMENT.md`.

### STT and diarization: units and terminology

The STT and diarization pipeline uses consistent units and terms. Key files: `backend/app/api/stt/constants.py`, `backend/app/api/stt/segment_builder.py`, `backend/app/api/stt/diarization_workers.py`, `backend/app/domain/stt/session_registry.py`, `backend/app/domain/stt/nemo_sortformer_diarizer.py`.

| Term | Unit(s) | Meaning |
|------|---------|--------|
| **Sample** | Index (integer); 16 kHz everywhere | One time step of audio. At 16 kHz mono, 1 second = 16,000 samples = 32,000 bytes (16-bit PCM). Ring buffer, speaker timeline, and segment extraction all use sample indices as the stream timebase. |
| **Segment** | Seconds (STT/diarization) or sample bounds (timeline) | **STT segment**: one transcript phrase from Google (text + `raw_start_s`/`raw_end_s` in seconds; has a session-scoped `segment_id`). **Diarization segment**: a span attributed to one speaker; NeMo returns `start_s`/`end_s` in seconds (relative then converted to absolute stream seconds); the speaker timeline stores intervals as `(start_sample, end_sample, ...)`. |
| **Window** | Seconds (config), samples (buffer math) | A contiguous time span used for diarization or extraction. E.g. `stt_nemo_diarization_window_s` (e.g. 12 s) is converted to `window_samples = int(window_s * 16000)` for ring-buffer slicing. Timeline retention is expressed as max samples (e.g. last 60 s). |
| **Frame** | 0.08 s (80 ms) | Used only in the NeMo streaming Sortformer pipeline: the model consumes audio in fixed 80 ms frames (2,560 bytes at 16 kHz). One frame → one speaker-probability vector; diarization segment boundaries are derived as `frame_index * 0.08` seconds. See `_STREAM_FRAME_LEN_S` in `nemo_sortformer_diarizer.py`. |

- **Ring buffer**: `AudioRingBuffer` is indexed by **sample** count (`total_samples`); `slice(start_sample, end_sample)` returns numpy int16 samples for that range.
- **Speaker timeline**: `DiarInterval` is `(start_sample, end_sample, spk_id, spk_conf, overlap_flag)`; all in sample indices so transcript segments can be aligned for attribution and clean-PCM extraction.

---

## Notes

- **README vs this doc**: The root `README.md` describes a Flutter client in `client/` and backend setup with Poetry. The **current** client is the React/Vite/Capacitor app in `mobile/`. Backend layout (FastAPI, PostgreSQL, Redis, clean architecture) is accurate; for frontend and native build, use this doc and `mobile/` as the source of truth.
- **Config file**: Optional `backend/config.yaml` (or path via `CONFIG_FILE`) overrides env; see `docs/SETTINGS_AND_ENVIRONMENT.md`.
- **STT and GCP**: Production STT uses Google Cloud Speech-to-Text; on DigitalOcean, use `GOOGLE_APPLICATION_CREDENTIALS_JSON` (inline JSON) as described in `docs/DEPLOY_DIGITALOCEAN.md`.
