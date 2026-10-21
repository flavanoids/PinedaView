# SPDX-License-Identifier: Apache-2.0
"""The Liquid Glass background image: PUT / GET / DELETE and its view revision."""

from __future__ import annotations

import struct
import zlib

import httpx


def _png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes([0, 10, 20, 30, 10, 20, 30]) * 2)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


async def test_wallpaper_round_trip(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/wallpaper")).status_code == 404
    # client.hasWallpaper() (and the mobile /settings page) probe with HEAD.
    assert (await client.head("/api/wallpaper")).status_code == 404

    put = await client.put("/api/wallpaper", files={"file": ("bg.png", _png(), "image/png")})
    assert put.status_code == 204

    got = await client.get("/api/wallpaper")
    assert got.status_code == 200
    assert got.headers["content-type"] == "image/png"
    assert (await client.head("/api/wallpaper")).status_code == 200

    device_id = (await client.post("/api/devices/pair", json={"name": "K"})).json()["id"]
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["wallpaper_rev"] > 0

    assert (await client.delete("/api/wallpaper")).status_code == 204
    assert (await client.delete("/api/wallpaper")).status_code == 404
    assert (await client.get("/api/wallpaper")).status_code == 404


async def test_wallpaper_rejects_non_images(client: httpx.AsyncClient) -> None:
    res = await client.put(
        "/api/wallpaper", files={"file": ("x.png", b"not an image", "image/png")}
    )
    assert res.status_code == 415
