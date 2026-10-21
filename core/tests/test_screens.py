# SPDX-License-Identifier: Apache-2.0
"""Screens: a new display waits as "New screen!" until it's kept from the
phone menu; the kiosk is always the same screen; nobody's leftovers go."""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview.registry import DEFAULT_PROFILE_ID, Registry
from pinedaview.runtime import Runtime

KIOSK_IP = "192.0.2.161"
KIOSK_ID = "3f862842aee4086a"


@pytest_asyncio.fixture
async def kiosk_runtime(runtime: Runtime) -> Runtime:
    runtime.settings.control.host = KIOSK_IP
    runtime.settings.control.screen = KIOSK_ID
    return runtime


@pytest_asyncio.fixture
async def app(kiosk_runtime: Runtime) -> AsyncIterator[object]:
    from pinedaview.api import create_app

    made = create_app(kiosk_runtime)
    async with LifespanManager(made):
        yield made


def _from(app: object, ip: str) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 5000))  # type: ignore[arg-type]
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _pair(http: httpx.AsyncClient, **body: object) -> dict[str, Any]:
    r = await http.post("/api/devices/pair", json={"name": "Screen", **body})
    assert r.status_code == 201
    return cast(dict[str, Any], r.json())


async def test_a_new_tablet_waits_until_kept(app: object) -> None:
    async with _from(app, "192.0.2.27") as http:
        ipad = await _pair(http, viewport_w=820, viewport_h=1180, kind="iPad")
        assert ipad["kept"] is False and ipad["kind"] == "iPad"
        view = (await http.get(f"/api/view/{ipad['id']}")).json()
        assert view["welcome"] is True

        r = await http.post(
            f"/api/devices/{ipad['id']}/keep",
            json={"name": "iPad", "colour": "teal", "shows": "cameras"},
        )
        assert r.status_code == 200
        kept = r.json()
        assert kept["kept"] and kept["name"] == "iPad" and kept["colour"] == "teal"
        assert kept["profile_id"] != DEFAULT_PROFILE_ID  # its own theme and cards
        assert [i["card"] for i in kept["grid"]["items"]] == ["home-cams"]
        view = (await http.get(f"/api/view/{ipad['id']}")).json()
        assert view["welcome"] is False and view["screen_name"] == "iPad"


async def test_keep_refuses_an_unknown_colour(app: object) -> None:
    async with _from(app, "192.0.2.27") as http:
        d = await _pair(http)
        r = await http.post(
            f"/api/devices/{d['id']}/keep", json={"name": "X", "colour": "plaid", "shows": "cards"}
        )
        assert r.status_code == 422


async def test_shows_switches_between_photo_clock_and_cards(app: object) -> None:
    async with _from(app, "192.0.2.27") as http:
        d = await _pair(http, viewport_w=600, viewport_h=960)
        await http.post(
            f"/api/devices/{d['id']}/keep", json={"name": "Tab", "colour": "violet", "shows": "mix"}
        )
        got = (await http.get("/api/devices")).json()
        mix = next(x for x in got if x["id"] == d["id"])
        assert mix["grid"]["cols"] == 6 and mix["grid"]["items"][0]["w"] == 6  # tall: cams on top

        r = await http.put(f"/api/devices/{d['id']}/shows", json={"shows": "photo"})
        assert r.json()["night_clock_hold"] and r.json()["night_clock_photo"]
        r = await http.put(f"/api/devices/{d['id']}/shows", json={"shows": "cards"})
        assert not r.json()["night_clock_hold"] and r.json()["grid"] is None


async def test_remove_sends_it_back_to_new_screen(app: object, kiosk_runtime: Runtime) -> None:
    async with _from(app, "192.0.2.27") as http:
        d = await _pair(http, viewport_w=820, viewport_h=1180, kind="iPad")
        kept = (
            await http.post(
                f"/api/devices/{d['id']}/keep",
                json={"name": "iPad", "colour": "teal", "shows": "photo"},
            )
        ).json()
        assert (await http.post(f"/api/devices/{d['id']}/forget")).status_code == 204
        back = await kiosk_runtime.devices.device(d["id"])
        assert back is not None
        assert not back.kept and back.name == "Screen" and not back.night_clock_hold
        assert back.kind == "iPad" and back.viewport_w == 820
        assert await kiosk_runtime.devices.profile(kept["profile_id"]) is None


async def test_the_kiosk_is_always_the_same_screen(app: object) -> None:
    async with _from(app, KIOSK_IP) as http:
        first = await _pair(http, viewport_w=2048, viewport_h=1280)
        again = await _pair(http, viewport_w=2048, viewport_h=1280)
        assert first["id"] == again["id"] == KIOSK_ID
        assert again["kept"] is True
        assert (await http.post(f"/api/devices/{KIOSK_ID}/forget")).status_code == 409
        listed = (await http.get("/api/devices")).json()
        assert [d["home"] for d in listed if d["id"] == KIOSK_ID] == [True]
        assert (await http.get("/api/control")).json()["snapshot"] is True


