"""Database base configuration."""
import os
import ssl
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

try:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
except ImportError as e:
    if "async_sessionmaker" in str(e):
        raise ImportError(
            "SQLAlchemy 2.x is required (async_sessionmaker). "
            "You may be using system Python with an older SQLAlchemy. "
            "Activate the backend venv (e.g. . venv/bin/activate) then: pip install -r requirements.txt"
        ) from e
    raise
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool


def normalize_async_pg_url(url: str) -> str:
    """Ensure URL uses asyncpg driver; cloud often gives postgresql:// (sync)."""
    u = (url or "").strip()
    if u.startswith("postgresql://") and "postgresql+asyncpg" not in u[:22]:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _ssl_context_no_verify() -> ssl.SSLContext:
    """SSL context that skips certificate verification (for local/one-off use only)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def async_pg_connect_args(url: str) -> dict:
    """Build connect_args for asyncpg: use ssl when URL has sslmode=require (asyncpg does not accept sslmode).
    Default: skip cert verification (managed Postgres on DO/Heroku often use certs that fail default verify).
    Set DATABASE_SSL_VERIFY=true to enable strict certificate verification."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    use_ssl = qs.get("sslmode") == ["require"]
    if not use_ssl:
        return {}
    verify = os.environ.get("DATABASE_SSL_VERIFY", "false").strip().lower()
    if verify in ("true", "1"):
        return {"ssl": True}
    return {"ssl": _ssl_context_no_verify()}


def async_pg_url_without_sslmode(url: str) -> str:
    """Return URL with sslmode removed so asyncpg does not get unknown kwarg sslmode."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs.pop("sslmode", None)
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


# Check if we're running in pytest (during collection or execution)
_is_pytest = 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in os.environ

# Only import settings if not in test mode to avoid dependency issues
if not _is_pytest:
    from app.settings import settings

    class _NullPoolTolerant(NullPool):
        """NullPool that logs connection terminate/close failures at DEBUG instead of ERROR.

        When the client disconnects during a streaming response, asyncpg's terminate() can
        raise (e.g. greenlet/await in bad state). The connection is gone anyway; we avoid
        ERROR spam by handling the close ourselves and logging at debug level only.
        """

        def _close_connection(self, connection, *, terminate=False):
            self.logger.debug(
                "%s connection %r",
                "Hard-closing" if terminate else "Closing",
                connection,
            )
            try:
                if terminate:
                    self._dialect.do_terminate(connection)
                else:
                    self._dialect.do_close(connection)
            except BaseException as e:
                if not isinstance(e, Exception):
                    raise
                self.logger.debug(
                    "Connection %s failed (connection may already be closed): %s",
                    "terminate" if terminate else "close",
                    e,
                    exc_info=True,
                )

    # NullPool: no connection reuse. Avoids pool-related "connection is closed" issues
    # when streaming responses are cancelled (client disconnect). Custom subclass
    # suppresses ERROR logs when terminate() raises on already-dead connections.
    # Normalize URL (asyncpg driver, strip sslmode so asyncpg gets ssl=True instead).
    _db_url = normalize_async_pg_url(settings.database_url)
    engine = create_async_engine(
        async_pg_url_without_sslmode(_db_url),
        connect_args=async_pg_connect_args(_db_url),
        echo=settings.database_echo,
        future=True,
        poolclass=_NullPoolTolerant,
    )
    
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    # In test mode, create dummy objects that will be overridden
    engine = None
    AsyncSessionLocal = None


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# Note: Models are imported in app/main.py to avoid circular imports
# Do not import models here as it creates a circular dependency:
# base.py -> models/__init__.py -> user.py -> base.py
