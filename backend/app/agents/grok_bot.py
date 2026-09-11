from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .types import DiscoveredActivity, utcnow

HOME = Path.home()
GROKBOT_ROOT = HOME / ".grokbot"
APP_SUPPORT = HOME / "Library" / "Application Support" / "Grok Bot"
DESKTOP_STATUS = APP_SUPPORT / "desktop-status.json"
DAEMON_STATUS = GROKBOT_ROOT / "local-exec-daemon.json"
DAEMON_LOG = GROKBOT_ROOT / "local-exec-daemon.log"
SESSION_MARKER = APP_SUPPORT / "sand-session-marker.json"


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _tail_log(path: Path, max_lines: int = 40) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max_lines:]
    except OSError:
        return ""
    useful = [line.strip() for line in lines if line.strip()]
    return "\n".join(useful[-8:])


def discover_grok_bot(limit: int = 20) -> list[DiscoveredActivity]:
    items: list[DiscoveredActivity] = []
    now = utcnow()

    desktop = _read_json(DESKTOP_STATUS)
    daemon = _read_json(DAEMON_STATUS)
    marker = _read_json(SESSION_MARKER)

    signed_in = bool(desktop.get("signedIn"))
    app_version = str(desktop.get("appVersion") or "")
    inflight = int(daemon.get("inflightCount") or 0)
    daemon_pid = daemon.get("pid")
    alive_ms = marker.get("aliveAtMs") or desktop.get("startedAtMs")
    updated = now
    if isinstance(alive_ms, (int, float)):
        ts = float(alive_ms)
        if ts > 1e12:
            ts /= 1000.0
        updated = datetime.fromtimestamp(ts, tz=timezone.utc)

    age_s = (now - updated).total_seconds()
    running = age_s < 15 * 60 and (daemon_pid is not None or desktop.get("pid") is not None)

    if inflight > 0:
        hint, live = "in_progress", True
        title = f"Grok Bot busy ({inflight} in flight)"
        priority = "high"
    elif running and signed_in:
        hint, live = "todo", True
        title = "Grok Bot online"
        priority = "medium"
    elif running:
        hint, live = "todo", False
        title = "Grok Bot running (signed out?)"
        priority = "low"
    else:
        hint, live = "done", False
        title = "Grok Bot idle / offline"
        priority = "low"

    log_tail = _tail_log(DAEMON_LOG)
    description_parts = [
        f"Desktop v{app_version}" if app_version else "Desktop status",
        f"signed_in={signed_in}",
        f"daemon_pid={daemon_pid}",
        f"inflight={inflight}",
    ]
    if log_tail:
        description_parts.append(log_tail)

    items.append(
        DiscoveredActivity(
            external_key="grok_bot:daemon:status",
            agent="grok_bot",
            title=title,
            description="\n".join(description_parts)[:2000],
            project_path=str(GROKBOT_ROOT),
            column_hint=hint,  # type: ignore[arg-type]
            priority=priority,  # type: ignore[arg-type]
            updated_at=updated,
            live=live,
            meta={"kind": "daemon"},
        )
    )

    # Recent meaningful log lines as lightweight activity cards.
    if DAEMON_LOG.exists():
        try:
            lines = DAEMON_LOG.read_text(encoding="utf-8", errors="ignore").splitlines()[-120:]
        except OSError:
            lines = []
        interesting: list[str] = []
        seen_lines: set[str] = set()
        for line in reversed(lines):
            clean = line.strip()
            if not clean:
                continue
            lower = clean.lower()
            if not any(token in lower for token in ("error", "task", "exec", "request", "tool", "fail")):
                continue
            if clean in seen_lines:
                continue
            seen_lines.add(clean)
            interesting.append(clean)
            if len(interesting) >= min(5, max(0, limit - 1)):
                break
        mtime = datetime.fromtimestamp(DAEMON_LOG.stat().st_mtime, tz=timezone.utc)
        for index, line in enumerate(interesting):
            items.append(
                DiscoveredActivity(
                    external_key=f"grok_bot:log:{abs(hash(line)) % 10_000_000}",
                    agent="grok_bot",
                    title=line[:120],
                    description="Recent Grok Bot daemon log line",
                    project_path=str(GROKBOT_ROOT),
                    column_hint="in_progress" if index == 0 and (now - mtime).total_seconds() < 600 else "done",
                    priority="medium",
                    updated_at=mtime,
                    live=index == 0 and (now - mtime).total_seconds() < 600,
                    meta={"kind": "log"},
                )
            )

    return items[:limit]
