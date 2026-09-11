#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer 3.11/3.12/3.13 — system python3 may be 3.14 without wheels yet.
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:${PATH}"
if [[ -z "${PYTHON:-}" ]]; then
  for candidate in python3.11 python3.12 python3.13 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON="$candidate"
      break
    fi
  done
fi
PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating virtualenv with $PYTHON…"
  "$PYTHON" -m venv "$VENV"
fi

# shellcheck disable=SC1091
source "$VENV/bin/activate"

pip install -q -r backend/requirements.txt

if [[ ! -d frontend/node_modules ]]; then
  echo "Installing frontend dependencies…"
  (cd frontend && npm install)
fi

if [[ ! -f frontend/dist/index.html ]]; then
  echo "Building frontend…"
  (cd frontend && npm run build)
fi

MODE="${1:-desktop}"

case "$MODE" in
  desktop)
    python desktop/launcher.py
    ;;
  browser)
    python desktop/launcher.py --browser
    ;;
  api)
    cd backend
    uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
    ;;
  dev)
    echo "Start API in one terminal: ./scripts/start.sh api"
    echo "Start UI in another:       cd frontend && npm run dev"
    ;;
  *)
    echo "Usage: ./scripts/start.sh [desktop|browser|api|dev]"
    exit 1
    ;;
esac
