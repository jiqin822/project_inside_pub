# Running Market Module Tests

## Prerequisites

1. **Install dependencies** (REQUIRED - run this first):
   ```bash
   cd backend
   poetry install
   ```
   
   This installs all dependencies including `email-validator` which is required for the User model.

2. **Verify email-validator is installed**:
   ```bash
   poetry run python -c "import email_validator; print('✓ email-validator is installed')"
   ```
   
   If this fails, run `poetry install` again.

2. **Ensure you're using Poetry's environment**:
   ```bash
   # Check Poetry environment
   poetry env info
   
   # If needed, activate Poetry shell
   poetry shell
   ```

## Running Tests

**IMPORTANT**: Always use `poetry run` to ensure Poetry's virtualenv is used, or activate the Poetry shell first.

### Option 1: Run all market tests (Recommended)
```bash
cd backend
poetry run pytest tests/test_market.py -v
```

**If you get import errors**, try activating Poetry shell first:
```bash
cd backend
poetry shell  # Activates Poetry's virtualenv
pytest tests/test_market.py -v
exit  # Exit when done
```

### Option 2: Run specific test class
```bash
cd backend
poetry run pytest tests/test_market.py::TestSpendFlow -v
```

### Option 3: Run specific test
```bash
cd backend
poetry run pytest tests/test_market.py::TestSpendFlow::test_purchase_item_success -v
```

### Option 4: Run with coverage
```bash
cd backend
poetry run pytest tests/test_market.py --cov=app.domain.market --cov=app.infra.db.repositories.market_repo --cov-report=html
```

## Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'email-validator'` or `pydantic_settings`

**Solution**: The test is using system Python instead of Poetry's virtualenv. Fix this:

```bash
cd backend

# 1. Verify Poetry environment
poetry env info

# 2. Reinstall dependencies to ensure everything is in the virtualenv
poetry install

# 3. Verify email-validator is installed
poetry show email-validator

# 4. Run tests using Poetry (this ensures the virtualenv is used)
poetry run pytest tests/test_market.py -v

# Alternative: Activate Poetry shell first
poetry shell
pytest tests/test_market.py -v
exit  # Exit shell when done
```

**If Poetry isn't using its virtualenv:**
```bash
# Check which Python Poetry is using
poetry env info --path

# If it shows a different path than expected, recreate the environment
poetry env remove python3.11
poetry install
```

### Issue: Tests can't find `app` module

**Solution**: The test file already includes path setup. If you still have issues:
```bash
cd backend
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
poetry run pytest tests/test_market.py
```

### Issue: Database connection errors

**Solution**: Market tests use in-memory SQLite, so no database setup is needed. If you see database errors, check that `aiosqlite` is installed:
```bash
poetry add --group dev aiosqlite
poetry install
```

## Test Structure

The test suite includes:
- **Economy Settings** (3 tests): Create, get, update
- **Wallets** (2 tests): Get/create, balance
- **Market Items** (4 tests): Create SPEND/EARN, get, delete
- **Spend Flow** (3 tests): Purchase, insufficient balance, redeem
- **Earn Flow** (3 tests): Accept, submit, approve
- **Transaction Cancellation** (3 tests): Cancel by holder/issuer, prevent cancel completed
- **Concurrency** (1 test): Double-spend prevention

Total: ~19 tests covering all key features.
