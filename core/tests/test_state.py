# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from datetime import datetime

from pinedaview.config import CountdownConfig
from pinedaview.state import DisplayState, StateController, compute_state, countdown_state

MON_0740 = datetime(2026, 8, 24, 7, 40)
MON_0805 = datetime(2026, 8, 24, 8, 5)
MON_1200 = datetime(2026, 8, 24, 12, 0)
SAT_0740 = datetime(2026, 8, 29, 7, 40)

assert MON_0740.weekday() == 0  # sanity: the fixtures really are Mon / Sat
assert SAT_0740.weekday() == 5


def test_countdown_disabled_is_always_idle() -> None:
    assert countdown_state(MON_0740, CountdownConfig()) is DisplayState.IDLE


def test_countdown_window_then_alert() -> None:
    cfg = CountdownConfig(enabled=True, start="07:30", end="08:00", alert_seconds=600)
    assert countdown_state(MON_0740, cfg) is DisplayState.COUNTDOWN
    assert countdown_state(MON_0805, cfg) is DisplayState.ALERT  # 08:00 to 08:10
    assert countdown_state(MON_1200, cfg) is DisplayState.IDLE


def test_countdown_skips_weekends_when_asked() -> None:
    cfg = CountdownConfig(enabled=True, start="07:30", end="08:00")
    assert countdown_state(SAT_0740, cfg) is DisplayState.IDLE
    assert countdown_state(SAT_0740, cfg.model_copy(update={"weekdays_only": False})) is (
        DisplayState.COUNTDOWN
    )


def test_playing_and_forced_take_precedence() -> None:
    cfg = CountdownConfig(enabled=True, start="07:30", end="08:00")
    assert compute_state(MON_0740, cfg, playing=True) is DisplayState.PLAYING
    assert compute_state(MON_0740, cfg, playing=True, forced=DisplayState.IDLE) is DisplayState.IDLE


def test_controller_tracks_mutable_inputs() -> None:
    ctrl = StateController(CountdownConfig())
    assert ctrl.current(MON_1200) is DisplayState.IDLE
    ctrl.playing = True
    assert ctrl.current(MON_1200) is DisplayState.PLAYING
    ctrl.playing = False
    ctrl.forced = DisplayState.ALERT
    assert ctrl.current(MON_1200) is DisplayState.ALERT
