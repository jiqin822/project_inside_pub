#!/bin/bash
# Install dependencies with trusted hosts to bypass SSL issues

cd "$(dirname "$0")"

echo "Installing backend dependencies..."
echo "Using trusted hosts to bypass SSL certificate issues"
echo ""

pip install --trusted-host pypi.org \
            --trusted-host pypi.python.org \
            --trusted-host files.pythonhosted.org \
            -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Dependencies installed successfully!"
    echo ""
    echo "Now start the server with:"
    echo "  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
else
    echo ""
    echo "✗ Installation failed. Try using conda instead:"
    echo "  conda install -c conda-forge fastapi uvicorn sqlalchemy asyncpg redis-py"
fi
