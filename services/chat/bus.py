"""One channel per chat session. Each subscriber has its own queue."""

from __future__ import annotations

import asyncio
import copy
import threading
import uuid
from typing import Any


class ChatBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channels: dict[str, dict[str, tuple[asyncio.Queue[dict[str, Any]], asyncio.AbstractEventLoop]]] = {}

    def subscribe(self, session_id: str) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        subscription_id = str(uuid.uuid4())
        with self._lock:
            self._channels.setdefault(session_id, {})[subscription_id] = (queue, loop)
        return subscription_id, queue

    def unsubscribe(self, session_id: str, subscription_id: str) -> None:
        with self._lock:
            channel = self._channels.get(session_id)
            if channel is None:
                return
            channel.pop(subscription_id, None)
            if not channel:
                self._channels.pop(session_id, None)

    def subscriber_count(self, session_id: str) -> int:
        with self._lock:
            return len(self._channels.get(session_id, {}))

    def publish(self, session_id: str, event: str, data: dict[str, Any]) -> int:
        """Copy the frame onto every subscriber queue for this session only."""
        frame = {"event": event, "data": copy.deepcopy(data)}
        with self._lock:
            targets = list(self._channels.get(session_id, {}).values())
        for queue, loop in targets:
            loop.call_soon_threadsafe(queue.put_nowait, copy.deepcopy(frame))
        return len(targets)

    def reset(self) -> None:
        with self._lock:
            self._channels.clear()


bus = ChatBus()
