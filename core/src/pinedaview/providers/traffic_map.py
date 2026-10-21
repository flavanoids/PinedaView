# SPDX-License-Identifier: Apache-2.0
"""Freeway speed map — the traffic card's map slide.

Keyless: Houston TranStar's own traffic map draws its freeway speeds from
``speed_segments.js``, regenerated about every minute. Each segment is one
direction of one stretch of freeway ("IH-10 Katy Eastbound from Kirkwood to
Beltway 8-West"): its shape as lat/lng points in the direction of travel, and
its live average speed. Active crashes and stalls come from the same site's
``incidents_json.js``.

The map underneath is the radar card's: Esri's Dark Gray Canvas with its roads
overlay, as a `_GRID` x `_GRID` slippy-tile mosaic around home, plus the same
``focus`` shift that puts home at the centre — just much closer in (radar is
capped at zoom 7 by RainViewer; this is zoom 12, ~10 miles across the card).

Segments and incidents are projected here into the mosaic's own 0-100
coordinates, so the card only draws an SVG. Each direction is pushed a little
to its own right, as on TranStar's map, so northbound and southbound sit side
by side instead of on top of each other.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from pinedaview.providers.base import ProviderContext
from pinedaview.providers.radar import _BASEMAP, _ROADS, _clamp, _point, _tile_xy
from pinedaview.providers.traffic_cams import _short_road

_SPEEDS_URL = "https://traffic.houstontranstar.org/data/layers/speed_segments.js"
_INCIDENTS_URL = "https://traffic.houstontranstar.org/data/layers/incidents_json.js"
_ZOOM = 12
_GRID = 3
# How far each direction sits off the shared centreline, in mosaic units (the
# mosaic is ~1.6x the card, so this is a couple of pixels on the kiosk).
_LANE_GAP = 0.3
# The card shows about the middle 62% of the mosaic; the slowest stretch is
# picked from roughly that window around home.
_VIEW_HALF = 31.0
_SLOW_MPH = 50
_STALE_AFTER_S = 10 * 60
_HOUSTON = ZoneInfo("America/Chicago")
_SEGMENT_RE = re.compile(r"new SpeedSegment\((.*?)\);")
_ARG_RE = re.compile(r'"([^"]*)"|(-?[\d.]+)')
_GENERATED_RE = re.compile(r"Auto-generated on (\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2} [AP]M)")
_DIRECTIONS = {
    "Northbound": "NB",
    "Southbound": "SB",
    "Eastbound": "EB",
    "Westbound": "WB",
    "Inbound": "IB",
    "Outbound": "OB",
}
_CRASH_KEYWORDS = ("accident", "crash", "collision", "overturn", "fire", "fatal")
_CLOSURE_KEYWORDS = ("closure", "closed", "blocked")
_FLOOD_KEYWORDS = ("high water", "flood", "water on road", "flooding")


def _center(ctx: ProviderContext) -> tuple[float, float] | None:
    """The card's ``mapCenter`` setting ("29.8, -95.5"), else the location the
    radar and weather use."""
    raw = ctx.card_setting("traffic", "mapCenter")
    if isinstance(raw, str) and raw.strip():
        try:
            lat, lon = (float(p) for p in raw.split(","))
        except ValueError:
            pass
        else:
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    return _point(ctx)


def _zoom(ctx: ProviderContext) -> int:
    """The card's ``mapZoom`` setting (10-14), defaulting to 12."""
    raw = ctx.card_setting("traffic", "mapZoom")
    if isinstance(raw, int) and 10 <= raw <= 14:
        return raw
    if isinstance(raw, str) and raw.strip().isdigit():
        val = int(raw.strip())
        if 10 <= val <= 14:
            return val
    return _ZOOM


def _level(mph: int) -> str:
    if mph < 0:
        return "none"
    if mph < 30:
        return "crawl"
    if mph < 40:
        return "slow"
    if mph < 50:
        return "ok"
    return "fast"


def _short_location(location: str, direction: str) -> str:
    """ "IH-10 Katy Eastbound from Kirkwood to Beltway 8-West" →
    "I-10 EB · Kirkwood → BW-8 West"."""
    road, _, stretch = location.partition(" from ")
    for word in _DIRECTIONS:
        road = road.replace(f" {word}", "")
    origin, _, dest = stretch.partition(" to ")

    def place(name: str) -> str:
        return name.replace("Beltway 8-", "BW-8 ").replace("IH-", "I-").strip()

    head = f"{_short_road(road.strip())} {direction}".strip()
    return f"{head} · {place(origin)} → {place(dest)}" if dest else head


