# Backend API

Communication + Relationship Coaching Backend built with FastAPI, SQLAlchemy 2.0, and Redis.

## Tech Stack

- **Python 3.11**
- **FastAPI** (REST + WebSockets)
- **Pydantic v2** (validation)
- **SQLAlchemy 2.0** (async ORM)
- **Alembic** (migrations)
- **PostgreSQL** (database)
- **Redis** (job queue + rate limiting)
- **JWT** (authentication)
- **bcrypt** (password hashing)
- **SendGrid** (email service - optional)

## Architecture

The backend follows a clean architecture pattern with strict layering:

```
app/
  api/          # FastAPI routes (HTTP/WS endpoints)
  domain/       # Business logic (models, services, policies)
  infra/        # Infrastructure (DB, Redis, security, WS manager)
```

- **API layer**: FastAPI routes, request/response models, dependency injection
- **Domain layer**: Pure business logic, no framework dependencies
- **Infra layer**: Database repositories, Redis, WebSocket manager, security

## Installation

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for PostgreSQL and Redis)
- Poetry (recommended) or pip

### Setup

1. **Start Docker services:**
   ```bash
   docker-compose up -d
   ```

2. **Configure environment (optional):**
   
   The app has sensible defaults in `app/settings.py`, so you can skip this step for local development.
   
   For the full process (precedence, config file, push overrides), see [docs/SETTINGS_AND_ENVIRONMENT.md](../docs/SETTINGS_AND_ENVIRONMENT.md).
   
   If you want to customize settings, create a `.env` file in the `backend/` directory with:
   ```bash
   # Application
   APP_NAME=Project Inside API
   APP_VERSION=0.1.0
   DEBUG=false
   
   # Database
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/project_inside
   DATABASE_ECHO=false
   
   # Redis
   REDIS_URL=redis://localhost:6379/0
   REDIS_QUEUE_URL=redis://localhost:6379/1
   
   # Security (IMPORTANT: Change in production!)
   SECRET_KEY=change-me-in-production-use-a-secure-random-string
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=15
   REFRESH_TOKEN_EXPIRE_DAYS=30
   
   # CORS (comma-separated, supports wildcards)
   CORS_ORIGINS=http://localhost:*,http://127.0.0.1:*,http://192.168.*.*:*
   
   # WebSocket
   WEBSOCKET_HEARTBEAT_INTERVAL=30
   WEBSOCKET_TIMEOUT=60
   
   # Rate Limiting
   NUDGE_RATE_LIMIT_SECONDS=10
   
   # Realtime Engine Thresholds
   SPEAKING_RATE_THRESHOLD=3.0
   OVERLAP_RATIO_THRESHOLD=0.3
   ```

