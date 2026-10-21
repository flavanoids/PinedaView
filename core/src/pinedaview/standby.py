# SPDX-License-Identifier: Apache-2.0
"""Standby mode: this pineda-web is the warm backup for another one.

Set ``[standby] primary`` on the backup box. Two things follow:

- While the primary is healthy, phones are sent there. The menu, upload and
  layout pages redirect, and ``/api/menu-url`` names the primary, so a QR code
  shown during a failover still leads to the right box afterwards and phone
  changes land where they're kept.
- Anything saved here (a theme, a photo, a card setting, the layout) touches
  ``<state_dir>/standby-changed``. ``scripts/sync-standby.sh`` on the primary
  sees it, copies this box's state back before it pushes its own again, and
  so changes made during an outage carry over instead of being overwritten.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import httpx

CHANGED_FLAG = "standby-changed"

PAGES = ("/menu", "/upload", "/layout")
"""What a phone opens; sent to the primary while it's up."""

_EPHEMERAL = (
    "/api/now-showing",
    "/api/takeover",
    "/api/timers",
    "/api/alarms",
    "/api/control/",
)
"""Writes that don't change saved state: what's on screen, timers (in
memory), alarms (kept by Antigua), restarts."""

_CHECK_EVERY_S = 10.0


def is_saving_write(method: str, path: str) -> bool:
    if method not in ("POST", "PUT", "PATCH", "DELETE") or not path.startswith("/api/"):
        return False
    if path.endswith("/identify"):
        return False
    return not path.startswith(_EPHEMERAL)


class Standby:
    def __init__(
        self, primary: str, state_dir: Path, http: Callable[[], httpx.AsyncClient]
    ) -> None:
        self.primary = primary.rstrip("/")
        self._flag = state_dir / CHANGED_FLAG
        self._http = http
        self._up = False
        self._checked = 0.0

    async def primary_up(self) -> bool:
        """Whether the primary answers its health check (cached a few seconds)."""
        now = time.monotonic()
        if now - self._checked >= _CHECK_EVERY_S:
            self._checked = now
            try:
                res = await self._http().get(self.primary + "/api/health", timeout=2.0)
                self._up = res.status_code == 200
            except httpx.HTTPError:
                self._up = False
        return self._up

    def mark_changed(self) -> None:
        self._flag.touch()
