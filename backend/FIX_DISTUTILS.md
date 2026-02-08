# Fix: ModuleNotFoundError: No module named 'distutils'

## Problem
Python 3.12+ removed `distutils` from the standard library, but the `redis` package still requires it.

## Solution

### Option 1: Install setuptools (provides distutils) - RECOMMENDED

Run this in your terminal (outside of Cursor's sandbox):

```bash
# Activate your conda environment
conda activate otter_school

# Install setuptools (which provides distutils)
conda install -y setuptools

# Or if conda doesn't work, try pip with user install:
pip install --user setuptools
```

Then restart the server:
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Use a different Python version

If you have Python 3.10 or 3.11 available, use that instead:

```bash
# Check available Python versions
which -a python3

# Use a specific version (e.g., Python 3.10)
python3.10 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Create a new conda environment with Python 3.11

```bash
conda create -n project_inside python=3.11
conda activate project_inside
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 4: Quick fix - install setuptools with user flag

```bash
cd backend
python -m pip install --user setuptools
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Why this happens

- Python 3.12+ removed `distutils` from the standard library
- The `redis` package (version 5.0.1) still imports `distutils.version.StrictVersion`
- `setuptools` provides a backport of `distutils` for newer Python versions

## After fixing

Once setuptools is installed, the server should start successfully and the CORS fix will be active, allowing your iPhone to connect.
