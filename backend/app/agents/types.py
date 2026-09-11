from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

AgentId = Literal["claude_code", "codex", "cursor", "grok", "grok_bot"]
ColumnHint = Literal["backlog", "todo", "in_progress", "blocked", "done"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class DiscoveredActivity:
    """Normalized activity discovered from a local agent directory."""

    external_key: str
    agent: AgentId
    title: str
    description: str = ""
    project_path: str = ""
    column_hint: ColumnHint = "todo"
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    updated_at: datetime = field(default_factory=utcnow)
    live: bool = False
    meta: dict[str, str] = field(default_factory=dict)
