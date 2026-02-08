# Fix Test Dependencies Issue

## Problem
Tests are failing with `ModuleNotFoundError: No module named 'email_validator'` even though it's listed in `pyproject.toml`.

**IMPORTANT:** If you're also seeing compilation errors for `greenlet` or `asyncpg`, see `FIX_PYTHON_VERSION.md` first. You may be using Python 3.14, which isn't supported yet.

## Solution

The dependencies need to be installed in Poetry's virtualenv:

```bash
cd backend

# Install all dependencies (this will install email-validator)
# Note: package-mode is disabled in pyproject.toml, so this works without --no-root
poetry install

# Verify email-validator is available
poetry run python -c "import email_validator; print('✓ email-validator installed')"

# Now run tests
poetry run pytest tests/test_market.py -v
```

## Why This Happens

- `pyproject.toml` lists `email-validator = "^2.3.0"` as a dependency
- `poetry show email-validator` shows it's in the lock file
- But `poetry install` must be run to actually install it in the virtualenv
- The test imports `User` model which uses `EmailStr` from pydantic, which requires `email-validator`

## Alternative: Use Poetry Shell

```bash
cd backend
poetry shell  # Activates the virtualenv
pytest tests/test_market.py -v  # Now runs in Poetry's environment
exit  # Exit when done
```
