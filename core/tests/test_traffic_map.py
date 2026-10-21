# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import httpx

from pinedaview.config import Settings
from pinedaview.providers.base import ProviderContext
from pinedaview.providers.traffic_cams import CamCache, TrafficCamsProvider
from pinedaview.providers.traffic_map import (
    _HOUSTON,
    _offset_right,
    _short_location,
    build_map,
    generated_at,
    parse_segments,
)
from pinedaview.stores import StoreRegistry

HOME = (29.836, -95.4975)


def _seg(lats: str, lngs: str, direction: str, mph: int, kind: str, location: str) -> str:
    offs = " ".join("0.004" for _ in lats.split())
    return (
        f'SpeedSegments[0] = new SpeedSegment("{lats}","{lngs}","{offs}","{offs}",'
        f'"{direction}",{mph},"3 minutes","2.40","{kind}","1302","1303","{location}",'
        '"51.20","67");\n'
    )


# The shape of TranStar's speed_segments.js: a header stamp, the constructor
# (whose parameter list must not parse as a segment), then one call per row.
_SPEEDS = (
    "// Houston TranStar Speed Segments. Auto-generated on 10/8/2026 1:21:35 PM\n"
    "function SpeedSegment(lats, lngs, latOffsets, lngOffsets, direction, speed)\n{}\n"
    + _seg(
        "29.836 29.836",
        "-95.53 -95.47",
        "EB",
        24,
        "ML",
        "IH-10 Katy Eastbound from Kirkwood to Beltway 8-West",
    )
    + _seg("29.836 29.836", "-95.47 -95.53", "WB", 62, "ML", "IH-10 Katy Westbound from A to B")
    + _seg("29.836 29.836", "-95.53 -95.47", "EB", 10, "HOV", "IH-10 Katy HOV from A to B")
    + _seg("31.0 31.1", "-97.0 -97.1", "NB", 5, "ML", "Far away Northbound from A to B")
    + _seg("29.83 29.84", "-95.50 -95.50", "NB", -1, "ML", "US-290 Northbound from C to D")
)


def test_parse_segments_keeps_main_lanes_only() -> None:
    segs = parse_segments(_SPEEDS)
    assert [s["mph"] for s in segs] == [24, 62, 5, -1]
    assert segs[0]["points"] == [(29.836, -95.53), (29.836, -95.47)]
    assert segs[0]["direction"] == "EB"


def test_generated_at_is_houston_time() -> None:
    stamp = generated_at(_SPEEDS)
    assert stamp == datetime(2026, 10, 8, 13, 21, 35, tzinfo=_HOUSTON)


def test_short_location() -> None:
    assert (
        _short_location("IH-10 Katy Eastbound from Kirkwood to Beltway 8-West", "EB")
        == "I-10 EB · Kirkwood → BW-8 West"
    )
    assert _short_location("Westpark Tollway", "WB") == "Westpark Tollway WB"


def test_offset_goes_to_the_right_of_travel() -> None:
    # Screen y points down: heading east (+x), the right-hand side is +y.
    east = _offset_right([(0.0, 0.0), (10.0, 0.0)], 1.0)
    assert east == [(0.0, 1.0), (10.0, 1.0)]
    west = _offset_right([(10.0, 0.0), (0.0, 0.0)], 1.0)
    assert west == [(10.0, -1.0), (0.0, -1.0)]


def _map(incidents: list[dict[str, Any]] | None = None, age_s: float = 60) -> dict[str, Any]:
    updated = datetime(2026, 10, 8, 13, 21, 35, tzinfo=_HOUSTON)
    return build_map(
        parse_segments(_SPEEDS),
        incidents or [],
        HOME,
        updated,
        updated + timedelta(seconds=age_s),
    )


def test_build_map_draws_nearby_segments_slowest_on_top() -> None:
    m = _map()
    # The far-away segment is off the mosaic; the rest are drawn, slowest last.
    assert [s["level"] for s in m["segments"]] == ["none", "fast", "crawl"]
    assert m["slowest"] == {"label": "I-10 EB · Kirkwood → BW-8 West", "mph": 24, "delay": 67}
    assert len(m["basemap"]) == len(m["roads"]) == 9
    assert "/tile/12/" in m["basemap"][0]
    assert all(abs(v) <= 17 for v in m["focus"].values())
    assert m["stale"] is False
    assert _map(age_s=15 * 60)["stale"] is True


def test_build_map_marks_active_incidents_only() -> None:
    incidents = [
        {"lat": "29.836", "lng": "-95.5", "desc": "Accident", "status": "Verified"},
        {"lat": "29.837", "lng": "-95.5", "desc": "Stall", "status": "Detected"},
        {"lat": "29.838", "lng": "-95.5", "desc": "Accident", "status": "Cleared"},
        {"lat": "nope", "lng": "-95.5", "desc": "Stall", "status": "Verified"},
    ]
    marks = _map(incidents)["incidents"]
    assert [m["crash"] for m in marks] == [True, False]


def test_incident_classification_keywords() -> None:
    incidents = [
        {"lat": "29.836", "lng": "-95.5", "desc": "Major Crash", "status": "Verified"},
        {"lat": "29.836", "lng": "-95.5", "desc": "Fatal Collision", "status": "Verified"},
        {"lat": "29.836", "lng": "-95.5", "desc": "Overturned Semi", "status": "Verified"},
        {"lat": "29.836", "lng": "-95.5", "desc": "Vehicle Fire", "status": "Verified"},
        {"lat": "29.836", "lng": "-95.5", "desc": "Mainlanes Closed", "status": "Verified"},
        {"lat": "29.836", "lng": "-95.5", "desc": "High Water on Freeway", "status": "Verified"},
        {"lat": "29.836", "lng": "-95.5", "desc": "Debris", "status": "Verified"},
    ]
    marks = _map(incidents)["incidents"]
    assert [m["kind"] for m in marks] == [
        "crash",
        "crash",
        "crash",
        "crash",
        "closure",
        "flood",
        "stall",
    ]
    assert [m["crash"] for m in marks] == [True, True, True, True, False, False, False]


