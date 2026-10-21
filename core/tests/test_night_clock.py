# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import httpx


async def test_night_clock_switches(client: httpx.AsyncClient) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "Kitchen"})).json()["id"]
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["night_clock"] is True and view["night_clock_hold"] is False

    r = await client.patch(f"/api/devices/{device_id}", json={"night_clock_hold": True})
    assert r.json()["night_clock_hold"] is True
    assert (await client.get(f"/api/view/{device_id}")).json()["night_clock_hold"] is True

    # Off wins: a held clock with the night clock switched off isn't shown.
    await client.patch(f"/api/devices/{device_id}", json={"night_clock": False})
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["night_clock"] is False and view["night_clock_hold"] is False


async def test_night_clock_font_and_colour(client: httpx.AsyncClient) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "Kitchen"})).json()["id"]
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["night_clock_font"] is None and view["night_clock_color"] is None

    patch = {"night_clock_font": "geist", "night_clock_color": "#7FD1FF"}
    assert (await client.patch(f"/api/devices/{device_id}", json=patch)).status_code == 200
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["night_clock_font"] == "geist" and view["night_clock_color"] == "#7FD1FF"

    # "" goes back to the clock's own; junk is refused.
    for bad in ({"night_clock_font": "comic_sans"}, {"night_clock_color": "pink"}):
        assert (await client.patch(f"/api/devices/{device_id}", json=bad)).status_code == 422
    await client.patch(
        f"/api/devices/{device_id}", json={"night_clock_font": "", "night_clock_color": ""}
    )
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["night_clock_font"] is None and view["night_clock_color"] is None


async def test_clock_only_can_show_photos(client: httpx.AsyncClient) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "Kitchen"})).json()["id"]
    assert (await client.get(f"/api/view/{device_id}")).json()["night_clock_photo"] is False

    r = await client.patch(f"/api/devices/{device_id}", json={"night_clock_photo": True})
    assert r.json()["night_clock_photo"] is True
    assert (await client.get(f"/api/view/{device_id}")).json()["night_clock_photo"] is True

    # It's part of the Night section's reset.
    await client.post("/api/config/reset", json={"section": "night", "device_id": device_id})
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["night_clock_photo"] is False


async def test_photo_clock_settings_live_on_the_screen(client: httpx.AsyncClient) -> None:
    device_id = (await client.post("/api/devices/pair", json={"name": "Kitchen"})).json()["id"]
    assert (await client.get(f"/api/view/{device_id}")).json()["photo_clock"] is None

    # Missing fields take their defaults.
    r = await client.patch(
        f"/api/devices/{device_id}", json={"photo_clock": {"glass": "frosted", "opacity": 0.2}}
    )
    assert r.status_code == 200
    pc = (await client.get(f"/api/view/{device_id}")).json()["photo_clock"]
    assert pc["glass"] == "frosted" and pc["opacity"] == 0.2 and pc["size"] == "l"

    for bad in ({"opacity": 1.5}, {"glass": "stained"}, {"font": "comic_sans"}):
        r = await client.patch(f"/api/devices/{device_id}", json={"photo_clock": bad})
        assert r.status_code == 422

    # Copied to another screen, and cleared by the Night section's reset.
    other = (await client.post("/api/devices/pair", json={"name": "Hall"})).json()["id"]
    await client.post(f"/api/devices/{other}/copy-from", json={"source": device_id})
    assert (await client.get(f"/api/view/{other}")).json()["photo_clock"]["opacity"] == 0.2

    await client.post("/api/config/reset", json={"section": "night", "device_id": device_id})
    assert (await client.get(f"/api/view/{device_id}")).json()["photo_clock"] is None
