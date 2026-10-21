# SPDX-License-Identifier: Apache-2.0
"""In-memory countdown timers set from the remote. They survive as long as the
server does — persistence isn't worth it for a kitchen timer.

A voice assistant (Antigua) can also mirror its own timers here with
:meth:`TimerService.sync`: it pushes its whole active list whenever it changes,
so the screen shows them without this server owning them."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from pinedaview.broadcast import Broadcaster

_TICK_SECONDS = 1.0


class Timer(BaseModel):
    id: str
    label: str
    fires_at: datetime
    source: str | None = None
    """Who owns it when mirrored from elsewhere (e.g. "antigua"); None when set here."""
    kind: Literal["timer", "alarm", "reminder"] = "timer"
    """An alarm or reminder is set for a time of day: screens show when it
    goes off rather than a countdown, and it takes over the screen when it
    does. Reminders only come from Antigua (the label is what to do)."""


class SyncedTimer(BaseModel):
    id: str
    label: str
    fires_at: datetime
    kind: Literal["timer", "alarm", "reminder"] = "timer"


class TimerService:
    def __init__(
        self, broadcaster: Broadcaster, on_fire: Callable[[Timer], None] | None = None
    ) -> None:
        self._broadcaster = broadcaster
        self._timers: dict[str, Timer] = {}
        self.on_fire = on_fire

    def list(self) -> list[Timer]:
        return sorted(self._timers.values(), key=lambda t: t.fires_at)

    def add(self, seconds: float, label: str, kind: Literal["timer", "alarm"] = "timer") -> Timer:
        timer = Timer(
            id=secrets.token_hex(6),
            label=label,
            fires_at=datetime.now(UTC) + timedelta(seconds=seconds),
            kind=kind,
        )
        self._timers[timer.id] = timer
        self._broadcaster.publish({"type": "timer", "action": "set", "id": timer.id})
        return timer

    def cancel(self, timer_id: str) -> bool:
        if self._timers.pop(timer_id, None) is None:
            return False
        self._broadcaster.publish({"type": "timer", "action": "cancel", "id": timer_id})
        return True

    def sync(self, source: str, timers: Sequence[SyncedTimer]) -> None:
        """Replace every timer mirrored from ``source`` with ``timers``."""
        kept = {k: t for k, t in self._timers.items() if t.source != source}
        now = datetime.now(UTC)
        for item in timers:
            if item.fires_at > now:
                timer_id = f"{source}:{item.id}"
                kept[timer_id] = Timer(
                    id=timer_id,
                    label=item.label,
                    fires_at=item.fires_at,
                    source=source,
                    kind=item.kind,
                )
        self._timers = kept
        self._broadcaster.publish({"type": "timer", "action": "sync", "source": source})

    def _fire_due(self, now: datetime) -> None:
        for timer in [t for t in self._timers.values() if t.fires_at <= now]:
            del self._timers[timer.id]
            self._broadcaster.publish(
                {"type": "timer", "action": "fire", "id": timer.id, "label": timer.label}
            )
            if self.on_fire is not None:
                self.on_fire(timer)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(_TICK_SECONDS)
            self._fire_due(datetime.now(UTC))
