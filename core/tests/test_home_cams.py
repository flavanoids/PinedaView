# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from pinedaview.config import Settings
from pinedaview.providers.base import ProviderContext
from pinedaview.providers.home_cams import HomeCamsProvider, home_cams
from pinedaview.registry import Registry
from pinedaview.runtime import Runtime
from pinedaview.stores import StoreRegistry


def _home(tmp_path: Path, name: str, *, age_min: float, every: float, battery: int | None) -> None:
    (tmp_path / f"{name}.jpg").write_bytes(b"\xff\xd8jpeg")
    meta = {
        "title": "Front door" if name == "front_door" else "Garage",
        "taken": time.time() - age_min * 60,
        "every": every,
        "battery": battery,
        "low_battery": 20,
    }
    (tmp_path / f"{name}.json").write_text(json.dumps(meta))


def test_each_camera_in_order_and_old_photos_go_amber(tmp_path: Path) -> None:
    _home(tmp_path, "garage", age_min=50, every=10, battery=99)  # overnight: still shown
    _home(tmp_path, "front_door", age_min=10, every=30, battery=None)
    cams = home_cams(tmp_path, ["front_door", "garage", "patio"])
    assert [c["id"] for c in cams] == ["front_door", "garage"]
    door, garage = cams
    assert door["label"] == "Front door" and not door["stale"] and door["battery"] is None
    assert door["src"].startswith("/api/home-cams/front_door.jpg?v=")
    assert garage["stale"] and not garage["lowBattery"]
    assert home_cams(None, ["front_door"]) == []


def test_a_low_battery_says_so(tmp_path: Path) -> None:
    _home(tmp_path, "front_door", age_min=600, every=30, battery=17)
    (cam,) = home_cams(tmp_path, ["front_door"])
    assert cam["lowBattery"] and cam["battery"] == 17 and cam["stale"]


def test_the_doorbell_battery_always_shows(tmp_path: Path) -> None:
    _home(tmp_path, "front_door", age_min=1, every=30, battery=27)
    _home(tmp_path, "garage", age_min=1, every=10, battery=96)
    door, garage = home_cams(tmp_path, ["front_door", "garage"], ["front_door"])
    assert door["alwaysBattery"] and not door["lowBattery"]
    assert not garage["alwaysBattery"]


async def test_the_provider_reads_the_configured_cameras(tmp_path: Path) -> None:
    _home(tmp_path, "garage", age_min=1, every=10, battery=99)
    settings = Settings()
    settings.cameras.snapshots_dir = tmp_path
    settings.cameras.streams = {"front_door": "SN1", "garage": "SN2"}
    value = await HomeCamsProvider().poll(ProviderContext(settings, StoreRegistry()))
    assert [c["id"] for c in value["cams"]] == ["garage"]


async def test_home_cam_photos_are_served_by_name_only(
    client: httpx.AsyncClient, runtime: Runtime, tmp_path: Path
) -> None:
    _home(tmp_path, "front_door", age_min=1, every=30, battery=50)
    runtime.settings.cameras.snapshots_dir = tmp_path
    runtime.settings.cameras.streams["front_door"] = "SN1"
    ok = await client.get("/api/home-cams/front_door.jpg")
    assert ok.status_code == 200 and ok.content == b"\xff\xd8jpeg"
    assert (await client.get("/api/home-cams/garage.jpg")).status_code == 404
    assert (await client.get("/api/home-cams/..%2Ffront_door.jpg")).status_code == 404


async def test_home_cams_take_the_moon_climate_slot(tmp_path: Path) -> None:
    reg = Registry(tmp_path / "pineda.db")
    await reg.init()
    await reg.update_profile("default", card_stack=["clock", "moon-climate", "photo"])
    assert await reg.retire_card("moon-climate", "home-cams", "photo") == 1
    profile = await reg.profile("default")
    assert profile is not None and profile.card_stack == ["clock", "home-cams", "photo"]
