from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from typing import Any


class EventHub:
    """In-process pub/sub for SSE board updates."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[str]] = []
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=32)
        with self._lock:
            self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    def publish(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event, default=str)
        with self._lock:
            subscribers = list(self._subscribers)
        loop = self._loop
        for queue in subscribers:
            if loop and loop.is_running():
                loop.call_soon_threadsafe(self._put_nowait, queue, payload)
            else:
                self._put_nowait(queue, payload)

    @staticmethod
    def _put_nowait(queue: asyncio.Queue[str], payload: str) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    async def stream(self) -> AsyncIterator[dict[str, str]]:
        queue = self.subscribe()
        try:
            yield {"event": "connected", "data": json.dumps({"ok": True})}
            while True:
                payload = await queue.get()
                event = "board"
                try:
                    parsed = json.loads(payload)
                    if isinstance(parsed, dict) and parsed.get("type"):
                        event = str(parsed["type"])
                except json.JSONDecodeError:
                    pass
                yield {"event": event, "data": payload}
        finally:
            self.unsubscribe(queue)


hub = EventHub()
