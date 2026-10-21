# SPDX-License-Identifier: Apache-2.0
"""Active weather alerts — US National Weather Service, keyless.

Needs a point. Uses ``location.latitude``/``longitude`` if set, otherwise the
coordinates wttr.in resolved into the ``weather`` store. Outside the US the feed
simply returns nothing, which is a valid empty result, not an error.
"""

from __future__ import annotations

from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError

_URL = "https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
_SEVERITY_ORDER = ("Extreme", "Severe", "Moderate", "Minor", "Unknown")


def _point(ctx: ProviderContext) -> tuple[float, float] | None:
    loc = ctx.settings.location
    if loc.latitude is not None and loc.longitude is not None:
        return loc.latitude, loc.longitude
    weather = ctx.store_value("weather")
    coords = weather.get("coords") if isinstance(weather, dict) else None
    if isinstance(coords, dict) and "lat" in coords and "lon" in coords:
        return float(coords["lat"]), float(coords["lon"])
    return None


def _rank(severity: str) -> int:
    return (
        _SEVERITY_ORDER.index(severity) if severity in _SEVERITY_ORDER else len(_SEVERITY_ORDER) - 1
    )


def _top(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_rank = len(_SEVERITY_ORDER)
    for feature in features:
        props = feature.get("properties", {})
        rank = _rank(props.get("severity", "Unknown"))
        if rank < best_rank:
            best_rank = rank
            best = {
                "severity": props.get("severity", "Unknown"),
                "event": props.get("event", "Alert"),
                "headline": props.get("headline", ""),
            }
    return best


class AlertsProvider(Provider):
    key = "alerts"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return cfg.alerts_interval_s

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        point = _point(ctx)
        if point is None:
            return None
        data = await ctx.fetch_json(
            _URL.format(lat=point[0], lon=point[1]),
            headers={"Accept": "application/geo+json"},
        )
        features = data.get("features") if isinstance(data, dict) else None
        if not isinstance(features, list):
            raise ProviderError("no 'features' array in NWS response")
        return {"count": len(features), "top": _top(features)}
