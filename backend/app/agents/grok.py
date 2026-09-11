from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .types import DiscoveredActivity, utcnow

HOME = Path.home()
GROK_ROOT = HOME / ".grok"
SEARCH_DB = GROK_ROOT / "sessions" / "session_search.sqlite"
ACTIVE_PATH = GROK_ROOT / "active_sessions.json"
BG_TASKS = GROK_ROOT / "long-running-background-tasks"


def discover_grok(limit: int = 40) -> list[DiscoveredActivity]:
    items: list[DiscoveredActivity] = []
    active_ids: set[str] = set()
    if ACTIVE_PATH.exists():
        try:
            payload = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                active_ids = {str(item) for item in payload}
            elif isinstance(payload, dict):
                active_ids = {str(key) for key in payload.keys()}
        except (OSError, json.JSONDecodeError):
            pass

    if SEARCH_DB.exists():
        try:
            con = sqlite3.connect(f"file:{SEARCH_DB}?mode=ro", uri=True)
            rows = con.execute(
                "SELECT session_id, cwd, updated_at, title, content "
                "FROM session_docs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            con.close()
        except sqlite3.Error:
            rows = []
        for session_id, cwd, updated_at, title, content in rows:
            if isinstance(updated_at, (int, float)):
                ts = float(updated_at)
                if ts > 1e12:
                    ts /= 1000.0
                updated = datetime.fromtimestamp(ts, tz=timezone.utc)
            else:
                updated = utcnow()
            live = str(session_id) in active_ids
            age_s = (utcnow() - updated).total_seconds()
            if live or age_s < 20 * 60:
                hint, live_flag = "in_progress", True
            elif age_s < 36 * 3600:
                hint, live_flag = "todo", False
            else:
                hint, live_flag = "done", False
            clean_title = str(title or "").strip() or f"Grok session {str(session_id)[:8]}"
            description = str(content or "").strip().splitlines()
            description = next((line for line in description if line.strip()), "")[:500]
            items.append(
                DiscoveredActivity(
                    external_key=f"grok:session:{session_id}",
                    agent="grok",
                    title=clean_title[:200],
                    description=description,
                    project_path=str(cwd or ""),
                    column_hint=hint,  # type: ignore[arg-type]
                    updated_at=updated,
                    live=live_flag,
                    meta={"kind": "session"},
                )
            )

    if BG_TASKS.exists():
        for path in BG_TASKS.iterdir():
            if not path.is_file():
                continue
            updated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            age_s = (utcnow() - updated).total_seconds()
            live = age_s < 30 * 60
            items.append(
                DiscoveredActivity(
                    external_key=f"grok:bg:{path.name}",
                    agent="grok",
                    title=f"Background: {path.stem}",
                    description=(path.read_text(encoding="utf-8", errors="ignore")[:400]
                                 if path.stat().st_size < 200_000 else "Long-running Grok background task"),
                    project_path="",
                    column_hint="in_progress" if live else "done",
                    priority="high" if live else "low",
                    updated_at=updated,
                    live=live,
                    meta={"kind": "background"},
                )
            )

    items.sort(key=lambda item: item.updated_at, reverse=True)
    return items[:limit]
