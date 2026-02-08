# Fix Database Port Configuration

## Issue

PostgreSQL is running on port **5433** (docker-compose mapping), but the backend default expects port **5432**.

## Solution

Create a `.env` file in the `backend/` directory:

```bash
cd backend
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/project_inside
REDIS_URL=redis://localhost:6379/0
REDIS_QUEUE_URL=redis://localhost:6379/1
EOF
```

Or manually create `.env` with:
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/project_inside
```

Then restart the server. The database connection warning should disappear.

## Quick Fix

**In your terminal (where server is running):**

1. Stop the server (Ctrl+C)
2. Create `.env` file:
   ```bash
   cd backend
   echo "DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/project_inside" > .env
   ```
3. Restart server:
   ```bash
   python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

The database connection should now work!
