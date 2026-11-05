# SPDX-License-Identifier: Apache-2.0
"""Alarms and reminders for the phone menu, kept by the voice assistant.

Antigua owns them: it saves them across restarts, repeats them, says them out
loud when they go off (or only shows them, ``speak: false``), and its backup
box rings them if the main one is down. The menu lists, sets and switches
them through ``[antigua] url`` (``GET/POST /alarms``, ``PATCH/DELETE
/alarms/<id>``), so ones set by voice and by phone are one list. Antigua
mirrors the running ones back through ``PUT /api/timers/sync/antigua``, which
is how the screens show them and take over when one goes off.
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field


class Alarm(BaseModel):
    id: str
    kind: Literal["alarm", "reminder"]
    label: str
    """Antigua's own words for it: "gym alarm for 6:30 AM, every weekday"."""
    name: str | None = None
    message: str | None = None
    """A reminder's "call mom"."""
    repeat: str | None = None
    """None (once), daily, weekdays, weekends, or weekday numbers "0,2,4" (Monday 0)."""
    hour: int | None = None
    minute: int = 0
    fires_at: float
    """Unix seconds of the next time it goes off (when it would, if switched off)."""
    speak: bool = True
    enabled: bool = True


class AlarmRequest(BaseModel):
    kind: Literal["alarm", "reminder"]
    time: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    """A one-time day; leave out (and repeat too) for the next time the clock reads ``time``."""
    repeat: str | None = None
    name: str | None = Field(default=None, max_length=40)
    message: str | None = Field(default=None, max_length=120)
    speak: bool = True


class AlarmSwitch(BaseModel):
    enabled: bool


class AntiguaError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


async def call_any(
    http: httpx.AsyncClient, bases: list[str | None], method: str, path: str, body: Any = None
) -> Any:
    """``call`` on the primary Antigua, then its fallback: whichever has them
    right now (the fallback answers 503 while the primary is up)."""
    tried = [b for b in bases if b]
    if not tried:
        raise AntiguaError(503, "this needs Antigua ([antigua] url)")
    for base in tried[:-1]:
        try:
            return await call(http, base, method, path, body)
        except AntiguaError as exc:
            if exc.status != 503:
                raise
    return await call(http, tried[-1], method, path, body)


async def call(
    http: httpx.AsyncClient, base: str | None, method: str, path: str, body: Any = None
) -> Any:
    """One request to Antigua. Its 4xx come back as they are (a time that
    has passed, an alarm that's gone); no config or no answer is a 503."""
    if not base:
        raise AntiguaError(503, "this needs Antigua ([antigua] url)")
    try:
        res = await http.request(method, base.rstrip("/") + path, json=body)
    except httpx.HTTPError as exc:
        raise AntiguaError(503, f"Antigua didn't answer: {exc}") from exc
    if res.status_code >= 400:
        try:
            detail = res.json().get("error") or res.text
        except ValueError:
            detail = res.text
        # Its own 503 means "the other one has them" (call_any moves on);
        # any other server error is a bad gateway.
        status = res.status_code if res.status_code < 500 or res.status_code == 503 else 502
        raise AntiguaError(status, detail)
    return res.json()
