# SPDX-License-Identifier: Apache-2.0
"""Settings preferences: household prefs that survive a restart, per-profile
and per-screen prefs in the view, guest-upload review, reset, copy, backup."""

from __future__ import annotations

from datetime import datetime

import httpx

from pinedaview.config import Settings
from pinedaview.household import HouseholdPrefs, load_household, save_household
from pinedaview.registry import Device, Profile
from pinedaview.state import DisplayState
from pinedaview.stores import StoreRegistry
from pinedaview.view import build_view_model

from .test_photo_uploads import _png


async def _pair(client: httpx.AsyncClient, name: str = "Kitchen") -> str:
    device_id: str = (await client.post("/api/devices/pair", json={"name": name})).json()["id"]
    return device_id


async def test_household_prefs_round_trip_and_reach_the_view(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    r = await client.post("/api/config", json={"time_format": "24h", "date_style": "short"})
    assert r.json()["time_format"] == "24h" and r.json()["date_style"] == "short"
    prefs = (await client.get(f"/api/view/{device_id}")).json()["prefs"]
    assert prefs["time_format"] == "24h" and prefs["date_style"] == "short"


async def test_config_rejects_a_bad_time(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/config", json={"countdown_start": "7:30am"})
    assert r.status_code == 422


def test_config_edits_survive_a_restart(settings: Settings) -> None:
    settings.units = "metric"
    settings.location.query = "Austin"
    settings.countdown.enabled = True
    save_household(settings, HouseholdPrefs(time_format="24h"))

    fresh = settings.model_copy(deep=True)
    fresh.location.query = "Houston"
    fresh.countdown.enabled = False
    prefs = load_household(fresh)
    assert prefs.time_format == "24h"
    assert fresh.model_dump()["units"] == "metric"
    assert fresh.location.query == "Austin"
    assert fresh.countdown.enabled is True


async def test_profile_prefs_reach_the_view(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    r = await client.patch(
        "/api/profiles/default",
        json={
            "pace": "relaxed",
            "photo_hold_s": 60,
            "photo_order": "shuffle",
            "photo_fit": "fit",
            "accent": "#ff8800",
            "wallpaper_everywhere": True,
            "hide_words": [" Election ", "election", "war"],
        },
    )
    assert r.status_code == 200
    assert r.json()["hide_words"] == ["Election", "war"]
    prefs = (await client.get(f"/api/view/{device_id}")).json()["prefs"]
    assert prefs["pace"] == "relaxed"
    assert prefs["photo_hold_s"] == 60
    assert prefs["photo_order"] == "shuffle"
    assert prefs["photo_fit"] == "fit"
    assert prefs["accent"] == "#ff8800"
    assert prefs["wallpaper_everywhere"] is True

    # "" clears the accent.
    r = await client.patch("/api/profiles/default", json={"accent": ""})
    assert r.json()["accent"] is None


async def test_profile_rejects_bad_values(client: httpx.AsyncClient) -> None:
    assert (await client.patch("/api/profiles/default", json={"accent": "red"})).status_code == 422
    r = await client.patch("/api/profiles/default", json={"night_theme": "no-such-theme"})
    assert r.status_code == 400
    r = await client.patch("/api/profiles/default", json={"night_theme": "off"})
    assert r.json()["night_theme"] == "off"


async def test_screen_schedule_reaches_the_view(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    r = await client.patch(
        f"/api/devices/{device_id}",
        json={"night_weeknight_start": "23:00", "night_end": "06:30", "peek_s": 120},
    )
    assert r.status_code == 200
    prefs = (await client.get(f"/api/view/{device_id}")).json()["prefs"]
    assert prefs["night_weeknight_start"] == "23:00"
    assert prefs["night_end"] == "06:30"
    assert prefs["peek_s"] == 120


async def test_blackout_can_be_cleared(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    await client.patch(
        f"/api/devices/{device_id}", json={"blackout_start": "22:00", "blackout_end": "06:00"}
    )
    r = await client.patch(
        f"/api/devices/{device_id}", json={"blackout_start": "", "blackout_end": ""}
    )
    assert r.json()["blackout_start"] is None and r.json()["blackout_end"] is None


def _brightness_at(device: Device, settings: Settings, hour: int) -> float:
    return build_view_model(
        device=device,
        profile=Profile(id="p", name="p"),
        settings=settings,
        stores=StoreRegistry(),
        state=DisplayState.IDLE,
        now=datetime(2026, 10, 12, hour, 0).astimezone(),
    ).brightness


def test_dim_window_lowers_brightness(settings: Settings) -> None:
    device = Device(
        id="d",
        name="d",
        profile_id="p",
        paired_at=datetime(2026, 1, 1).astimezone(),
        brightness=0.9,
        dim_start="21:00",
        dim_end="07:00",
        dim_level=0.3,
    )
    assert _brightness_at(device, settings, 23) == 0.3
    assert _brightness_at(device, settings, 12) == 0.9


def test_hidden_words_filter_news_and_quotes(settings: Settings) -> None:
    stores = StoreRegistry()
    stores.get_or_create("news", stale_after_s=600).publish(
        {"stories": [{"title": "Election results"}, {"title": "Puppies"}]}
    )
    stores.get_or_create("dailyContent", stale_after_s=600).publish(
        {"affirmations": [{"text": "Be kind", "author": "A"}, {"text": "War is", "author": "B"}]}
    )
    device = Device(id="d", name="d", profile_id="p", paired_at=datetime(2026, 1, 1).astimezone())
    profile = Profile(id="p", name="p", card_stack=["news", "affirmation"], hide_words=["war"])
    view = build_view_model(
        device=device,
        profile=profile,
        settings=settings,
        stores=stores,
        state=DisplayState.IDLE,
    )
    assert [s["title"] for s in view.data["news"]["stories"]] == [
        "Election results",
        "Puppies",
    ]
    assert [q["text"] for q in view.data["dailyContent"]["affirmations"]] == ["Be kind"]


async def test_guest_uploads_follow_the_policy(client: httpx.AsyncClient) -> None:
    png = {"file": ("guest.png", _png(), "image/png")}

    await client.post("/api/config", json={"guest_uploads": "off"})
    assert (await client.post("/api/photos", files=png)).status_code == 403

    await client.post("/api/config", json={"guest_uploads": "review"})
    r = await client.post("/api/photos", files=png)
    assert r.status_code == 201 and r.json()["pending"] is True
    name = r.json()["name"]
    assert (await client.get("/api/photos")).json() == []
    assert [p["name"] for p in (await client.get("/api/photos/pending")).json()] == [name]

    assert (await client.post(f"/api/photos/{name}/approve")).status_code == 200
    assert [p["name"] for p in (await client.get("/api/photos")).json()] == [name]
    assert (await client.get("/api/photos/pending")).json() == []


async def test_owner_uploads_skip_review(client: httpx.AsyncClient) -> None:
    await client.post("/api/config", json={"guest_uploads": "off"})
    r = await client.post("/api/photos/library", files={"file": ("mine.png", _png(), "image/png")})
    assert r.status_code == 201 and r.json()["pending"] is False


async def test_reset_a_section(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    await client.patch("/api/profiles/default", json={"photo_hold_s": 300, "photo_fit": "fit"})
    await client.patch(f"/api/devices/{device_id}", json={"peek_s": 300, "dim_start": "20:00"})
    await client.post("/api/config", json={"guest_uploads": "off", "time_format": "24h"})

    r = await client.post("/api/config/reset", json={"section": "photos", "profile_id": "default"})
    assert r.json()["guest_uploads"] == "open"
    assert r.json()["time_format"] == "24h"  # another section's
    profile = next(p for p in (await client.get("/api/profiles")).json() if p["id"] == "default")
    assert profile["photo_hold_s"] == 20 and profile["photo_fit"] == "fill"

    await client.post("/api/config/reset", json={"section": "night", "device_id": device_id})
    device = next(d for d in (await client.get("/api/devices")).json() if d["id"] == device_id)
    assert device["peek_s"] == 60 and device["dim_start"] is None


async def test_copy_settings_from_another_screen(client: httpx.AsyncClient) -> None:
    source = await _pair(client, "Kitchen")
    target = await _pair(client, "Hall")
    await client.patch(
        f"/api/devices/{source}",
        json={"brightness": 0.6, "night_end": "07:00", "cards_off": ["radar"]},
    )
    await client.patch(f"/api/devices/{target}", json={"blackout_start": "22:00"})
    r = await client.post(f"/api/devices/{target}/copy-from", json={"source": source})
    copied = r.json()
    assert copied["name"] == "Hall"
    assert copied["brightness"] == 0.6
    assert copied["night_end"] == "07:00"
    assert copied["cards_off"] == ["radar"]
    assert copied["blackout_start"] is None


async def test_backup_and_restore(client: httpx.AsyncClient) -> None:
    device_id = await _pair(client)
    await client.patch("/api/profiles/default", json={"pace": "brisk"})
    await client.patch(f"/api/devices/{device_id}", json={"peek_s": 90})
    await client.post("/api/config", json={"time_format": "24h"})
    backup = (await client.get("/api/config/backup")).json()
    assert backup["format"] == "pineda-settings"

    await client.patch("/api/profiles/default", json={"pace": "normal"})
    await client.patch(f"/api/devices/{device_id}", json={"peek_s": 30})
    await client.post("/api/config", json={"time_format": "12h"})
    backup["devices"].append({**backup["devices"][0], "id": "ffffffffffffffff"})

    r = await client.post("/api/config/restore", json=backup)
    assert r.json() == {"profiles": 1, "screens": 1, "skipped_screens": 1}
    profile = next(p for p in (await client.get("/api/profiles")).json() if p["id"] == "default")
    assert profile["pace"] == "brisk"
    device = next(d for d in (await client.get("/api/devices")).json() if d["id"] == device_id)
    assert device["peek_s"] == 90
    assert (await client.get("/api/config")).json()["time_format"] == "24h"


async def test_after_sunset_theme_can_be_turned_off(client: httpx.AsyncClient) -> None:
    # Without coordinates the night switch can't happen either way; this pins
    # that "off" is accepted and stays on the day theme.
    device_id = await _pair(client)
    await client.patch("/api/profiles/default", json={"night_theme": "off"})
    view = (await client.get(f"/api/view/{device_id}")).json()
    profile = next(p for p in (await client.get("/api/profiles")).json() if p["id"] == "default")
    assert view["theme"] == profile["theme"]
