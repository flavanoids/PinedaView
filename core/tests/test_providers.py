# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from pinedaview.config import Settings
from pinedaview.providers import (
    AirQualityProvider,
    AlertsProvider,
    MoonProvider,
    WeatherProvider,
    default_providers,
)
from pinedaview.providers.base import ProviderError
from pinedaview.providers.commute import CommuteProvider, _during_rush
from pinedaview.providers.moon import compute
from pinedaview.providers.radar import RadarProvider
from pinedaview.secrets import SecretStore
from tests.conftest import FakeContext, load_fixture


def test_default_providers_have_unique_keys() -> None:
    keys = [p.key for p in default_providers()]
    assert keys == sorted(set(keys), key=keys.index)
    assert "weather" in keys and "dailyContent" in keys


# ── weather ───────────────────────────────────────────────────────────────────


def _weather_ctx(settings: Settings) -> FakeContext:
    return FakeContext(
        settings,
        responses=[
            load_fixture("open_meteo_geocode.json"),
            load_fixture("open_meteo_forecast.json"),
        ],
    )


async def test_weather_geocodes_then_parses_to_si(settings: Settings) -> None:
    ctx = _weather_ctx(settings)
    value = await WeatherProvider().poll(ctx)

    assert "geocoding-api" in ctx.requested_urls[0]
    assert value["current"]["tempC"] == pytest.approx(33.6, abs=0.1)
    assert value["current"]["desc"] == "Mainly Clear"
    assert value["current"]["code"] == "116"
    assert value["current"]["windDir"] == "SSW"
    assert value["current"]["isDay"] is True
    assert value["coords"] == {"lat": 29.7633, "lon": -95.3633}
    assert value["place"] == "Houston, Texas"


async def test_weather_hourly_is_the_next_24_hours(settings: Settings) -> None:
    value = await WeatherProvider().poll(_weather_ctx(settings))
    hours = value["hourly"]
    assert [h["hour"] for h in hours] == list(range(24))
    assert hours[0]["isDay"] is False  # 00:00 slot
    assert hours[6]["isDay"] is True  # 06:00 slot
    assert hours[15]["precip"] == 40  # 15:00 slot


async def test_weather_daily_outlook(settings: Settings) -> None:
    value = await WeatherProvider().poll(_weather_ctx(settings))
    days = value["forecast"]
    assert len(days) == 4
    assert days[0]["desc"] == "Overcast"
    assert days[1]["code"] == "353"  # WMO 80 → light showers
    assert days[0]["sunrise"] == "7:04 AM"
    assert days[0]["sunset"] == "7:33 PM"
    assert days[2]["precip"] == 47


async def test_weather_skips_geocode_for_lat_lon_query(settings: Settings) -> None:
    settings.location.query = "29.7604,-95.3698"
    ctx = FakeContext(settings, responses=[load_fixture("open_meteo_forecast.json")])
    value = await WeatherProvider().poll(ctx)
    assert "geocoding-api" not in ctx.requested_urls[0]
    assert value["coords"] == {"lat": 29.7604, "lon": -95.3698}


async def test_weather_skips_geocode_for_pinned_coords(settings: Settings) -> None:
    settings.location.latitude = 40.0
    settings.location.longitude = -73.0
    ctx = FakeContext(settings, responses=[load_fixture("open_meteo_forecast.json")])
    value = await WeatherProvider().poll(ctx)
    assert [u for u in ctx.requested_urls if "open-meteo" in u] == ctx.requested_urls[:1]
    assert value["coords"] == {"lat": 40.0, "lon": -73.0}


async def test_weather_rejects_junk(settings: Settings) -> None:
    ctx = FakeContext(
        settings,
        responses=[load_fixture("open_meteo_geocode.json"), {"nope": True}],
    )
    with pytest.raises(ProviderError):
        await WeatherProvider().poll(ctx)


