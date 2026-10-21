# SPDX-License-Identifier: Apache-2.0
"""Weather — Open-Meteo, keyless.

Resolves the configured location to coordinates (geocoding it by name unless it
is already ``lat,lon`` or the config pins latitude/longitude), then pulls
``current`` + ``hourly`` + ``daily`` from the forecast API and normalizes to SI.
The client formats to °F or °C per the viewer's unit choice; this provider never
picks a unit.

For US locations it also attaches ``climate`` — today's 1991-2020 normal
high/low and the record high/low with their years — from NOAA's ACIS
(threaded city records where one exists, else the nearest station). That's
fetched once a day and cached; any failure there just leaves it off.

Also surfaces the resolved coordinates and place name so the air-quality,
alerts, and radar providers can follow the same location without geocoding it
again. WMO weather codes are mapped back to the legacy wttr.in / WWO numbering
so the client's ``WeatherGlyph`` needs no new icon table.
"""

from __future__ import annotations

import json
import logging
import math
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError

logger = logging.getLogger(__name__)

_ALLOW = ["api.open-meteo.com", "geocoding-api.open-meteo.com", "data.rcc-acis.org"]

_GEOCODE_URL = (
    "https://geocoding-api.open-meteo.com/v1/search?name={q}&count=1&language=en&format=json"
)
_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat:.4f}&longitude={lon:.4f}"
    "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
    "weather_code,wind_speed_10m,wind_direction_10m,uv_index,is_day"
    "&hourly=temperature_2m,apparent_temperature,weather_code,"
    "precipitation_probability,uv_index,is_day"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,sunrise,sunset"
    "&timezone=auto&forecast_days=6&wind_speed_unit=ms&temperature_unit=celsius"
)

# WMO weather code → (short description, glyph code). The glyph code is the
# legacy WWO numbering `WeatherGlyph` already understands; every value here is a
# key that map actually has, so nothing falls through to the thermometer.
_WMO: dict[int, tuple[str, str]] = {
    0: ("Clear", "113"),
    1: ("Mainly Clear", "116"),
    2: ("Partly Cloudy", "116"),
    3: ("Overcast", "122"),
    45: ("Fog", "248"),
    48: ("Rime Fog", "248"),
    51: ("Light Drizzle", "266"),
    53: ("Drizzle", "266"),
    55: ("Heavy Drizzle", "296"),
    56: ("Freezing Drizzle", "182"),
    57: ("Freezing Drizzle", "182"),
    61: ("Light Rain", "296"),
    63: ("Rain", "302"),
    65: ("Heavy Rain", "308"),
    66: ("Freezing Rain", "320"),
    67: ("Freezing Rain", "320"),
    71: ("Light Snow", "179"),
    73: ("Snow", "338"),
    75: ("Heavy Snow", "338"),
    77: ("Snow Grains", "179"),
    80: ("Light Showers", "353"),
    81: ("Showers", "356"),
    82: ("Heavy Showers", "359"),
    85: ("Snow Showers", "179"),
    86: ("Snow Showers", "338"),
    95: ("Thunderstorm", "200"),
    96: ("Thunderstorm", "386"),
    99: ("Hailstorm", "389"),
}

_COMPASS = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return round(n) if n is not None else None


def _round1(value: Any) -> float | None:
    n = _num(value)
    return round(n, 1) if n is not None else None


def _wmo(code: Any) -> tuple[str, str]:
    return _WMO.get(_int(code) or 0, ("Unknown", "113"))


def _compass(deg: Any) -> str:
    d = _num(deg)
    return "" if d is None else _COMPASS[round(d / 22.5) % 16]


def _hour_of(iso: str) -> int:
    try:
        return int(iso[11:13])
    except (ValueError, IndexError):
        return 0


def _fmt_time(iso: str) -> str:
    """``2026-09-10T07:12`` → ``7:12 AM`` (the string shape the card expects)."""
    try:
        dt = datetime.strptime(iso[:16], "%Y-%m-%dT%H:%M")
    except ValueError:
        return ""
    hour = dt.hour % 12 or 12
    return f"{hour}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def _parse_lat_lon(query: str) -> tuple[float, float] | None:
    parts = query.split(",")
    if len(parts) != 2:
        return None
    lat, lon = _num(parts[0]), _num(parts[1])
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _parse_current(cur: dict[str, Any]) -> dict[str, Any]:
    desc, glyph = _wmo(cur.get("weather_code"))
    return {
        "tempC": _round1(cur.get("temperature_2m")),
        "feelsLikeC": _round1(cur.get("apparent_temperature")),
        "desc": desc,
        "code": glyph,
        "humidity": _int(cur.get("relative_humidity_2m")),
        "windMs": _round1(cur.get("wind_speed_10m")),
        "windDir": _compass(cur.get("wind_direction_10m")),
        "windDeg": _int(cur.get("wind_direction_10m")),
        "uvIndex": _int(cur.get("uv_index")),
        "isDay": bool(cur.get("is_day", 1)),
    }


def _column(block: dict[str, Any], key: str, i: int) -> Any:
    values = block.get(key)
    return values[i] if isinstance(values, list) and i < len(values) else None


