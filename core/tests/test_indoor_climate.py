# SPDX-License-Identifier: Apache-2.0
"""Indoor-climate provider — polls the home AC telemetry server."""

from __future__ import annotations

from typing import Any

import pytest

from pinedaview.config import Settings
from pinedaview.providers.base import ProviderError
from pinedaview.providers.indoor_climate import IndoorClimateProvider
from tests.conftest import FakeContext


def _ac_current() -> dict[str, Any]:
    return {
        "latest": {
            "indoor_temp": 74.0,
            "humidity_pct": 65,
            "current_setpoint": 73.0,
            "weather_outdoor": 83.0,
            "time": "2026-09-10T09:30",
        },
        "runtime": {"runtime_pct_30m": 30},
        "thermal": {"time_constant_hours": 2.5},
        "server_time": "2026-09-10T09:31:00",
    }


async def test_indoor_climate_parses_to_si(settings: Settings) -> None:
    ctx = FakeContext(settings, responses=[_ac_current()])
    value = await IndoorClimateProvider().poll(ctx)

    assert value is not None
    assert value["tempC"] == 23.3  # 74F
    assert value["humidity"] == 65
    assert value["setpointC"] == 22.8  # 73F
    assert value["outdoorC"] == 28.3  # 83F
    assert value["runtimePct"] == 30
    assert value["sampledAt"] == "2026-09-10T09:30"
    assert "192.0.2.171" in ctx.requested_urls[0]


async def test_indoor_climate_rejects_junk(settings: Settings) -> None:
    ctx = FakeContext(settings, responses=[{"nope": True}])
    with pytest.raises(ProviderError):
        await IndoorClimateProvider().poll(ctx)


async def test_indoor_climate_rejects_missing_temp(settings: Settings) -> None:
    payload = _ac_current()
    payload["latest"]["indoor_temp"] = None
    ctx = FakeContext(settings, responses=[payload])
    with pytest.raises(ProviderError):
        await IndoorClimateProvider().poll(ctx)
