# SPDX-License-Identifier: Apache-2.0
"""Settings → Connect: the status list reflects what's already configured,
the forms check before they save, and saved addresses survive a restart
without touching config.toml."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager

from pinedaview.api import create_app
from pinedaview.config import Settings, load_settings
from pinedaview.connections import load_connections, save_connection
from pinedaview.runtime import Runtime, build_runtime

_ICS = """BEGIN:VCALENDAR
VERSION:2.0
X-WR-CALNAME:Family (Proton)
BEGIN:VEVENT
UID:soccer
SUMMARY:Soccer
DTSTART:20260912T220000Z
DTEND:20260912T233000Z
END:VEVENT
END:VCALENDAR
"""


def _services(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.startswith("https://calendar.proton.me/"):
        return httpx.Response(200, text=_ICS)
    if url == "https://example.com/not-a-calendar":
        return httpx.Response(200, text="<html>hello</html>")
    if url == "http://hass.local:8123/api/config":
        if request.headers.get("authorization") != "Bearer good":
            return httpx.Response(401)
        return httpx.Response(200, json={"location_name": "Casa Pineda"})
    if url == "http://antigua.local:9393/alarms":
        return httpx.Response(200, json=[])
    return httpx.Response(404)


@pytest_asyncio.fixture
async def connect_client(settings: Settings) -> AsyncIterator[tuple[httpx.AsyncClient, Runtime]]:
    runtime = build_runtime(settings, providers=[])
    await runtime.http.aclose()
    runtime.http = httpx.AsyncClient(transport=httpx.MockTransport(_services))
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield http, runtime


def _row(rows: list[dict[str, object]], row_id: str) -> dict[str, object]:
    return next(r for r in rows if r["id"] == row_id)


async def test_fresh_install_lists_everything_disconnected(
    connect_client: tuple[httpx.AsyncClient, Runtime],
) -> None:
    http, _ = connect_client
    rows = (await http.get("/api/connect")).json()
    assert {r["id"] for r in rows} >= {
        "apple-calendar",
        "google-calendar",
        "calendar-links",
        "home-assistant",
        "antigua",
        "cameras",
        "airplay",
        "google-maps",
    }
    assert not any(r["connected"] for r in rows)
    # Google needs its one-time Cloud setup before it can be connected here.
    assert _row(rows, "google-calendar")["available"] is False


async def test_existing_setup_shows_connected(tmp_path: Path) -> None:
    settings = load_settings(
        overrides={
            "state_dir": tmp_path,
            "photos_dir": str(tmp_path / "photos"),
            "api": {"db_path": str(tmp_path / "pineda.db")},
            "config_file": str(tmp_path / "config.toml"),
            "antigua": {"url": "http://antigua.local:9393"},
        }
    )
    runtime = build_runtime(settings, providers=[])
    runtime.secrets.set("google_maps", "k")
    await runtime.http.aclose()
    runtime.http = httpx.AsyncClient(transport=httpx.MockTransport(_services))
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            rows = (await http.get("/api/connect")).json()
    antigua = _row(rows, "antigua")
    assert antigua["connected"] is True
    assert antigua["problem"] is None
    assert _row(rows, "google-maps")["connected"] is True


async def test_calendar_link_is_checked_named_and_shown(
    connect_client: tuple[httpx.AsyncClient, Runtime],
) -> None:
    http, runtime = connect_client
    bad = await http.post(
        "/api/connect/calendar-links", json={"url": "https://example.com/not-a-calendar"}
    )
    assert bad.status_code == 400
    assert "isn't a calendar" in bad.json()["detail"]

    res = await http.post(
        "/api/connect/calendar-links",
        json={"url": "webcal://calendar.proton.me/api/calendar/v1/url/abc/calendar.ics"},
    )
    assert res.status_code == 200
    link = res.json()
    assert link["name"] == "Family (Proton)"  # taken from the feed
    sources = runtime.card_settings["calendar"]["sources"]
    assert sources == [
        {
            "calendarId": link["id"],
            "label": "Family (Proton)",
            "color": None,
            "selected": True,
            "type": "ics",
        }
    ]
    stored = json.loads(runtime.secrets.get("calendar_links") or "[]")
    assert stored[0]["url"].startswith("https://calendar.proton.me/")  # webcal → https

    assert (await http.delete(f"/api/connect/calendar-links/{link['id']}")).status_code == 204
    assert runtime.card_settings["calendar"]["sources"] == []
    assert runtime.secrets.get("calendar_links") is None


async def test_home_assistant_checks_the_token(
    connect_client: tuple[httpx.AsyncClient, Runtime],
) -> None:
    http, runtime = connect_client
    bad = await http.put(
        "/api/connect/home-assistant", json={"url": "hass.local:8123", "token": "nope"}
    )
    assert bad.status_code == 400
    assert runtime.secrets.get("home_assistant") is None

    ok = await http.put(
        "/api/connect/home-assistant", json={"url": "hass.local:8123/", "token": "good"}
    )
    assert ok.status_code == 204
    row = _row((await http.get("/api/connect")).json(), "home-assistant")
    assert row["connected"] is True
    assert row["detail"] == "Casa Pineda"
    assert row["values"] == {"url": "http://hass.local:8123"}  # the token never comes back


async def test_antigua_address_persists_without_config_toml(
    connect_client: tuple[httpx.AsyncClient, Runtime], settings: Settings
) -> None:
    http, runtime = connect_client
    res = await http.put("/api/connect/antigua", json={"url": "antigua.local:9393"})
    assert res.status_code == 204
    assert runtime.settings.antigua.url == "http://antigua.local:9393"
    assert not settings.config_file.exists()

    fresh = load_settings(overrides={"state_dir": settings.state_dir})
    load_connections(fresh)
    assert fresh.antigua.url == "http://antigua.local:9393"


async def test_airplay_refuses_an_unreachable_broker(
    connect_client: tuple[httpx.AsyncClient, Runtime],
) -> None:
    http, runtime = connect_client
    res = await http.put("/api/connect/airplay", json={"host": "127.0.0.1", "port": 1})
    assert res.status_code == 400
    assert runtime.settings.mqtt.enabled is False


def test_connections_overlay_ignores_unknown_fields(settings: Settings) -> None:
    save_connection(settings, "cameras", {"go2rtc": "http://cams:1984", "streams": {"x": "y"}})
    doc = json.loads((settings.state_dir / "connections.json").read_text())
    assert doc == {"cameras": {"go2rtc": "http://cams:1984"}}
