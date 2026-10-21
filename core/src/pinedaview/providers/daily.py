# SPDX-License-Identifier: Apache-2.0
"""Publishes the day's affirmation and multilingual word into the
``dailyContent`` store. Not a network source — it polls cheaply on the clock
and only advances the affirmation history when the calendar date changes."""

from __future__ import annotations

from datetime import date
from typing import Any

from pinedaview.config import ProviderConfig
from pinedaview.content.daily import daily_affirmations, daily_word
from pinedaview.providers.base import Provider, ProviderContext


class DailyContentProvider(Provider):
    key = "dailyContent"

    def __init__(self, interval_s: int | None = None) -> None:
        super().__init__(interval_s)
        self._served_on: date | None = None
        self._last: dict[str, Any] | None = None

    def _default_interval_s(self, cfg: ProviderConfig) -> int:
        return cfg.daily_content_interval_s

    async def poll(self, ctx: ProviderContext) -> dict[str, Any]:
        today = date.today()
        if self._last is None or self._served_on != today:
            quotes = daily_affirmations(ctx.settings.state_dir, today)
            self._last = {
                "date": today.isoformat(),
                # `affirmation` (singular) stays for older clients; `affirmations`
                # is the rotating set the card cross-fades through.
                "affirmation": quotes[0],
                "affirmations": quotes,
                "word": daily_word(today),
            }
            self._served_on = today
        return self._last