async def test_settle_decides_old_screens_once_and_forgets_strays(tmp_path: Path) -> None:
    reg = Registry(tmp_path / "r.db")
    await reg.init()
    kiosk = await reg.pair_device("Screen")
    named = await reg.pair_device("Hall")
    old = await reg.pair_device("Screen")
    recent = await reg.pair_device("Screen")
    week_ago = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    with sqlite3.connect(tmp_path / "r.db") as conn:
        conn.execute("UPDATE devices SET kept = NULL")  # from before screens were kept
        conn.execute(
            "UPDATE devices SET last_seen = ?, paired_at = ? WHERE id = ?",
            (week_ago, week_ago, old.id),
        )
    assert await reg.settle_screens(kiosk.id) == 1
    left = {d.id: d.kept for d in await reg.devices()}
    assert left == {kiosk.id: True, named.id: True, recent.id: False}


async def test_pop_ups_are_the_kitchens_alone(app: object) -> None:
    recipe = {"title": "Tea", "ingredients": [{"items": ["1 bag"]}], "steps": ["Steep."]}
    async with _from(app, KIOSK_IP) as kitchen, _from(app, "192.0.2.27") as tab:
        await _pair(kitchen)
        ipad = await _pair(tab)
        await tab.post(
            f"/api/devices/{ipad['id']}/keep",
            json={"name": "iPad", "colour": "teal", "shows": "cards"},
        )
        assert (await tab.put("/api/takeover", json={"card": recipe})).status_code == 200
        assert (await kitchen.get(f"/api/view/{KIOSK_ID}")).json()["takeover"] is not None
        assert (await tab.get(f"/api/view/{ipad['id']}")).json()["takeover"] is None


async def test_a_tablet_can_take_camera_pop_ups(app: object, kiosk_runtime: Runtime) -> None:
    kiosk_runtime.settings.cameras.streams = {"front_door": "T8210"}
    door = {"kind": "camera", "camera": "front_door", "title": "Front door"}
    recipe = {"title": "Tea", "ingredients": [{"items": ["1 bag"]}], "steps": ["Steep."]}
    async with _from(app, "192.0.2.27") as tab:
        ipad = await _pair(tab)
        await tab.post(
            f"/api/devices/{ipad['id']}/keep",
            json={"name": "iPad", "colour": "teal", "shows": "cameras"},
        )
        r = await tab.patch(f"/api/devices/{ipad['id']}", json={"popups": "cameras"})
        assert r.json()["popups"] == "cameras"
        await tab.put("/api/takeover", json={"card": recipe})
        assert (await tab.get(f"/api/view/{ipad['id']}")).json()["takeover"] is None
        shown = await tab.put("/api/takeover", json={"card": door})
        assert shown.status_code == 200, shown.text
        assert (await tab.get(f"/api/view/{ipad['id']}")).json()["takeover"] is not None


async def test_turning_a_mix_tablet_turns_its_layout(app: object) -> None:
    async with _from(app, "192.0.2.27") as tab:
        d = await _pair(tab, viewport_w=600, viewport_h=960)
        await tab.post(
            f"/api/devices/{d['id']}/keep", json={"name": "Tab", "colour": "rose", "shows": "mix"}
        )
        r = await tab.put(f"/api/devices/{d['id']}/viewport", json={"w": 960, "h": 600})
        assert r.status_code == 204
        turned = next(x for x in (await tab.get("/api/devices")).json() if x["id"] == d["id"])
        assert (turned["viewport_w"], turned["viewport_h"]) == (960, 600)
        assert turned["grid"]["items"][0]["h"] == 6  # wide: the cameras down the left


async def test_the_same_tablet_again_takes_over_its_old_setup(
    app: object, kiosk_runtime: Runtime
) -> None:
    async with _from(app, "192.0.2.27") as tab:
        first = await _pair(tab, kind="Android tablet")
        await tab.post(
            f"/api/devices/{first['id']}/keep",
            json={"name": "Onn", "colour": "violet", "shows": "cameras"},
        )
        await tab.patch(f"/api/devices/{first['id']}", json={"popups": "cameras"})
        again = await _pair(tab, kind="Android tablet")  # a home-screen icon's own storage
        r = await tab.post(f"/api/devices/{again['id']}/replace", json={"old": first["id"]})
        assert r.status_code == 200
        took = r.json()
        assert took["id"] == again["id"] and took["kept"] and took["name"] == "Onn"
        assert took["popups"] == "cameras" and took["grid"]["items"][0]["card"] == "home-cams"
        assert await kiosk_runtime.devices.device(first["id"]) is None
        refused = await tab.post(f"/api/devices/{again['id']}/replace", json={"old": KIOSK_ID})
        assert refused.status_code in (404, 409)


async def test_a_forgotten_id_comes_back_as_a_new_screen(app: object) -> None:
    async with _from(app, "192.0.2.27") as tab:
        view = await tab.get("/api/view/0123456789abcdef")
        assert view.status_code == 200 and view.json()["welcome"] is True
        assert (await tab.get("/api/view/not-an-id")).status_code == 404
