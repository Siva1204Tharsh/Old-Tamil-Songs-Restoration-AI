#!/usr/bin/env bash
# Start the FastAPI backend server
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
    echo "   Run: python3 -m venv venv && source venv/bin/activate"
    echo "   Then: pip install -r backend/requirements.txt"
    exit 1
fi

# Ensure storage directories exist
mkdir -p "$ROOT_DIR/storage/uploads" \
         "$ROOT_DIR/storage/processed" \
         "$ROOT_DIR/storage/temporary" \
         "$ROOT_DIR/logs"

cd "$ROOT_DIR/backend"

echo "🚀 Starting FastAPI at http://127.0.0.1:8000"
echo "📚 API docs: http://127.0.0.1:8000/docs"
echo ""

exec uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --reload \
    --log-level info
