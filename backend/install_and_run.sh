#!/bin/bash
# Install dependencies and start the backend server

cd "$(dirname "$0")"

echo "=== Installing Backend Dependencies ==="
echo ""

# Check if we're in a conda environment
if [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo "Detected conda environment: $CONDA_DEFAULT_ENV"
    echo "Using: $(which python)"
    echo ""
fi

# Install dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Failed to install dependencies"
    echo "Make sure you have internet connection and pip is working"
    exit 1
fi

echo ""
echo "=== Dependencies Installed Successfully ==="
echo ""
echo "Starting backend server..."
echo "Server will be available at: http://0.0.0.0:8000"
echo "Press Ctrl+C to stop"
echo ""

# Start the server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
