# Fix Python Version Compatibility Issue

## Problem

Poetry is failing to install dependencies because you're using **Python 3.14.2** (from conda environment `otter_school`), but the dependencies `greenlet` and `asyncpg` don't support Python 3.14 yet.

**Error symptoms:**
- `greenlet` compilation errors: `unknown type name '_PyCFrame'`, `no member named 'recursion_limit'`
- `asyncpg` compilation errors: `call to undeclared function '_PyInterpreterState_GetConfig'`

## Solution

The project requires **Python 3.11 or 3.12** (as specified in `pyproject.toml`). You have two options:

### Option 1: Use Poetry's Virtualenv (Recommended)

Poetry already has a virtualenv with Python 3.11.6. Use it:

```bash
cd backend

# Make sure Poetry uses its own virtualenv
poetry env use python3.11  # or python3.12

# Install dependencies (package-mode is now disabled in pyproject.toml)
poetry install

# Run tests
poetry run pytest tests/test_market.py -v
```

### Option 2: Create a New Conda Environment with Python 3.11 or 3.12

If you prefer using conda:

```bash
# Create a new conda environment with Python 3.11
conda create -n project_inside python=3.11
conda activate project_inside

# Install Poetry if not already installed
# Then install dependencies
cd backend
poetry install  # package-mode is disabled, so this works without --no-root

# Run tests
poetry run pytest tests/test_market.py -v
```

Or with Python 3.12:

```bash
conda create -n project_inside python=3.12
conda activate project_inside
cd backend
poetry install
poetry run pytest tests/test_market.py -v
```

### Option 3: Use System Python 3.11/3.12

If you have Python 3.11 or 3.12 installed on your system:

```bash
cd backend

# Tell Poetry to use a specific Python version
poetry env use /usr/local/bin/python3.11  # or wherever Python 3.11 is

# Or use python3.12
poetry env use /usr/local/bin/python3.12

# Install dependencies
poetry install  # package-mode is disabled, so this works without --no-root

# Run tests
poetry run pytest tests/test_market.py -v
```

## Verify Python Version

After setting up the environment, verify:

```bash
poetry run python --version
# Should show: Python 3.11.x or Python 3.12.x (NOT 3.14.x)
```

## Why This Happens

- Python 3.14 is very new (released in 2024)
- C extension packages like `greenlet` and `asyncpg` need to be updated to support new Python versions
- These packages haven't released Python 3.14-compatible versions yet
- The project specifies `python = "^3.11"` which means 3.11, 3.12, or 3.13 (but 3.14 is too new)

## Summary

**Quick fix:** Use Poetry's virtualenv with Python 3.11.6 (already set up) or create a conda environment with Python 3.11/3.12.
