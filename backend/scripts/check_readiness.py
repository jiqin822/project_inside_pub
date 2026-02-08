#!/usr/bin/env python3
"""Run readiness checks and report pass/fail per item and overall. Exit 0 if all required checks pass, 1 otherwise."""
import sys
from pathlib import Path

# Ensure backend app is on path when run as script
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from app.readiness import run_all_checks, is_ready


def main() -> int:
    checks = run_all_checks()
    ready, summary = is_ready(checks)
    for name, msg in summary.items():
        status = "OK" if checks[name][0] else "FAIL"
        print(f"  {name}: {status}  {msg}")
    print("")
    if ready:
        print("Readiness: READY (all required checks passed)")
        return 0
    print("Readiness: NOT READY (one or more required checks failed)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