async def test_weather_raises_when_geocode_is_empty(settings: Settings) -> None:
    ctx = FakeContext(settings, responses=[{"results": []}])
    with pytest.raises(ProviderError):
        await WeatherProvider().poll(ctx)


async def test_weather_label_override_wins(settings: Settings) -> None:
    settings.location.label = "Home"
    value = await WeatherProvider().poll(_weather_ctx(settings))
    assert value["place"] == "Home"


def test_weather_hourly_drops_slots_already_past() -> None:
    from datetime import datetime

    from pinedaview.providers.weather import _parse_hourly

    block = {
        "time": [f"2026-09-10T{h:02d}:00" for h in range(24)],
        "temperature_2m": list(range(24)),
        "weather_code": [0] * 24,
        "precipitation_probability": [0] * 24,
        "uv_index": [0] * 24,
        "is_day": [1] * 24,
    }
    hours = _parse_hourly(block, datetime(2026, 9, 10, 13, 30))
    assert [h["hour"] for h in hours] == list(range(13, 24))


def _climate_ctx(settings: Settings, *acis: Any) -> FakeContext:
    settings.location.query = "29.7604,-95.3698"
    return FakeContext(settings, responses=[load_fixture("open_meteo_forecast.json"), *acis])


_STATIONS = {"meta": [{"sids": ["IAH 3"], "ll": [-95.36, 29.98]}]}
_RECORDS = {
    "meta": {"name": "Houston Area", "valid_daterange": [["1888-07-01", "2026-10-11"]]},
    "smry": [[["96", "1991-10-12"]], [["42", "1977-10-12"]]],
}
_NORMALS = {"data": [["2026-10-12", "84", "62"]]}


async def test_weather_climate_from_the_threaded_city_record(settings: Settings) -> None:
    ctx = _climate_ctx(settings, _STATIONS, _RECORDS, _NORMALS)
    climate = (await WeatherProvider().poll(ctx))["climate"]
    assert "IAHthr" in urllib.parse.unquote(ctx.requested_urls[2])
    assert climate == {
        "normalHighC": 28.9,
        "normalLowC": 16.7,
        "recordHighC": 35.6,
        "recordHighYear": 1991,
        "recordLowC": 5.6,
        "recordLowYear": 1977,
        "since": 1888,
        "station": "Houston Area",
    }


async def test_weather_climate_falls_back_past_an_unknown_thread(settings: Settings) -> None:
    ctx = _climate_ctx(settings, _STATIONS, {"error": "Unknown sId"}, _RECORDS, _NORMALS)
    climate = (await WeatherProvider().poll(ctx))["climate"]
    assert '"sid":"IAH"' in urllib.parse.unquote(ctx.requested_urls[3])
    assert climate["recordLowYear"] == 1977


async def test_weather_climate_is_none_outside_the_us(settings: Settings) -> None:
    ctx = _climate_ctx(settings, {"meta": []})
    assert (await WeatherProvider().poll(ctx))["climate"] is None


async def test_weather_climate_is_fetched_once_a_day(settings: Settings) -> None:
    provider = WeatherProvider()
    await provider.poll(_climate_ctx(settings, _STATIONS, _RECORDS, _NORMALS))
    again = _climate_ctx(settings)
    assert (await provider.poll(again))["climate"]["since"] == 1888
    assert len(again.requested_urls) == 1


async def test_weather_survives_a_climate_failure(settings: Settings) -> None:
    value = await WeatherProvider().poll(_climate_ctx(settings))  # ACIS answers nothing
    assert value["climate"] is None
    assert value["current"]["tempC"] is not None


# ── air quality ───────────────────────────────────────────────────────────────


async def test_air_quality_defers_without_coords(settings: Settings) -> None:
    ctx = FakeContext(settings, responses=[load_fixture("open_meteo.json")])
    assert await AirQualityProvider().poll(ctx) is None


