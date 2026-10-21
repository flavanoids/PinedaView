# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pinedaview.config import Settings
from pinedaview.registry import Device, Profile
from pinedaview.state import DisplayState
from pinedaview.stores import StoreRegistry
from pinedaview.timers import Timer
from pinedaview.view import ViewModel, build_view_model

_DEVICE = Device(id="d1", name="Kitchen", profile_id="p1", paired_at=datetime.now(UTC))
_PROFILE = Profile(
    id="p1",
    name="Kitchen",
    layout="wide_grid",
    card_stack=["clock", "weather", "affirmation", "phrase", "moon"],
    theme="warm",
)


def _stores(*, stale_weather: bool = False) -> StoreRegistry:
    reg = StoreRegistry()
    reg.get_or_create("weather", stale_after_s=0).publish({"current": {}})
    reg.get_or_create("moon", stale_after_s=100).publish({"phase": 0.5})
    reg.get_or_create("dailyContent", stale_after_s=100).publish({"affirmation": {}})
    if stale_weather:
        reg.get_or_create("weather", stale_after_s=0).note_failure()
    return reg


def _build(state: DisplayState, stores: StoreRegistry | None = None) -> ViewModel:
    return build_view_model(
        device=_DEVICE,
        profile=_PROFILE,
        settings=Settings(),
        stores=stores or _stores(),
        state=state,
    )


def test_idle_puts_the_clock_in_the_hero() -> None:
    vm = _build(DisplayState.IDLE)
    assert vm.hero.kind == "card"
    assert vm.hero.card == "clock"
    assert [c.id for c in vm.cards] == ["weather", "affirmation", "phrase", "moon"]
    assert vm.theme == "warm"
    assert vm.units == "imperial"
    assert [t.kind for t in vm.tickers] == ["clock"]


def test_photo_outranks_the_clock_for_the_hero() -> None:
    profile = Profile(
        id="p1",
        name="Den",
        layout="wide_grid",
        card_stack=["clock", "weather", "photo", "affirmation"],
        theme="warm",
    )
    vm = build_view_model(
        device=_DEVICE,
        profile=profile,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.IDLE,
    )
    assert vm.hero.card == "photo"
    assert "photo" not in [c.id for c in vm.cards]
    assert "clock" in [c.id for c in vm.cards]


def test_hero_card_override_pins_the_hero() -> None:
    profile = Profile(
        id="p1",
        name="Den",
        layout="wide_grid",
        card_stack=["clock", "weather", "photo", "affirmation"],
        hero_card="weather",
    )
    vm = build_view_model(
        device=_DEVICE,
        profile=profile,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.IDLE,
    )
    assert vm.hero.card == "weather"

    # A device override beats the profile's.
    device = _DEVICE.model_copy(update={"hero_card": "affirmation"})
    vm = build_view_model(
        device=device,
        profile=profile,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.IDLE,
    )
    assert vm.hero.card == "affirmation"


def test_hero_card_override_beats_the_now_playing_takeover() -> None:
    # Someone who pinned a hero (e.g. the photo frame) wants it to stay put,
    # not get bumped every time music starts — unlike countdown/alert, a
    # now-playing takeover doesn't override a pin.
    profile = _PROFILE.model_copy(
        update={"card_stack": [*_PROFILE.card_stack, "photo"], "hero_card": "photo"}
    )
    vm = build_view_model(
        device=_DEVICE,
        profile=profile,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.PLAYING,
    )
    assert vm.hero.kind == "card"
    assert vm.hero.card == "photo"
    # The night clock's corner music card still gets the track.
    assert "nowPlaying" in vm.data


def test_view_embeds_store_data_for_its_cards() -> None:
    vm = _build(DisplayState.IDLE)
    assert set(vm.data) == {"weather", "moon", "dailyContent"}
    assert vm.data["moon"] == {"phase": 0.5}
    assert vm.data["weather"] == {"current": {}}


def test_playing_swaps_the_hero_to_now_playing() -> None:
    vm = _build(DisplayState.PLAYING)
    assert vm.hero.kind == "nowPlaying"
    assert {c.id for c in vm.cards} == set(_PROFILE.card_stack)


def test_playing_hero_drops_the_now_playing_card_from_the_grid() -> None:
    profile = _PROFILE.model_copy(update={"card_stack": [*_PROFILE.card_stack, "now-playing"]})
    vm = build_view_model(
        device=_DEVICE,
        profile=profile,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.PLAYING,
    )
    assert vm.hero.kind == "nowPlaying"
    assert "now-playing" not in {c.id for c in vm.cards}


def test_switched_off_cards_leave_the_grid() -> None:
    vm = build_view_model(
        device=_DEVICE.model_copy(update={"cards_off": ["affirmation"]}),
        profile=_PROFILE,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.IDLE,
    )
    assert [c.id for c in vm.cards] == ["weather", "phrase", "moon"]


def test_countdown_adds_a_ticker_and_owns_the_hero() -> None:
    vm = _build(DisplayState.COUNTDOWN)
    assert vm.hero.kind == "countdown"
    assert [t.kind for t in vm.tickers] == ["clock", "countdown"]
    assert vm.tickers[1].target is not None


