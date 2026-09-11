# Agent Task Tracker

Localhost kanban board for tracking work across **Claude Code**, **ChatGPT Codex**, **Cursor**, **Grok**, and **Grok Bot**.

## Stack

- **Backend:** FastAPI + SQLite (`data/tasks.db`)
- **Frontend:** React + Vite + TypeScript with drag-and-drop columns
- **Desktop shell:** pywebview native window on macOS / Windows / Linux (browser fallback available)

## Requirements

- Python **3.11–3.13** (3.14 may lack wheels for some deps)
- Node.js 20+
- macOS / Windows / Linux

## Quick start (dev)

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

This creates a virtualenv, installs dependencies, builds the UI, and opens a native desktop window at `http://127.0.0.1:8787`.

## Native app (double-click)

Build a standalone app with PyInstaller (must run on each target OS — no cross-compile):

```bash
chmod +x scripts/build-app.sh
./scripts/build-app.sh
```

| OS | Output |
|----|--------|
| macOS | `dist/Agent Task Tracker.app` |
| Windows | `dist/Agent Task Tracker/Agent Task Tracker.exe` |
| Linux | `dist/Agent Task Tracker/Agent Task Tracker` |

The packaged app stores its SQLite DB in the OS app-data folder (not inside the `.app` / install dir):
- macOS: `~/Library/Application Support/Agent Task Tracker/`
- Windows: `%APPDATA%\\Agent Task Tracker\\`
- Linux: `~/.local/share/agent-task-tracker/`

**macOS Gatekeeper:** unsigned local builds may need Right-click → Open the first time.

### Other modes

```bash
./scripts/start.sh browser   # system browser instead of native window
./scripts/start.sh api       # API + built UI only (reload)
./scripts/start.sh dev       # prints how to run API + Vite separately
```

### Development (hot reload UI)

Terminal 1:

```bash
./scripts/start.sh api
```

Terminal 2:

```bash
cd frontend && npm install && npm run dev
```

Open `http://127.0.0.1:5173` — Vite proxies `/api` to the backend.

## Features

- Pulls **real local agent activity** from:
  - Claude Code (`~/.claude/tasks`, `history.jsonl`)
  - ChatGPT Codex (`~/.codex/session_index.jsonl`, session rollouts)
  - Cursor (`~/.cursor/projects/*/agent-transcripts`)
  - Grok (`~/.grok/sessions/session_search.sqlite`)
  - Grok Bot (`~/.grokbot` + desktop status)
- Background watcher every ~2s + SSE (`/api/events`) for live board updates
- Columns auto-map from activity status / recency
- Read-only board (agent dirs are never written)
- Filter by agent / project; hide projects locally (tracker DB only) and restore later
- Collapse columns to the latest 10 tasks

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Health check |
| GET | `/api/sync/status` | Last sync + per-agent counts |
| POST | `/api/sync/now` | Force rescan now |
| GET | `/api/events` | SSE live board updates |
| GET | `/api/board` | Full board with columns + tasks (+ hidden project list) |
| GET | `/api/projects/hidden` | List locally hidden projects |
| POST | `/api/projects/hide` | Hide a project from the board (local only) |
| POST | `/api/projects/unhide` | Restore a hidden project |

Interactive docs: `http://127.0.0.1:8787/docs`
