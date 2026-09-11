from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .types import DiscoveredActivity, utcnow

HOME = Path.home()
CLAUDE_ROOT = HOME / ".claude"
TASKS_DIR = CLAUDE_ROOT / "tasks"
HISTORY_PATH = CLAUDE_ROOT / "history.jsonl"

STATUS_MAP = {
    "pending": "todo",
    "todo": "todo",
    "open": "todo",
    "in_progress": "in_progress",
    "in-progress": "in_progress",
    "active": "in_progress",
    "running": "in_progress",
    "blocked": "blocked",
    "completed": "done",
    "complete": "done",
    "done": "done",
    "cancelled": "done",
    "canceled": "done",
}


def _parse_ts(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def discover_claude(limit: int = 40) -> list[DiscoveredActivity]:
    items: list[DiscoveredActivity] = []

    if TASKS_DIR.exists():
        for path in TASKS_DIR.rglob("*.json"):
            if path.name.startswith("."):
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            task_id = str(data.get("id") or path.stem)
            session = path.parent.name
            status = str(data.get("status") or "todo").lower()
            hint = STATUS_MAP.get(status, "todo")
            subject = str(data.get("subject") or data.get("activeForm") or f"Claude task {task_id}")
            description = str(data.get("description") or "")
            updated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            items.append(
                DiscoveredActivity(
                    external_key=f"claude_code:task:{session}:{task_id}",
                    agent="claude_code",
                    title=subject.strip()[:200] or f"Claude task {task_id}",
                    description=description.strip()[:2000],
                    project_path="",
                    column_hint=hint,  # type: ignore[arg-type]
                    priority="high" if hint == "blocked" else "medium",
                    updated_at=updated,
                    live=hint == "in_progress",
                    meta={"kind": "task", "status": status, "session": session},
                )
            )

    # Recent history prompts as sessions (skip slash commands).
    if HISTORY_PATH.exists():
        try:
            lines = HISTORY_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-300:]
        except OSError:
            lines = []
        latest: dict[str, dict] = {}
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            session_id = str(row.get("sessionId") or "")
            display = str(row.get("display") or "").strip()
            if not session_id or not display or display.startswith("/"):
                continue
            latest[session_id] = row
        for session_id, row in list(latest.items())[-limit:]:
            updated = _parse_ts(row.get("timestamp")) or utcnow()
            age_s = (utcnow() - updated).total_seconds()
            if age_s < 20 * 60:
                hint = "in_progress"
                live = True
            elif age_s < 36 * 3600:
                hint = "todo"
                live = False
            else:
                hint = "done"
                live = False
            key = f"claude_code:session:{session_id}"
            if any(item.external_key.startswith(f"claude_code:task:{session_id}:") for item in items):
                continue
            items.append(
                DiscoveredActivity(
                    external_key=key,
                    agent="claude_code",
                    title=str(row.get("display") or "Claude session")[:200],
                    description="Claude Code session from local history",
                    project_path=str(row.get("project") or ""),
                    column_hint=hint,  # type: ignore[arg-type]
                    updated_at=updated,
                    live=live,
                    meta={"kind": "session"},
                )
            )

    items.sort(key=lambda item: item.updated_at, reverse=True)
    return items[:limit]
