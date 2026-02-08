# Fix: "No module named uvicorn" in Conda Environment

## Problem
You're in the `otter_school` conda environment, but uvicorn is installed in the base anaconda environment.

## Solution Options

### Option 1: Install in Current Conda Environment (Recommended)

**In your terminal, run these commands:**

```bash
# Make sure you're in the otter_school environment
conda activate otter_school

# Install dependencies
cd backend
pip install -r requirements.txt
```

**If you get SSL errors, try:**
```bash
# Fix SSL certificates (macOS)
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
```

**Or use conda-forge:**
```bash
conda install -c conda-forge fastapi uvicorn sqlalchemy asyncpg redis-py python-jose passlib
pip install pydantic-settings python-multipart websockets httpx alembic email-validator
```

### Option 2: Use Base Anaconda Environment

If you want to use the base environment where uvicorn is already installed:

```bash
# Deactivate current environment
conda deactivate

# Run from base environment
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Create New Conda Environment for Backend

```bash
# Create a fresh environment
conda create -n project_inside python=3.11
conda activate project_inside

# Install dependencies
cd backend
pip install -r requirements.txt

# Start server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Quick Fix (Try This First)

**Run in your terminal:**

```bash
conda activate otter_school
cd backend
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt
```

Then start the server:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Verify Installation

After installing, verify uvicorn is available:
```bash
python -c "import uvicorn; print(uvicorn.__version__)"
```

Should print a version number (e.g., `0.24.0`).

## After Server Starts

Once you see `Uvicorn running on http://0.0.0.0:8000`:

1. **Find your IP:**
   ```bash
   ipconfig getifaddr en0
   ```

2. **Run Flutter:**
   ```bash
   cd ../client
   flutter run --dart-define=API_BASE_URL=http://YOUR_IP:8000
   ```
