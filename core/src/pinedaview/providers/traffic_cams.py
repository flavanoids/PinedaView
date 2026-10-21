# SPDX-License-Identifier: Apache-2.0
"""Traffic cameras — Houston TranStar CCTV snapshots for the traffic card, which
loops them during commute windows, led by a freeway speed map
(``traffic_map.py``).

TranStar overwrites each camera's JPEG in place about every 3 minutes (measured
2026-09-29: 17:54:01 → 17:57:02 → 18:00:03). The ``?arg=`` its own site appends
is only a cache-buster — every value returns the same file. So this polls on
that cadence with ``If-Modified-Since`` and keeps exactly one image per camera
in memory: a refresh replaces it, a camera dropped from the list or gone stale
is evicted, and outside the windows the cache is emptied. Browsers get the bytes
from ``GET /api/cams/{file}``; the Pi never talks to TranStar.

Some cameras are short flipbooks (``frameCount`` > 1 in TranStar's catalogue):
``{id}-1.jpg`` … ``{id}-N.jpg`` played at ``framePauseMs``. Those frames are
cached the same way. A missing one — TranStar answers 200 with an HTML error
page, not a 404 — is skipped.
"""

from __future__ import annotations

import contextlib
import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError
from pinedaview.providers.commute import _during_rush as in_window

_SNAPSHOT_HOST = "www.houstontranstar.org"
_SNAPSHOT_URL = f"https://{_SNAPSHOT_HOST}/snapshots/cctv/"
_CATALOGUE_HOST = "traffic.houstontranstar.org"
_CATALOGUE_URL = f"https://{_CATALOGUE_HOST}/data/layers/cctvSnapshots_out.js"
_CATALOGUE_TTL_S = 24 * 3600
_AMBER_AFTER_S = 6 * 60  # missed a refresh (two 3-minute cycles)
_DROP_AFTER_S = 15 * 60  # too old to tell you anything about traffic now
_MAX_FRAMES = 12
_ID_RE = re.compile(r"^\d{1,5}$")
_FILE_RE = re.compile(r"^(\d{1,5})(?:-(\d{1,2}))?\.jpg$")
_KEEP_CAPS = {"FM", "SH", "US", "IH", "BW", "N", "S", "E", "W", "NE", "NW", "SE", "SW"}
_ROUTE_RE = re.compile(r"^(?:IH|US|SH|FM|Spur)-\d+\b")
_CAMERA_RE = re.compile(r"new CctvCamera\((.*?)\);")
_FIELD_RE = re.compile(r"'((?:[^'\\]|\\.)*)'")


@dataclass
class CamInfo:
    label: str
    frames: int = 1
    frame_ms: int = 0
    lat: float | None = None
    lng: float | None = None


@dataclass
class _Image:
    data: bytes
    last_modified: str | None
    captured: float  # epoch seconds, from Last-Modified


class CamCache:
    """One JPEG per camera file (``407.jpg``, ``324-3.jpg``) — never more."""

    def __init__(self) -> None:
        self._images: dict[str, _Image] = {}

    def get(self, name: str) -> bytes | None:
        image = self._images.get(name)
        return image.data if image is not None else None

    def entry(self, name: str) -> _Image | None:
        return self._images.get(name)

    def put(self, name: str, image: _Image) -> None:
        self._images[name] = image

    def names(self) -> set[str]:
        return set(self._images)

    def keep_only(self, names: set[str]) -> None:
        for name in self.names() - names:
            del self._images[name]


CAM_CACHE = CamCache()


def valid_file(name: str) -> bool:
    return _FILE_RE.match(name) is not None


def _short_road(roadway: str) -> str:
    """Just the route number where there is one — the catalogue's "Northwest" /
    "North Loop" / "Katy" suffix pushed most labels past a single cell's width.
    Named roads ("Westpark Tollway", "Westheimer") are kept whole."""
    numbered = _ROUTE_RE.match(roadway)
    if numbered:
        return numbered.group(0).replace("IH-", "I-")
    if roadway.startswith("Beltway 8"):
        return "BW-8"
    return roadway


