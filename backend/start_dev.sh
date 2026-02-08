#!/bin/bash
# Start the backend server. Prefers Poetry env when available.

cd "$(dirname "$0")"

# Prefer Poetry so deps (including SpeechBrain for speaker IDs) are available
if command -v poetry >/dev/null 2>&1 && [ -f pyproject.toml ]; then
    echo "Starting backend server (Poetry env)..."
    # NeMo check uses same env as server; warn if missing so user knows why server logs fallback disabled
    if ! poetry run python scripts/check_nemo.py 2>/dev/null; then
        echo "  (NeMo not in Poetry env; server will log NeMo fallback disabled. To enable: poetry run pip install -r requirements-nemo.txt  or set STT_ENABLE_NEMO_DIARIZATION_FALLBACK=false)"
        echo ""
    fi
    exec poetry run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fi

echo "Starting backend server..."
echo "Make sure dependencies are installed: pip install -r requirements.txt"
echo ""

# Without Poetry, prefer .venv in backend so same env as 'python scripts/check_nemo.py'
if [ -d .venv ] && [ -f .venv/bin/activate ]; then
    # shellcheck source=/dev/null
    source .venv/bin/activate
fi

# Check if uvicorn is installed
if ! python3 -c "import uvicorn" 2>/dev/null; then
    echo "ERROR: uvicorn is not installed!"
    echo "Please run: pip install -r requirements.txt"
    exit 1
fi

# Warn if SpeechBrain (speaker encoder) is missing - speaker IDs will show 0%
if ! python3 -c "from speechbrain.inference.classifiers import EncoderClassifier" 2>/dev/null; then
    echo "WARNING: SpeechBrain not found in this Python env. Speaker IDs will be 0%."
    echo "  For speaker IDs, install: pip install speechbrain"
    echo ""
fi

# NeMo check uses same python as server; warn if missing
if ! python3 scripts/check_nemo.py 2>/dev/null; then
    echo "  (NeMo not in this env; server will log NeMo fallback disabled. Activate the venv where you ran pip install -r requirements-nemo.txt, or set STT_ENABLE_NEMO_DIARIZATION_FALLBACK=false)"
    echo ""
fi

# Start the server
exec python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
