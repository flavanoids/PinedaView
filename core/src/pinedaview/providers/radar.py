# SPDX-License-Identifier: Apache-2.0
"""Rain radar — RainViewer's newest composite frame, tiled client-side, plus
NEXRAD storm-cell tracks.

Keyless: RainViewer publishes recent radar composite frames as map tiles. This
provider resolves the newest frame and *which* tiles cover the configured
location; the browser fetches the tile images straight from RainViewer's
cache, so no image bytes pass through this server.

Only the newest frame is sent — the card is a still image, refreshed each poll.
The old ~2-hour timelapse loop never let the page go idle and was ~70% of the
Pi kiosk's CPU (DECISIONS 0023/0024). Motion comes from storm tracks instead:
the Iowa Environmental Mesonet republishes NEXRAD's per-cell storm attributes
(position, heading, speed, hail probability, rotation) as keyless GeoJSON. Each
nearby cell becomes an arrow from where it is to where it'll be in
`_TRACK_MINUTES`, in the mosaic's own coordinates. US-only; anywhere else, or if
the feed is down, the card just shows the radar.

Each frame is a small square mosaic of slippy-map tiles (`_GRID` x `_GRID`)
around the location, plus a ``focus`` offset — how far, as a percent of the
mosaic, to shift it so the location sits dead centre. The card scales the
mosaic to cover the card and applies that shift. A matching mosaic of Esri's
"Dark Gray Canvas" basemap tiles goes underneath so the precipitation reads
against coastlines and water rather than empty black, and Esri's roads
overlay over that, so the freeways are there to place a storm by.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError

_INDEX_URL = "https://api.rainviewer.com/public/weather-maps.json"
_TILE_HOST = "https://tilecache.rainviewer.com"
_ZOOM = 7  # RainViewer's public composite tiles stop at 7 (8+ is a placeholder)
_GRID = 3  # NxN tile mosaic centred on the location
_TILE_PX = 512
_COLOR = 4  # RainViewer "weather channel" palette — reads over a dark card
_OPTIONS = "1_1"  # smooth, show snow
_STORMS_URL = "https://mesonet.agron.iastate.edu/geojson/nexrad_attr.geojson"
_TRACK_MINUTES = 30  # arrow length: where the cell will be in this long
_MAX_STORM_AGE_S = 20 * 60  # drop cells from radars that stopped reporting
_DEDUPE_KM = 12.0  # overlapping radars report one cell under different IDs
_MAX_STORMS = 16
_KM_PER_DEG = 111.2
# Esri "Dark Gray Canvas" basemap — keyless, {z}/{y}/{x} order. Attribution
# "Esri" is shown on the card. (CARTO's keyless tiles now come back watermarked.)
_BASEMAP = (
    "https://services.arcgisonline.com/ArcGIS/rest/services"
    "/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
)
# Esri's transparent roads overlay (same host and terms): freeways and major
# highways over the basemap, under the radar. The card greys it so roads
# don't read as light rain.
_ROADS = (
    "https://services.arcgisonline.com/ArcGIS/rest/services"
    "/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}"
)


def _point(ctx: ProviderContext) -> tuple[float, float] | None:
    loc = ctx.settings.location
    if loc.latitude is not None and loc.longitude is not None:
        return loc.latitude, loc.longitude
    weather = ctx.store_value("weather")
    coords = weather.get("coords") if isinstance(weather, dict) else None
    if isinstance(coords, dict) and "lat" in coords and "lon" in coords:
        return float(coords["lat"]), float(coords["lon"])
    return None


def _tile_xy(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Fractional slippy-map tile coordinates of a point."""
    n = 2**zoom
    xf = (lon + 180.0) / 360.0 * n
    yf = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return xf, yf


