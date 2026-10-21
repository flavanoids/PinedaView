# SPDX-License-Identifier: Apache-2.0
"""Fan-out of change events to every connected SSE stream.

Each subscriber gets its own bounded queue. Producers publish from the event
loop with ``put_nowait`` and never block; a subscriber that falls behind simply
drops events (it will get a full fresh view model on the next one anyway).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)

_QUEUE_MAX = 64

Event = dict[str, Any]


class Broadcaster:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event: Event) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("dropping SSE event for a slow subscriber")

    @contextlib.contextmanager
    def subscription(self) -> Iterator[asyncio.Queue[Event]]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
