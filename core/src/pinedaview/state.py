# SPDX-License-Identifier: Apache-2.0
"""Display state.

Four states, computed — not a long-lived object that mutates itself. Music
playing (or a manual override) wins over the clock; otherwise an optional
weekday countdown window drives ``COUNTDOWN`` then ``ALERT``. ``LISTENING`` from
PinedaDisplay's voice assistant does not exist here.
"""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum

from pinedaview.config import CountdownConfig

_SATURDAY = 5


class DisplayState(StrEnum):
    IDLE = "idle"
    PLAYING = "playing"
    COUNTDOWN = "countdown"
    ALERT = "alert"


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def countdown_state(now: datetime, cfg: CountdownConfig) -> DisplayState:
    """``COUNTDOWN`` / ``ALERT`` / ``IDLE`` for the wall clock alone."""
    if not cfg.enabled:
        return DisplayState.IDLE
    if cfg.weekdays_only and now.weekday() >= _SATURDAY:
        return DisplayState.IDLE

    current = _minutes(now.time())
    start = _minutes(parse_hhmm(cfg.start))
    end = _minutes(parse_hhmm(cfg.end))
    alert_end = end + (cfg.alert_seconds + 59) // 60

    if start <= current < end:
        return DisplayState.COUNTDOWN
    if end <= current < alert_end:
        return DisplayState.ALERT
    return DisplayState.IDLE


def compute_state(
    now: datetime,
    cfg: CountdownConfig,
    *,
    playing: bool,
    forced: DisplayState | None = None,
) -> DisplayState:
    if forced is not None:
        return forced
    if playing:
        return DisplayState.PLAYING
    return countdown_state(now, cfg)


class StateController:
    """Holds the two mutable inputs (is music playing, is a state forced) that
    the API endpoints toggle. Everything else about the state is derived."""

    def __init__(self, cfg: CountdownConfig) -> None:
        self._cfg = cfg
        self.playing = False
        self.forced: DisplayState | None = None

    def current(self, now: datetime | None = None) -> DisplayState:
        return compute_state(
            now or datetime.now().astimezone(),
            self._cfg,
            playing=self.playing,
            forced=self.forced,
        )