async def test_air_quality_reads_weather_coords(settings: Settings) -> None:
    ctx = FakeContext(
        settings,
        responses=[load_fixture("open_meteo.json")],
        stores={"weather": {"coords": {"lat": 1.0, "lon": 2.0}}},
    )
    value = await AirQualityProvider().poll(ctx)
    assert value == {"usAqi": 42, "pm25": 8.1, "pm10": 12.0, "ozone": 30.0}
    assert "latitude=1.0000" in ctx.requested_urls[0]


async def test_air_quality_uses_explicit_config_coords(settings: Settings) -> None:
    settings.location.latitude = 40.0
    settings.location.longitude = -73.0
    ctx = FakeContext(settings, responses=[load_fixture("open_meteo.json")])
    assert await AirQualityProvider().poll(ctx) is not None


# ── commute ──────────────────────────────────────────────────────────────────

_DIRECTIONS_RESPONSE = {
    "status": "OK",
    "routes": [
        {
            "legs": [
                {
                    "duration": {"value": 1200},
                    "duration_in_traffic": {"value": 1500},
                }
            ]
        }
    ],
}


async def test_commute_passes_a_stop_s_avoid_param(settings: Settings, tmp_path: Path) -> None:
    secrets = SecretStore(tmp_path)
    secrets.set("google_maps", "k")
    ctx = FakeContext(
        settings,
        responses=[_DIRECTIONS_RESPONSE],
        secrets=secrets,
        card_settings={
            "commute": {"stops": [{"label": "Work", "address": "123 Main St", "avoid": "tolls"}]}
        },
    )
    value = await CommuteProvider().poll(ctx)
    assert value is not None
    assert value["routes"] == [
        {
            "label": "Work",
            "address": "123 Main St",
            "minutes": 25,
            "delayMinutes": 5,
            "status": "OK",
        }
    ]
    assert value["duringRush"] is False
    assert "avoid=tolls" in ctx.requested_urls[0]


async def test_commute_omits_avoid_when_a_stop_has_none(settings: Settings, tmp_path: Path) -> None:
    secrets = SecretStore(tmp_path)
    secrets.set("google_maps", "k")
    ctx = FakeContext(
        settings,
        responses=[_DIRECTIONS_RESPONSE],
        secrets=secrets,
        card_settings={"commute": {"stops": [{"label": "Work", "address": "x"}]}},
    )
    await CommuteProvider().poll(ctx)
    assert "avoid=" not in ctx.requested_urls[0]


async def test_commute_returns_no_routes_without_a_key(settings: Settings) -> None:
    ctx = FakeContext(settings, card_settings={"commute": {"stops": []}})
    assert await CommuteProvider().poll(ctx) is None


_DELAYED_RESPONSE = {
    "status": "OK",
    "routes": [
        {
            "legs": [
                {
                    "duration": {"value": 600},
                    "duration_in_traffic": {"value": 1800},
                }
            ]
        }
    ],
}


def test_during_rush_handles_a_wrapping_window_and_bad_input() -> None:
    from datetime import datetime

    noon = datetime(2026, 1, 1, 12, 0)
    assert _during_rush("06:00-09:00", datetime(2026, 1, 1, 7, 30)) is True
    assert _during_rush("06:00-09:00", noon) is False
    # wraps past midnight
    assert _during_rush("22:00-05:00", datetime(2026, 1, 1, 23, 0)) is True
    assert _during_rush("22:00-05:00", datetime(2026, 1, 1, 12, 0)) is False
    assert _during_rush(None, noon) is False
    assert _during_rush("garbage", noon) is False


async def test_commute_sorts_by_delay_during_the_rush_window(
    settings: Settings, tmp_path: Path
) -> None:
    secrets = SecretStore(tmp_path)
    secrets.set("google_maps", "k")
    ctx = FakeContext(
        settings,
        # calm route first, delayed route second — sort should flip that
        responses=[_DIRECTIONS_RESPONSE, _DELAYED_RESPONSE],
        secrets=secrets,
        card_settings={
            "commute": {
                "stops": [
                    {"label": "Calm", "address": "a"},
                    {"label": "Delayed", "address": "b"},
                ],
                "rushWindow": "00:00-23:59",  # always "now", any time tests run
            }
        },
    )
    value = await CommuteProvider().poll(ctx)
    assert value is not None
    assert value["duringRush"] is True
    assert [r["label"] for r in value["routes"]] == ["Delayed", "Calm"]


