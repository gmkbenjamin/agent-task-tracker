from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from .types import DiscoveredActivity, utcnow

HOME = Path.home()
PROJECTS_DIR = HOME / ".cursor" / "projects"
QUERY_RE = re.compile(r"<user_query>\s*(.*?)\s*</user_query>", re.DOTALL | re.IGNORECASE)


def _project_path_from_slug(slug: str) -> str:
    # Users-user-Documents-KES -> /Users/user/Documents/KES (best effort)
    if slug.startswith("Users-"):
        return "/" + slug.replace("-", "/")
    return unquote(slug.replace("%2F", "/"))


def _clean_title(text: str) -> str:
    # Collapse real whitespace and literal "\n" / "\t" leftovers from JSONL.
    cleaned = (
        text.replace("\\n", " ")
        .replace("\\r", " ")
        .replace("\\t", " ")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
    )
    return " ".join(cleaned.split()).strip()


def _extract_text_parts(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                chunks.append(str(part.get("text") or ""))
            elif isinstance(part, str):
                chunks.append(part)
        return "\n".join(chunks)
    return ""


def _first_user_query(path: Path) -> str:
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for _ in range(40):
                line = handle.readline()
                if not line:
                    break
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("role") != "user":
                    continue
                message = row.get("message") or {}
                text = _extract_text_parts(message.get("content"))
                if not text:
                    continue
                match = QUERY_RE.search(text)
                raw = match.group(1) if match else text
                cleaned = _clean_title(raw)
                if cleaned:
                    return cleaned[:200]
    except OSError:
        return ""
    return ""


def discover_cursor(limit: int = 40) -> list[DiscoveredActivity]:
    if not PROJECTS_DIR.exists():
        return []

    transcripts: list[Path] = []
    for path in PROJECTS_DIR.glob("*/agent-transcripts/*/*.jsonl"):
        if "subagents" in path.parts:
            continue
        transcripts.append(path)

    transcripts.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    items: list[DiscoveredActivity] = []
    for path in transcripts[: limit * 2]:
        conversation_id = path.stem
        project_slug = path.parts[-4] if len(path.parts) >= 4 else ""
        project_path = _project_path_from_slug(project_slug)
        title = _first_user_query(path) or f"Cursor agent {conversation_id[:8]}"
        updated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age_s = (utcnow() - updated).total_seconds()
        if age_s < 20 * 60:
            hint, live = "in_progress", True
        elif age_s < 36 * 3600:
            hint, live = "todo", False
        else:
            hint, live = "done", False
        items.append(
            DiscoveredActivity(
                external_key=f"cursor:transcript:{conversation_id}",
                agent="cursor",
                title=title[:200],
                description=f"Cursor agent transcript ({conversation_id[:8]})",
                project_path=project_path,
                column_hint=hint,  # type: ignore[arg-type]
                updated_at=updated,
                live=live,
                meta={"kind": "transcript", "project": project_slug},
            )
        )
        if len(items) >= limit:
            break
    return items
