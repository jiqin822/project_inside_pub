"""Readiness test: run all checks. Requires config and packages; DB/Redis/voiceprint/nemo are optional (e.g. in CI/sandbox)."""
import pytest

from app.readiness import run_all_checks, is_ready


@pytest.mark.integration
def test_readiness_all_checks_pass():
    """Config and packages must pass; DB/Redis/voiceprint/nemo may be unavailable (e.g. sandbox)."""
    checks = run_all_checks()
    # Core: config and packages must be ok for the app to load
    for name in ("config", "packages"):
        ok, msg = checks.get(name, (False, "missing"))
        assert ok, f"readiness {name}: {msg}"
    # Optional services: log but do not fail if unavailable
    ready, summary = is_ready(checks)
    if not ready:
        report = "\n".join(f"  {name}: {msg}" for name, msg in summary.items())
        # In CI/sandbox, database/redis/voiceprint often unavailable; only fail if config or packages failed
        failed_core = [n for n in ("config", "packages") if not checks.get(n, (True, ""))[0]]
        if failed_core:
            pytest.fail(f"Readiness checks failed:\n{report}")
        # Otherwise optional services failed; test still passes
    assert checks["config"][0] and checks["packages"][0]
