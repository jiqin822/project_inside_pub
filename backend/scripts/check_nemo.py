#!/usr/bin/env python3
"""Check NeMo diarization dependencies. Exit 0 if available, 1 otherwise."""
import sys
from pathlib import Path

# Ensure backend app is on path when run as script
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))


def main() -> int:
    try:
        from app.domain.stt.nemo_sortformer_diarizer import nemo_diarization_available
    except ImportError as e:
        print(f"nemo: FAIL  could not import diarizer: {e}")
        return 1

    ok, err = nemo_diarization_available()
    if ok:
        print("nemo: OK  NeMo diarization available")
        return 0
    print(f"nemo: FAIL  {err}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
