"""Alembic environment configuration."""
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy import text
from alembic import context
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.settings import settings
from app.infra.db.base import (
    Base,
    normalize_async_pg_url,
    async_pg_url_without_sslmode,
    async_pg_connect_args,
)
from app.infra.db.models import *  # noqa: F401, F403

# this is the Alembic Config object
config = context.config

# Use same URL normalization as app (asyncpg driver, strip sslmode / use ssl=True for DO).
_db_url = normalize_async_pg_url(settings.database_url)
config.set_main_option("sqlalchemy.url", async_pg_url_without_sslmode(_db_url))
_db_connect_args = async_pg_connect_args(_db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _widen_alembic_version_num(connection):
    """Widen alembic_version.version_num so long revision IDs fit (Alembic default is VARCHAR(32))."""
    connection.execute(text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'alembic_version'
            ) AND (
                SELECT character_maximum_length FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'alembic_version' AND column_name = 'version_num'
            ) IS DISTINCT FROM 255 THEN
                ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(255);
            END IF;
        END $$;
    """))


def do_run_migrations(connection):
    """Run migrations with connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using async engine (asyncpg)."""
    connectable = create_async_engine(
        async_pg_url_without_sslmode(_db_url),
        connect_args=_db_connect_args,
        poolclass=pool.NullPool,
        future=True,
    )

    # Widen alembic_version.version_num in a separate connection so it commits before migrations.
    async with connectable.connect() as alt_conn:
        await alt_conn.run_sync(_widen_alembic_version_num)
        await alt_conn.commit()

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
