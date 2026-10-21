# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import datetime
from email.utils import formatdate
from typing import Any

import httpx
import pytest

from pinedaview.config import Settings
from pinedaview.providers.base import ProviderContext, ProviderError
from pinedaview.providers.traffic_cams import (
    CamCache,
    TrafficCamsProvider,
    camera_ids,
    parse_catalogue,
    valid_file,
)
from pinedaview.stores import StoreRegistry


def _cam(name: str, road: str, place: str, path: str, frames: str, pause: str) -> str:
    fields = [name, "0", road, place, "29.8", "-95.4", "South", path, "True", frames, pause]
    quoted = ",".join(f"'{f}'" for f in fields)
    return f"camera = new CctvCamera({quoted});\naddCctvCamera(0, camera);\n"


# The shape of TranStar's cctvSnapshots_out.js, including its commented-out
# example line (fewer fields — must be ignored).
_CATALOGUE = (
    "var cctvCameras = new Array();\n"
    "// camera = new CctvCamera('10 Katy at Silber', '1','','','/images/210.jpg');\n"
    + _cam("290 NORTHWEST @ PINEMONT", "US-290 Northwest", "PINEMONT", "407.jpg", "1", "0")
    + _cam("10 Katy @ West BW-8", "IH-10 Katy", "West BW-8", "324.jpg", "3", "300")
)
ALWAYS = "00:00-23:59"
NEVER = "03:00-03:01"


def _jpeg(body: bytes, age_s: float = 30) -> httpx.Response:
    return httpx.Response(
        200,
        content=body,
        headers={
            "content-type": "image/jpeg",
            "last-modified": formatdate(time.time() - age_s, usegmt=True),
        },
    )


Handler = Callable[[httpx.Request], httpx.Response]


def _ctx(settings: Settings, handler: Handler, **card: Any) -> ProviderContext:
    values = {"cameras": ["407"], "weekdayWindow": ALWAYS, "weekendWindow": ALWAYS, **card}
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return ProviderContext(
        settings, StoreRegistry(), card_settings={"traffic": values}, client=client
    )


async def _poll(provider: TrafficCamsProvider, ctx: ProviderContext) -> dict[str, Any]:
    value = await provider.poll(ctx)
    assert value is not None
    return value


def _catalogue_or(route: Mapping[str, Handler | httpx.Response]) -> Handler:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("cctvSnapshots_out.js"):
            return httpx.Response(200, text=_CATALOGUE)
        name = request.url.path.rsplit("/", 1)[-1]
        found = route.get(name)
        if found is None:
            # TranStar's "missing" answer: a 200 HTML error page, not a 404.
            return httpx.Response(200, text="<html>not found</html>")
        return found(request) if callable(found) else found

    return handle


def test_parse_catalogue_labels_and_frames() -> None:
    cams = parse_catalogue(_CATALOGUE)
    assert set(cams) == {"407", "324"}
    assert cams["407"].label == "US-290 @ Pinemont"
    assert cams["407"].frames == 1
    assert cams["324"].label == "I-10 @ West BW-8"  # mixed case left alone
    assert (cams["324"].frames, cams["324"].frame_ms) == (3, 300)


@pytest.mark.parametrize(
    ("roadway", "location", "label"),
    [
        ("US-290 Northwest", "PINEMONT", "US-290 @ Pinemont"),
        ("IH-610 West Loop", "WESTHEIMER", "I-610 @ Westheimer"),
        ("IH-10 Katy Managed Lane", "Bunker Hill", "I-10 @ Bunker Hill"),
        ("SH-99 Lanier Parkway-East", "FM 1960", "SH-99 @ FM 1960"),
        ("Beltway 8-West", "Clay", "BW-8 @ Clay"),
        ("Westpark Tollway", "Gessner", "Westpark Tollway @ Gessner"),
        ("Westheimer", "Kirby", "Westheimer @ Kirby"),
        ("IH-45 North", "N MAIN ST", "I-45 @ N Main St"),
    ],
)
def test_labels_shorten_numbered_routes_only(roadway: str, location: str, label: str) -> None:
    text = _cam("x", roadway, location, "1.jpg", "1", "0")
    assert parse_catalogue(text)["1"].label == label


def test_camera_ids_keep_digits_only_and_dedupe() -> None:
    assert camera_ids(["407", 408, " 614 ", "407", "../etc", ""]) == ["407", "408", "614"]
    assert camera_ids("407") == []


def test_valid_file() -> None:
    assert valid_file("407.jpg") and valid_file("324-6.jpg")
    assert not valid_file("../407.jpg") and not valid_file("407.png")


async def test_outside_window_publishes_inactive_and_empties_cache(settings: Settings) -> None:
    cache = CamCache()
    provider = TrafficCamsProvider(cache=cache)
    active = _ctx(settings, _catalogue_or({"407.jpg": _jpeg(b"a")}))
    assert (await _poll(provider, active))["active"] is True
    assert cache.names() == {"407.jpg"}

    def no_network(_: httpx.Request) -> httpx.Response:
        raise AssertionError("fetched outside the window")

    quiet = _ctx(settings, no_network, weekdayWindow=NEVER, weekendWindow=NEVER)
    assert await _poll(provider, quiet) == {"active": False, "cams": []}
    assert cache.names() == set()


async def test_poll_publishes_labelled_cams_and_serves_bytes(settings: Settings) -> None:
    cache = CamCache()
    ctx = _ctx(
        settings,
        _catalogue_or({"407.jpg": _jpeg(b"pinemont"), "999.jpg": _jpeg(b"unknown")}),
        cameras=["407", "999"],
    )
    value = await _poll(TrafficCamsProvider(cache=cache), ctx)

    first, second = value["cams"]
    assert first["label"] == "US-290 @ Pinemont"
    assert first["src"].startswith("/api/cams/407.jpg?v=")
    assert first["frames"] == [] and first["stale"] is False
    assert datetime.fromisoformat(first["capturedAt"]).tzinfo is not None
    assert second["label"] == "Camera 999"  # not in the catalogue
    assert cache.get("407.jpg") == b"pinemont"


