#!/bin/bash
# Quick fix for distutils error

echo "🔧 Fixing distutils error..."
echo ""

cd "$(dirname "$0")"

# Try to install setuptools with user flag (works even if conda env is not writable)
echo "Installing setuptools (provides distutils)..."
python -m pip install --user setuptools 2>&1 | grep -v "WARNING\|Retrying" || echo "Note: Installation may have warnings, but should still work"

echo ""
echo "✅ Done! Now try starting the server:"
echo "   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
