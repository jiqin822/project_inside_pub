# Quick Start Guide

## Prerequisites
- Python 3.11+
- Poetry
- Flutter SDK
- Docker & Docker Compose

## Backend Setup (5 minutes)

1. **Start services:**
   ```bash
   make docker-up
   ```

2. **Install dependencies:**
   ```bash
   cd backend
   pip install poetry
   poetry install
   ```

3. **Set up environment:**
   ```bash
   cp env.example .env
   # Edit .env if needed
   ```

4. **Run migrations:**
   ```bash
   cd backend
   poetry run alembic revision --autogenerate -m "Initial migration"
   poetry run alembic upgrade head
   ```

5. **Start server:**
   ```bash
   make dev
   ```

   Server runs at: http://localhost:8000
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/health

## Frontend Setup (3 minutes)

1. **Install dependencies:**
   ```bash
   cd client
   flutter pub get
   ```

2. **Run app:**
   ```bash
   flutter run
   ```

   For web:
   ```bash
   flutter run -d chrome
   ```

## Test the Setup

### Backend Health Check
```bash
curl http://localhost:8000/health
```

### Register a User
```bash
curl -X POST http://localhost:8000/v1/admin/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123",
    "full_name": "Test User"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/v1/admin/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=test123"
```

## Next Steps

1. Open Flutter app and register/login
2. Create a relationship
3. Test WebSocket connection (tap WiFi icon in relationships list)
4. Send a poke to test REST + WS integration

## Troubleshooting

- **Database connection errors**: Ensure Docker services are running (`docker ps`)
- **Port conflicts**: Change ports in `docker-compose.yml` and `.env`
- **Flutter build errors**: Run `flutter clean && flutter pub get`
