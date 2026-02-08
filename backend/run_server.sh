#!/bin/bash
# Run backend server using system Python (which has all dependencies installed)

cd "$(dirname "$0")"

# Find system Python (not conda) which has all dependencies
# Try common locations
if [ -f "/usr/bin/python3" ]; then
    PYTHON="/usr/bin/python3"
elif [ -f "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3" ]; then
    PYTHON="/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
else
    # Fallback: use python3 from PATH but ensure it's not conda
    PYTHON=$(which -a python3 | grep -v conda | head -1)
    if [ -z "$PYTHON" ]; then
        PYTHON="python3"
    fi
fi

echo "Using Python: $PYTHON"
echo "Starting backend server on http://0.0.0.0:8000"
echo "Press Ctrl+C to stop"
echo ""

$PYTHON -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