def _mosaic(lat: float, lon: float, zoom: int) -> tuple[list[tuple[int, int]], float, float]:
    """The `_GRID`x`_GRID` tile block around the point, plus the shift (percent
    of the mosaic, x and y) that moves the point to the mosaic's centre."""
    xf, yf = _tile_xy(lat, lon, zoom)
    # Anchor the block so the point lands near its centre (works for odd and
    # even _GRID alike).
    x0 = round(xf - _GRID / 2)
    y0 = round(yf - _GRID / 2)
    tiles = [(x0 + dx, y0 + dy) for dy in range(_GRID) for dx in range(_GRID)]
    # Point position within the block, 0..1; shift the mosaic the other way.
    # Clamp so the card's cover-scaled mosaic always has margin to shift into.
    dx_pct = _clamp((0.5 - (xf - x0) / _GRID) * 100, -14, 14)
    dy_pct = _clamp((0.5 - (yf - y0) / _GRID) * 100, -14, 14)
    return tiles, round(dx_pct, 2), round(dy_pct, 2)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _storms(payload: Any, origin: tuple[int, int], now: datetime) -> list[dict[str, Any]]:
    """NEXRAD storm cells inside the mosaic, as mosaic-percent track arrows.

    ``drct`` is the direction the cell is moving *from* (meteorological
    convention — verified 2026-09-23 against 63 cells' actual scan-to-scan
    displacement, all within 45° of ``drct + 180``), ``sknt`` its speed in
    knots."""
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(features, list):
        return []
    x0, y0 = origin
    cells: list[tuple[float, float, float, dict[str, Any]]] = []
    for feature in features:
        try:
            props = feature["properties"]
            lon, lat = (float(c) for c in feature["geometry"]["coordinates"][:2])
            valid = datetime.fromisoformat(str(props["valid"]).replace("Z", "+00:00"))
            heading = (float(props.get("drct") or 0) + 180) % 360  # → toward
            knots = float(props.get("sknt") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if (now - valid).total_seconds() > _MAX_STORM_AGE_S:
            continue
        xf, yf = _tile_xy(lat, lon, _ZOOM)
        x, y = (xf - x0) / _GRID * 100, (yf - y0) / _GRID * 100
        if not (0 <= x <= 100 and 0 <= y <= 100):
            continue
        cells.append(
            (
                lat,
                lon,
                float(props.get("max_dbz") or 0),
                {"x": x, "y": y, "heading": heading, "knots": knots, "props": props},
            )
        )

    # Strongest first, so the dedupe keeps the best-observed copy of a cell.
    cells.sort(key=lambda c: c[2], reverse=True)
    kept: list[tuple[float, float, dict[str, Any]]] = []
    for lat, lon, _dbz, cell in cells:
        coslat = math.cos(math.radians(lat))
        if any(
            math.hypot((lon - klon) * coslat, lat - klat) * _KM_PER_DEG < _DEDUPE_KM
            for klat, klon, _ in kept
        ):
            continue
        kept.append((lat, lon, cell))
        if len(kept) >= _MAX_STORMS:
            break

    storms = []
    for lat, lon, cell in kept:
        props, knots, heading = cell["props"], cell["knots"], cell["heading"]
        km = knots * 1.852 * _TRACK_MINUTES / 60
        rad = math.radians(heading)
        lat2 = lat + km * math.cos(rad) / _KM_PER_DEG
        lon2 = lon + km * math.sin(rad) / (_KM_PER_DEG * math.cos(math.radians(lat)))
        xf2, yf2 = _tile_xy(lat2, lon2, _ZOOM)
        storms.append(
            {
                "x": round(cell["x"], 2),
                "y": round(cell["y"], 2),
                "x2": round((xf2 - x0) / _GRID * 100, 2),
                "y2": round((yf2 - y0) / _GRID * 100, 2),
                "mph": round(knots * 1.15078),
                "hail": int(props.get("poh") or 0) >= 50,
                "rotation": str(props.get("meso") or "NONE") != "NONE"
                or str(props.get("tvs") or "NONE") != "NONE",
            }
        )
    return storms


class RadarProvider(Provider):
    key = "radar"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:  # noqa: ARG002
        return 600

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        point = _point(ctx)
        if point is None:
            return None
        index = await ctx.fetch_json(_INDEX_URL, allow_hosts=["api.rainviewer.com"])
        if not isinstance(index, dict):
            raise ProviderError("unexpected RainViewer index payload")
        radar = index.get("radar")
        past = radar.get("past") if isinstance(radar, dict) else None
        if not isinstance(past, list) or not past:
            raise ProviderError("no radar frames in RainViewer index")

        tiles, dx, dy = _mosaic(*point, _ZOOM)
        window = [f for f in past[-1:] if isinstance(f, dict) and "path" in f]
        frames = [
            {
                "time": datetime.fromtimestamp(f["time"], tz=UTC).isoformat()
                if isinstance(f.get("time"), int | float)
                else None,
                "tiles": [
                    f"{_TILE_HOST}{f['path']}/{_TILE_PX}/{_ZOOM}/{x}/{y}/{_COLOR}/{_OPTIONS}.png"
                    for x, y in tiles
                ],
            }
            for f in window
        ]
        if not frames:
            raise ProviderError("no usable radar frames")
        basemap = [_BASEMAP.format(z=_ZOOM, x=tx, y=ty) for tx, ty in tiles]
        roads = [_ROADS.format(z=_ZOOM, x=tx, y=ty) for tx, ty in tiles]
        try:
            payload = await ctx.fetch_json(_STORMS_URL, allow_hosts=["mesonet.agron.iastate.edu"])
            storms = _storms(payload, tiles[0], datetime.now(UTC))
        except ProviderError:
            storms = []  # tracks are extra — the radar still stands on its own
        return {
            "cols": _GRID,
            "focus": {"dx": dx, "dy": dy},
            "basemap": basemap,
            "roads": roads,
            "frames": frames,
            "storms": storms,
            "generated_at": frames[-1]["time"],
        }
