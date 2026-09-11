from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models
from .agents import discover_all
from .agents.types import DiscoveredActivity
from .database import SessionLocal
from .events import hub

COLUMN_HINT_TO_NAME = {
    "backlog": "Backlog",
    "todo": "Todo",
    "in_progress": "In Progress",
    "blocked": "Blocked",
    "done": "Done",
}

_lock = threading.Lock()
_last_fingerprint: str | None = None
_last_sync_at: datetime | None = None
_last_counts: dict[str, int] = {}
_stop = threading.Event()
_thread: threading.Thread | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(items: list[DiscoveredActivity]) -> str:
    payload = [
        {
            "k": item.external_key,
            "t": item.title,
            "c": item.column_hint,
            "u": item.updated_at.isoformat(),
            "l": item.live,
            "p": item.project_path,
            "d": item.description[:120],
        }
        for item in items
    ]
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _column_map(db: Session) -> dict[str, models.Column]:
    columns = db.scalars(select(models.Column)).all()
    return {column.name: column for column in columns}


def _next_position(db: Session, column_id: int) -> int:
    current = db.scalar(
        select(func.max(models.Task.position)).where(models.Task.column_id == column_id)
    )
    return 0 if current is None else int(current) + 1


def _clean_text(value: str) -> str:
    cleaned = (
        value.replace("\\n", " ")
        .replace("\\r", " ")
        .replace("\\t", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
    )
    return " ".join(cleaned.split()).strip()


def apply_discovered(db: Session, items: list[DiscoveredActivity]) -> bool:
    columns = _column_map(db)
    existing = {
        task.external_key: task
        for task in db.scalars(
            select(models.Task).where(models.Task.source == "synced")
        ).all()
        if task.external_key
    }
    seen: set[str] = set()
    changed = False

    for item in items:
        seen.add(item.external_key)
        target_name = COLUMN_HINT_TO_NAME.get(item.column_hint, "Todo")
        target = columns.get(target_name) or columns.get("Todo")
        if target is None:
            continue

        title = _clean_text(item.title)[:200] or item.title[:200]
        description = _clean_text(item.description) if item.description else ""

        task = existing.get(item.external_key)
        if task is None:
            db.add(
                models.Task(
                    title=title,
                    description=description,
                    agent=item.agent,
                    priority=item.priority,
                    project_path=item.project_path or "",
                    column_id=target.id,
                    position=_next_position(db, target.id),
                    source="synced",
                    external_key=item.external_key,
                    live=bool(item.live),
                    last_seen_at=item.updated_at,
                )
            )
            changed = True
            continue

        updates = {
            "title": title,
            "description": description,
            "agent": item.agent,
            "priority": item.priority,
            "project_path": item.project_path or "",
            "live": bool(item.live),
            "last_seen_at": item.updated_at,
        }
        for key, value in updates.items():
            if getattr(task, key) != value:
                setattr(task, key, value)
                changed = True

        if task.column_id != target.id:
            task.column_id = target.id
            task.position = _next_position(db, target.id)
            changed = True

    for key, task in existing.items():
        if key not in seen:
            db.delete(task)
            changed = True

    if changed:
        db.commit()
    return changed


def sync_once(force_broadcast: bool = False) -> dict:
    global _last_fingerprint, _last_sync_at, _last_counts
    with _lock:
        items = discover_all()
        fingerprint = _fingerprint(items)
        counts: dict[str, int] = {}
        for item in items:
            counts[item.agent] = counts.get(item.agent, 0) + 1

        changed = fingerprint != _last_fingerprint
        db = SessionLocal()
        try:
            board_changed = False
            if changed or _last_fingerprint is None:
                board_changed = apply_discovered(db, items)
        finally:
            db.close()

        _last_fingerprint = fingerprint
        _last_sync_at = _utcnow()
        _last_counts = counts

        if board_changed or force_broadcast or changed:
            hub.publish(
                {
                    "type": "board",
                    "at": _last_sync_at.isoformat(),
                    "counts": counts,
                    "total": len(items),
                }
            )

        return {
            "ok": True,
            "changed": board_changed or changed,
            "counts": counts,
            "synced_at": _last_sync_at.isoformat(),
            "total": len(items),
        }


def sync_status() -> dict:
    return {
        "synced_at": _last_sync_at.isoformat() if _last_sync_at else None,
        "counts": _last_counts,
        "watching": _thread is not None and _thread.is_alive(),
    }


def _loop(interval: float) -> None:
    while not _stop.is_set():
        try:
            sync_once()
        except Exception as exc:  # noqa: BLE001
            hub.publish({"type": "error", "message": str(exc)})
        _stop.wait(interval)


def start_watcher(interval: float = 2.0) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(
        target=_loop, args=(interval,), daemon=True, name="agent-sync"
    )
    _thread.start()


def stop_watcher() -> None:
    _stop.set()
