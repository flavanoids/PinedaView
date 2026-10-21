# SPDX-License-Identifier: Apache-2.0
"""Sunrise/sunset — drives the day/night theme flip (see themes.Theme.night
and view.py's theme resolution).

Astronomical, not a poll: astral computes sunrise/sunset locally from
lat/lon/date, so a flip lands within a second of the real transition instead
of waiting on the next weather poll (up to 900s+jitter), and DST just falls
out of it for free — every call takes an aware local datetime, and astral
resolves "today"'s sun times against that datetime's own UTC offset, so a
recompute made the morning after a DST changeover already sees the new
offset without any special-casing here.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from astral import Observer
from astral.sun import sun as _sun

from pinedaview.broadcast import Broadcaster
from pinedaview.config import Settings
from pinedaview.stores import StoreRegistry

logger = logging.getLogger(__name__)

# No pinned/geocoded coordinates yet (weather hasn't polled, or is disabled) —
# check back soon rather than never flipping the theme at all.
_RETRY_SECONDS = 300.0


def resolve_coords(
    settings: Settings, stores: StoreRegistry | None = None
) -> tuple[float, float] | None:
    """Best-available (lat, lon) for this server: explicit config, else a
    pinned "lat,lon" location query, else whatever the weather provider last
    resolved (it does its own geocoding; duplicating that here would mean a
    second network round-trip for the same answer)."""
    loc = settings.location
    if loc.latitude is not None and loc.longitude is not None:
        return loc.latitude, loc.longitude
    parts = loc.query.split(",")
    if len(parts) == 2:
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            pass
        else:
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    if stores is not None:
        store = stores.get("weather")
        snap = store.snapshot() if store is not None else None
        coords = (snap.value or {}).get("coords") if snap is not None else None
        if coords:
            return coords["lat"], coords["lon"]
    return None


def _sun_times(lat: float, lon: float, moment: datetime) -> tuple[datetime, datetime]:
    observer = Observer(latitude=lat, longitude=lon)
    times = _sun(observer, date=moment.date(), tzinfo=moment.tzinfo or UTC)
    return times["sunrise"], times["sunset"]


def is_night(moment: datetime, lat: float, lon: float) -> bool:
    try:
        sunrise, sunset = _sun_times(lat, lon, moment)
    except ValueError:
        # Polar day/night, or another edge astral refuses to compute — never
        # flip rather than crash the view.
        return False
    return moment < sunrise or moment >= sunset


def next_transition(moment: datetime, lat: float, lon: float) -> datetime | None:
    """The next sunrise or sunset strictly after `moment`, in its own tz."""
    try:
        sunrise, sunset = _sun_times(lat, lon, moment)
        candidates = [t for t in (sunrise, sunset) if t > moment]
        if candidates:
            return min(candidates)
        tomorrow = _sun(
            Observer(latitude=lat, longitude=lon),
            date=moment.date() + timedelta(days=1),
            tzinfo=moment.tzinfo or UTC,
        )
        return tomorrow["sunrise"]
    except ValueError:
        return None


class SunScheduler:
    """Sleeps until the next sunrise/sunset boundary, then broadcasts a view
    change so a live-connected display's theme flips promptly instead of
    waiting on the next weather poll or a page reload."""

    def __init__(self, settings: Settings, stores: StoreRegistry, broadcaster: Broadcaster) -> None:
        self._settings = settings
        self._stores = stores
        self._broadcaster = broadcaster

    async def run(self) -> None:
        while True:
            coords = resolve_coords(self._settings, self._stores)
            if coords is None:
                await asyncio.sleep(_RETRY_SECONDS)
                continue
            moment = datetime.now().astimezone()
            target = next_transition(moment, *coords)
            if target is None:
                await asyncio.sleep(_RETRY_SECONDS)
                continue
            delay = max(1.0, (target - moment).total_seconds())
            await asyncio.sleep(delay)
            self._broadcaster.publish({"type": "config", "reason": "sun"})