def test_camera_projections_and_alerts() -> None:
    cams = [{"id": "407", "label": "US-290 @ Pinemont", "lat": 29.836, "lng": -95.5}]
    incidents = [
        {
            "lat": "29.836",
            "lng": "-95.5",
            "desc": "Major Crash",
            "location": "at Kirkwood",
            "status": "Verified",
        }
    ]
    updated = datetime(2026, 10, 8, 13, 21, 35, tzinfo=_HOUSTON)
    m = build_map(
        parse_segments(_SPEEDS),
        incidents,
        HOME,
        updated,
        updated,
        cameras=cams,
    )
    assert len(m["cameras"]) == 1
    assert m["cameras"][0]["id"] == "407"
    assert m["cameras"][0]["label"] == "US-290 @ Pinemont"
    assert len(m["alerts"]) >= 2
    assert m["alerts"][0]["type"] == "slow"
    assert "24 mph (+67m)" in m["alerts"][0]["text"]
    assert m["alerts"][1]["type"] == "crash"
    assert "Major Crash · at Kirkwood" in m["alerts"][1]["text"]


def test_no_slowest_when_everything_flows() -> None:
    fast = _seg(
        "29.836 29.836", "-95.53 -95.47", "EB", 60, "ML", "IH-10 Katy Eastbound from A to B"
    )
    m = build_map(parse_segments(fast), [], HOME, None, datetime.now(_HOUSTON))
    assert m["slowest"] is None
    assert m["stale"] is True  # no stamp to vouch for it


def _ctx(settings: Settings, handler: Any, **card: Any) -> ProviderContext:
    values = {"cameras": [], "weekdayWindow": "00:00-23:59", "weekendWindow": "00:00-23:59"}
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ProviderContext(
        settings,
        StoreRegistry(),
        card_settings={"traffic": {**values, **card}},
        client=client,
    )


def _transtar(request: httpx.Request) -> httpx.Response:
    if request.url.path.endswith("speed_segments.js"):
        now_str = datetime.now(_HOUSTON).strftime("%m/%d/%Y %I:%M:%S %p")
        speeds_fresh = _SPEEDS.replace("10/8/2026 1:21:35 PM", now_str)
        return httpx.Response(200, text=speeds_fresh)
    if request.url.path.endswith("incidents_json.js"):
        incident = {"lat": "29.836", "lng": "-95.5", "desc": "Accident", "status": "Verified"}
        return httpx.Response(200, text=json.dumps({"incidents": [incident]}))
    if request.url.path.endswith("cctvSnapshots_out.js"):
        camera = (
            "camera = new CctvCamera('US-290 @ Pinemont','0','US-290','PINEMONT',"
            "'29.836','-95.5','S','407.jpg','True','1','0');\n"
            "addCctvCamera(0, camera);\n"
        )
        return httpx.Response(200, text=camera)
    return httpx.Response(200, text="<html>not found</html>")


async def test_provider_adds_the_map_centred_on_the_card_setting(settings: Settings) -> None:
    provider = TrafficCamsProvider(cache=CamCache())
    value = await provider.poll(
        _ctx(settings, _transtar, mapCenter="29.836, -95.4975", cameras=["407"])
    )
    assert value is not None
    m = value["map"]
    assert m is not None
    assert m["slowest"]["mph"] == 24
    assert len(m["incidents"]) == 1
    assert len(m["cameras"]) == 1
    assert m["cameras"][0]["id"] == "407"


async def test_map_retains_last_good_when_transtar_is_down(settings: Settings) -> None:
    def down(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    provider = TrafficCamsProvider(cache=CamCache())
    # Initial good poll
    good_ctx = _ctx(settings, _transtar, mapCenter="29.836, -95.4975")
    value1 = await provider.poll(good_ctx)
    assert value1 is not None
    assert value1["map"] is not None
    assert value1["map"]["stale"] is False

    # Subsequent poll when TranStar fails retains last-good map with stale=True
    down_ctx = _ctx(settings, down, mapCenter="29.836, -95.4975")
    value2 = await provider.poll(down_ctx)
    assert value2 is not None
    assert value2["map"] is not None
    assert value2["map"]["stale"] is True
    assert value2["map"]["slowest"]["mph"] == 24


async def test_map_is_none_when_transtar_is_down_initially(settings: Settings) -> None:
    def down(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    provider = TrafficCamsProvider(cache=CamCache())
    value = await provider.poll(_ctx(settings, down, mapCenter="29.836, -95.4975"))
    assert value is not None
    assert value["map"] is None


async def test_bad_map_center_falls_back_to_location(settings: Settings) -> None:
    provider = TrafficCamsProvider(cache=CamCache())
    settings.location.latitude, settings.location.longitude = HOME
    value = await provider.poll(_ctx(settings, _transtar, mapCenter="not a place"))
    assert value is not None
    assert value["map"] is not None


async def test_custom_map_zoom_setting(settings: Settings) -> None:
    provider = TrafficCamsProvider(cache=CamCache())
    value = await provider.poll(_ctx(settings, _transtar, mapCenter="29.836, -95.4975", mapZoom=11))
    assert value is not None
    assert value["map"]["zoom"] == 11
    assert "/tile/11/" in value["map"]["basemap"][0]
