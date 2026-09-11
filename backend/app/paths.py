from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def resource_root() -> Path:
    """Bundled read-only assets (frontend dist, etc.)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    # backend/app/paths.py → repo root
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """Writable SQLite + local prefs. Frozen apps use the OS app-data location."""
    if not is_frozen():
        path = resource_root() / "data"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Agent Task Tracker"
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        path = Path(base) / "Agent Task Tracker"
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) if xdg else Path.home() / ".local" / "share"
        path = base / "agent-task-tracker"

    path.mkdir(parents=True, exist_ok=True)
    return path


def frontend_dist() -> Path:
    return resource_root() / "frontend" / "dist"