def _soften(shouted: str) -> str:
    """ "PINEMONT" -> "Pinemont", "N MAIN ST" -> "N Main St", but "FM 1960"
    and "BW-8" stay put."""
    return " ".join(
        w if w in _KEEP_CAPS or any(c.isdigit() for c in w) else w.capitalize()
        for w in shouted.split()
    )


def _label(roadway: str, location: str, fallback: str) -> str:
    """``"US-290 @ Pinemont"`` from roadway ``"US-290 Northwest"`` and location
    ``"PINEMONT"`` — short enough for a pill on a one-cell card."""
    if not roadway or not location:
        return fallback
    road = _short_road(roadway)
    # The catalogue shouts some locations ("PINEMONT") but not others
    # ("West BW-8") — only soften the all-caps ones.
    place = _soften(location) if location.isupper() else location
    return f"{road} @ {place}"


def parse_catalogue(text: str) -> dict[str, CamInfo]:
    """TranStar's ``cctvSnapshots_out.js``: one ``new CctvCamera(name, monitor,
    roadway, location, lat, lng, dir, path, validimg, frameCount,
    framePauseMs)`` per camera, keyed here by id (``"407"``)."""
    cams: dict[str, CamInfo] = {}
    for match in _CAMERA_RE.finditer(text):
        fields = _FIELD_RE.findall(match.group(1))
        if len(fields) < 11 or not fields[7].endswith(".jpg"):
            continue
        cam_id = fields[7].removesuffix(".jpg")
        try:
            frames, frame_ms = int(fields[9]), int(fields[10])
        except ValueError:
            frames, frame_ms = 1, 0
        lat: float | None = None
        lng: float | None = None
        if len(fields) > 5:
            with contextlib.suppress(ValueError, TypeError):
                lat, lng = float(fields[4]), float(fields[5])
        cams[cam_id] = CamInfo(
            label=_label(fields[2], fields[3], fields[0]),
            frames=max(1, min(frames, _MAX_FRAMES)),
            frame_ms=frame_ms,
            lat=lat,
            lng=lng,
        )
    return cams


def camera_ids(value: object) -> list[str]:
    """The card setting, cleaned — digits only, since each id lands in a URL."""
    if not isinstance(value, list):
        return []
    ids = (str(v).strip() for v in value)
    return [i for i in dict.fromkeys(ids) if _ID_RE.match(i)]


def _captured(last_modified: str | None) -> float:
    if last_modified:
        try:
            return parsedate_to_datetime(last_modified).timestamp()
        except (TypeError, ValueError):
            pass
    return time.time()


