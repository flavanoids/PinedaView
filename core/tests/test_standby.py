# SPDX-License-Identifier: Apache-2.0
"""Standby mode: phones go to the primary while it's up; saving flags the sync."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview.runtime import Runtime
from pinedaview.standby import CHANGED_FLAG, is_saving_write

PRIMARY = "http://primary.test:8090"


@pytest_asyncio.fixture
async def standby(runtime: Runtime) -> AsyncIterator[tuple[httpx.AsyncClient, dict[str, bool]]]:
    from pinedaview.api import create_app

    state = {"up": True}

    def handle(req: httpx.Request) -> httpx.Response:
        assert str(req.url) == PRIMARY + "/api/health"
        return httpx.Response(200 if state["up"] else 503)

    runtime.settings.standby.primary = PRIMARY
    runtime.http = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http, state


async def test_phones_go_to_the_primary_while_it_is_up(
    standby: tuple[httpx.AsyncClient, dict[str, bool]],
) -> None:
    http, _ = standby
    r = await http.get("/menu?screen=abc")
    assert r.status_code == 307 and r.headers["location"] == PRIMARY + "/menu?screen=abc"
    assert (await http.get("/api/menu-url")).json() == {"url": PRIMARY + "/menu"}


async def test_with_the_primary_down_this_box_serves(
    runtime: Runtime, standby: tuple[httpx.AsyncClient, dict[str, bool]]
) -> None:
    http, state = standby
    state["up"] = False
    assert (await http.get("/menu")).status_code == 200
    assert not (runtime.settings.state_dir / CHANGED_FLAG).exists()

    await http.post("/api/now-showing", json={"device_id": "x", "card": "photo", "item": "a"})
    assert not (runtime.settings.state_dir / CHANGED_FLAG).exists()  # nothing saved

    r = await http.post("/api/profiles", json={"name": "Den"})
    assert r.status_code == 201
    assert (runtime.settings.state_dir / CHANGED_FLAG).exists()


def test_what_counts_as_saving() -> None:
    assert is_saving_write("PUT", "/api/card-settings/clock")
    assert is_saving_write("POST", "/api/photos")
    assert not is_saving_write("GET", "/api/photos")
    assert not is_saving_write("POST", "/api/alarms")
    assert not is_saving_write("DELETE", "/api/takeover")
    assert not is_saving_write("POST", "/api/devices/abc/identify")
