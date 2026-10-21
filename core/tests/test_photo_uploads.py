# SPDX-License-Identifier: Apache-2.0
"""The guest photo drop-off: the /upload page and the public POST /api/photos."""

from __future__ import annotations

import struct
import zlib
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview.config import Settings, load_settings
from pinedaview.runtime import build_runtime


def _png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes([0, 200, 120, 60, 200, 120, 60]) * 2)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


async def test_upload_page_is_served(client: httpx.AsyncClient) -> None:
    res = await client.get("/upload")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Add photos" in res.text
    assert "/api/photos" in res.text


async def test_menu_page_has_photo_management_and_trashcan_animation(
    client: httpx.AsyncClient,
) -> None:
    res = await client.get("/menu")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "manage-photos-btn" in res.text
    assert "Manage photos" in res.text
    assert "photo-delete-tpl" in res.text
    assert "trash-anim" in res.text
    assert "del-badge" in res.text


@pytest_asyncio.fixture
async def write_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    settings: Settings = load_settings(
        overrides={
            "state_dir": str(tmp_path),
            "photos_dir": str(tmp_path / "photos"),
            "api": {"db_path": str(tmp_path / "p.db"), "write_token": "sekret"},
            "config_file": str(tmp_path / "config.toml"),
        }
    )
    from pinedaview.api import create_app

    app = create_app(build_runtime(settings, providers=[]))
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def test_guests_can_upload_without_the_write_token(write_client: httpx.AsyncClient) -> None:
    res = await write_client.post("/api/photos", files={"file": ("guest.png", _png(), "image/png")})
    assert res.status_code == 201
    name = res.json()["name"]

    # ...but editing and deleting still need the token.
    assert (await write_client.delete(f"/api/photos/{name}")).status_code == 401
    ok = await write_client.delete(
        f"/api/photos/{name}", headers={"authorization": "Bearer sekret"}
    )
    assert ok.status_code == 204


async def test_other_writes_still_need_the_token(write_client: httpx.AsyncClient) -> None:
    assert (await write_client.patch("/api/profiles/default", json={})).status_code == 401
