# SPDX-License-Identifier: Apache-2.0
"""Moon phase — a synodic-month calculation, no network. Accurate to ~1 day,
which is all a dashboard needs. Ported from PinedaDisplay's ``moon.py``."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.providers.base import Provider, ProviderContext

_KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=UTC)
_SYNODIC_MONTH = 29.53058867

_PHASE_NAMES: tuple[tuple[float, str], ...] = (
    (0.03, "New Moon"),
    (0.22, "Waxing Crescent"),
    (0.28, "First Quarter"),
    (0.47, "Waxing Gibbous"),
    (0.53, "Full Moon"),
    (0.72, "Waning Gibbous"),
    (0.78, "Last Quarter"),
    (0.97, "Waning Crescent"),
)
_MAJOR_PHASES: tuple[tuple[float, str], ...] = (
    (0.0, "New Moon"),
    (0.25, "First Quarter"),
    (0.5, "Full Moon"),
    (0.75, "Last Quarter"),
)


def _phase_fraction(moment: datetime) -> float:
    days = (moment - _KNOWN_NEW_MOON).total_seconds() / 86400.0
    cycles = days / _SYNODIC_MONTH
    return cycles - math.floor(cycles)


def _phase_name(fraction: float) -> str:
    for threshold, name in _PHASE_NAMES:
        if fraction <= threshold:
            return name
    return "New Moon"


def _next_major(fraction: float, moment: datetime) -> tuple[str, datetime]:
    for target, name in _MAJOR_PHASES:
        if fraction < target - 0.02:
            return name, moment + timedelta(days=(target - fraction) * _SYNODIC_MONTH)
    return "New Moon", moment + timedelta(days=(1.0 - fraction) * _SYNODIC_MONTH)


def compute(moment: datetime | None = None) -> dict[str, Any]:
    now = moment or datetime.now(UTC)
    fraction = _phase_fraction(now)
    next_name, next_at = _next_major(fraction, now)
    return {
        "phase": round(fraction, 4),
        "name": _phase_name(fraction),
        "illumination": round((1 - math.cos(fraction * 2 * math.pi)) / 2 * 100, 1),
        "ageDays": round(fraction * _SYNODIC_MONTH, 1),
        "nextPhase": {"name": next_name, "at": next_at.isoformat()},
    }


class MoonProvider(Provider):
    key = "moon"

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return cfg.moon_interval_s

    async def poll(self, _ctx: ProviderContext) -> dict[str, Any]:
        return compute()