def _parse_hourly(block: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """The next 24 hours, one slot per hour starting with the current one —
    the card's curve and rain-chance row read every one."""
    cutoff = now.replace(minute=0, second=0, microsecond=0)
    out: list[dict[str, Any]] = []
    for i, iso in enumerate(block.get("time", [])):
        try:
            slot = datetime.strptime(iso[:13], "%Y-%m-%dT%H")
        except ValueError:
            continue
        if slot < cutoff:
            continue
        desc, glyph = _wmo(_column(block, "weather_code", i))
        out.append(
            {
                "hour": slot.hour,
                "tempC": _round1(_column(block, "temperature_2m", i)),
                "feelsLikeC": _round1(_column(block, "apparent_temperature", i)),
                "desc": desc,
                "code": glyph,
                "precip": _int(_column(block, "precipitation_probability", i)) or 0,
                "uvIndex": _int(_column(block, "uv_index", i)) or 0,
                "isDay": bool(_column(block, "is_day", i)),
            }
        )
        if len(out) >= 24:
            break
    return out


# Open-Meteo's daily weather_code is the worst any hour might bring, so one
# hour of possible drizzle paints a 92%-dry day as showers. Below this rain
# chance (the card's own cut-off for showing one), a wet code reads dry:
# showers, drizzle and storms as partly cloudy, steady rain as overcast.
_DRY_BELOW = 10


def _dry_code(code: Any) -> Any:
    n = _int(code)
    if n is None:
        return code
    if 61 <= n <= 65:
        return 3
    if 51 <= n <= 55 or 80 <= n <= 82 or 95 <= n <= 99:
        return 2
    return code


def _parse_daily(block: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, day in enumerate(block.get("time", [])[:6]):
        precip = _int(_column(block, "precipitation_probability_max", i)) or 0
        code = _column(block, "weather_code", i)
        desc, glyph = _wmo(_dry_code(code) if precip < _DRY_BELOW else code)
        out.append(
            {
                "index": i,
                "date": day,
                "highC": _round1(_column(block, "temperature_2m_max", i)),
                "lowC": _round1(_column(block, "temperature_2m_min", i)),
                "desc": desc,
                "code": glyph,
                "precip": precip,
                "sunrise": _fmt_time(_column(block, "sunrise", i) or ""),
                "sunset": _fmt_time(_column(block, "sunset", i) or ""),
            }
        )
    return out


# ── climate: normals and records (NOAA ACIS, US only) ────────────────────────

_ACIS = "https://data.rcc-acis.org/{path}?params={params}"
# How far around the location to look for a station, in degrees.
_ACIS_REACH = 0.6
# Stations tried for a threaded city record before settling for the nearest.
_ACIS_TRIES = 4


def _acis_url(path: str, params: dict[str, Any]) -> str:
    return _ACIS.format(
        path=path, params=urllib.parse.quote(json.dumps(params, separators=(",", ":")))
    )


def _f_to_c(value: Any) -> float | None:
    f = _num(value)
    return round((f - 32) * 5 / 9, 1) if f is not None else None


def _record(smry: Any) -> tuple[float | None, int | None]:
    """ACIS ``[["96", "1991-10-12"]]`` → (35.6, 1991)."""
    try:
        value, when = smry[0]
        return _f_to_c(value), int(when[:4])
    except (TypeError, ValueError, IndexError):
        return None, None


class WeatherProvider(Provider):
    key = "weather"

    def __init__(self, interval_s: int | None = None) -> None:
        super().__init__(interval_s)
        # (lat, lon) → ACIS station ids to try, nearest first; [] outside the US.
        self._stations: tuple[tuple[float, float], list[str]] | None = None
        # (lat, lon, date) → today's climate, or None when there's none to show.
        self._climate: tuple[tuple[float, float, date], dict[str, Any] | None] | None = None

    async def _station_ids(self, ctx: ProviderContext, lat: float, lon: float) -> list[str]:
        key = (round(lat, 2), round(lon, 2))
        if self._stations and self._stations[0] == key:
            return self._stations[1]
        recent = date.today() - timedelta(days=30)
        meta = await ctx.fetch_json(
            _acis_url(
                "StnMeta",
                {
                    "bbox": [
                        lon - _ACIS_REACH,
                        lat - _ACIS_REACH,
                        lon + _ACIS_REACH,
                        lat + _ACIS_REACH,
                    ],
                    "elems": "maxt",
                    "meta": "sids,ll",
                    "sdate": recent.isoformat(),
                    "edate": date.today().isoformat(),
                },
            ),
            allow_hosts=_ALLOW,
        )
        near: list[tuple[float, str]] = []
        for station in meta.get("meta", []) if isinstance(meta, dict) else []:
            ll = station.get("ll")
            faa = [s.split()[0] for s in station.get("sids", []) if s.endswith(" 3")]
            if faa and isinstance(ll, list) and len(ll) == 2:
                near.append((math.dist((lat, lon), (ll[1], ll[0])), faa[0]))
        near.sort()
        # A city's threaded record (e.g. "Houston Area", back to 1888) first,
        # then the nearest airport's own shorter record as a fallback.
        ids = [f"{faa}thr 9" for _, faa in near[:_ACIS_TRIES]]
        ids += [faa for _, faa in near[:1]]
        self._stations = (key, ids)
        return ids

    async def _fetch_climate(
        self, ctx: ProviderContext, lat: float, lon: float, today: date
    ) -> dict[str, Any] | None:
        day = today.strftime("%m-%d")
        yesterday = (today - timedelta(days=1)).isoformat()
        for sid in await self._station_ids(ctx, lat, lon):
            records = await ctx.fetch_json(
                _acis_url(
                    "StnData",
                    {
                        "sid": sid,
                        "sdate": "por",
                        "edate": yesterday,
                        "meta": "name,valid_daterange",
                        "elems": [
                            {
                                "name": name,
                                "interval": "dly",
                                "duration": "dly",
                                "smry": [{"reduce": reduce, "add": "date"}],
                                "smry_only": 1,
                                "groupby": ["year", day, day],
                            }
                            for name, reduce in (("maxt", "max"), ("mint", "min"))
                        ],
                    },
                ),
                allow_hosts=_ALLOW,
            )
            if not isinstance(records, dict) or "smry" not in records:
                continue  # "Unknown sId" — no threaded record for this one
            high, high_year = _record(records["smry"][0])
            low, low_year = _record(records["smry"][1])
            normals = await ctx.fetch_json(
                _acis_url(
                    "StnData",
                    {
                        "sid": sid,
                        "sdate": today.isoformat(),
                        "edate": today.isoformat(),
                        "elems": [{"name": "maxt", "normal": "1"}, {"name": "mint", "normal": "1"}],
                    },
                ),
                allow_hosts=_ALLOW,
            )
            rows = normals.get("data") if isinstance(normals, dict) else None
            row = rows[0] if rows else []
            meta = records.get("meta", {})
            since = (meta.get("valid_daterange") or [[""]])[0][0][:4]
            return {
                "normalHighC": _f_to_c(row[1] if len(row) > 1 else None),
                "normalLowC": _f_to_c(row[2] if len(row) > 2 else None),
                "recordHighC": high,
                "recordHighYear": high_year,
                "recordLowC": low,
                "recordLowYear": low_year,
                "since": int(since) if since.isdigit() else None,
                "station": meta.get("name"),
            }
        return None

    async def _climate_for(
        self, ctx: ProviderContext, lat: float, lon: float
    ) -> dict[str, Any] | None:
        """Today's normals and records, fetched once a day. Never raises: a
        failure is logged, left uncached, and retried on the next poll."""
        key = (round(lat, 2), round(lon, 2), date.today())
        if self._climate and self._climate[0] == key:
            return self._climate[1]
        try:
            climate = await self._fetch_climate(ctx, lat, lon, key[2])
        except (ProviderError, KeyError, TypeError, ValueError, AttributeError) as exc:
            logger.info("climate lookup failed, retrying next poll: %s", exc)
            return None
        self._climate = (key, climate)
        return climate

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return cfg.weather_interval_s

    async def _resolve(self, ctx: ProviderContext) -> tuple[float, float, str]:
        loc = ctx.settings.location
        if loc.latitude is not None and loc.longitude is not None:
            label = loc.label or f"{loc.latitude:.2f}, {loc.longitude:.2f}"
            return loc.latitude, loc.longitude, label
        pinned = _parse_lat_lon(loc.query)
        if pinned is not None:
            return pinned[0], pinned[1], loc.label or loc.query
        data = await ctx.fetch_json(
            _GEOCODE_URL.format(q=urllib.parse.quote(loc.query)), allow_hosts=_ALLOW
        )
        results = data.get("results") if isinstance(data, dict) else None
        if not results:
            raise ProviderError(f"could not geocode {loc.query!r}")
        top = results[0]
        lat, lon = _num(top.get("latitude")), _num(top.get("longitude"))
        if lat is None or lon is None:
            raise ProviderError("geocoder returned no coordinates")
        name = ", ".join(p for p in (top.get("name"), top.get("admin1")) if p)
        return lat, lon, loc.label or name or loc.query

    async def poll(self, ctx: ProviderContext) -> dict[str, Any]:
        lat, lon, place = await self._resolve(ctx)
        data = await ctx.fetch_json(_FORECAST_URL.format(lat=lat, lon=lon), allow_hosts=_ALLOW)
        if not isinstance(data, dict) or "current" not in data:
            raise ProviderError("unexpected Open-Meteo payload shape")
        # Open-Meteo (timezone=auto) returns local wall-clock strings, so the
        # "is this slot still ahead of us" check compares against naive local now.
        now = datetime.now()
        return {
            "current": _parse_current(data.get("current", {})),
            "hourly": _parse_hourly(data.get("hourly", {}), now),
            "forecast": _parse_daily(data.get("daily", {})),
            "climate": await self._climate_for(ctx, lat, lon),
            "coords": {"lat": lat, "lon": lon},
            "place": place,
        }