class TrafficCamsProvider(Provider):
    key = "traffic"

    def __init__(self, interval_s: int | None = None, cache: CamCache | None = None) -> None:
        super().__init__(interval_s)
        self.cache = cache or CAM_CACHE
        self._catalogue: dict[str, CamInfo] = {}
        self._catalogue_at = 0.0
        self._last_good_map: dict[str, Any] | None = None

    def _default_interval_s(self, cfg: ProviderConfig) -> int:  # noqa: ARG002
        return 180

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        now = datetime.now().astimezone()
        weekend = now.weekday() >= 5
        window = ctx.card_setting("traffic", "weekendWindow" if weekend else "weekdayWindow")
        if not in_window(window, now):
            self.cache.keep_only(set())
            return {"active": False, "cams": []}

        client = ctx.http_client
        if client is None:
            raise ProviderError("traffic cams need the shared HTTP client")
        ids = camera_ids(ctx.card_setting("traffic", "cameras"))
        await self._refresh_catalogue(client, ctx)

        cams: list[dict[str, Any]] = []
        keep: set[str] = set()
        cams_for_map: list[dict[str, Any]] = []
        for cam_id in ids:
            cam = await self._camera(client, ctx, cam_id, keep)
            if cam is not None:
                cams.append(cam)
            info = self._catalogue.get(cam_id)
            if info and info.lat is not None and info.lng is not None:
                cams_for_map.append(
                    {
                        "id": cam_id,
                        "label": info.label,
                        "lat": info.lat,
                        "lng": info.lng,
                    }
                )
        self.cache.keep_only(keep)
        # Imported here: traffic_map borrows this module's road shortening.
        from pinedaview.providers.traffic_map import fetch_map

        fresh_map = await fetch_map(client, ctx, cameras=cams_for_map)
        if fresh_map is not None:
            self._last_good_map = fresh_map
            active_map = fresh_map
        elif self._last_good_map is not None:
            active_map = {**self._last_good_map, "stale": True}
        else:
            active_map = None

        return {"active": True, "cams": cams, "map": active_map}

    async def _camera(
        self, client: httpx.AsyncClient, ctx: ProviderContext, cam_id: str, keep: set[str]
    ) -> dict[str, Any] | None:
        """One camera's slot, or ``None`` when it has nothing fresh enough to
        show. Adds every file it still needs to ``keep``."""
        info = self._catalogue.get(cam_id, CamInfo(label=f"Camera {cam_id}"))
        main = await self._fetch(client, ctx, f"{cam_id}.jpg")
        if main is None or time.time() - main.captured > _DROP_AFTER_S:
            return None
        keep.add(f"{cam_id}.jpg")
        frames: list[str] = []
        if info.frames > 1:
            for n in range(1, info.frames + 1):
                frame = await self._fetch(client, ctx, f"{cam_id}-{n}.jpg")
                if frame is not None:
                    keep.add(f"{cam_id}-{n}.jpg")
                    frames.append(f"/api/cams/{cam_id}-{n}.jpg?v={int(frame.captured)}")
        return {
            "id": cam_id,
            "label": info.label,
            "src": f"/api/cams/{cam_id}.jpg?v={int(main.captured)}",
            # A lone surviving frame isn't a flipbook — just show the still.
            "frames": frames if len(frames) > 1 else [],
            "frameMs": info.frame_ms or 300,
            "capturedAt": datetime.fromtimestamp(main.captured).astimezone().isoformat(),
            "stale": time.time() - main.captured > _AMBER_AFTER_S,
        }

    async def _refresh_catalogue(self, client: httpx.AsyncClient, ctx: ProviderContext) -> None:
        if self._catalogue and time.time() - self._catalogue_at < _CATALOGUE_TTL_S:
            return
        headers = {"User-Agent": ctx.settings.providers.user_agent}
        try:
            response = await client.get(_CATALOGUE_URL, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError:
            return  # labels fall back to "Camera 407"; retried next poll
        parsed = parse_catalogue(response.text)
        if parsed:
            self._catalogue, self._catalogue_at = parsed, time.time()

    async def _fetch(
        self, client: httpx.AsyncClient, ctx: ProviderContext, name: str
    ) -> _Image | None:
        """The current image for ``name`` — refetched only if TranStar has a
        newer one. A failed fetch keeps the last good copy (the caller decides
        when it's too old to show)."""
        cached = self.cache.entry(name)
        headers = {"User-Agent": ctx.settings.providers.user_agent}
        if cached is not None and cached.last_modified:
            headers["If-Modified-Since"] = cached.last_modified
        try:
            response = await client.get(_SNAPSHOT_URL + name, headers=headers)
        except httpx.HTTPError:
            return cached
        if response.status_code == 304:
            return cached
        is_jpeg = response.headers.get("content-type", "").startswith("image/jpeg")
        if response.status_code != 200 or not is_jpeg:
            return cached if response.status_code >= 500 else None
        last_modified = response.headers.get("last-modified")
        image = _Image(response.content, last_modified, _captured(last_modified))
        self.cache.put(name, image)
        return image