def parse_segments(text: str) -> list[dict[str, Any]]:
    """Every ``new SpeedSegment(lats, lngs, latOffsets, lngOffsets, direction,
    speed, travelTime, dist, facilityType, originId, destId, location,
    historicalDiff, delay)`` in TranStar's file. HOV lanes are dropped — they'd
    draw over the main lanes they run beside."""
    segments = []
    for match in _SEGMENT_RE.finditer(text):
        args = [q or n for q, n in _ARG_RE.findall(match.group(1))]
        if len(args) < 12 or args[8] != "ML":
            continue
        try:
            lats = [float(v) for v in args[0].split()]
            lngs = [float(v) for v in args[1].split()]
            mph = int(float(args[5]))
        except ValueError:
            continue
        if len(lats) < 2 or len(lats) != len(lngs):
            continue
        delay = 0
        if len(args) > 13:
            try:
                delay = int(float(args[13]))
            except (ValueError, TypeError):
                delay = 0
        diff = 0.0
        if len(args) > 12:
            try:
                diff = float(args[12])
            except (ValueError, TypeError):
                diff = 0.0
        segments.append(
            {
                "points": list(zip(lats, lngs, strict=True)),
                "direction": args[4],
                "mph": mph,
                "location": args[11],
                "delay": delay,
                "diff": diff,
            }
        )
    return segments


def generated_at(text: str) -> datetime | None:
    match = _GENERATED_RE.search(text[:200])
    if not match:
        return None
    try:
        naive = datetime.strptime(match.group(1), "%m/%d/%Y %I:%M:%S %p")
    except ValueError:
        return None
    return naive.replace(tzinfo=_HOUSTON)


def _offset_right(pts: list[tuple[float, float]], gap: float) -> list[tuple[float, float]]:
    """Shift a polyline `gap` to the right of its direction of travel (screen
    coordinates, y down), using each vertex's averaged segment normal."""
    out = []
    for i, (x, y) in enumerate(pts):
        nx = ny = 0.0
        for a, b in ((i - 1, i), (i, i + 1)):
            if a >= 0 and b < len(pts):
                dx, dy = pts[b][0] - pts[a][0], pts[b][1] - pts[a][1]
                length = math.hypot(dx, dy)
                if length:
                    nx, ny = nx - dy / length, ny + dx / length
        length = math.hypot(nx, ny)
        if length:
            x, y = x + nx / length * gap, y + ny / length * gap
        out.append((x, y))
    return out


def _process_segments(
    segments: list[dict[str, Any]],
    project: Callable[[float, float], tuple[float, float]],
    hx: float,
    hy: float,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, list[dict[str, Any]]]:
    drawn: list[dict[str, Any]] = []
    slowest: dict[str, Any] | None = None
    slow_candidates: list[dict[str, Any]] = []
    for seg in segments:
        pts = [project(a, b) for a, b in seg["points"]]
        if not any(-5 <= x <= 105 and -5 <= y <= 105 for x, y in pts):
            continue
        pts = _offset_right(pts, _LANE_GAP)
        drawn.append(
            {
                "d": " ".join(f"{x:.2f},{y:.2f}" for x, y in pts),
                "level": _level(seg["mph"]),
            }
        )
        in_view = any(abs(x - hx) < _VIEW_HALF and abs(y - hy) < _VIEW_HALF for x, y in pts)
        if in_view and 0 <= seg["mph"] < _SLOW_MPH:
            candidate: dict[str, Any] = {
                "label": _short_location(seg["location"], seg["direction"]),
                "mph": seg["mph"],
            }
            if seg.get("delay", 0) > 0:
                candidate["delay"] = seg["delay"]
            slow_candidates.append(candidate)
            if slowest is None or seg["mph"] < slowest["mph"]:
                slowest = candidate

    # Slowest drawn last, so red sits on top where directions cross.
    order = {"none": 0, "fast": 1, "ok": 2, "slow": 3, "crawl": 4}
    drawn.sort(key=lambda s: order[s["level"]])
    return drawn, slowest, slow_candidates


