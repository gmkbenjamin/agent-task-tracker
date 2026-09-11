#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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
pip install -q "pyinstaller>=6.3,<7"

if [[ ! -d frontend/node_modules ]]; then
  echo "Installing frontend dependencies…"
  (cd frontend && npm install)
fi

echo "Building frontend…"
(cd frontend && npm run build)

echo "Packaging native app with PyInstaller…"
pyinstaller --noconfirm --clean desktop/agent_task_tracker.spec

echo
echo "Done."
case "$(uname -s)" in
  Darwin)
    echo "  macOS app:  $ROOT/dist/Agent Task Tracker.app"
    echo "  Double-click to launch. First open may need:"
    echo "    Right-click → Open  (unsigned local build / Gatekeeper)"
    ;;
  MINGW*|MSYS*|CYGWIN*|Windows_NT)
    echo "  Windows exe: $ROOT/dist/Agent Task Tracker/Agent Task Tracker.exe"
    ;;
  *)
    echo "  Linux binary: $ROOT/dist/Agent Task Tracker/Agent Task Tracker"
    ;;
esac
