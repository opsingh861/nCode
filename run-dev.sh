#!/usr/bin/env bash
# run-dev.sh
# Start backend and frontend in watch development mode from project root.
# Usage:
#   ./run-dev.sh

set -euo pipefail
IFS=$'\n\t'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Backend venv activation path (adjust if you use globally installed Python environment).
BACKEND_PYTHON="$ROOT_DIR/backend/.venv/Scripts/python.exe"

if [[ ! -x "$BACKEND_PYTHON" ]]; then
  echo "[error] Python executable not found at $BACKEND_PYTHON"
  echo "Install dependencies in backend/.venv or update RUN_DEV_BACKEND_PYTHON." 
  exit 1
fi

# Ensure backend virtual env has pip and required packages
ensure_backend_dependencies() {
  echo "[backend] Verifying Python dependencies..."

  if ! "$BACKEND_PYTHON" -c "import pkgutil, sys; sys.exit(0 if pkgutil.find_loader('click') else 1)" 2>/dev/null; then
    echo "[backend] click not installed, bootstrapping dependencies."

    if ! "$BACKEND_PYTHON" -m pip --version >/dev/null 2>&1; then
      echo "[backend] pip not found, attempting ensurepip..."
      "$BACKEND_PYTHON" -m ensurepip --upgrade
      "$BACKEND_PYTHON" -m pip install --upgrade pip
    fi

    if [[ -f "$ROOT_DIR/backend/requirements.txt" ]]; then
      "$BACKEND_PYTHON" -m pip install -r "$ROOT_DIR/backend/requirements.txt"
    elif [[ -f "$ROOT_DIR/requirements.txt" ]]; then
      # If the backend-specific requirements file isn't present, fall back to
      # the project's top-level requirements.txt which contains FastAPI and
      # other runtime dependencies used by the backend.
      "$BACKEND_PYTHON" -m pip install -r "$ROOT_DIR/requirements.txt"
    else
      # Minimal fallback: ensure at least the webserver and click are present.
      "$BACKEND_PYTHON" -m pip install uvicorn click fastapi
    fi
  fi

  echo "[backend] dependency check complete."
}

# Optionally set environment variables
export HOST="0.0.0.0"
export PORT="8000"
export MAX_UPLOAD_SIZE_MB="20"

ensure_backend_dependencies

echo "Starting backend and frontend in watch mode..."

echo "[backend] Starting uvicorn on http://0.0.0.0:8000"
"$BACKEND_PYTHON" -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "[frontend] Starting npm dev server (port 3000)"
cd "$ROOT_DIR/frontend"
# npm may be in PATH for npx users; if not, use corepack or update accordingly.
if command -v npm >/dev/null 2>&1; then
  npm run dev &
else
  echo "[warn] npm not found in PATH; try using yarn or install Node.js"
  exit 1
fi
FRONTEND_PID=$!

cleanup() {
  echo "\nStopping frontend and backend..."
  kill "$FRONTEND_PID" "$BACKEND_PID" 2>/dev/null || true
  wait "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" 2>/dev/null || true
  echo "Done."
}

trap cleanup EXIT INT TERM

# Wait for both processes to end (usually Ctrl-C will end it)
wait -n "$FRONTEND_PID" "$BACKEND_PID"
EXIT_CODE=$?
cleanup
exit $EXIT_CODE
