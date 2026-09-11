from __future__ import annotations

from .claude import discover_claude
from .codex import discover_codex
from .cursor import discover_cursor
from .grok import discover_grok
from .grok_bot import discover_grok_bot
from .types import DiscoveredActivity


def discover_all(limit_per_agent: int = 40) -> list[DiscoveredActivity]:
    discovered: list[DiscoveredActivity] = []
    discovered.extend(discover_claude(limit_per_agent))
    discovered.extend(discover_codex(limit_per_agent))
    discovered.extend(discover_cursor(limit_per_agent))
    discovered.extend(discover_grok(limit_per_agent))
    discovered.extend(discover_grok_bot(min(20, limit_per_agent)))
    discovered.sort(key=lambda item: item.updated_at, reverse=True)
    return discovered
