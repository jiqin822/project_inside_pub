# Project Inside

Communication + relationship coaching product with a FastAPI backend and a React/Vite/Capacitor client for web, iOS, and Android.

## Quick Links
- `docs/TECH_STACK.md` - Current stack and deployment details
- `backend/README.md` - Backend architecture and API details
- `docs/PERSONALIZATION_ENGINE.md` - Insider Compass personalization engine
- `mobile/INSTALL_ON_PHONE.md` - Native build/install notes
- `docs/DEPLOY_DIGITALOCEAN.md` - Production deployment guide

## Architecture

### Backend
- **Tech Stack**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL, Redis
- **Architecture**: Clean layering (api -> domain -> infra) with dependency injection
- **Integrations**: Google Cloud STT v2, Gemini, SpeechBrain (speaker embeddings), optional NeMo diarization, FCM, SendGrid

### Client (Web + Mobile)
- **Tech Stack**: React 19, TypeScript 5.8, Vite 6, Capacitor 8
- **State/Data**: TanStack React Query, Zustand, Zod
- **Targets**: Web SPA, iOS, Android (single codebase in `mobile/`)

### Infrastructure
- **Local**: Docker Compose (PostgreSQL, Redis, MySQL, optional voiceprint API)
- **Production**: DigitalOcean App Platform (`.do/app.yaml`) with `mobile/` static site + `backend/` service

## Project Structure

```
project_inside/
├── backend/      # FastAPI API + WebSockets
├── mobile/       # React/Vite/Capacitor app
├── contracts/    # API + WebSocket schemas
├── docs/         # Product, infra, and design docs
├── deploy/       # Nginx configs + deploy scripts
├── .do/          # DigitalOcean App Platform spec
├── scripts/      # Ops helpers
└── docker-compose.yml
```

## Setup

### Prerequisites
- Python 3.11+
- Node.js 22+
- Docker and Docker Compose
- PostgreSQL 15+ (or use Docker)
- Redis 7+ (or use Docker)

### Backend Setup

1. **Install dependencies:**
   ```bash
   make install
   ```

2. **Start Docker services:**
   ```bash
   make docker-up
   ```

3. **Set up environment variables (optional for local defaults):**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your configuration
   ```

4. **Run database migrations:**
   ```bash
   make migrate
   ```

5. **Start the development server:**
   ```bash
   make dev
   ```

   The API will be available at `http://localhost:8000`
   - API docs: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`

### Client Setup (Web)

1. **Install dependencies:**
   ```bash
   cd mobile
   npm install
   ```

2. **Set up environment variables:**
   - Set `VITE_API_BASE_URL` in `mobile/.env.development` or `mobile/.env.local`

3. **Run the app:**
   ```bash
   npm run dev
   ```

### Client Setup (iOS/Android)

See `mobile/INSTALL_ON_PHONE.md` and `mobile/CAPACITOR_SETUP.md`.

## Development

### Backend
- **Run tests:** `make test`
- **Lint code:** `make lint`
- **Format code:** `make format`

### Client
- **Run tests:** `cd mobile && npm run test`
- **Build:** `cd mobile && npm run build`
- **Preview:** `cd mobile && npm run preview`

## Environment Variables

See `backend/.env.example` and `docs/SETTINGS_AND_ENVIRONMENT.md` for backend configuration.
Client environment files live in `mobile/.env.development`, `mobile/.env.production`, and `mobile/.env.local`.

Key backend variables:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - JWT secret (change in production!)
- `GEMINI_API_KEY` - Gemini API key
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` - GCP credentials JSON

## License

[Your License Here]
