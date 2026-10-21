# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from pinedaview.registry import DEFAULT_PROFILE_ID, Registry


@pytest.fixture
async def registry(tmp_path: Path) -> Registry:
    reg = Registry(tmp_path / "reg.db")
    await reg.init()
    return reg


async def test_init_seeds_a_default_profile(registry: Registry) -> None:
    profile = await registry.profile(DEFAULT_PROFILE_ID)
    assert profile is not None
    assert profile.card_stack[0] == "clock"
    assert [p.id for p in await registry.profiles()] == [DEFAULT_PROFILE_ID]


async def test_init_is_idempotent(tmp_path: Path) -> None:
    reg = Registry(tmp_path / "reg.db")
    await reg.init()
    await reg.init()
    assert len(await reg.profiles()) == 1


async def test_pair_and_fetch_device(registry: Registry) -> None:
    device = await registry.pair_device("Kitchen", (1024, 600))
    assert device.profile_id == DEFAULT_PROFILE_ID
    assert device.viewport_w == 1024
    fetched = await registry.device(device.id)
    assert fetched is not None and fetched.name == "Kitchen"


async def test_update_device_allow_lists_fields(registry: Registry) -> None:
    device = await registry.pair_device("Screen")
    updated = await registry.update_device(device.id, name="Bedside", tier="lite", bogus="x")
    assert updated is not None
    assert updated.name == "Bedside"
    assert updated.tier == "lite"


async def test_cards_off_round_trips(registry: Registry) -> None:
    device = await registry.pair_device("Screen")
    assert device.cards_off == []
    await registry.update_device(device.id, cards_off=["photo"])
    fetched = await registry.device(device.id)
    assert fetched is not None and fetched.cards_off == ["photo"]


async def test_update_missing_device_returns_none(registry: Registry) -> None:
    assert await registry.update_device("nope", name="x") is None


async def test_touch_sets_last_seen(registry: Registry) -> None:
    device = await registry.pair_device("Screen")
    assert device.last_seen is None
    await registry.touch(device.id)
    refreshed = await registry.device(device.id)
    assert refreshed is not None and refreshed.last_seen is not None


async def test_retire_card_moves_its_successor_into_the_slot(registry: Registry) -> None:
    await registry.update_profile(
        DEFAULT_PROFILE_ID, card_stack=["clock", "affirmation", "phrase", "moon"]
    )
    # The kiosk had the cams in the quote's cell: they move, the quote returns.
    kiosk = await registry.pair_device("Kiosk")
    await registry.update_device(kiosk.id, card_stack=["clock", "traffic", "phrase", "moon"])
    untouched = await registry.pair_device("Other")
    await registry.update_device(untouched.id, card_stack=["clock", "moon"])

    assert await registry.retire_card("phrase", "traffic", "affirmation") == 2

    profile = await registry.profile(DEFAULT_PROFILE_ID)
    assert profile is not None
    assert profile.card_stack == ["clock", "affirmation", "traffic", "moon"]
    device = await registry.device(kiosk.id)
    assert device is not None
    assert device.card_stack == ["clock", "affirmation", "traffic", "moon"]
    other = await registry.device(untouched.id)
    assert other is not None and other.card_stack == ["clock", "moon"]
    assert await registry.retire_card("phrase", "traffic", "affirmation") == 0


async def test_animated_background_round_trips_and_switches_off(registry: Registry) -> None:
    start = await registry.profile(DEFAULT_PROFILE_ID)
    assert start is not None and start.animated_background is False
    on = await registry.update_profile(DEFAULT_PROFILE_ID, animated_background=True)
    assert on is not None and on.animated_background is True
    # False isn't None, so it must still be written, not skipped as "unset".
    off = await registry.update_profile(DEFAULT_PROFILE_ID, animated_background=False)
    assert off is not None and off.animated_background is False


async def test_font_round_trips_and_clears_back_to_the_theme(registry: Registry) -> None:
    start = await registry.profile(DEFAULT_PROFILE_ID)
    assert start is not None and start.font is None
    on = await registry.update_profile(DEFAULT_PROFILE_ID, font="geist")
    assert on is not None and on.font == "geist"
    # "" hands the type back to the theme.
    off = await registry.update_profile(DEFAULT_PROFILE_ID, font="")
    assert off is not None and off.font is None
