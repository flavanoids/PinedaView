# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import httpx
from asgi_lifespan import LifespanManager

from pinedaview.config import load_settings
from pinedaview.runtime import Runtime, build_runtime


def _png(colour: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes([0, *colour, *colour]) * 2)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


async def _commute_enabled_client(
    tmp_path: Path,
) -> tuple[httpx.AsyncClient, Runtime, LifespanManager]:
    # "commute" ships in Settings.disabled_cards by default (see config.py) —
    # it polls the billed Google Directions API. These tests exercise the
    # secret-gating behaviour that keeps it off even when re-enabled, so they
    # opt back in explicitly rather than relying on the shared fixtures.
    settings = load_settings(
        overrides={
            "state_dir": tmp_path,
            "photos_dir": str(tmp_path / "photos"),
            "location": {"query": "Houston"},
            "api": {"db_path": str(tmp_path / "pineda.db")},
            "config_file": str(tmp_path / "config.toml"),
            "disabled_cards": [],
        }
    )
    runtime = build_runtime(settings, providers=[])
    from pinedaview.api import create_app

    app = create_app(runtime)
    manager = LifespanManager(app)
    await manager.__aenter__()
    transport = httpx.ASGITransport(app=app)
    http = httpx.AsyncClient(transport=transport, base_url="http://test")
    return http, runtime, manager


async def test_commute_ships_disabled_by_default(client: httpx.AsyncClient) -> None:
    # See config.py: Settings.disabled_cards defaults to ["commute"].
    cards = {c["id"]: c for c in (await client.get("/api/cards")).json()}
    assert "commute" not in cards


async def test_list_cards_reports_status(tmp_path: Path) -> None:
    http, _runtime, manager = await _commute_enabled_client(tmp_path)
    try:
        cards = {c["id"]: c for c in (await http.get("/api/cards")).json()}
        assert cards["clock"]["status"] == "ready"
        assert cards["commute"]["status"] == "blocked"
        assert "maps" in cards["commute"]["reason"]
        assert cards["weather"]["has_provider"] is True
    finally:
        await http.aclose()
        await manager.__aexit__(None, None, None)


async def test_health_counts_cards(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/health")).json()
    assert body["cards_total"] >= 8
    assert 0 < body["cards_ready"] <= body["cards_total"]


async def test_card_settings_round_trip(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/cards/weather/settings")).json()["values"] == {
        "showFeelsLike": True
    }
    updated = await client.put(
        "/api/cards/weather/settings", json={"values": {"showFeelsLike": False, "bogus": 1}}
    )
    assert updated.json()["values"] == {"showFeelsLike": False}
    assert (await client.get("/api/cards/nope/settings")).status_code == 404


async def test_secret_add_unblocks_commute(tmp_path: Path) -> None:
    http, runtime, manager = await _commute_enabled_client(tmp_path)
    try:
        assert runtime.cards.status("commute").ready is False
        assert (await http.put("/api/secrets/google_maps", json={"value": "k"})).status_code == 204
        assert (await http.get("/api/secrets")).json()["names"] == ["google_maps"]
        assert runtime.cards.status("commute").ready is True
        assert (await http.delete("/api/secrets/google_maps")).status_code == 204
        assert (await http.delete("/api/secrets/google_maps")).status_code == 404
    finally:
        await http.aclose()
        await manager.__aexit__(None, None, None)


async def test_photo_upload_list_delete(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/photos", files={"file": ("a.png", _png(), "image/png")})
    assert resp.status_code == 201
    name = resp.json()["name"]
    assert [p["name"] for p in (await client.get("/api/photos")).json()] == [name]
    r1 = await client.get(f"/api/photos/{name}")
    assert r1.status_code == 200
    assert "public, max-age=86400" in r1.headers.get("cache-control", "")
    r2 = await client.get(f"/api/photos/{name}/display")
    assert r2.status_code == 200
    assert "public, max-age=86400" in r2.headers.get("cache-control", "")
    r3 = await client.get(f"/api/photos/{name}/thumb")
    assert r3.status_code == 200
    assert "public, max-age=86400" in r3.headers.get("cache-control", "")
    assert (await client.delete(f"/api/photos/{name}")).status_code == 204
    assert (await client.delete(f"/api/photos/{name}")).status_code == 404


async def test_photo_upload_rejects_junk(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/photos", files={"file": ("a.png", b"nope", "image/png")})
    assert resp.status_code == 415


async def test_photo_reorder_and_rotate(client: httpx.AsyncClient) -> None:
    names = []
    for colour in ((10, 20, 30), (40, 50, 60), (70, 80, 90)):
        r = await client.post(
            "/api/photos", files={"file": (f"{colour[0]}.png", _png(colour), "image/png")}
        )
        names.append(r.json()["name"])

    reversed_names = list(reversed(names))
    res = await client.post("/api/photos/reorder", json={"names": reversed_names})
    assert res.status_code == 200
    assert [p["name"] for p in res.json()] == reversed_names
    assert [p["name"] for p in (await client.get("/api/photos")).json()] == reversed_names

    rot = await client.post(f"/api/photos/{names[0]}/rotate?degrees=90")
    assert rot.status_code == 200
    assert rot.json()["rotation"] == 90


async def test_photo_becomes_the_wallpaper(client: httpx.AsyncClient) -> None:
    name = (
        await client.post("/api/photos", files={"file": ("w.png", _png(), "image/png")})
    ).json()["name"]
    assert (await client.get("/api/wallpaper")).status_code == 404
    assert (await client.post(f"/api/photos/{name}/use-as-wallpaper")).status_code == 204
    got = await client.get("/api/wallpaper")
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/jpeg"
    assert (await client.post("/api/photos/nope.png/use-as-wallpaper")).status_code == 404
