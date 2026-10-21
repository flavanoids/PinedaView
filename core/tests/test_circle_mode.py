# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from pinedaview.config import Settings
from pinedaview.registry import Device, Profile, Registry
from pinedaview.state import DisplayState
from pinedaview.stores import StoreRegistry
from pinedaview.view import ViewModel, build_view_model


def _device(**fields: object) -> Device:
    return Device(id="d", name="d", profile_id="p", paired_at=datetime.now(UTC), **fields)


def _view(device: Device, state: DisplayState = DisplayState.IDLE) -> ViewModel:
    profile = Profile(
        id="p", name="p", card_stack=["clock", "weather", "photo", "moon", "phrase", "news"]
    )
    return build_view_model(
        device=device, profile=profile, settings=Settings(), stores=StoreRegistry(), state=state
    )


def test_circle_stack_rejects_too_many_duplicates_and_the_clock() -> None:
    with pytest.raises(ValidationError, match="at most 4"):
        _device(circle_stack=["a", "b", "c", "d", "e"])
    with pytest.raises(ValidationError, match="once"):
        _device(circle_stack=["moon", "moon"])
    with pytest.raises(ValidationError, match="hands are its clock"):
        _device(circle_stack=["clock"])


def test_rectangle_screens_are_unchanged() -> None:
    vm = _view(_device())
    assert vm.shape == "rect" and vm.circle == []


def test_circle_centre_is_the_hero_and_the_rest_keep_their_slots() -> None:
    vm = _view(_device(shape="circle", circle_stack=["photo", "moon", "weather", "phrase"]))
    assert vm.shape == "circle"
    assert vm.circle == ["photo", "moon", "weather", "phrase"]
    assert vm.hero.kind == "card" and vm.hero.card == "photo"
    assert [c.id for c in vm.cards] == ["moon", "weather", "phrase"]


def test_circle_defaults_to_the_first_four_without_the_clock() -> None:
    vm = _view(_device(shape="circle", cards_off=["moon"]))
    assert vm.circle == ["weather", "photo", "phrase", "news"]
    assert vm.hero.card == "weather"


def test_countdown_takes_the_circle_centre() -> None:
    vm = _view(_device(shape="circle", circle_stack=["photo", "moon"]), DisplayState.COUNTDOWN)
    assert vm.hero.kind == "countdown"
    assert [c.id for c in vm.cards] == ["moon"]


@pytest.fixture
async def registry(tmp_path: Path) -> Registry:
    reg = Registry(tmp_path / "reg.db")
    await reg.init()
    return reg


async def test_shape_and_circle_stack_persist(registry: Registry) -> None:
    device = await registry.pair_device("Hall")
    assert device.shape == "rect" and device.circle_stack is None
    updated = await registry.update_device(
        device.id, shape="circle", circle_stack=["photo", "weather"]
    )
    assert updated is not None
    assert updated.shape == "circle" and updated.circle_stack == ["photo", "weather"]
    cleared = await registry.update_device(device.id, circle_stack=[])
    assert cleared is not None and cleared.circle_stack is None


async def test_device_patch_checks_circle_cards(client: httpx.AsyncClient) -> None:
    device_id = str((await client.post("/api/devices/pair", json={"name": "Hall"})).json()["id"])
    url = f"/api/devices/{device_id}"
    r = await client.patch(url, json={"shape": "circle", "circle_stack": ["photo", "weather"]})
    assert r.status_code == 200
    view = (await client.get(f"/api/view/{device_id}")).json()
    assert view["shape"] == "circle" and view["circle"] == ["photo", "weather"]
    assert (await client.patch(url, json={"circle_stack": ["nope"]})).status_code == 422
    assert (await client.patch(url, json={"circle_stack": ["clock"]})).status_code == 422
    assert (await client.patch(url, json={"shape": "oval"})).status_code == 422


def test_round_photo_clock_is_off_by_default() -> None:
    from pinedaview.registry import PhotoClock

    clock = PhotoClock()
    assert (clock.face, clock.seconds, clock.sweep) == ("digits", False, False)
    assert PhotoClock(face="hands", seconds=True, sweep=True).face == "hands"
    with pytest.raises(ValidationError):
        PhotoClock(face="sundial")