async def test_commute_leaves_order_alone_outside_the_rush_window(
    settings: Settings, tmp_path: Path
) -> None:
    secrets = SecretStore(tmp_path)
    secrets.set("google_maps", "k")
    ctx = FakeContext(
        settings,
        responses=[_DIRECTIONS_RESPONSE, _DELAYED_RESPONSE],
        secrets=secrets,
        card_settings={
            "commute": {
                "stops": [
                    {"label": "Calm", "address": "a"},
                    {"label": "Delayed", "address": "b"},
                ],
                "rushWindow": "00:00-00:00",  # empty window, never "now"
            }
        },
    )
    value = await CommuteProvider().poll(ctx)
    assert value is not None
    assert value["duringRush"] is False
    assert [r["label"] for r in value["routes"]] == ["Calm", "Delayed"]


# ── alerts ────────────────────────────────────────────────────────────────────


async def test_alerts_picks_highest_severity(settings: Settings) -> None:
    ctx = FakeContext(
        settings,
        responses=[load_fixture("nws_alerts.json")],
        stores={"weather": {"coords": {"lat": 29.8, "lon": -95.5}}},
    )
    value = await AlertsProvider().poll(ctx)
    assert value is not None
    assert value["count"] == 2
    assert value["top"]["severity"] == "Severe"
    assert value["top"]["event"] == "Heat Advisory"


async def test_alerts_defers_without_point(settings: Settings) -> None:
    ctx = FakeContext(settings, responses=[load_fixture("nws_alerts.json")])
    assert await AlertsProvider().poll(ctx) is None


async def test_alerts_empty_feed_is_not_an_error(settings: Settings) -> None:
    settings.location.latitude = 51.5
    settings.location.longitude = -0.1
    ctx = FakeContext(settings, responses=[{"features": []}])
    value = await AlertsProvider().poll(ctx)
    assert value == {"count": 0, "top": None}


# ── moon ──────────────────────────────────────────────────────────────────────


async def test_moon_needs_no_network(settings: Settings) -> None:
    ctx = FakeContext(settings)
    value = await MoonProvider().poll(ctx)
    assert 0.0 <= value["phase"] < 1.0
    assert 0.0 <= value["illumination"] <= 100.0
    assert value["nextPhase"]["name"] in {
        "New Moon",
        "First Quarter",
        "Full Moon",
        "Last Quarter",
    }


# ── radar ─────────────────────────────────────────────────────────────────────

_RAINVIEWER_INDEX = {
    "radar": {
        "past": [
            {"time": 1, "path": "/v2/radar/1"},
            {"time": 2, "path": "/v2/radar/2"},
        ]
    }
}


async def test_radar_builds_a_tile_mosaic_for_the_configured_point(settings: Settings) -> None:
    settings.location.latitude = 29.76
    settings.location.longitude = -95.37
    ctx = FakeContext(settings, responses=[_RAINVIEWER_INDEX])
    value = await RadarProvider().poll(ctx)
    assert value is not None
    assert value["cols"] == 3
    assert len(value["frames"]) == 1  # newest only — a still image, no loop
    tiles = value["frames"][0]["tiles"]
    assert len(tiles) == 9  # 3x3
    assert tiles[0].startswith("https://tilecache.rainviewer.com/v2/radar/2/512/7/")
    assert tiles[0].endswith("/4/1_1.png")
    assert len(value["basemap"]) == 9
    assert "arcgisonline.com" in value["basemap"][0]
    assert value["basemap"][0].endswith("/tile/7/51/29")  # {z}/{y}/{x}
    assert value["roads"][0].endswith("/World_Transportation/MapServer/tile/7/51/29")
    assert -14 <= value["focus"]["dx"] <= 14
    assert -14 <= value["focus"]["dy"] <= 14
    assert value["generated_at"].startswith("1970-01-01T00:00:02")
    assert "api.rainviewer.com" in ctx.requested_urls[0]
    assert value["storms"] == []  # storm feed unavailable → radar still stands


