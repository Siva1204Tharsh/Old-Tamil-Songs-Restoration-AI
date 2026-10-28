#!/usr/bin/env bash
# Start the Streamlit frontend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
# Find virtual environment
if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
    VENV="$ROOT_DIR/venv"
elif [ -f "$(dirname "$ROOT_DIR")/venv/bin/activate" ]; then
    VENV="$(dirname "$ROOT_DIR")/venv"
fi

# Activate virtual environment
if [ -n "$VENV" ] && [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
    echo "✅ Virtual environment activated: $VENV"
else
    echo "❌ Virtual environment not found at $ROOT_DIR/venv or $(dirname "$ROOT_DIR")/venv"
    exit 1
fi

cd "$ROOT_DIR/frontend"

echo "🚀 Starting Streamlit at http://127.0.0.1:8501"
echo ""
echo "Make sure the backend is running first:"
echo "  ./scripts/start_backend.sh"
echo ""

exec streamlit run app.py \
    --server.address 127.0.0.1 \
    --server.port 8501 \
    --server.headless true \
    --browser.gatherUsageStats false \
    --theme.base dark \
    --theme.primaryColor "#6C63FF" \
    --theme.backgroundColor "#0E0E1A" \
    --theme.secondaryBackgroundColor "#1A1A2E" \
    --theme.textColor "#E0E0E0"
