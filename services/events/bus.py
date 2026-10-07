"""One queue per subscriber. Publishing copies the event to every queue."""

from __future__ import annotations

import copy
import threading
import uuid
from queue import Queue
from typing import Any


class Subscription:
    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.queue: Queue[dict[str, Any]] = Queue()


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[str, Subscription] = {}
        self._published: set[str] = set()

    def subscribe(self) -> Subscription:
        subscription = Subscription()
        with self._lock:
            self._subscribers[subscription.id] = subscription
        return subscription

    def unsubscribe(self, subscription_id: str) -> None:
        with self._lock:
            self._subscribers.pop(subscription_id, None)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(self, event: str, data: dict[str, Any], event_id: str) -> int:
        """Fan out a copy. Removing a frame from one queue leaves the others intact."""
        frame = {"id": event_id, "event": event, "data": copy.deepcopy(data)}
        with self._lock:
            targets = list(self._subscribers.values())
        for subscription in targets:
            subscription.queue.put(copy.deepcopy(frame))
        return len(targets)

    def publish_once(self, key: str, event: str, data: dict[str, Any]) -> bool:
        """Publish at most one frame for a ticket. Later intake steps do not repeat it."""
        frame = {"id": key, "event": event, "data": copy.deepcopy(data)}
        with self._lock:
            if key in self._published:
                return False
            self._published.add(key)
            targets = list(self._subscribers.values())
        for subscription in targets:
            subscription.queue.put(copy.deepcopy(frame))
        return True

    def reset(self) -> None:
        with self._lock:
            self._subscribers.clear()
            self._published.clear()


bus = EventBus()
