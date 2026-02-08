"""Pytest configuration for tests directory."""
import asyncio
import inspect
import pytest

# Load pytest-asyncio when available so async fixtures and tests work (e.g. test_market.py).
try:
    import pytest_asyncio  # noqa: F401
    pytest_plugins = ("pytest_asyncio",)
    _has_pytest_asyncio = True
except ImportError:
    pytest_plugins = ()
    _has_pytest_asyncio = False


def pytest_configure(config):
    """Register markers and ensure asyncio_mode=auto when pytest-asyncio is present."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (requires pytest-asyncio)"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests that need a real DB (deselect with '-m \"not integration\"')"
    )
    # Force asyncio_mode=auto so async tests/fixtures run without @pytest.mark.asyncio on each
    if _has_pytest_asyncio:
        config.option.asyncio_mode = getattr(
            config.option, "asyncio_mode", None
        ) or "auto"


def pytest_collection_modifyitems(config, items):
    """Skip tests that need async fixtures when pytest-asyncio is not installed."""
    if _has_pytest_asyncio:
        return
    skip = pytest.mark.skip(reason="pytest-asyncio not installed; install with: pip install pytest-asyncio")
    # Skip tests from modules that use async fixtures (activity_api, market)
    for item in items:
        nodeid = getattr(item, "nodeid", "") or ""
        if "test_activity_api" in nodeid or "test_market" in nodeid:
            item.add_marker(skip)
            continue
        if not hasattr(item, "fixturenames"):
            continue
        for name in item.fixturenames:
            try:
                defs = item.session._fixturemanager.getfixturedefs(name, item.nodeid)
                if defs and any(inspect.iscoroutinefunction(d.func) for d in defs):
                    item.add_marker(skip)
                    break
            except Exception:
                pass


def pytest_pyfunc_call(pyfuncitem):
    """When pytest-asyncio is not installed, run async test functions with asyncio.run()."""
    if _has_pytest_asyncio:
        return None  # let pytest-asyncio handle it
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None  # sync test, run normally
    # Async test without plugin: run it with asyncio.run()
    asyncio.run(pyfuncitem.obj(**pyfuncitem.funcargs))
    return True  # we handled it
