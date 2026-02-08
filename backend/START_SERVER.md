# Starting the Backend Server

## Issue: "No module named uvicorn"

The Makefile expects Poetry, but you're using a conda environment. Here are your options:

## Option 1: Install Dependencies with pip (Recommended)

```bash
cd backend
pip install -r requirements.txt
```

Then start the server directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Option 2: Use Poetry (If Available)

```bash
cd backend
poetry install
poetry shell
make dev
```

## Option 3: Modify Makefile to Use Current Python

If you want to keep using `make dev`, you can temporarily modify the Makefile or run:

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Quick Start (After Installing Dependencies)

1. **Install dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Start the server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Verify it's running:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status":"ok","version":"0.1.0"}
   ```

4. **Find your IP for Flutter:**
   ```bash
   # macOS
   ipconfig getifaddr en0
   
   # Then run Flutter with:
   cd ../client
   flutter run --dart-define=API_BASE_URL=http://YOUR_IP:8000
   ```

## Troubleshooting

### If pip install fails:
- Make sure you have internet connection
- Try: `pip install --upgrade pip` first
- Use conda: `conda install -c conda-forge fastapi uvicorn`

### If port 8000 is already in use:
```bash
lsof -i :8000
# Kill the process or use a different port
```
