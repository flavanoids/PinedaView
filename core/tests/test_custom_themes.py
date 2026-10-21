# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import httpx

from pinedaview.themes import CustomColours, custom_theme, ink_for

_COLOURS = {
    "label": "Lake house",
    "stage": "#10202a",
    "accent": "#FFB000",
    "weather": "#1f5f7a",
    "clock": "#2a3d4f",
    "affirmation": "#4d6a5a",
    "phrase": "#344c63",
}


def test_text_colour_follows_the_background() -> None:
    assert ink_for("#000000") == "#f7f2ea"
    assert ink_for("#ffffff") == "#221d1a"
    assert ink_for("#f3d9d2", "#e8aebe") == "#221d1a"


def test_custom_theme_fills_in_the_rest() -> None:
    theme = custom_theme("custom-x", CustomColours(**_COLOURS))
    assert theme.custom and theme.night is None
    assert theme.accent == "#ffb000"
    assert theme.on_stage == "#f7f2ea"
    assert theme.cards["forecast"] == theme.cards["clock"]
    assert "nowPlaying" in theme.cards


async def test_make_edit_use_and_delete(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/themes/custom", json=_COLOURS)
    assert r.status_code == 201
    name = r.json()["name"]
    assert name.startswith("custom-")
    listed = (await client.get("/api/themes")).json()["themes"]
    assert any(t["name"] == name and t["label"] == "Lake house" for t in listed)

    rev = (await client.get("/api/view/" + await _pair(client))).json()["theme_rev"]
    r = await client.put(f"/api/themes/custom/{name}", json={**_COLOURS, "label": "Lake"})
    assert r.json()["label"] == "Lake"
    assert (await client.get("/api/view/" + await _pair(client))).json()["theme_rev"] > rev

    await client.patch("/api/profiles/default", json={"theme": name})
    assert (await client.delete(f"/api/themes/custom/{name}")).status_code == 409
    await client.patch("/api/profiles/default", json={"theme": "blush"})
    assert (await client.delete(f"/api/themes/custom/{name}")).status_code == 204
    assert (await client.delete(f"/api/themes/custom/{name}")).status_code == 404
    assert (await client.delete("/api/themes/custom/blush")).status_code == 404


async def test_rejects_bad_colours(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/themes/custom", json={**_COLOURS, "stage": "red"})
    assert r.status_code == 422
    r = await client.post("/api/themes/custom", json={**_COLOURS, "label": ""})
    assert r.status_code == 422


async def test_a_theme_can_come_with_a_font(client: httpx.AsyncClient) -> None:
    assert custom_theme("custom-x", CustomColours(**_COLOURS)).font is None
    r = await client.post("/api/themes/custom", json={**_COLOURS, "font": "young_serif"})
    name = r.json()["name"]
    listed = (await client.get("/api/themes")).json()["themes"]
    assert next(t for t in listed if t["name"] == name)["font"] == "young_serif"
    # "" goes back to the usual type.
    r = await client.put(f"/api/themes/custom/{name}", json={**_COLOURS, "font": ""})
    assert r.json()["font"] is None
    r = await client.post("/api/themes/custom", json={**_COLOURS, "font": "comic_sans"})
    assert r.status_code == 422


async def _pair(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/devices/pair", json={"name": "Kitchen"})
    return str(r.json()["id"])