3. **Install dependencies:**

   **Using Poetry (recommended):**
   ```bash
   poetry install
   poetry shell
   ```
   Speaker IDs use [SpeechBrain](https://speechbrain.readthedocs.io/) ECAPA-TDNN (included in main deps; no LLVM required).

   **Using pip:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Run migrations:**
   ```bash
   make migrate
   # Or: alembic upgrade head
   ```

5. **Start the server:**
   ```bash
   make dev
   # Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   **Speaker IDs (STT):** Speaker embeddings use SpeechBrain ECAPA-TDNN. Ensure `speechbrain` is installed in the env you use to run the server, or speaker scores will be 0%.

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs
- **Health**: http://localhost:8000/health

## API Endpoints

### Authentication
- `POST /v1/auth/signup` - Sign up new user
- `POST /v1/auth/login` - Login
- `POST /v1/auth/refresh` - Refresh access token

### Users
- `GET /v1/users/me` - Get current user (requires auth)

### Relationships
- `POST /v1/relationships` - Create relationship
- `GET /v1/relationships` - List user's relationships
- `PUT /v1/relationships/{rid}/consent/{uid}` - Update consent

### History
- `GET /v1/history/sessions` - List session history

### Sessions (Coach)
- `POST /v1/sessions` - Create session
- `POST /v1/sessions/{sid}/finalize` - Finalize session (enqueue review)
- `GET /v1/sessions/{sid}/report` - Get session report
- `GET /v1/activities/suggestions?rid=...` - Get activity suggestions

### Pokes (Interaction)
- `POST /v1/pokes` - Send poke
- `GET /v1/pokes?rid=...` - List pokes for relationship

### WebSocket
- `WS /v1/sessions/{sid}/ws?token=<access_token>` - Real-time session coaching

## WebSocket Protocol

### Client Messages
```json
{
  "type": "client.feature_frame",
  "sid": "<session_id>",
  "payload": {
    "timestamp_ms": 1234567890,
    "speaking_rate": 2.3,
    "overlap_ratio": 0.1
  }
}
```

### Server Messages
```json
{
  "type": "server.nudge",
  "sid": "<session_id>",
  "payload": {
    "nudge_type": "SLOW_DOWN",
    "intensity": 1,
    "message": "Try slowing down."
  }
}
```

```json
{
  "type": "server.session_state",
  "payload": {
    "sid": "<session_id>",
    "participants": ["user1", "user2"]
  }
}
```

## Development

### Running Tests
```bash
make test
# Or: pytest
```

### Linting
```bash
make lint
# Or: ruff check .
```

### Formatting
```bash
make format
# Or: black .
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
make migrate
# Or: alembic upgrade head

# Rollback
alembic downgrade -1
```

## Environment Variables

See `.env.example` for all available settings. Key variables:

- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `SECRET_KEY` - JWT secret (change in production!)
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Access token expiry (default: 15)
- `REFRESH_TOKEN_EXPIRE_DAYS` - Refresh token expiry (default: 30)
- `CORS_ORIGINS` - Allowed CORS origins (comma-separated)

## Project Structure

```
backend/
  app/
    api/
      admin/          # Auth, users, relationships, history routes
      coach/           # Sessions, reports, activities routes
      interaction/     # Pokes, WebSocket routes
      deps.py          # FastAPI dependencies (auth, DB)
    domain/
      admin/           # User, relationship, consent models & services
      coach/           # Session models, services, analyzers
      interaction/     # Poke models, services, rate limiting
      common/          # Shared types, errors
    infra/
      db/
        models/        # SQLAlchemy ORM models
        repositories/  # Repository implementations
        base.py        # DB engine, session factory
        session.py     # Session dependency
      security/        # JWT, password hashing
      realtime/        # WebSocket manager
      messaging/       # Redis bus
      jobs/            # Job queue, tasks
    main.py            # FastAPI app
    settings.py        # Configuration
    tests/             # Tests
  alembic/             # Migrations
  pyproject.toml       # Dependencies, tool configs
  requirements.txt     # Production dependencies
  Makefile             # Common commands
  docker-compose.yml   # PostgreSQL + Redis
```

## Notes

- All endpoints are versioned under `/v1`
- JWT tokens required for all endpoints except `/health`, `/v1/auth/signup`, `/v1/auth/login`, `/v1/auth/refresh`
- WebSocket connections require access token in query param: `?token=<access_token>`
- Rate limiting: Max 1 nudge per 10 seconds per (session_id, user_id)
- Session finalization enqueues a background job to generate report
- Real-time coaching engine uses rule-based analysis (speaking rate, overlap ratio thresholds)

## Email Configuration

The backend supports email sending via SendGrid for relationship invitations.

### Setup SendGrid (Optional)

1. **Create a SendGrid account**: https://sendgrid.com (free tier: 100 emails/day)

2. **Get your API key**:
   - Go to https://app.sendgrid.com/settings/api_keys
   - Create a new API key with "Mail Send" permissions
   - Copy the API key

3. **Configure environment variables**:
   ```bash
   SENDGRID_API_KEY=your_api_key_here
   EMAIL_FROM_ADDRESS=noreply@yourdomain.com
   EMAIL_FROM_NAME=Project Inside
   ```

4. **Verify your sender domain** (recommended for production):
   - In SendGrid dashboard, go to Settings → Sender Authentication
   - Verify your domain or use single sender verification

### Email Service Behavior

- **With SendGrid API key**: Emails are sent via SendGrid with HTML templates
- **Without SendGrid API key**: Uses console email service (logs to console, no actual emails sent)

The system automatically selects the appropriate service based on configuration.
