# SPDX-License-Identifier: Apache-2.0
"""Air quality — Open-Meteo, keyless. Follows the weather location by reading
its resolved coordinates out of the ``weather`` store."""

from __future__ import annotations

from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError

_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    "?latitude={lat:.4f}&longitude={lon:.4f}"
    "&current=us_aqi,pm2_5,pm10,ozone"
)


def _coords(ctx: ProviderContext) -> tuple[float, float] | None:
    loc = ctx.settings.location
    if loc.latitude is not None and loc.longitude is not None:
        return loc.latitude, loc.longitude
    weather = ctx.store_value("weather")
    coords = weather.get("coords") if isinstance(weather, dict) else None
    if isinstance(coords, dict) and "lat" in coords and "lon" in coords:
        return float(coords["lat"]), float(coords["lon"])
    return None


class AirQualityProvider(Provider):
    key = "airQuality"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return cfg.air_quality_interval_s

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        coords = _coords(ctx)
        if coords is None:
            return None
        data = await ctx.fetch_json(_URL.format(lat=coords[0], lon=coords[1]))
        current = data.get("current") if isinstance(data, dict) else None
        if not isinstance(current, dict):
            raise ProviderError("no 'current' block in Open-Meteo response")
        return {
            "usAqi": current.get("us_aqi"),
            "pm25": current.get("pm2_5"),
            "pm10": current.get("pm10"),
            "ozone": current.get("ozone"),
        }
