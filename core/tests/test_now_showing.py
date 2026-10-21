# SPDX-License-Identifier: Apache-2.0
"""What's on screen right now (for a voice assistant), and mirrored timers."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import httpx
from PIL import Image

from pinedaview.broadcast import Broadcaster
from pinedaview.now_showing import NowShowingStore
from pinedaview.runtime import Runtime
from pinedaview.timers import SyncedTimer, TimerService


def _jpeg_taken(when: str) -> bytes:
    img = Image.new("RGB", (8, 8), (10, 20, 30))
    exif = img.getexif()
    exif[0x0132] = when  # DateTime, "YYYY:MM:DD HH:MM:SS"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def _seed_daily(runtime: Runtime) -> None:
    runtime.stores.get_or_create("dailyContent", stale_after_s=600).publish(
        {
            "affirmations": [
                {"text": "When they go low, we go high.", "author": "Michelle Obama", "year": 2016}
            ],
            "word": {
                "english": "Honestly, I don't know",
                "note": "la neta = the truth",
                "languages": [{"code": "es", "text": "La neta, no sé", "pron": "lah NEH-tah"}],
            },
        }
    )


def test_store_prefers_named_device_else_latest() -> None:
    store = NowShowingStore()
    store.report("kiosk", "photo", "a.jpg")
    store.report("phone", "photo", "b.jpg")
    assert store.get("photo", "kiosk").item == "a.jpg"  # type: ignore[union-attr]
    assert store.get("photo").item == "b.jpg"  # type: ignore[union-attr]
    assert store.get("quote") is None
    assert store.get("photo", "nobody") is None


async def test_now_showing_round_trip(runtime: Runtime, client: httpx.AsyncClient) -> None:
    runtime.settings.disabled_cards = ["commute"]  # the phrase card opted back in
    _seed_daily(runtime)
    photo = runtime.photos.add("beach.jpg", _jpeg_taken("2019:06:14 19:02:11"))

    for card, item in (("photo", photo.name), ("quote", "When they go low, we go high.")):
        resp = await client.post(
            "/api/now-showing", json={"device_id": "kiosk", "card": card, "item": item}
        )
        assert resp.status_code == 204

    body = (await client.get("/api/now-showing", params={"device_id": "kiosk"})).json()
    # The camera's own wall clock, not shifted by any zone.
    assert body["photo"]["taken_local"] == "2019-06-14T19:02:11"
    assert body["quote"]["author"] == "Michelle Obama"
    assert body["quote"]["year"] == 2016
    assert body["phrase"] == {
        "english": "Honestly, I don't know",
        "spanish": "La neta, no sé",
        "pron": "lah NEH-tah",
        "note": "la neta = the truth",
    }


async def test_retired_phrase_card_is_not_showing(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    _seed_daily(runtime)  # the word of the day still exists; no screen shows it
    assert (await client.get("/api/now-showing")).json()["phrase"] is None


async def test_now_showing_empty(client: httpx.AsyncClient) -> None:
    body = (await client.get("/api/now-showing")).json()
    assert body == {"photo": None, "quote": None, "phrase": None, "look": None}


async def test_photo_without_exif_has_no_date(runtime: Runtime, client: httpx.AsyncClient) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    photo = runtime.photos.add("screenshot.png", buf.getvalue())
    await client.post(
        "/api/now-showing", json={"device_id": "k", "card": "photo", "item": photo.name}
    )
    body = (await client.get("/api/now-showing")).json()
    assert body["photo"]["name"] == photo.name
    assert body["photo"]["taken_local"] is None


async def test_now_showing_stays_open_with_a_write_token(runtime: Runtime) -> None:
    from asgi_lifespan import LifespanManager

    from pinedaview.api import create_app

    runtime.settings.api.write_token = "secret"
    app = create_app(runtime)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            resp = await http.post(
                "/api/now-showing", json={"device_id": "k", "card": "quote", "item": "x"}
            )
    assert resp.status_code == 204


def test_sync_replaces_only_that_source() -> None:
    svc = TimerService(Broadcaster())
    local = svc.add(60, "Tea")
    soon = datetime.now(UTC) + timedelta(minutes=5)
    svc.sync("antigua", [SyncedTimer(id="1", label="pasta", fires_at=soon)])
    assert {t.id for t in svc.list()} == {local.id, "antigua:1"}

    svc.sync("antigua", [SyncedTimer(id="2", label="eggs", fires_at=soon)])
    assert {t.id for t in svc.list()} == {local.id, "antigua:2"}

    svc.sync("antigua", [])
    assert [t.id for t in svc.list()] == [local.id]


def test_sync_drops_already_expired() -> None:
    svc = TimerService(Broadcaster())
    past = datetime.now(UTC) - timedelta(seconds=1)
    svc.sync("antigua", [SyncedTimer(id="1", label="old", fires_at=past)])
    assert svc.list() == []


async def test_sync_endpoint(client: httpx.AsyncClient) -> None:
    fires = (datetime.now(UTC) + timedelta(minutes=4)).isoformat()
    resp = await client.put(
        "/api/timers/sync/antigua",
        json={"timers": [{"id": "7", "label": "pasta", "fires_at": fires}]},
    )
    assert resp.status_code == 204
    timers = (await client.get("/api/timers")).json()
    assert [(t["id"], t["source"]) for t in timers] == [("antigua:7", "antigua")]

    bad = await client.put("/api/timers/sync/bad!name", json={"timers": []})
    assert bad.status_code == 400