def test_stale_store_flags_its_cards_and_lists_the_store() -> None:
    vm = _build(DisplayState.IDLE, _stores(stale_weather=True))
    card_state = {c.id: c.stale for c in vm.cards}
    assert card_state["weather"] is True
    assert card_state["moon"] is False
    assert "weather" in vm.stale_stores
    assert set(vm.stale_since) == set(vm.stale_stores)


def test_alert_banner_comes_from_the_alerts_store() -> None:
    reg = _stores()
    reg.get_or_create("alerts", stale_after_s=100).publish(
        {"count": 1, "top": {"severity": "Severe", "event": "Heat Advisory", "headline": "hot"}}
    )
    vm = build_view_model(
        device=_DEVICE,
        profile=_PROFILE,
        settings=Settings(),
        stores=reg,
        state=DisplayState.IDLE,
    )
    assert vm.alert is not None
    assert vm.alert.event == "Heat Advisory"


def test_alerts_card_gets_its_store_data_and_stale_flag() -> None:
    reg = _stores(stale_weather=False)
    reg.get_or_create("alerts", stale_after_s=0).publish({"count": 0, "top": None})
    profile = _PROFILE.model_copy(update={"card_stack": [*_PROFILE.card_stack, "alerts"]})
    vm = build_view_model(
        device=_DEVICE, profile=profile, settings=Settings(), stores=reg, state=DisplayState.IDLE
    )
    assert vm.data["alerts"] == {"count": 0, "top": None}
    assert {c.id: c.stale for c in vm.cards}.get("alerts") is False


def test_timer_card_gets_the_live_timer_list() -> None:
    profile = _PROFILE.model_copy(update={"card_stack": [*_PROFILE.card_stack, "timer"]})
    running = Timer(id="t1", label="Pasta", fires_at=datetime.now(UTC))
    vm = build_view_model(
        device=_DEVICE,
        profile=profile,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.IDLE,
        timers=[running],
    )
    assert vm.data["timer"] == [running.model_dump(mode="json")]


def test_timer_card_omitted_from_view_when_not_on_the_stack() -> None:
    vm = _build(DisplayState.IDLE)
    assert "timer" not in vm.data


@pytest.mark.parametrize("mini", ["moon-climate", "home-cams"])
def test_mini_cards_get_the_timers(mini: str) -> None:
    profile = _PROFILE.model_copy(update={"card_stack": ["clock", mini]})
    timer = Timer(id="antigua:1", label="pasta", fires_at=datetime.now(UTC), source="antigua")
    vm = build_view_model(
        device=_DEVICE,
        profile=profile,
        settings=Settings(),
        stores=_stores(),
        state=DisplayState.IDLE,
        timers=[timer],
    )
    assert vm.data["timer"][0]["label"] == "pasta"


def _radar_view(
    weather: object, card_settings: dict[str, dict[str, object]] | None = None
) -> list[str]:
    reg = StoreRegistry()
    if weather is not None:
        reg.get_or_create("weather", stale_after_s=100).publish(weather)
    profile = Profile(id="p1", name="Den", card_stack=["clock", "weather", "radar"])
    vm = build_view_model(
        device=_DEVICE,
        profile=profile,
        settings=Settings(),
        stores=reg,
        state=DisplayState.IDLE,
        card_settings=card_settings,
    )
    return [c.id for c in vm.cards if not c.hidden]


def _forecast(today: int, hourly: list[int]) -> dict[str, object]:
    return {
        "current": {},
        "hourly": [{"precip": p} for p in hourly],
        "forecast": [{"precip": today}, {"precip": 90}],
    }


def test_radar_hides_on_a_dry_day() -> None:
    assert "radar" not in _radar_view(_forecast(10, [0, 5, 15]))


def test_radar_shows_when_today_or_the_next_hours_could_rain() -> None:
    assert "radar" in _radar_view(_forecast(20, [0, 0]))
    assert "radar" in _radar_view(_forecast(5, [0, 40]))


def test_radar_cutoff_follows_the_card_setting() -> None:
    dry = _forecast(10, [10])
    assert "radar" in _radar_view(dry, {"radar": {"hideBelow": 0}})
    assert "radar" not in _radar_view(_forecast(30, [30]), {"radar": {"hideBelow": 50}})


def _dry_radar_cells(stack: list[str]) -> list[tuple[str, bool]]:
    reg = StoreRegistry()
    reg.get_or_create("weather", stale_after_s=100).publish(_forecast(0, [0]))
    profile = Profile(id="p1", name="Den", card_stack=stack)
    vm = build_view_model(
        device=_DEVICE, profile=profile, settings=Settings(), stores=reg, state=DisplayState.IDLE
    )
    return [(c.id, c.hidden) for c in vm.cards]


def test_a_hidden_radar_frees_its_slot_for_the_last_card() -> None:
    assert _dry_radar_cells(["clock", "radar", "now-playing", "news"]) == [
        ("now-playing", False),
        ("news", False),
    ]


def test_a_hidden_radar_frees_its_slot_for_now_playing_too() -> None:
    assert _dry_radar_cells(["clock", "radar", "news", "now-playing"]) == [
        ("news", False),
        ("now-playing", False),
    ]


def test_radar_shows_before_the_first_weather_fetch() -> None:
    assert "radar" in _radar_view(None)
