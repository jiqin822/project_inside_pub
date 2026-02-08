# Quick Start: Backend Server

## Problem: "No module named uvicorn"

You're in a conda environment, but the Makefile expects Poetry. Here's how to fix it:

## Solution: Install Dependencies and Run Directly

### Step 1: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- fastapi
- uvicorn
- sqlalchemy
- asyncpg (PostgreSQL driver)
- redis
- And all other dependencies

### Step 2: Start the Server

**Option A: Use the helper script (easiest)**
```bash
./install_and_run.sh
```

**Option B: Run manually**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Option C: Use make (after installing dependencies)**
```bash
# Modify Makefile or just run directly:
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Verify Server is Running

In another terminal:
```bash
curl http://localhost:8000/health
```

Should return: `{"status":"ok","version":"0.1.0"}`

### Step 4: Find Your IP for Flutter

```bash
# macOS
ipconfig getifaddr en0

# If that doesn't work, try:
ipconfig getifaddr en1
```

### Step 5: Run Flutter App

```bash
cd ../client
flutter run --dart-define=API_BASE_URL=http://YOUR_IP:8000
```

## Troubleshooting

### If pip install fails:
- Check internet connection
- Try: `pip install --upgrade pip` first
- Use conda: `conda install -c conda-forge fastapi uvicorn sqlalchemy asyncpg redis`

### If port 8000 is busy:
```bash
lsof -i :8000
# Kill the process or change port in uvicorn command
```

### If database connection fails:
Make sure PostgreSQL is running:
```bash
# Using docker-compose
cd .. && docker-compose up -d postgres

# Or check if it's running
docker ps | grep postgres
```

## Expected Output

When the server starts successfully, you should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx]
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

Then you can access:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
