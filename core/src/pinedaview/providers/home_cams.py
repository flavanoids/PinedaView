# SPDX-License-Identifier: Apache-2.0
"""Home cameras — the doorbell and garage photos Antigua takes every so
often, for the home-cams mini card.

Both are Eufy battery cameras, so Antigua wakes each one only rarely (the
doorbell every 30 minutes, the garage every 10, daytime only: see Antigua's
security skill) and leaves ``<name>.jpg`` plus ``<name>.json`` (title, when,
how often, battery) in ``[cameras] snapshots_dir``. This only reads those
files — it never wakes a camera. The browser gets the bytes from
``GET /api/home-cams/{name}.jpg``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Collection
from datetime import datetime
from pathlib import Path
from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext

_STALE_AFTER = 2.5  # refreshes missed before the photo's time turns amber


def home_cams(
    snapshots_dir: Path | None, names: list[str], always_battery: Collection[str] = ()
) -> list[dict[str, Any]]:
    """Each camera's latest photo, in [cameras.streams] order. An old photo
    still shows (overnight there are none newer), its time in amber; a
    battery below Antigua's warning level puts a "charge it" note on it, and
    an ``always_battery`` camera's level is on the card the whole time."""
    if snapshots_dir is None:
        return []
    cams = []
    for name in names:
        try:
            meta = json.loads((snapshots_dir / f"{name}.json").read_text())
            taken = float(meta["taken"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if not (snapshots_dir / f"{name}.jpg").is_file():
            continue
        every = max(float(meta.get("every") or 30), 1) * 60
        battery = meta.get("battery")
        known = isinstance(battery, int | float) and not isinstance(battery, bool)
        cams.append(
            {
                "id": name,
                "label": str(meta.get("title") or name),
                "src": f"/api/home-cams/{name}.jpg?v={int(taken)}",
                "capturedAt": datetime.fromtimestamp(taken).astimezone().isoformat(),
                "stale": time.time() - taken > every * _STALE_AFTER,
                "battery": int(battery) if known else None,
                "lowBattery": known and battery < float(meta.get("low_battery") or 20),
                "alwaysBattery": name in always_battery,
            }
        )
    return cams


class HomeCamsProvider(Provider):
    key = "homeCams"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:  # noqa: ARG002
        return 60

    async def poll(self, ctx: ProviderContext) -> dict[str, Any]:
        cams = ctx.settings.cameras
        return {"cams": home_cams(cams.snapshots_dir, list(cams.streams), cams.always_battery)}