async def test_refresh_sends_if_modified_since_and_keeps_copy_on_304(
    settings: Settings,
) -> None:
    cache = CamCache()
    provider = TrafficCamsProvider(cache=cache)
    await _poll(provider, _ctx(settings, _catalogue_or({"407.jpg": _jpeg(b"v1")})))

    seen: list[str | None] = []

    def not_modified(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("if-modified-since"))
        return httpx.Response(304)

    value = await _poll(provider, _ctx(settings, _catalogue_or({"407.jpg": not_modified})))
    assert seen and seen[0] is not None
    assert value["cams"][0]["id"] == "407"
    assert cache.get("407.jpg") == b"v1"


async def test_new_capture_replaces_old_one_cache_never_grows(settings: Settings) -> None:
    cache = CamCache()
    provider = TrafficCamsProvider(cache=cache)
    await _poll(provider, _ctx(settings, _catalogue_or({"407.jpg": _jpeg(b"old", age_s=200)})))
    await _poll(provider, _ctx(settings, _catalogue_or({"407.jpg": _jpeg(b"new", age_s=10)})))
    assert cache.names() == {"407.jpg"}
    assert cache.get("407.jpg") == b"new"


async def test_removed_camera_is_evicted(settings: Settings) -> None:
    cache = CamCache()
    provider = TrafficCamsProvider(cache=cache)
    route = {"407.jpg": _jpeg(b"a"), "408.jpg": _jpeg(b"b")}
    await _poll(provider, _ctx(settings, _catalogue_or(route), cameras=["407", "408"]))
    await _poll(provider, _ctx(settings, _catalogue_or(route), cameras=["408"]))
    assert cache.names() == {"408.jpg"}


async def test_old_capture_goes_amber_then_drops(settings: Settings) -> None:
    provider = TrafficCamsProvider(cache=CamCache())
    amber = await _poll(provider, _ctx(settings, _catalogue_or({"407.jpg": _jpeg(b"a", 8 * 60)})))
    assert amber["cams"][0]["stale"] is True

    provider = TrafficCamsProvider(cache=CamCache())
    gone = await _poll(provider, _ctx(settings, _catalogue_or({"407.jpg": _jpeg(b"a", 20 * 60)})))
    assert gone["cams"] == []


async def test_server_error_keeps_last_good_image(settings: Settings) -> None:
    cache = CamCache()
    provider = TrafficCamsProvider(cache=cache)
    await _poll(provider, _ctx(settings, _catalogue_or({"407.jpg": _jpeg(b"good")})))

    def down(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    value = await _poll(provider, _ctx(settings, down))
    assert [c["id"] for c in value["cams"]] == ["407"]
    assert cache.get("407.jpg") == b"good"


async def test_flipbook_skips_missing_frame(settings: Settings) -> None:
    cache = CamCache()
    # 324 has 3 frames in the catalogue; frame 1 is TranStar's HTML error page.
    route = {"324.jpg": _jpeg(b"still"), "324-2.jpg": _jpeg(b"f2"), "324-3.jpg": _jpeg(b"f3")}
    value = await _poll(
        TrafficCamsProvider(cache=cache), _ctx(settings, _catalogue_or(route), cameras=["324"])
    )
    cam = value["cams"][0]
    assert [f.split("?")[0] for f in cam["frames"]] == [
        "/api/cams/324-2.jpg",
        "/api/cams/324-3.jpg",
    ]
    assert cam["frameMs"] == 300
    assert cache.names() == {"324.jpg", "324-2.jpg", "324-3.jpg"}


async def test_single_surviving_frame_is_not_a_flipbook(settings: Settings) -> None:
    route = {"324.jpg": _jpeg(b"still"), "324-2.jpg": _jpeg(b"f2")}
    value = await _poll(
        TrafficCamsProvider(cache=CamCache()), _ctx(settings, _catalogue_or(route), cameras=["324"])
    )
    assert value["cams"][0]["frames"] == []


async def test_catalogue_failure_falls_back_to_plain_labels(settings: Settings) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".js"):
            return httpx.Response(503)
        return _jpeg(b"a")

    value = await _poll(TrafficCamsProvider(cache=CamCache()), _ctx(settings, handle))
    assert value["cams"][0]["label"] == "Camera 407"


async def test_needs_http_client(settings: Settings) -> None:
    ctx = ProviderContext(
        settings,
        StoreRegistry(),
        card_settings={"traffic": {"weekdayWindow": ALWAYS, "weekendWindow": ALWAYS}},
    )
    with pytest.raises(ProviderError):
        await _poll(TrafficCamsProvider(cache=CamCache()), ctx)


async def test_api_serves_cached_image_and_404s_otherwise(client: httpx.AsyncClient) -> None:
    from pinedaview.providers.traffic_cams import CAM_CACHE, _Image

    CAM_CACHE.put("407.jpg", _Image(b"\xff\xd8jpeg", None, time.time()))
    try:
        ok = await client.get("/api/cams/407.jpg?v=1")
        assert ok.status_code == 200
        assert ok.headers["content-type"] == "image/jpeg"
        assert ok.content == b"\xff\xd8jpeg"
        assert (await client.get("/api/cams/408.jpg")).status_code == 404
        assert (await client.get("/api/cams/secrets.json")).status_code == 404
    finally:
        CAM_CACHE.keep_only(set())