def _storm(lon: float, lat: float, **props: object) -> dict[str, object]:
    base: dict[str, object] = {
        "valid": datetime.now(UTC).isoformat(),
        "drct": 270,  # moving *from* the west, i.e. heading east
        "sknt": 20,
        "max_dbz": 50,
        "poh": 0,
        "meso": "NONE",
        "tvs": "NONE",
    }
    return {
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {**base, **props},
    }


async def test_radar_projects_nearby_storm_cells_as_track_arrows(settings: Settings) -> None:
    settings.location.latitude = 29.76
    settings.location.longitude = -95.37
    storms = {
        "features": [
            _storm(-95.37, 29.76, poh=60),  # at home, heading east, hail likely
            _storm(-95.38, 29.77, max_dbz=40),  # same cell from a second radar
            _storm(-95.0, 30.0, drct=180, meso="MESO", max_dbz=45),  # rotating, heading north
            _storm(-80.0, 40.0),  # far outside the mosaic
            _storm(-95.2, 29.8, valid="2020-01-01T00:00:00Z"),  # stale radar
            {"properties": {}},  # malformed
        ]
    }
    ctx = FakeContext(settings, responses=[_RAINVIEWER_INDEX, storms])
    value = await RadarProvider().poll(ctx)
    assert value is not None
    assert "mesonet.agron.iastate.edu" in ctx.requested_urls[1]
    home, rotating = value["storms"]
    assert home["hail"] and not home["rotation"]
    assert home["mph"] == 23
    assert home["x2"] > home["x"] and home["y2"] == pytest.approx(home["y"], abs=0.1)
    # The home cell sits where the focus shift says the location is.
    assert home["x"] == pytest.approx(50 - value["focus"]["dx"], abs=0.1)
    assert rotating["rotation"] and not rotating["hail"]
    assert rotating["y2"] < rotating["y"]  # heading north = up the map


async def test_radar_reads_weather_coords_as_a_fallback(settings: Settings) -> None:
    ctx = FakeContext(
        settings,
        responses=[_RAINVIEWER_INDEX],
        stores={"weather": {"coords": {"lat": 1.0, "lon": 2.0}}},
    )
    value = await RadarProvider().poll(ctx)
    assert value is not None and len(value["frames"]) == 1


async def test_radar_defers_without_a_point(settings: Settings) -> None:
    ctx = FakeContext(settings, responses=[_RAINVIEWER_INDEX])
    assert await RadarProvider().poll(ctx) is None


async def test_radar_rejects_an_empty_frame_list(settings: Settings) -> None:
    settings.location.latitude = 29.76
    settings.location.longitude = -95.37
    ctx = FakeContext(settings, responses=[{"radar": {"past": []}}])
    with pytest.raises(ProviderError):
        await RadarProvider().poll(ctx)


def test_moon_known_full_moon() -> None:
    from datetime import UTC, datetime

    # 2000-01-21 was a full moon (~15 days after the reference new moon).
    result = compute(datetime(2000, 1, 21, 4, 40, tzinfo=UTC))
    assert result["name"] == "Full Moon"
    assert result["illumination"] > 98


def test_weather_low_rain_chance_days_read_dry() -> None:
    from pinedaview.providers.weather import _parse_daily

    block = {
        "time": ["2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"],
        "weather_code": [80, 61, 95, 80],
        "precipitation_probability_max": [8, 3, 9, 13],
    }
    days = _parse_daily(block)
    assert [d["desc"] for d in days] == [
        "Partly Cloudy",
        "Overcast",
        "Partly Cloudy",
        "Light Showers",
    ]