def _process_incidents(
    incidents: list[dict[str, Any]],
    project: Callable[[float, float], tuple[float, float]],
    hx: float,
    hy: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    marks: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    for inc in incidents:
        if str(inc.get("status", "")).lower() == "cleared":
            continue
        try:
            x, y = project(float(inc["lat"]), float(inc["lng"]))
        except (KeyError, TypeError, ValueError):
            continue
        if not (-5 <= x <= 105 and -5 <= y <= 105):
            continue
        desc = str(inc.get("desc", "")).strip()
        loc = str(inc.get("location", "")).strip()
        desc_lower = desc.lower()
        crash = any(w in desc_lower for w in _CRASH_KEYWORDS)
        if crash:
            kind = "crash"
        elif any(w in desc_lower for w in _CLOSURE_KEYWORDS):
            kind = "closure"
        elif any(w in desc_lower for w in _FLOOD_KEYWORDS):
            kind = "flood"
        else:
            kind = "stall"
        marks.append(
            {
                "x": round(x, 2),
                "y": round(y, 2),
                "crash": crash,
                "kind": kind,
                "desc": desc,
                "location": loc,
            }
        )
        if abs(x - hx) < _VIEW_HALF and abs(y - hy) < _VIEW_HALF:
            alert_text = f"{desc} · {loc}" if loc else desc
            if kind in ("crash", "closure", "flood") and alert_text:
                alerts.append({"type": kind, "text": alert_text})
    return marks, alerts


def _process_cameras(
    cameras: list[dict[str, Any]] | None,
    project: Callable[[float, float], tuple[float, float]],
) -> list[dict[str, Any]]:
    cam_markers: list[dict[str, Any]] = []
    for c in cameras or []:
        try:
            cx, cy = project(float(c["lat"]), float(c["lng"]))
        except (KeyError, TypeError, ValueError):
            continue
        if -5 <= cx <= 105 and -5 <= cy <= 105:
            cam_markers.append(
                {
                    "id": str(c["id"]),
                    "label": str(c.get("label", f"Camera {c['id']}")),
                    "x": round(cx, 2),
                    "y": round(cy, 2),
                }
            )
    return cam_markers


def _build_alerts(
    slowest: dict[str, Any] | None,
    slow_candidates: list[dict[str, Any]],
    incident_alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if slowest is not None:
        delay_str = f" (+{slowest['delay']}m)" if slowest.get("delay") else ""
        alerts.append(
            {
                "type": "slow",
                "text": f"{slowest['mph']} mph{delay_str} · {slowest['label']}",
            }
        )
    for inc_alert in incident_alerts[:2]:
        alerts.append(inc_alert)
    if len(alerts) < 3 and len(slow_candidates) > 1:
        slow_candidates.sort(key=lambda c: c["mph"])
        for sc in slow_candidates[1:]:
            if sc["label"] != (slowest["label"] if slowest else ""):
                delay_str = f" (+{sc['delay']}m)" if sc.get("delay") else ""
                alerts.append(
                    {
                        "type": "slow",
                        "text": f"{sc['mph']} mph{delay_str} · {sc['label']}",
                    }
                )
                break
    return alerts


def build_map(
    segments: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    center: tuple[float, float],
    updated: datetime | None,
    now: datetime,
    zoom: int = _ZOOM,
    cameras: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lat, lon = center
    xf, yf = _tile_xy(lat, lon, zoom)
    x0, y0 = round(xf - _GRID / 2), round(yf - _GRID / 2)
    tiles = [(x0 + dx, y0 + dy) for dy in range(_GRID) for dx in range(_GRID)]
    hx, hy = (xf - x0) / _GRID * 100, (yf - y0) / _GRID * 100

    def project(plat: float, plon: float) -> tuple[float, float]:
        px, py = _tile_xy(plat, plon, zoom)
        return (px - x0) / _GRID * 100, (py - y0) / _GRID * 100

    drawn, slowest, slow_candidates = _process_segments(segments, project, hx, hy)
    marks, incident_alerts = _process_incidents(incidents, project, hx, hy)
    cam_markers = _process_cameras(cameras, project)
    alerts = _build_alerts(slowest, slow_candidates, incident_alerts)

    return {
        "cols": _GRID,
        "zoom": zoom,
        "focus": {
            "dx": round(_clamp(50 - hx, -17, 17), 2),
            "dy": round(_clamp(50 - hy, -17, 17), 2),
        },
        "basemap": [_BASEMAP.format(z=zoom, x=tx, y=ty) for tx, ty in tiles],
        "roads": [_ROADS.format(z=zoom, x=tx, y=ty) for tx, ty in tiles],
        "segments": drawn,
        "incidents": marks,
        "cameras": cam_markers,
        "slowest": slowest,
        "alerts": alerts,
        "updatedAt": updated.isoformat() if updated else None,
        "stale": updated is None or (now - updated).total_seconds() > _STALE_AFTER_S,
    }


async def fetch_map(
    client: httpx.AsyncClient,
    ctx: ProviderContext,
    cameras: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """The map slide, or ``None`` when there's no centre or TranStar's speeds
    can't be read — the card then just shows the cameras."""
    center = _center(ctx)
    if center is None:
        return None
    zoom = _zoom(ctx)
    headers = {"User-Agent": ctx.settings.providers.user_agent}
    try:
        response = await client.get(_SPEEDS_URL, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    segments = parse_segments(response.text)
    if not segments:
        return None
    incidents: list[dict[str, Any]] = []
    try:
        inc = await client.get(_INCIDENTS_URL, headers=headers)
        inc.raise_for_status()
        listed = json.loads(inc.text).get("incidents")
        if isinstance(listed, list):
            incidents = [i for i in listed if isinstance(i, dict)]
    except (httpx.HTTPError, ValueError, AttributeError):
        pass  # markers are extra — the speeds stand on their own
    return build_map(
        segments,
        incidents,
        center,
        generated_at(response.text),
        datetime.now(_HOUSTON),
        zoom=zoom,
        cameras=cameras,
    )
