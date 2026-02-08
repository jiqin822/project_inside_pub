# Fix Market Tests JSONB Issue

## Problem

Market tests were failing with:
```
sqlalchemy.exc.CompileError: (in table 'users', column 'goals'): Compiler <sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler object> can't render element of type JSONB
```

**Root Cause**: The tests use in-memory SQLite, but the `users` table has a `goals` column that uses `JSONB` (PostgreSQL-specific type). SQLite doesn't support `JSONB`.

## Solution

Modified `tests/test_market.py` to:

1. **Create a separate users table for tests** using `JSON` instead of `JSONB` for SQLite compatibility
2. **Create minimal user records** in the `sample_users` fixture to satisfy foreign key constraints
3. **Create both the users table and market tables** before running tests

## Changes Made

1. Added imports for `JSON` type from `sqlalchemy.types`
2. Created a minimal `users` table definition using `JSON` instead of `JSONB`
3. Updated `sample_users` fixture to be async and create actual user records in the database
4. Modified `db_session` fixture to create both the users table and market tables

## Running Tests

After installing dependencies:

```bash
cd backend
poetry install  # Install email-validator and other dependencies
poetry run pytest tests/test_market.py -v
```

## Note

The `JSONBType` adapter class was created but not used in the final solution. It's kept in the file for potential future use if we need to make the UserModel itself SQLite-compatible.
