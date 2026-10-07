"""Authenticated SSE generator. Each connection owns one bus subscription."""

from __future__ import annotations

from collections.abc import Iterator
from queue import Empty

from events.bus import bus
from events.frames import format_frame, keepalive_frame


def iter_sse(keepalive_seconds: float) -> Iterator[str]:
    subscription = bus.subscribe()
    try:
        while True:
            try:
                item = subscription.queue.get(timeout=keepalive_seconds)
            except Empty:
                yield keepalive_frame()
                continue
            yield format_frame(str(item["id"]), str(item["event"]), item["data"])
    finally:
        bus.unsubscribe(subscription.id)
