# SPDX-License-Identifier: Apache-2.0
"""Indoor climate — the home's AC telemetry server (ac-data-server on
primary-server, port 8321), read-only.

The server exposes the resideo-smart-cooling skill's ``/current`` payload:
latest logged indoor temp / humidity / setpoint / outdoor temp. Polling the
``latest`` row means the card updates within ~90 s of each 30-minute engine
tick. Values arrive in Fahrenheit and are normalized to Celsius here, the
same convention the weather provider uses — the client formats per unit.
"""

from __future__ import annotations

from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext, ProviderError

_URL = "http://192.0.2.171:8321/current"
_ALLOW_HOSTS = ["192.0.2.171"]


def _f_to_c(value: Any) -> float | None:
    try:
        return round((float(value) - 32) * 5 / 9, 1)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_current(data: dict[str, Any]) -> dict[str, Any]:
    latest = data.get("latest")
    if not isinstance(latest, dict):
        raise ProviderError("unexpected ac-data-server payload shape")
    runtime = data.get("runtime")
    runtime_30 = _int(runtime.get("runtime_pct_30m")) if isinstance(runtime, dict) else None
    parsed = {
        "tempC": _f_to_c(latest.get("indoor_temp")),
        "humidity": _int(latest.get("humidity_pct")),
        "setpointC": _f_to_c(latest.get("current_setpoint")),
        "outdoorC": _f_to_c(latest.get("weather_outdoor")),
        "runtimePct": runtime_30,
        "sampledAt": latest.get("time", ""),
    }
    if parsed["tempC"] is None:
        raise ProviderError("ac-data-server returned no indoor temp")
    return parsed


class IndoorClimateProvider(Provider):
    key = "indoorClimate"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return cfg.indoor_climate_interval_s

    async def poll(self, ctx: ProviderContext) -> dict[str, Any] | None:
        data = await ctx.fetch_json(_URL, allow_hosts=_ALLOW_HOSTS)
        if not isinstance(data, dict) or "latest" not in data:
            raise ProviderError("unexpected ac-data-server payload shape")
        return _parse_current(data)
