from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .types import DiscoveredActivity, utcnow

HOME = Path.home()
CODEX_ROOT = HOME / ".codex"
INDEX_PATH = CODEX_ROOT / "session_index.jsonl"
SESSIONS_DIR = CODEX_ROOT / "sessions"


def _parse_iso(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _cwd_lookup(limit_files: int = 80) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not SESSIONS_DIR.exists():
        return mapping
    files = sorted(
        SESSIONS_DIR.rglob("rollout-*.jsonl"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:limit_files]
    for path in files:
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                first = handle.readline()
            meta = json.loads(first)
        except (OSError, json.JSONDecodeError):
            continue
        payload = meta.get("payload") if isinstance(meta.get("payload"), dict) else meta
        session_id = str(payload.get("session_id") or payload.get("id") or "")
        cwd = str(payload.get("cwd") or "")
        if session_id and cwd and session_id not in mapping:
            mapping[session_id] = cwd
    return mapping


def discover_codex(limit: int = 40) -> list[DiscoveredActivity]:
    if not INDEX_PATH.exists():
        return []

    try:
        lines = INDEX_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-400:]
    except OSError:
        return []

    latest: dict[str, dict] = {}
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        session_id = str(row.get("id") or "")
        if not session_id:
            continue
        prev = latest.get(session_id)
        if prev is None:
            latest[session_id] = row
            continue
        prev_ts = _parse_iso(prev.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        row_ts = _parse_iso(row.get("updated_at")) or datetime.min.replace(tzinfo=timezone.utc)
        if row_ts >= prev_ts:
            latest[session_id] = row

    cwds = _cwd_lookup()
    items: list[DiscoveredActivity] = []
    for session_id, row in latest.items():
        updated = _parse_iso(row.get("updated_at")) or utcnow()
        age_s = (utcnow() - updated).total_seconds()
        if age_s < 20 * 60:
            hint, live = "in_progress", True
        elif age_s < 36 * 3600:
            hint, live = "todo", False
        else:
            hint, live = "done", False
        title = str(row.get("thread_name") or f"Codex session {session_id[:8]}").strip()
        items.append(
            DiscoveredActivity(
                external_key=f"codex:session:{session_id}",
                agent="codex",
                title=title[:200],
                description="ChatGPT Codex thread from ~/.codex/session_index.jsonl",
                project_path=cwds.get(session_id, ""),
                column_hint=hint,  # type: ignore[arg-type]
                updated_at=updated,
                live=live,
                meta={"kind": "session"},
            )
        )

    items.sort(key=lambda item: item.updated_at, reverse=True)
    return items[:limit]
