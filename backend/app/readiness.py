"""Readiness checks: config, packages, database, redis, optional voiceprint API."""
import asyncio
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logger = logging.getLogger(__name__)

# Result: (passed: bool, message: str)
CheckResult = tuple[bool, str]
ChecksDict = dict[str, CheckResult]


def check_config() -> CheckResult:
    """Load settings and read app_name / database_url."""
    try:
        from app.settings import get_settings
        s = get_settings()
        _ = s.app_name
        _ = s.database_url
        _ = s.redis_url
        return True, "ok"
    except Exception as e:
        return False, str(e)


def check_packages() -> CheckResult:
    """Import critical modules: uvicorn, sqlalchemy, redis, app.main."""
    missing = []
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        missing.append("uvicorn")
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        missing.append("sqlalchemy")
    try:
        import redis  # noqa: F401
    except ImportError:
        missing.append("redis")
    try:
        import app.main  # noqa: F401
    except ImportError as e:
        missing.append(f"app.main ({e})")
    if missing:
        return False, f"missing: {', '.join(missing)}"
    return True, "ok"


async def _check_database_async(database_url: str) -> CheckResult:
    """Run a trivial query against the database."""
    try:
        engine = create_async_engine(database_url, pool_pre_ping=True)
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def check_database() -> CheckResult:
    """Check database connectivity using settings.database_url."""
    try:
        from app.settings import get_settings
        url = get_settings().database_url
        return asyncio.run(_check_database_async(url))
    except Exception as e:
        return False, str(e)


def check_redis() -> CheckResult:
    """Check Redis connectivity using settings.redis_url."""
    try:
        from app.settings import get_settings
        import redis as redis_lib
        url = get_settings().redis_url
        client = redis_lib.from_url(url)
        client.ping()
        client.close()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def check_nemo() -> CheckResult:
    """Optional: NeMo diarization fallback. Pass if import + availability check succeed."""
    try:
        from app.domain.stt.nemo_sortformer_diarizer import nemo_diarization_available
        ok, err = nemo_diarization_available()
        if ok:
            return True, "ok"
        return False, err or "not available"
    except Exception as e:
        return False, str(e)


def check_voiceprint() -> CheckResult:
    """If voiceprint_api_url is set, GET health; else skip."""
    try:
        from app.settings import get_settings
        url = (get_settings().voiceprint_api_url or "").strip().rstrip("/")
        if not url:
            return True, "skipped (not configured)"
        try:
            import httpx
            r = httpx.get(f"{url}/voiceprint/health", timeout=5.0)
            if r.status_code == 200:
                return True, "ok"
            return False, f"status {r.status_code}"
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, str(e)


def run_all_checks() -> ChecksDict:
    """Run all readiness checks (sync). Returns dict of check_name -> (passed, message)."""
    return {
        "config": check_config(),
        "packages": check_packages(),
        "database": check_database(),
        "redis": check_redis(),
        "nemo": check_nemo(),
        "voiceprint": check_voiceprint(),
    }


async def run_all_checks_async() -> ChecksDict:
    """Run all readiness checks (async). Use from async context (e.g. GET /ready) to avoid nested event loop."""
    from app.settings import get_settings
    db_url = get_settings().database_url
    db_result = await _check_database_async(db_url)
    return {
        "config": check_config(),
        "packages": check_packages(),
        "database": db_result,
        "redis": check_redis(),
        "nemo": check_nemo(),
        "voiceprint": check_voiceprint(),
    }


def is_ready(checks: ChecksDict | None = None) -> tuple[bool, dict[str, str]]:
    """
    True if all required checks pass. Optional checks (e.g. voiceprint) can be skipped.
    Returns (ready: bool, checks_summary: dict of name -> "ok" | "skipped" | error message).
    """
    if checks is None:
        checks = run_all_checks()
    required = {"config", "packages", "database"}
    summary: dict[str, str] = {}
    for name, (passed, msg) in checks.items():
        if passed:
            summary[name] = "ok" if msg == "ok" else msg  # e.g. "skipped (not configured)"
        else:
            summary[name] = msg
    all_required = all(checks[n][0] for n in required if n in checks)
    return all_required, summary
